from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / "test/.env.test", override=False)

E2E_BASE_URL = os.getenv("TEST_BASE_URL", os.getenv("API_BASE_URL", "http://localhost:5050")).rstrip("/")
E2E_USER_ID = os.getenv("E2E_USER_ID", "1")
E2E_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    return E2E_BASE_URL


@pytest_asyncio.fixture(scope="function")
async def e2e_client(e2e_base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=e2e_base_url, timeout=E2E_TIMEOUT, follow_redirects=True) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def e2e_headers(e2e_client: httpx.AsyncClient) -> dict[str, str]:
    """单用户模式不需要平台登录头。"""
    return {}


@pytest_asyncio.fixture(scope="function")
async def e2e_agent_context(e2e_client: httpx.AsyncClient, e2e_headers: dict[str, str]) -> dict[str, str | int]:
    user_id = int(E2E_USER_ID)

    default_response = await e2e_client.get("/api/chat/default_agent", headers=e2e_headers)
    default_agent_id = None
    if default_response.status_code == 200:
        default_agent_id = default_response.json().get("default_agent_id")

    if default_agent_id:
        agent_id = str(default_agent_id)
    else:
        response = await e2e_client.get("/api/chat/agent", headers=e2e_headers)
        if response.status_code != 200:
            pytest.fail(f"Failed to list agents for E2E tests (status={response.status_code}): {response.text}")
        agents = response.json().get("agents") or []
        if not agents:
            pytest.fail("No agents are available for E2E tests.")
        agent_id = str(agents[0]["id"])

    config_response = await e2e_client.get(f"/api/chat/agent/{agent_id}/configs", headers=e2e_headers)
    if config_response.status_code != 200:
        pytest.fail(
            f"Failed to list agent configs for E2E tests (status={config_response.status_code}): {config_response.text}"
        )

    configs = config_response.json().get("configs") or []
    if not configs:
        pytest.fail(f"No agent configs are available for E2E tests under agent {agent_id}.")

    config_id = configs[0].get("id")
    if not config_id:
        pytest.fail(f"Agent config payload missing id field for agent {agent_id}.")

    return {"agent_id": agent_id, "agent_config_id": int(config_id), "user_id": int(user_id)}
