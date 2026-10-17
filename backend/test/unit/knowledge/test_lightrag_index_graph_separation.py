import pytest

from zixuetong.knowledge.implementations.lightrag import LightRagKB


class _FakeRag:
    def __init__(self):
        self.ainsert_calls = 0

    async def ainsert(self, **kwargs):
        self.ainsert_calls += 1


@pytest.mark.asyncio
async def test_index_file_does_not_build_graph():
    """入库路径不能调用实体抽取：index_file 只写向量。"""
    kb = LightRagKB("/tmp/zixuetong-test")
    kb.databases_meta["db-1"] = {
        "name": "kb",
        "metadata": {"chunk_preset_id": "general"},
    }
    kb.files_meta["file-1"] = {
        "database_id": "db-1",
        "status": "parsed",
        "markdown_file": "http://minio/bucket/file-1.md",
        "filename": "demo.md",
        "processing_params": {},
    }

    fast_insert_calls = {"count": 0}

    async def fake_fast_insert(rag, **kwargs):
        fast_insert_calls["count"] += 1

    async def fake_read_markdown(path):
        return "hello world"

    async def fake_get_rag(db_id):
        return _FakeRag()

    kb._fast_insert_chunks = fake_fast_insert
    kb._read_markdown_from_minio = fake_read_markdown
    kb._get_lightrag_instance = fake_get_rag
    kb.chunk_markdown = lambda *args, **kwargs: [{"content": "hello world"}]

    # 这些方法只负责持久化/队列，与本次断言无关，替换掉避免依赖数据库
    async def noop_async(*args, **kwargs):
        return None

    kb._persist_file = noop_async
    kb._save_metadata = noop_async
    kb._add_to_processing_queue = lambda *args, **kwargs: None
    kb._remove_from_processing_queue = lambda *args, **kwargs: None

    result = await kb.index_file("db-1", "file-1")

    assert fast_insert_calls["count"] == 1
    assert result["graph_status"] == "pending"
    assert result["status"] == "indexed"
