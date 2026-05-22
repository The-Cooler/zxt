import pytest

from yuxi.knowledge.web_reader.models import WebPageSnapshot, WebReadSession
from yuxi.knowledge.web_reader.session_store import load_session, save_session


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def get(self, key):
        return self.values.get(key)


@pytest.mark.asyncio
async def test_session_store_round_trip(monkeypatch):
    redis = FakeRedis()

    async def fake_get_redis_client():
        return redis

    monkeypatch.setattr("yuxi.knowledge.web_reader.session_store.get_redis_client", fake_get_redis_client)

    session = WebReadSession(
        session_id="s1",
        db_id="db1",
        root_url="https://example.com",
        root_snapshot=WebPageSnapshot(url="https://example.com", final_url="https://example.com"),
        created_by="u1",
    )

    await save_session(session)
    loaded = await load_session("s1")

    assert loaded.session_id == "s1"
    assert loaded.root_snapshot.final_url == "https://example.com"
