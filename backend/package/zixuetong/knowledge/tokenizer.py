"""LightRAG tokenizer 的离线实现。

背景：LightRAG 默认使用 TiktokenTokenizer，其构造过程会通过
tiktoken.encoding_for_model() 从 openaipublic.blob.core.windows.net
同步下载编码表。国内网络访问该 CDN 极慢（实测 196KB / 100s 仍未完成），
且该下载发生在 async 调用路径上、未做线程池隔离，会直接阻塞事件循环，
表现为「生成回复时整个服务卡住数十秒」。

本模块提供不依赖网络、不依赖三方分词库的 tokenizer：
- 中文按字符计（一个汉字约等于一个 token）
- 连续 ASCII 字母/数字按每 4 字符 1 个 token 估算

重要：LightRAG 的切块逻辑（operate.py）会 encode 整段文本后按 token 区间
切片，再对切片调用 decode 还原成 chunk 文本，因此 decode 必须能按任意
token 索引区间还原出对应原文，不能只做计数。
"""

from __future__ import annotations

import re

from lightrag.utils import Tokenizer

_ASCII_RUN = re.compile(r"[A-Za-z0-9]+")
_TOKEN_CHARS = 4  # 英文平均约 4 字符/token


class _OfflineEncoder:
    """实现 tiktoken 编码器所需的最小接口（encode/decode）。

    encode 把文本切成 token，并记录每个 token 覆盖的原始片段，
    decode 依据该映射按索引区间还原文本，支持 LightRAG 的切片调用方式。
    """

    def encode(self, content: str) -> list[int]:
        self._segments: list[str] = []
        if not content:
            return []

        pos = 0
        for match in _ASCII_RUN.finditer(content):
            # 匹配前的非 ASCII 部分（中文、标点、空白）逐字符作为一个 token
            for char in content[pos : match.start()]:
                self._segments.append(char)

            # 连续 ASCII 段按 _TOKEN_CHARS 个字符一组，每组一个 token
            run = match.group()
            for i in range(0, len(run), _TOKEN_CHARS):
                self._segments.append(run[i : i + _TOKEN_CHARS])
            pos = match.end()

        for char in content[pos:]:
            self._segments.append(char)

        return list(range(len(self._segments)))

    def decode(self, tokens: list[int]) -> str:
        segments = getattr(self, "_segments", None)
        if not segments or not tokens:
            return ""

        parts: list[str] = []
        for token in tokens:
            index = int(token)
            if 0 <= index < len(segments):
                parts.append(segments[index])
        return "".join(parts)


class OfflineTokenizer(Tokenizer):
    """LightRAG Tokenizer 的离线等价实现。"""

    def __init__(self, model_name: str = "offline"):
        super().__init__(model_name=model_name, tokenizer=_OfflineEncoder())
