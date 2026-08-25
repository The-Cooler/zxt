import pytest

from zixuetong.knowledge.web_reader.similarity import compute_similarities, cosine_similarity


def test_cosine_similarity_bounds():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([], [0, 1]) == 0.0
    assert cosine_similarity([1], [1, 1]) == 0.0


@pytest.mark.asyncio
async def test_compute_similarities_empty_text_returns_zero():
    scores = await compute_similarities("", ["candidate"], {"model_id": "fake"})
    assert scores == [0.0]

    scores = await compute_similarities("root", ["", "   "], {"model_id": "fake"})
    assert scores == [0.0, 0.0]
