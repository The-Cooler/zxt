from __future__ import annotations

import math

TEXT_LIMIT = 12000


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


async def compute_similarities(root_text: str, candidate_texts: list[str], embed_info: dict | None) -> list[float]:
    if not candidate_texts:
        return []

    if not root_text.strip():
        return [0.0 for _ in candidate_texts]

    non_empty_indexes = [idx for idx, text in enumerate(candidate_texts) if text.strip()]
    if not non_empty_indexes:
        return [0.0 for _ in candidate_texts]

    if not embed_info or not embed_info.get("model_id"):
        raise ValueError("知识库缺少 embedding 模型配置，无法计算网页相似度")

    from zixuetong.models.embed import select_embedding_model

    model = select_embedding_model(embed_info["model_id"])
    root_input = root_text[:TEXT_LIMIT]
    candidate_inputs = [candidate_texts[idx][:TEXT_LIMIT] for idx in non_empty_indexes]
    batch_size = int(getattr(model, "batch_size", 40) or 40)
    vectors = await model.abatch_encode([root_input, *candidate_inputs], batch_size=batch_size)

    if len(vectors) != len(candidate_inputs) + 1:
        raise ValueError("embedding 模型返回数量异常，无法计算网页相似度")

    scores = [0.0 for _ in candidate_texts]
    root_vector = vectors[0]
    for offset, idx in enumerate(non_empty_indexes, start=1):
        scores[idx] = cosine_similarity(root_vector, vectors[offset])
    return scores
