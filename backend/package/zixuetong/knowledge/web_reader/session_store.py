from __future__ import annotations

import json
import os

from zixuetong.services.run_queue_service import get_redis_client

from .models import WebReadSession

SESSION_TTL_SECONDS = int(os.getenv("ZIXUETONG_WEB_READ_SESSION_TTL_SECONDS", "86400"))
SESSION_KEY_PREFIX = "zixuetong:web-read-session:"


def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


async def save_session(session: WebReadSession) -> None:
    redis = await get_redis_client()
    payload = session.model_dump_json() if hasattr(session, "model_dump_json") else session.json()
    await redis.set(_session_key(session.session_id), payload, ex=SESSION_TTL_SECONDS)


async def load_session(session_id: str) -> WebReadSession:
    redis = await get_redis_client()
    payload = await redis.get(_session_key(session_id))
    if not payload:
        raise ValueError("网页读取会话不存在或已过期")
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    if hasattr(WebReadSession, "model_validate"):
        return WebReadSession.model_validate(data)
    return WebReadSession.parse_obj(data)
