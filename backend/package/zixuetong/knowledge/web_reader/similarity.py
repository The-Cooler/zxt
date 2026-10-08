from __future__ import annotations

import math

import httpx

TEXT_LIMIT = 12000


def _compute_tfidf_similarity(root_text: str, candidate_texts: list[str]) -> list[float]:
    """使用 TF-IDF + 余弦相似度计算文本相似度（免费、本地计算）"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
    except ImportError:
        raise ValueError(
            "需要安装 scikit-learn 才能使用免费相似度计算。"
            "请运行: pip install scikit-learn"
        )

    if not candidate_texts:
        return []

    if not root_text.strip():
        return [0.0 for _ in candidate_texts]

    # 过滤空文本
    non_empty_indexes = [idx for idx, text in enumerate(candidate_texts) if text.strip()]
    if not non_empty_indexes:
        return [0.0 for _ in candidate_texts]

    # 准备文本（限制长度）
    texts = [root_text[:TEXT_LIMIT]] + [candidate_texts[idx][:TEXT_LIMIT] for idx in non_empty_indexes]

    # 使用 TF-IDF 向量化（支持中英文）
    vectorizer = TfidfVectorizer(
        max_features=1000,
        ngram_range=(1, 2),  # 使用 1-2 gram 提高准确度
        min_df=1,
        token_pattern=r"(?u)\b\w+\b",  # 支持中文分词
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        # 如果所有文本都是空的或无法提取特征
        return [0.0 for _ in candidate_texts]

    # 计算余弦相似度
    similarities = sklearn_cosine(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    # 映射回原始索引
    scores = [0.0 for _ in candidate_texts]
    for offset, idx in enumerate(non_empty_indexes):
        scores[idx] = float(max(0.0, min(1.0, similarities[offset])))

    return scores


class WebReaderSimilarityError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _embedding_http_error_message(error: httpx.HTTPStatusError) -> tuple[str, int]:
    status_code = error.response.status_code
    provider_message = error.response.text.strip()

    if status_code == 402:
        return (
            "Embedding 模型调用失败：模型供应商返回 402 Payment Required，"
            "通常表示账号余额不足、套餐限制或该模型未开通计费权限。"
            "请检查模型配置和供应商账户后重试。",
            402,
        )
    if status_code in {401, 403}:
        return (
            "Embedding 模型调用失败：模型供应商拒绝了认证或权限校验。"
            "请检查 API Key、模型权限和知识库绑定的 Embedding 模型配置。",
            502,
        )
    if status_code == 429:
        return (
            "Embedding 模型调用失败：模型供应商请求频率受限。"
            "请稍后重试，或调整模型供应商限流配置。",
            429,
        )

    detail = f"供应商返回 HTTP {status_code}"
    if provider_message:
        detail = f"{detail}: {provider_message[:300]}"
    return (f"Embedding 模型调用失败：{detail}", 502)


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
    """计算文本相似度

    默认使用 TF-IDF + 余弦相似度（免费、本地计算）
    如果需要使用 Embedding API（更准确但消耗额度），可以在此修改
    """
    # 默认使用免费方案，避免递归抓取时消耗大量 Embedding 额度
    return _compute_tfidf_similarity(root_text, candidate_texts)

    # 如需使用 Embedding API（更准确但消耗额度），取消下面代码的注释：
    # if not candidate_texts:
    #     return []
    #
    # if not root_text.strip():
    #     return [0.0 for _ in candidate_texts]
    #
    # non_empty_indexes = [idx for idx, text in enumerate(candidate_texts) if text.strip()]
    # if not non_empty_indexes:
    #     return [0.0 for _ in candidate_texts]
    #
    # if not embed_info or not embed_info.get("model_id"):
    #     raise ValueError("知识库缺少 embedding 模型配置，无法计算网页相似度")
    #
    # from zixuetong.models.embed import select_embedding_model
    #
    # model = select_embedding_model(embed_info["model_id"])
    # root_input = root_text[:TEXT_LIMIT]
    # candidate_inputs = [candidate_texts[idx][:TEXT_LIMIT] for idx in non_empty_indexes]
    # batch_size = int(getattr(model, "batch_size", 40) or 40)
    # try:
    #     vectors = await model.abatch_encode([root_input, *candidate_inputs], batch_size=batch_size)
    # except httpx.HTTPStatusError as exc:
    #     message, status_code = _embedding_http_error_message(exc)
    #     raise WebReaderSimilarityError(message, status_code=status_code) from exc
    # except httpx.RequestError as exc:
    #     raise WebReaderSimilarityError(
    #         "Embedding 模型连接失败：无法连接到模型供应商,请检查模型服务地址和网络连接。",
    #         status_code=502,
    #     ) from exc
    # except Exception as exc:
    #     raise WebReaderSimilarityError(
    #         f"Embedding 模型调用失败：{exc}",
    #         status_code=502,
    #     ) from exc
    #
    # if len(vectors) != len(candidate_inputs) + 1:
    #     raise WebReaderSimilarityError("Embedding 模型返回数量异常，无法计算网页相似度", status_code=502)
    #
    # scores = [0.0 for _ in candidate_texts]
    # root_vector = vectors[0]
    # for offset, idx in enumerate(non_empty_indexes, start=1):
    #     scores[idx] = cosine_similarity(root_vector, vectors[offset])
    # return scores
