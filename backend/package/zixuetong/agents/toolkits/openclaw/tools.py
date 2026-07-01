"""OpenClaw 工具 - 查询 OpenClaw 知识、共享知识到 OpenClaw"""

from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

from zixuetong.utils import logger


class QueryOpenClawInput(BaseModel):
    """查询 OpenClaw 知识输入模型"""

    query: str = Field(description="要查询的问题或关键词")


class ShareKnowledgeInput(BaseModel):
    """共享知识到 OpenClaw 输入模型"""

    knowledge: str = Field(description="要共享的知识内容")


@tool(args_schema=QueryOpenClawInput)
async def query_openclaw(query: str, runtime: ToolRuntime = None) -> str:
    """查询 OpenClaw 的知识库，获取自学通范围之外的外部知识

    当用户的问题可能需要外部知识源、跨平台知识或 OpenClaw 特有的洞察时使用此工具。

    Args:
        query: 查询的问题或关键词

    Returns:
        OpenClaw 返回的知识内容
    """
    from zixuetong.services.openclaw.bridge_service import openclaw_bridge

    if not openclaw_bridge.is_connected:
        return "OpenClaw 未连接，无法查询外部知识"

    try:
        result = await openclaw_bridge.query_openclaw_knowledge(query)
        if result is None:
            return "查询 OpenClaw 知识未返回结果"
        return str(result)
    except Exception as e:
        logger.error(f"查询 OpenClaw 知识失败: {e}")
        return f"查询 OpenClaw 知识失败: {e}"


@tool(args_schema=ShareKnowledgeInput)
async def share_knowledge_to_openclaw(knowledge: str, runtime: ToolRuntime = None) -> str:
    """将知识共享给 OpenClaw，使其可以学习和传播

    当在对话中产生了有价值的新知识、洞察或总结时，使用此工具将其推送到 OpenClaw。

    Args:
        knowledge: 要共享的知识内容

    Returns:
        共享结果
    """
    from zixuetong.services.openclaw.bridge_service import openclaw_bridge

    if not openclaw_bridge.is_connected:
        return "OpenClaw 未连接，无法共享知识"

    try:
        result = await openclaw_bridge.push_knowledge_to_openclaw([{"content": knowledge}])
        if result is None:
            return "共享知识到 OpenClaw 未返回确认"
        return "知识已成功共享到 OpenClaw"
    except Exception as e:
        logger.error(f"共享知识到 OpenClaw 失败: {e}")
        return f"共享知识到 OpenClaw 失败: {e}"


def get_openclaw_tools():
    """获取 OpenClaw 工具列表"""
    return [query_openclaw, share_knowledge_to_openclaw]
