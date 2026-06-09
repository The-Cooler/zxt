import pytest

from server.routers import knowledge_router
from zixuetong.knowledge.web_reader.models import DiscoveredLink, WebPageSnapshot, WebReadSession


def _session() -> WebReadSession:
    return WebReadSession(
        session_id="session-1",
        db_id="db1",
        root_url="https://example.com",
        root_snapshot=WebPageSnapshot(
            url="https://example.com",
            final_url="https://example.com",
            title="Root",
            html="<html><body><h1>Root</h1></body></html>",
            text="Root",
        ),
        discovered_map={
            "https://example.com/a": DiscoveredLink(
                url="https://example.com/a",
                base_url="https://example.com",
                parents=["https://example.com"],
                title="Page A",
                depth=1,
                status="ready",
            )
        },
        created_by="user-1",
    )


@pytest.mark.asyncio
async def test_preview_web_reader_page_returns_root_html(monkeypatch):
    async def fake_load_session(session_id):
        assert session_id == "session-1"
        return _session()

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)

    result = await knowledge_router.preview_web_reader_page(
        "session-1",
        url="https://example.com",
        current_user=type("User", (), {"user_id": "user-1"})(),
    )

    assert result["url"] == "https://example.com"
    assert result["title"] == "Root"
    assert "<h1>Root</h1>" in result["html"]


@pytest.mark.asyncio
async def test_preview_web_reader_page_rejects_unknown_url(monkeypatch):
    async def fake_load_session(session_id):
        return _session()

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)

    with pytest.raises(knowledge_router.HTTPException) as exc:
        await knowledge_router.preview_web_reader_page(
            "session-1",
            url="https://evil.example.com",
            current_user=type("User", (), {"user_id": "user-1"})(),
        )

    assert exc.value.status_code == 400
