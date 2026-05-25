import pytest

from yuxi.knowledge.implementations.lightrag import LightRagKB, limit_extracted_graph_results, resolve_ingestion_options


def test_resolve_ingestion_options_defaults_to_standard():
    options = resolve_ingestion_options({})

    assert options["index_mode"] == "standard"
    assert options["max_graph_nodes"] is None
    assert options["max_graph_relations"] is None


def test_resolve_ingestion_options_accepts_fast_mode():
    options = resolve_ingestion_options({"index_mode": "fast"})

    assert options["index_mode"] == "fast"
    assert options["max_graph_nodes"] is None
    assert options["max_graph_relations"] is None


def test_resolve_ingestion_options_clamps_graph_limits():
    options = resolve_ingestion_options(
        {
            "index_mode": "graph",
            "max_graph_nodes": 5000,
            "max_graph_relations": 9000,
        }
    )

    assert options["index_mode"] == "graph"
    assert options["max_graph_nodes"] == 1000
    assert options["max_graph_relations"] == 3000


def test_resolve_ingestion_options_ignores_invalid_limits():
    options = resolve_ingestion_options(
        {
            "index_mode": "standard",
            "max_graph_nodes": 0,
            "max_graph_relations": "bad",
        }
    )

    assert options["index_mode"] == "standard"
    assert options["max_graph_nodes"] is None
    assert options["max_graph_relations"] is None


def test_limit_extracted_graph_results_keeps_only_allowed_nodes_and_relations():
    chunk_results = [
        (
            {
                "A": [{"entity_name": "A", "source_id": "chunk-1"}],
                "B": [{"entity_name": "B", "source_id": "chunk-1"}],
                "C": [{"entity_name": "C", "source_id": "chunk-1"}],
            },
            {
                ("A", "B"): [{"src_id": "A", "tgt_id": "B", "source_id": "chunk-1"}],
                ("B", "C"): [{"src_id": "B", "tgt_id": "C", "source_id": "chunk-1"}],
            },
        )
    ]

    limited = limit_extracted_graph_results(chunk_results, max_nodes=2, max_relations=2)

    assert list(limited[0][0]) == ["A", "B"]
    assert list(limited[0][1]) == [("A", "B")]


def test_limit_extracted_graph_results_can_limit_relations_only():
    chunk_results = [
        (
            {
                "A": [{"entity_name": "A", "source_id": "chunk-1"}],
                "B": [{"entity_name": "B", "source_id": "chunk-1"}],
                "C": [{"entity_name": "C", "source_id": "chunk-1"}],
            },
            {
                ("A", "B"): [{"src_id": "A", "tgt_id": "B", "source_id": "chunk-1"}],
                ("B", "C"): [{"src_id": "B", "tgt_id": "C", "source_id": "chunk-1"}],
            },
        )
    ]

    limited = limit_extracted_graph_results(chunk_results, max_nodes=None, max_relations=1)

    assert list(limited[0][0]) == ["A", "B", "C"]
    assert list(limited[0][1]) == [("A", "B")]


def test_limit_extracted_graph_results_counts_unique_nodes_across_chunks():
    chunk_results = [
        ({"A": [{"entity_name": "A"}]}, {}),
        (
            {
                "A": [{"entity_name": "A"}],
                "B": [{"entity_name": "B"}],
            },
            {},
        ),
    ]

    limited = limit_extracted_graph_results(chunk_results, max_nodes=2, max_relations=None)

    assert list(limited[0][0]) == ["A"]
    assert list(limited[1][0]) == ["A", "B"]


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
    kb = LightRagKB("/tmp/yuxi-test")
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
