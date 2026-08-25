import pytest

from server.routers import knowledge_router
from zixuetong.knowledge.web_reader.models import CleanedWebPage, DiscoveredLink, WebPageSnapshot, WebReadSession


class _UploadResult:
    def __init__(self, url: str, object_name: str):
        self.url = url
        self.bucket_name = "knowledgebases"
        self.object_name = object_name


class _FakeMinio:
    KB_BUCKETS = {"documents": "knowledgebases"}

    def __init__(self):
        self.uploads = []
        self.objects = {}

    def ensure_bucket_exists(self, bucket_name):
        self.bucket_name = bucket_name
        return True

    async def aupload_file(self, *, bucket_name, object_name, data, content_type=None):
        self.uploads.append(
            {
                "bucket_name": bucket_name,
                "object_name": object_name,
                "data": data,
                "content_type": content_type,
            }
        )
        self.objects[(bucket_name, object_name)] = data
        return _UploadResult(f"minio://{bucket_name}/{object_name}", object_name)

    async def adownload_file(self, bucket_name, object_name):
        return self.objects[(bucket_name, object_name)]

    async def adelete_file(self, bucket_name, object_name):
        self.objects.pop((bucket_name, object_name), None)


class _FakeReader:
    async def fetch_page(self, url, *, depth=0, parent_url=None):
        assert url == "https://example.com/a"
        return WebPageSnapshot(
            url=url,
            final_url=url,
            title="Page A",
            html="<html><body><nav>Menu</nav><main><h1>Page A</h1><p>Useful child text.</p></main></body></html>",
            text="Menu Page A Useful child text.",
            depth=depth,
            parent_url=parent_url,
        )


def _session() -> WebReadSession:
    return WebReadSession(
        session_id="session-1",
        db_id="db1",
        root_url="https://example.com",
        root_snapshot=WebPageSnapshot(
            url="https://example.com",
            final_url="https://example.com",
            title="Root",
            html="<html><body><header>Top</header><main><h1>Root</h1><p>Useful root text.</p></main></body></html>",
            text="Top Root Useful root text.",
        ),
        discovered_map={
            "https://example.com/a": DiscoveredLink(
                url="https://example.com/a",
                base_url="https://example.com",
                parents=["https://example.com"],
                title="Page A",
                depth=1,
                status="ready",
                selected=True,
            )
        },
        selected_urls=["https://example.com/a"],
        created_by="user-1",
    )


def _session_with_cleaned_pages() -> WebReadSession:
    session = _session()
    session.cleaned_pages = [
        CleanedWebPage(
            source_url="https://example.com",
            title="Root",
            path="minio://knowledgebases/db1/upload/web-reader/session-1/root.md",
            content_hash="hash-root",
            filename="Root.md",
            file_size=128,
        ),
        CleanedWebPage(
            source_url="https://example.com/a",
            title="Page A",
            path="minio://knowledgebases/db1/upload/web-reader/session-1/a.md",
            content_hash="hash-a",
            filename="Page-A.md",
            file_size=64,
        ),
    ]
    return session


@pytest.mark.asyncio
async def test_clean_web_reader_session_uploads_cleaned_markdown_and_saves_session(monkeypatch):
    session = _session()
    fake_minio = _FakeMinio()
    saved_sessions = []

    async def fake_load_session(session_id):
        assert session_id == "session-1"
        return session

    async def fake_save_session(updated):
        saved_sessions.append(updated)

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)
    monkeypatch.setattr(knowledge_router, "save_session", fake_save_session)
    monkeypatch.setattr(knowledge_router, "get_minio_client", lambda: fake_minio)
    monkeypatch.setattr(knowledge_router, "ScraplingWebReader", lambda: _FakeReader())

    result = await knowledge_router.clean_web_reader_session(
        "session-1",
        current_user=type("User", (), {"user_id": "user-1"})(),
    )

    assert result["status"] == "cleaned"
    assert result["cleaned_count"] == 2
    assert len(fake_minio.uploads) == 2
    assert fake_minio.uploads[0]["content_type"] == "text/markdown"
    uploaded_text = fake_minio.uploads[0]["data"].decode("utf-8")
    assert "# Root" in uploaded_text
    assert "Useful root text." in uploaded_text
    assert "Top" not in uploaded_text
    assert saved_sessions[0].cleaned_pages[0].source_url == "https://example.com"


