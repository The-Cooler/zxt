"""
Shared pytest fixtures for integration tests that exercise the live API service.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import anyio
import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from zixuetong.storage.postgres.manager import pg_manager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "test/.env.test", override=False)

API_BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:5050").rstrip("/")
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
SANDBOX_CONTAINER_PREFIX = os.getenv("ZIXUETONG_SANDBOX_CONTAINER_PREFIX", "zixuetong-sandbox")


@pytest_asyncio.fixture(scope="function")
async def test_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        yield client


@pytest.fixture(scope="function")
def admin_headers() -> dict[str, str]:
    """单用户模式不需要平台登录头。"""
    return {}


@pytest_asyncio.fixture(scope="function")
async def standard_user(admin_headers: dict[str, str]) -> dict:
    """兼容旧测试命名：单用户模式下只有系统 owner，且始终拥有最高权限。"""
    if not pg_manager._initialized:
        pg_manager.initialize()

    from sqlalchemy import select
    from zixuetong.storage.postgres.models_business import User

    async with pg_manager.get_async_session_context() as session:
        result = await session.execute(select(User).order_by(User.id).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            pytest.fail("单用户系统 owner 不存在，无法运行集成测试。")
        user_payload = user.to_dict()

    return {"user": user_payload, "headers": admin_headers}


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_knowledge_databases():
    async def run_cleanup() -> None:
        headers: dict[str, str] = {}

        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            try:
                list_response = await client.get("/api/knowledge/databases", headers=headers)
            except Exception as exc:
                print(f"Warning: Failed to list knowledge databases for cleanup: {exc}")
                return

            if list_response.status_code != 200:
                return

            databases = list_response.json().get("databases", [])
            prefixes = ("pytest_", "py_test")
            for entry in databases:
                name = entry.get("name") or ""
                db_id = entry.get("db_id")
                if not db_id or not isinstance(name, str) or not name.startswith(prefixes):
                    continue
                try:
                    delete_response = await client.delete(f"/api/knowledge/databases/{db_id}", headers=headers)
                    if delete_response.status_code not in (200, 404):
                        print(f"Warning: Failed to cleanup knowledge database {db_id}: {delete_response.text}")
                except Exception as exc:
                    print(f"Warning: Exception during cleanup of {db_id}: {exc}")

    try:
        anyio.run(run_cleanup)
    except Exception as exc:
        print(f"Warning: Exception during session cleanup startup: {exc}")
    yield
    try:
        anyio.run(run_cleanup)
    except Exception as exc:
        print(f"Warning: Exception during session cleanup teardown: {exc}")


def _docker_api_request(method: str, path: str) -> list[dict] | dict:
    cmd = [
        "curl",
        "-sS",
        "--unix-socket",
        os.getenv("ZIXUETONG_DOCKER_API_SOCKET", "/var/run/docker.sock"),
        "-X",
        method,
        f"{os.getenv('ZIXUETONG_DOCKER_API_BASE', 'http://localhost').rstrip('/')}{path}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Docker API request failed")
    text = (result.stdout or "").strip()
    if not text:
        return {}
    return json.loads(text)


def _cleanup_sandbox_containers() -> None:
    try:
        containers = _docker_api_request("GET", "/containers/json?all=true")
    except Exception as exc:
        print(f"Warning: Failed to list sandbox containers for cleanup: {exc}")
        return

    for container in containers if isinstance(containers, list) else []:
        names = container.get("Names") or []
        if not any(name.lstrip("/").startswith(f"{SANDBOX_CONTAINER_PREFIX}-") for name in names):
            continue
        container_id = container.get("Id")
        if not container_id:
            continue
        try:
            _docker_api_request("POST", f"/containers/{container_id}/stop?t=2")
        except Exception:
            pass
        try:
            _docker_api_request("DELETE", f"/containers/{container_id}?force=true")
        except Exception as exc:
            print(f"Warning: Failed to cleanup sandbox container {container_id[:12]}: {exc}")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_sandboxes():
    _cleanup_sandbox_containers()
    yield
    _cleanup_sandbox_containers()


@pytest_asyncio.fixture(scope="function")
async def knowledge_database(
    test_client: httpx.AsyncClient,
    admin_headers: dict[str, str],
) -> AsyncGenerator[dict, None]:
    import time

    unique_id = uuid.uuid4().hex
    timestamp = int(time.time() * 1000000)
    db_name = f"pytest_kb_{timestamp}_{unique_id}"
    db_id = None

    try:
        create_response = await test_client.post(
            "/api/knowledge/databases",
            json={
                "database_name": db_name,
                "description": "Pytest managed knowledge base",
                "embed_model_name": "siliconflow/BAAI/bge-m3",
                "kb_type": "lightrag",
                "additional_params": {},
            },
            headers=admin_headers,
        )

        if create_response.status_code == 200:
            db_payload = create_response.json()
            db_id = db_payload["db_id"]
        elif create_response.status_code == 409:
            error_detail = create_response.json().get("detail", "")
            pytest.fail(f"Knowledge database name conflict: {error_detail}. Please clean up old test databases first.")
        else:
            pytest.fail(
                f"Failed to create knowledge database (status={create_response.status_code}): {create_response.text}"
            )

        yield db_payload if db_id else {"db_id": db_id, "name": db_name}

    finally:
        if db_id:
            try:
                delete_response = await test_client.delete(f"/api/knowledge/databases/{db_id}", headers=admin_headers)
                if delete_response.status_code != 200:
                    print(f"Warning: Failed to cleanup knowledge database {db_id}: {delete_response.text}")
            except Exception as exc:
                print(f"Warning: Exception during cleanup of {db_id}: {exc}")
