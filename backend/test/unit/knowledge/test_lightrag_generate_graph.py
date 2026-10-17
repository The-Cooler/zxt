import pytest

from zixuetong.knowledge.implementations.lightrag import LightRagKB


class _ChunksVdb:
    def __init__(self):
        self.upserts = 0

    async def upsert(self, *args, **kwargs):
        self.upserts += 1


class _FakeRag:
    workspace = "kb-test"

    def __init__(self):
        self.adelete_called = False
        self.chunks_vdb = _ChunksVdb()

    async def adelete_by_doc_id(self, *args, **kwargs):
        self.adelete_called = True


class _Storage:
    def __init__(self):
        self.data = {}

    async def get_by_id(self, key):
        return self.data.get(key)


class _FakeLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


async def _fake_pipeline_lock(rag):
    return {}, _FakeLock()


@pytest.fixture
def kb_with_chunks(monkeypatch):
    kb = LightRagKB("/tmp/zixuetong-test")
    kb.databases_meta["db-1"] = {"name": "kb", "metadata": {}}
    kb.files_meta["file-1"] = {
        "database_id": "db-1",
        "status": "indexed",
        "path": "/tmp/demo.md",
        "processing_params": {},
    }

    rag = _FakeRag()
    rag.text_chunks = type("TextChunks", (), {})()
    rag.text_chunks._data = {
        "chunk-a": {"full_doc_id": "file-1", "chunk_order_index": 1, "content": "A"},
        "chunk-b": {"full_doc_id": "file-1", "chunk_order_index": 0, "content": "B"},
        "chunk-other": {"full_doc_id": "file-2", "chunk_order_index": 0, "content": "C"},
    }
    rag.full_entities = _Storage()
    rag.full_relations = _Storage()
    rag.llm_response_cache = None
    rag.chunk_entity_relation_graph = object()
    rag.entities_vdb = object()
    rag.relationships_vdb = object()
    rag.entity_chunks = None
    rag.relation_chunks = None

    async def fake_insert_done():
        return None

    rag._insert_done = fake_insert_done

    async def fake_get_rag(db_id):
        return rag

    async def fake_persist(file_id):
        return None

    async def fake_extract(chunks, **kwargs):
        return [({"A": [{"entity_name": "A"}]}, {})]

    async def fake_merge(**kwargs):
        rag.merge_calls = kwargs
        rag.full_entities.data["file-1"] = {"entity_names": ["A"]}
        rag.full_relations.data["file-1"] = {"relation_pairs": [["A", "B"]]}

    monkeypatch.setattr(
        "zixuetong.knowledge.implementations.lightrag.extract_entities",
        fake_extract,
    )
    monkeypatch.setattr(
        "zixuetong.knowledge.implementations.lightrag.merge_nodes_and_edges",
        fake_merge,
    )
    monkeypatch.setattr(
        "zixuetong.knowledge.implementations.lightrag._get_pipeline_lock",
        _fake_pipeline_lock,
    )
    # 真实 LightRAG 是 dataclass，假实例不是；这里替换 asdict 避免测试夹具依赖
    monkeypatch.setattr(
        "zixuetong.knowledge.implementations.lightrag.asdict",
        lambda _rag: {"workspace": "kb-test"},
    )
    kb._get_lightrag_instance = fake_get_rag
    kb._persist_file = fake_persist
    kb._add_to_processing_queue = lambda *a, **k: None
    kb._remove_from_processing_queue = lambda *a, **k: None
    return kb, rag


@pytest.mark.asyncio
async def test_generate_graph_does_not_touch_chunks(kb_with_chunks):
    kb, rag = kb_with_chunks
    result = await kb.generate_graph("db-1", "file-1")

    assert rag.adelete_called is False
    assert rag.chunks_vdb.upserts == 0
    assert result["graph_status"] == "built"
    assert result["chunks_total"] == 2
    assert result["chunks_succeeded"] == 2
    assert result["entity_count"] == 1
    assert result["relation_count"] == 1
    assert result["failed_chunks"] == []
    assert kb.files_meta["file-1"]["status"] == "indexed"


@pytest.mark.asyncio
async def test_generate_graph_processes_all_chunks(kb_with_chunks, monkeypatch):
    kb, rag = kb_with_chunks
    seen: list[str] = []

    async def recording_extract(chunks, **kwargs):
        seen.extend(chunks.keys())
        return [({}, {})]

    monkeypatch.setattr(
        "zixuetong.knowledge.implementations.lightrag.extract_entities",
        recording_extract,
    )

    await kb.generate_graph("db-1", "file-1")

    assert sorted(seen) == ["chunk-a", "chunk-b"]


@pytest.mark.asyncio
async def test_generate_graph_records_failed_chunks_and_keeps_status(kb_with_chunks, monkeypatch):
    kb, rag = kb_with_chunks

    async def flaky_extract(chunks, **kwargs):
        if "chunk-b" in chunks:
            raise RuntimeError("boom")
        return [({}, {})]

    monkeypatch.setattr(
        "zixuetong.knowledge.implementations.lightrag.extract_entities",
        flaky_extract,
    )

    result = await kb.generate_graph("db-1", "file-1")

    assert result["graph_status"] == "failed"
    assert result["chunks_succeeded"] == 1
    assert result["failed_chunks"][0]["chunk_id"] == "chunk-b"
    assert kb.files_meta["file-1"]["status"] == "indexed"