@pytest.mark.asyncio
async def test_commit_web_reader_session_uses_cleaned_files_without_refetching(monkeypatch):
    session = _session_with_cleaned_pages()
    session.cleaned_pages = session.cleaned_pages[:1]
    add_calls = []

    async def fake_load_session(session_id):
        return session

    async def fake_add_documents(db_id, items, params, current_user):
        add_calls.append((db_id, items, params, current_user.user_id))
        return {"task_id": "task-1", "message": "queued"}

    class RefetchForbiddenReader:
        async def fetch_page(self, *args, **kwargs):
            raise AssertionError("commit should reuse cleaned files")

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)
    monkeypatch.setattr(knowledge_router, "add_documents", fake_add_documents)
    monkeypatch.setattr(knowledge_router, "ScraplingWebReader", lambda: RefetchForbiddenReader())

    result = await knowledge_router.commit_web_reader_session(
        "session-1",
        auto_index=True,
        chunk_params={"index_mode": "fast"},
        current_user=type("User", (), {"user_id": "user-1"})(),
    )

    assert result["task_id"] == "task-1"
    db_id, items, params, user_id = add_calls[0]
    assert db_id == "db1"
    assert items == ["minio://knowledgebases/db1/upload/web-reader/session-1/root.md"]
    assert user_id == "user-1"
    assert params["auto_index"] is True
    assert params["content_type"] == "file"
    assert params["_preprocessed_map"][items[0]]["filename"] == "Root.md"


@pytest.mark.asyncio
async def test_get_cleaned_web_reader_page_returns_markdown_content(monkeypatch):
    session = _session_with_cleaned_pages()
    fake_minio = _FakeMinio()
    fake_minio.objects[("knowledgebases", "db1/upload/web-reader/session-1/root.md")] = b"# Root\n\nClean text"

    async def fake_load_session(session_id):
        return session

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)
    monkeypatch.setattr(knowledge_router, "get_minio_client", lambda: fake_minio)

    result = await knowledge_router.get_cleaned_web_reader_page(
        "session-1",
        source_url="https://example.com",
        current_user=type("User", (), {"user_id": "user-1"})(),
    )

    assert result["source_url"] == "https://example.com"
    assert result["content"] == "# Root\n\nClean text"


@pytest.mark.asyncio
async def test_update_cleaned_web_reader_page_saves_edited_markdown(monkeypatch):
    session = _session_with_cleaned_pages()
    fake_minio = _FakeMinio()
    saved_sessions = []

    async def fake_load_session(session_id):
        return session

    async def fake_save_session(updated):
        saved_sessions.append(updated)

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)
    monkeypatch.setattr(knowledge_router, "save_session", fake_save_session)
    monkeypatch.setattr(knowledge_router, "get_minio_client", lambda: fake_minio)

    result = await knowledge_router.update_cleaned_web_reader_page(
        "session-1",
        source_url="https://example.com",
        content="# Root\n\nEdited clean text",
        current_user=type("User", (), {"user_id": "user-1"})(),
    )

    updated_page = saved_sessions[0].cleaned_pages[0]
    bucket_name, object_name = knowledge_router.parse_minio_url(updated_page.path)
    assert result["page"]["file_size"] == len("# Root\n\nEdited clean text".encode("utf-8"))
    assert updated_page.content_hash != "hash-root"
    assert fake_minio.objects[(bucket_name, object_name)] == b"# Root\n\nEdited clean text"


@pytest.mark.asyncio
async def test_delete_cleaned_web_reader_page_removes_page_from_commit(monkeypatch):
    session = _session_with_cleaned_pages()
    fake_minio = _FakeMinio()
    saved_sessions = []

    async def fake_load_session(session_id):
        return session

    async def fake_save_session(updated):
        saved_sessions.append(updated)

    monkeypatch.setattr(knowledge_router, "load_session", fake_load_session)
    monkeypatch.setattr(knowledge_router, "save_session", fake_save_session)
    monkeypatch.setattr(knowledge_router, "get_minio_client", lambda: fake_minio)

    result = await knowledge_router.delete_cleaned_web_reader_page(
        "session-1",
        source_url="https://example.com/a",
        current_user=type("User", (), {"user_id": "user-1"})(),
    )

    assert result["cleaned_count"] == 1
    assert [page.source_url for page in saved_sessions[0].cleaned_pages] == ["https://example.com"]
