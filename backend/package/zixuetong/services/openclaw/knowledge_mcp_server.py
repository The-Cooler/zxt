"""自学通知识库 MCP 服务器

将自学通的知识库查询能力暴露为 MCP 服务器工具，
让 OpenClaw 等外部智能体能直接查询本项目的 RAG 知识库。
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from zixuetong.utils import logger

# 创建 MCP 服务器实例
mcp = FastMCP("自学通知识库", instructions="查询自学通知识库，支持语义检索和知识图谱查询")


@mcp.tool()
async def query_knowledge_base(query: str, db_name: str | None = None) -> str:
    """在自学通知识库中检索内容

    Args:
        query: 查询关键词或问题
        db_name: 知识库名称（可选，默认查询第一个可用知识库）

    Returns:
        检索到的相关内容
    """
    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        return "LITE 模式下知识库不可用"

    from zixuetong.knowledge import knowledge_base

    try:
        if db_name:
            # 通过名称查找 db_id
            retrievers = knowledge_base.get_retrievers()
            for db_id, info in retrievers.items():
                if info.get("name") == db_name:
                    result = await knowledge_base.aquery(query, db_id=db_id)
                    return str(result)
            return f"知识库 '{db_name}' 不存在"
        else:
            # 查询第一个可用知识库
            retrievers = knowledge_base.get_retrievers()
            if not retrievers:
                return "当前没有可用的知识库"
            first_db_id = list(retrievers.keys())[0]
            result = await knowledge_base.aquery(query, db_id=first_db_id)
            return str(result)
    except Exception as e:
        logger.error(f"MCP 知识库查询失败: {e}")
        return f"查询失败: {e}"


@mcp.tool()
async def list_knowledge_bases() -> str:
    """列出自学通中所有可用的知识库

    Returns:
        知识库列表（名称和描述）
    """
    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        return "LITE 模式下知识库不可用"

    from zixuetong.knowledge import knowledge_base

    try:
        retrievers = knowledge_base.get_retrievers()
        if not retrievers:
            return "当前没有可用的知识库"

        lines = []
        for db_id, info in retrievers.items():
            name = info.get("name", "未知")
            description = info.get("description", "无描述")
            lines.append(f"- {name} (ID: {db_id}): {description}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"MCP 获取知识库列表失败: {e}")
        return f"获取列表失败: {e}"


@mcp.tool()
async def get_knowledge_base_mindmap(db_name: str) -> str:
    """获取自学通知识库的思维导图结构

    Args:
        db_name: 知识库名称

    Returns:
        思维导图层级结构文本
    """
    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        return "LITE 模式下知识库不可用"

    from zixuetong.knowledge import knowledge_base
    from zixuetong.repositories.knowledge_base_repository import KnowledgeBaseRepository

    try:
        retrievers = knowledge_base.get_retrievers()
        target_db_id = None
        for db_id, info in retrievers.items():
            if info.get("name") == db_name:
                target_db_id = db_id
                break

        if not target_db_id:
            return f"知识库 '{db_name}' 不存在"

        repo = KnowledgeBaseRepository()
        kb = await repo.get_by_id(target_db_id)
        if not kb:
            return f"知识库 '{db_name}' 不存在"

        mindmap = kb.mindmap
        if not mindmap:
            return f"知识库 '{db_name}' 还没有生成思维导图"

        def mindmap_to_text(node, level=0):
            indent = "  " * level
            text = f"{indent}- {node.get('content', '')}\n"
            for child in node.get("children", []):
                text += mindmap_to_text(child, level + 1)
            return text

        return f"知识库 {db_name} 的思维导图结构:\n\n{mindmap_to_text(mindmap)}"
    except Exception as e:
        logger.error(f"MCP 获取思维导图失败: {e}")
        return f"获取思维导图失败: {e}"


def create_mcp_app():
    """创建 MCP 服务器 ASGI 应用"""
    return mcp.http_app()
