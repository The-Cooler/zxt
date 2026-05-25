import pytest

from yuxi.knowledge.graphs.triple_extraction_service import normalize_triples


def test_normalize_triples_accepts_legacy_and_extended_formats():
    triples = normalize_triples(
        [
            {"h": "北京", "r": "首都", "t": "中国"},
            {
                "h": {"name": "孙悟空", "title": "齐天大圣"},
                "r": {"type": "徒弟", "source": "西游记"},
                "t": {"name": "唐僧", "role": "师父"},
            },
        ]
    )

    assert triples == [
        {"h": "北京", "r": "首都", "t": "中国"},
        {
            "h": {"name": "孙悟空", "title": "齐天大圣"},
            "r": {"type": "徒弟", "source": "西游记"},
            "t": {"name": "唐僧", "role": "师父"},
        },
    ]


def test_normalize_triples_filters_invalid_and_deduplicates():
    triples = normalize_triples(
        [
            {"h": "A", "r": "关联", "t": "B"},
            {"h": "A", "r": "关联", "t": "B"},
            {"h": "A", "r": "", "t": "C"},
            {"head": "C", "relation": "包含", "tail": "D"},
            "not-a-triple",
        ]
    )

    assert triples == [
        {"h": "A", "r": "关联", "t": "B"},
        {"h": "C", "r": "包含", "t": "D"},
    ]


def test_normalize_triples_rejects_non_list_payload():
    with pytest.raises(ValueError, match="三元组数据必须是数组"):
        normalize_triples({"items": []})
