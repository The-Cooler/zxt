import pytest

from zixuetong.knowledge.implementations.lightrag import LightRagKB, resolve_ingestion_options


def test_resolve_ingestion_options_defaults_to_fast():
    options = resolve_ingestion_options({})

    assert options["index_mode"] == "fast"


def test_resolve_ingestion_options_keeps_explicit_mode():
    options = resolve_ingestion_options({"index_mode": "graph"})

    assert options["index_mode"] == "graph"


def test_resolve_ingestion_options_ignores_graph_limits():
    options = resolve_ingestion_options(
        {
            "index_mode": "graph",
            "max_graph_nodes": 5000,
            "max_graph_relations": 9000,
        }
    )

    assert "max_graph_nodes" not in options
    assert "max_graph_relations" not in options


def test_generate_graph_uses_all_chunks_without_limits():
    """全量抽取：节点/关系上限不再参与图谱流程。"""
    assert not hasattr(LightRagKB, "_scoped_graph_limits")


class FakeStorage:
    def __init__(self):
        self.data = {}
        self.index_done_called = False

    async def upsert(self, data):
        self.data.update(data)

    async def index_done_callback(self):
        self.index_done_called = True


class FakeRag:
    def __init__(self):
        self.custom_kg = None
        self.full_docs = FakeStorage()
        self.doc_status = FakeStorage()

    async def ainsert_custom_kg(self, custom_kg, full_doc_id=None):
        self.custom_kg = {"custom_kg": custom_kg, "full_doc_id": full_doc_id}


@pytest.mark.asyncio
async def test_fast_insert_chunks_records_doc_status_for_future_delete():
    kb = LightRagKB("/tmp/zixuetong-test")
    rag = FakeRag()

    await kb._fast_insert_chunks(
        rag,
        markdown_content="hello\nworld",
        chunks=[{"content": "hello"}, {"content": "world"}],
        file_id="file-1",
        file_path="/tmp/demo.md",
    )

    assert rag.custom_kg["full_doc_id"] == "file-1"
    assert rag.custom_kg["custom_kg"]["entities"] == []
    assert rag.custom_kg["custom_kg"]["relationships"] == []
    status = rag.doc_status.data["file-1"]
    assert status["status"].value == "processed"
    assert status["chunks_count"] == 2
    assert status["chunks_list"] == [
        "chunk-5d41402abc4b2a76b9719d911017c592",
        "chunk-7d793037a0760186574b0282f2f435e7",
    ]
    assert rag.full_docs.data["file-1"]["content"] == "hello\nworld"
    assert rag.doc_status.index_done_called is True
    assert rag.full_docs.index_done_called is True
