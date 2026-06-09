from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

import json_repair

from zixuetong import config
from zixuetong.knowledge.utils.kb_utils import parse_minio_url
from zixuetong.models import select_model
from zixuetong.plugins.parser.unified import Parser, is_supported_file_extension
from zixuetong.storage.minio import get_minio_client
from zixuetong.utils import logger

MAX_EXTRACTION_CHARS = 18000
MAX_TRIPLES = 200


def normalize_triples(raw_triples: Any, *, max_triples: int = MAX_TRIPLES) -> list[dict[str, Any]]:
    """Normalize model/user triples into the upload graph format."""
    if isinstance(raw_triples, dict):
        if "triples" not in raw_triples:
            raise ValueError("三元组数据必须是数组")
        raw_triples = raw_triples.get("triples", [])

    if not isinstance(raw_triples, list):
        raise ValueError("三元组数据必须是数组")

    triples: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for item in raw_triples:
        if not isinstance(item, dict):
            continue

        h_value = item.get("h") or item.get("head") or item.get("source")
        r_value = item.get("r") or item.get("relation") or item.get("type")
        t_value = item.get("t") or item.get("tail") or item.get("target")

        h_name, h_props = _normalize_node(h_value)
        t_name, t_props = _normalize_node(t_value)
        r_type, r_props = _normalize_relation(r_value)

        if not h_name or not t_name or not r_type:
            continue

        key = (h_name, r_type, t_name)
        if key in seen:
            continue
        seen.add(key)

        triple: dict[str, Any] = {
            "h": {"name": h_name, **h_props} if h_props else h_name,
            "r": {"type": r_type, **r_props} if r_props else r_type,
            "t": {"name": t_name, **t_props} if t_props else t_name,
        }
        triples.append(triple)

        if len(triples) >= max_triples:
            break

    return triples


async def extract_triples_from_file(
    *,
    file_path: str,
    llm_model_spec: str | None = None,
    max_triples: int = MAX_TRIPLES,
) -> dict[str, Any]:
    """Extract graph triples from an uploaded MinIO file without writing Neo4j."""
    text, filename = await _read_uploaded_file_as_markdown(file_path)
    truncated = False
    if len(text) > MAX_EXTRACTION_CHARS:
        text = text[:MAX_EXTRACTION_CHARS]
        truncated = True

    if not text.strip():
        raise ValueError("文件内容为空，无法识别关系")

    model = select_model(model_spec=llm_model_spec or config.default_model)
    prompt = _build_extraction_prompt(text=text, max_triples=max_triples)
    response = await model.call(prompt, stream=False)
    content = getattr(response, "content", "") if response else ""
    triples = normalize_triples(json_repair.loads(_strip_json_fence(content)), max_triples=max_triples)

    if not triples:
        raise ValueError("未识别到有效三元组，请检查文件内容或更换模型后重试")

    return {
        "triples": triples,
        "count": len(triples),
        "filename": filename,
        "truncated": truncated,
        "max_triples": max_triples,
    }


async def _read_uploaded_file_as_markdown(file_path: str) -> tuple[str, str]:
    bucket_name, object_name = parse_minio_url(file_path)
    ext = Path(object_name).suffix.lower()
    if ext == ".jsonl":
        raise ValueError("图谱页不再支持 JSONL 三元组文件，请选择普通文本/文档文件生成全局关系草稿")
    if not is_supported_file_extension(object_name):
        raise ValueError(f"不支持的文件类型: {ext or 'unknown'}")

    minio_client = get_minio_client()
    file_data = await minio_client.adownload_file(bucket_name, object_name)

    with tempfile.NamedTemporaryFile(mode="wb", suffix=ext or ".txt", delete=False) as temp_file:
        temp_file.write(file_data)
        temp_path = temp_file.name

    try:
        markdown = await Parser.aparse(temp_path, params={})
        return markdown, Path(object_name).name
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to clean up graph extraction temp file {temp_path}: {e}")


def _build_extraction_prompt(*, text: str, max_triples: int) -> str:
    return f"""
你是知识图谱关系抽取助手。请从给定文本中抽取对构建知识图谱有价值的实体关系三元组。

要求：
- 只返回 JSON，不要包含 Markdown、解释或额外文字。
- JSON 格式必须是：{{"triples":[{{"h":"头实体","r":"关系","t":"尾实体"}}]}}
- h、r、t 必须是简短字符串。
- 关系 r 使用自然、明确的中文短语，例如“属于”“负责”“位于”“引用”“包含”“作者是”。
- 不要输出缺少上下文依据的关系。
- 合并重复或等价三元组。
- 最多返回 {max_triples} 条。

文本：
{text}
""".strip()


def _strip_json_fence(content: str) -> str:
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r"```$", "", content).strip()
    return content


def _normalize_node(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, dict):
        props = {k: v for k, v in value.items() if v is not None}
        name = str(props.pop("name", "")).strip()
        return name, props
    if value is None:
        return "", {}
    return str(value).strip(), {}


def _normalize_relation(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, dict):
        props = {k: v for k, v in value.items() if v is not None}
        relation_type = str(props.pop("type", "")).strip()
        return relation_type, props
    if value is None:
        return "", {}
    return str(value).strip(), {}
