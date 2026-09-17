"""SubAgent 服务层"""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from zixuetong.repositories.subagent_repository import SubAgentRepository
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.utils import logger
from zixuetong.utils.paths import OUTPUTS_DIR_NAME

# SubAgent specs cache for get_subagent_specs
_subagent_specs_cache: list[dict[str, Any]] | None = None
_subagent_specs_lock = asyncio.Lock()


@asynccontextmanager
async def _get_session(db: AsyncSession | None = None):
    """获取数据库会话的上下文管理器"""
    if db is not None:
        yield db
    else:
        async with pg_manager.get_async_session_context() as session:
            yield session


# 内置 SubAgent 配置
_DEFAULT_SUBAGENTS = [
    {
        "name": "research-agent",
        "description": "利用搜索工具，用于研究更深入的问题。将调研结果写入到主题研究文件中。",
        "system_prompt": (
            "你是一位专注的研究员。你的工作是根据用户的问题进行研究。"
            "进行彻底的研究，然后用详细的答案回复用户的问题，只有你的最终答案会被传递给用户。"
            "除了你的最终信息，他们不会知道任何其他事情，所以你的最终报告应该就是你的最终信息！"
            f"将调研结果保存到主题研究文件中 {OUTPUTS_DIR_NAME}/sub_research/xxx.md 中。"
        ),
        "tools": ["tavily_search"],
        "is_builtin": True,
    },
    {
        "name": "critique-agent",
        "description": "用于评论最终报告。给这个代理一些关于你希望它如何评论报告的信息。",
        "system_prompt": (
            "你是一位专注的编辑。你的任务是评论一份报告。\n\n"
            "你可以在 `final_report.md` 找到这份报告。\n\n"
            "你可以在 `question.txt` 找到这份报告的问题/主题。\n\n"
            "用户可能会要求评论报告的特定方面。请用详细的评论回复用户，指出报告中可以改进的地方。\n\n"
            "如果有助于你评论报告，你可以使用搜索工具来搜索信息\n\n"
            "不要自己写入 `final_report.md`。\n\n"
            "需要检查的事项：\n"
            "- 检查每个部分的标题是否恰当\n"
            "- 检查报告的写法是否像论文或教科书——它应该是以文本为主，不要只是一个项目符号列表！\n"
            "- 检查报告是否全面。如果任何段落或部分过短，或缺少重要细节，请指出来。\n"
            "- 检查文章是否涵盖了行业的关键领域，确保了整体理解，并且没有遗漏重要部分。\n"
            "- 检查文章是否深入分析了原因、影响和趋势，提供了有价值的见解\n"
            "- 检查文章是否紧扣研究主题并直接回答问题\n"
            "- 检查文章是否结构清晰、语言流畅、易于理解。"
        ),
        "tools": [],
        "is_builtin": True,
    },
    {
        "name": "学习计划Agent",
        "description": "用于拆解学习目标、制定阶段计划、检查计划进展并给出下一步学习安排。",
        "system_prompt": (
            "你是学习计划子智能体。你的任务是围绕用户的学习目标生成清晰、可执行、可复盘的学习计划。"
            "你需要先识别学习主题、当前基础、可用时间和目标期限，再拆分阶段、任务清单、复盘节点和下一步建议。"
            "当用户已有学习计划时，优先续接现有计划，指出当前状态、未完成任务和建议推进顺序。"
        ),
        "tools": [],
        "is_builtin": True,
    },
    {
        "name": "学习助手",
        "description": "用于围绕个人学习、知识库检索、学习计划推进和学习反馈整理提供协助。",
        "system_prompt": (
            "你是学习助手子智能体。你的任务是帮助用户围绕个人知识库持续学习。"
            "你需要用清晰的步骤回答学习问题，必要时整理学习反馈、薄弱点、下一步行动和可复盘的结论。"
            "如果用户的问题更适合制定计划、验收结果或深入研究，请说明应交给对应子智能体处理。"
        ),
        "tools": [],
        "is_builtin": True,
    },
    {
        "name": "验收Agent",
        "description": "用于根据目标、清单和现有结果检查完成度，输出缺口、风险和后续修正建议。",
        "system_prompt": (
            "你是验收子智能体。你的任务是对照用户给出的目标、清单和当前结果进行完成度检查。"
            "你需要区分已完成、未验证、存在缺口和需要返工的部分，优先指出会影响实际可用性的风险。"
            "结论必须基于可复核证据；证据不足时标记为未验证，不要把推测当作完成。"
        ),
        "tools": [],
        "is_builtin": True,
    },
]

_SYNCED_SUBAGENT_FIELDS = ("description", "system_prompt", "tools", "model", "is_builtin")


