"""「重新生成」服务：截断指定 AI 回复及其后续内容，返回可重发的用户提问。

设计要点：
- 与 GPT 一致，该操作只在最后一条 AI 回复上可用，因此截断是「删到末尾」。
- 两处状态必须同步清理，否则重新生成时模型会看到已被删除的历史：
  1. 业务库 conversations/messages（前端历史展示的数据源）
  2. LangGraph checkpointer（模型实际读取的上下文）
"""

from __future__ import annotations

from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from sqlalchemy.ext.asyncio import AsyncSession

from zixuetong.repositories.conversation_repository import ConversationRepository
from zixuetong.utils.logging_config import logger


class RegenerateError(Exception):
    """重新生成失败（消息不存在、不是 AI 回复等）。"""


async def _resolve_agent(agent_id: str):
    from zixuetong.agents.buildin import agent_manager

    agent = agent_manager.get_agent(agent_id)
    if agent is None:
        raise RegenerateError(f"智能体不存在: {agent_id}")
    return agent


async def _truncate_langgraph_state(*, agent, thread_id: str, user_id: str, keep_count: int) -> None:
    """把 LangGraph 中的消息裁剪到前 keep_count 条。

    通过 RemoveMessage(REMOVE_ALL_MESSAGES) 清空后重放保留的消息，
    与 SummaryOffloadMiddleware 中的做法一致。
    """
    graph = await agent.get_graph()
    config = {"configurable": {"thread_id": thread_id, "user_id": str(user_id)}}

    state = await graph.aget_state(config)
    messages = list(getattr(state, "values", {}).get("messages", []) or [])
    if not messages:
        await graph.aupdate_state(config=config, values={"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]})
        return

    kept = messages[:keep_count]
    await graph.aupdate_state(
        config=config,
        values={"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *kept]},
    )


async def regenerate_from_message_view(
    *,
    thread_id: str,
    message_id: int,
    current_user_id: str,
    db: AsyncSession,
) -> dict:
    """删除指定 AI 消息及其后续全部消息，返回对应的用户提问。

    Returns:
        {"thread_id": ..., "agent_id": ..., "query": ..., "deleted_count": ...}
    """
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
    if conversation is None or str(conversation.user_id) != str(current_user_id):
        raise RegenerateError("对话不存在或无权访问")

    messages = await conv_repo.get_messages(conversation.id)
    target_index = next((i for i, m in enumerate(messages) if m.id == message_id), None)
    if target_index is None:
        raise RegenerateError("消息不存在或不属于当前对话")

    target = messages[target_index]
    if target.role != "assistant":
        raise RegenerateError("只能对助手回复执行重新生成")

    # 重新生成只对最后一条 AI 回复开放：其后再无消息，
    # 因此被截断的必然是该 AI 回复本身（及其 tool 消息）。
    if target_index != len(messages) - 1 and any(
        m.role == "assistant" for m in messages[target_index + 1 :]
    ):
        raise RegenerateError("仅支持重新生成最后一条回复")

    # 回溯找到本轮的用户提问
    query_index = next(
        (i for i in range(target_index - 1, -1, -1) if messages[i].role == "user"),
        None,
    )
    if query_index is None:
        raise RegenerateError("未找到对应的用户提问")

    query_message = messages[query_index]
    query = query_message.content or ""

    # 1. 截断业务库：连同该轮提问一起删除（提问由前端重新插入并重发），
    #    否则重新生成会留下重复的用户消息。
    deleted_count = await conv_repo.delete_messages_from(conversation.id, query_message.id)

    # 2. 截断 LangGraph：保留该提问之前的所有消息
    keep_count = query_index
    try:
        agent = await _resolve_agent(conversation.agent_id)
        await _truncate_langgraph_state(
            agent=agent,
            thread_id=thread_id,
            user_id=str(current_user_id),
            keep_count=keep_count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"截断 LangGraph 状态失败 thread={thread_id}: {exc}")

    logger.info(
        f"Regenerate truncated thread={thread_id} from message={message_id}, deleted={deleted_count}"
    )

    return {
        "thread_id": thread_id,
        "agent_id": conversation.agent_id,
        "query": query,
        "deleted_count": deleted_count,
    }
