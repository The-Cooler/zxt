"""支持提取第三方 OpenAI 兼容服务 reasoning_content 的 ChatOpenAI 子类。

背景：langchain_openai 的 ChatOpenAI 官方声明不解析非标准字段
（见 langchain_openai/chat_models/base.py 中 ChatOpenAI 的 API scope 说明），
其 _convert_delta_to_message_chunk 只处理 function_call 与 tool_calls，
因此 DeepSeek 等模型返回的 delta.reasoning_content 会被直接丢弃。

本项目需要把推理过程透传给前端（前端读取 additional_kwargs.reasoning_content），
且不必绑定 DeepSeek 官方 SDK 行为，因此在 ChatOpenAI 基础上做最小增量扩展。
"""

from __future__ import annotations

from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI


class ChatOpenAIWithReasoning(ChatOpenAI):
    """在标准 ChatOpenAI 之上保留 delta.reasoning_content。

    仅新增对 reasoning_content 字段的提取，不改变其余任何行为。
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None

        choices = chunk.get("choices") or []
        if not choices:
            return generation_chunk

        message = getattr(generation_chunk, "message", None)
        if not isinstance(message, AIMessageChunk):
            return generation_chunk

        delta = choices[0].get("delta") or {}
        reasoning = delta.get("reasoning_content")
        if reasoning:
            existing = message.additional_kwargs.get("reasoning_content") or ""
            message.additional_kwargs["reasoning_content"] = existing + reasoning

        return generation_chunk