async def init_builtin_subagents() -> None:
    """初始化内置 SubAgent，并以代码定义覆盖展示字段。"""
    async with pg_manager.get_async_session_context() as session:
        repo = SubAgentRepository(session)
        for data in _DEFAULT_SUBAGENTS:
            item = await repo.get_by_name(data["name"])
            if item is None:
                await repo.create(
                    name=data["name"],
                    description=data["description"],
                    system_prompt=data["system_prompt"],
                    tools=data.get("tools", []),
                    model=None,
                    is_builtin=data.get("is_builtin", False),
                    created_by="system",
                )
                continue

            changed = False
            for field in _SYNCED_SUBAGENT_FIELDS:
                next_value = data.get(field)
                current_value = getattr(item, field)
                if current_value != next_value:
                    setattr(item, field, deepcopy(next_value))
                    changed = True
            if changed:
                item.updated_by = "system"
        await session.commit()
    clear_specs_cache()


async def get_subagent_specs(db: AsyncSession | None = None) -> list[dict[str, Any]]:
    """获取所有 subagent specs，用于 SubAgentMiddleware（工具名称未解析）"""
    global _subagent_specs_cache
    if _subagent_specs_cache is not None:
        return deepcopy(_subagent_specs_cache)
    async with _subagent_specs_lock:
        if _subagent_specs_cache is not None:
            return deepcopy(_subagent_specs_cache)
        async with _get_session(db) as session:
            repo = SubAgentRepository(session)
            _subagent_specs_cache = await repo.list_all_specs()
    return deepcopy(_subagent_specs_cache)


def clear_specs_cache() -> None:
    """清除 subagent specs 缓存"""
    global _subagent_specs_cache
    _subagent_specs_cache = None


async def get_subagents_from_names(selected_names: Any, *, db: AsyncSession | None = None) -> list[dict[str, Any]]:
    """根据名称获取 subagent specs（含工具解析）。"""
    specs = await get_subagent_specs(db)

    if not selected_names:
        return []

    selected_set = set(selected_names)
    available = {spec["name"] for spec in specs if isinstance(spec.get("name"), str)}

    matched = [spec for spec in specs if spec.get("name") in selected_set]
    missing = [n for n in selected_names if n not in available]
    if missing:
        logger.warning(f"Configured subagents not found, skip: {missing}")

    # 处理工具
    # 仅从子智能体配置中的工具名称进行解析；不做 Tavily/MCP 特殊注入。
    from zixuetong.agents.toolkits import get_all_tool_instances

    all_tools = get_all_tool_instances()
    all_tool_names = {tool.name: tool for tool in all_tools}
    resolved_specs = []
    for spec in matched:
        resolved_spec = dict(spec)
        tool_names = spec.get("tools", [])
        resolved_spec["tools"] = [all_tool_names[name] for name in tool_names if name in all_tool_names]
        resolved_specs.append(resolved_spec)

    return resolved_specs


async def get_all_subagents(db: AsyncSession | None = None) -> list[dict[str, Any]]:
    """获取所有 SubAgent（含禁用的）"""
    async with _get_session(db) as session:
        repo = SubAgentRepository(session)
        items = await repo.list_all()
    return [item.to_dict() for item in items]


async def get_subagent(name: str, db: AsyncSession | None = None) -> dict[str, Any] | None:
    """获取单个 SubAgent"""
    async with _get_session(db) as session:
        repo = SubAgentRepository(session)
        item = await repo.get_by_name(name)
    return item.to_dict() if item else None


async def create_subagent(
    data: dict[str, Any],
    created_by: str | None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """创建 SubAgent"""
    async with _get_session(db) as session:
        repo = SubAgentRepository(session)
        item = await repo.create(
            name=data["name"],
            description=data["description"],
            system_prompt=data["system_prompt"],
            tools=data.get("tools"),
            model=data.get("model"),
            is_builtin=False,
            created_by=created_by,
        )
    clear_specs_cache()
    return item.to_dict()


async def update_subagent(
    name: str,
    data: dict[str, Any],
    updated_by: str | None,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """更新 SubAgent"""
    async with _get_session(db) as session:
        repo = SubAgentRepository(session)
        item = await repo.get_by_name(name)
        if not item:
            return None
        if item.is_builtin:
            raise ValueError("内置 SubAgent 不可编辑")
        item = await repo.update(
            item,
            description=data.get("description"),
            system_prompt=data.get("system_prompt"),
            tools=data.get("tools"),
            model=data.get("model"),
            model_provided="model" in data,
            updated_by=updated_by,
        )
    clear_specs_cache()
    return item.to_dict()


async def delete_subagent(name: str, db: AsyncSession | None = None) -> bool:
    """删除 SubAgent"""
    async with _get_session(db) as session:
        repo = SubAgentRepository(session)
        item = await repo.get_by_name(name)
        if not item:
            return False
        if item.is_builtin:
            raise ValueError("内置 SubAgent 不可删除")
        await repo.delete(item)
    clear_specs_cache()
    return True


async def set_subagent_enabled(
    name: str,
    enabled: bool,
    *,
    updated_by: str | None,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """更新 SubAgent 启用状态。"""
    async with _get_session(db) as session:
        repo = SubAgentRepository(session)
        item = await repo.get_by_name(name)
        if not item:
            return None
        item.enabled = enabled
        item.updated_by = updated_by
        await session.commit()
        await session.refresh(item)
    clear_specs_cache()
    return item.to_dict()
