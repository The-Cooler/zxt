"""历史警告学习器 - 分析过去的错误/警告并共享给 OpenClaw"""

from __future__ import annotations

import os

from zixuetong.config.app import config
from zixuetong.utils import logger


async def analyze_and_share_warnings() -> dict:
    """分析历史警告并共享给 OpenClaw

    查询过去的 agent run 失败记录、task 失败记录，总结模式，
    通过 OpenClaw bridge 与 OpenClaw 共享，使其能学习并预防类似问题。

    Returns:
        分析结果摘要
    """
    from zixuetong.services.openclaw.bridge_service import openclaw_bridge

    if not openclaw_bridge.is_connected:
        return {"status": "skipped", "reason": "OpenClaw 未连接"}

    warnings: list[dict] = []

    try:
        from zixuetong.storage.postgres.manager import pg_manager
        from sqlalchemy import select, text
        from zixuetong.storage.postgres.models_business import AgentRun, TaskRecord

        async with pg_manager.get_async_session_context() as session:
            # 查询最近的失败 Agent Run
            result = await session.execute(
                select(AgentRun)
                .where(AgentRun.status == "failed")
                .order_by(AgentRun.created_at.desc())
                .limit(50)
            )
            failed_runs = result.scalars().all()

            for run in failed_runs:
                warnings.append({
                    "type": "agent_run_failed",
                    "agent_id": run.agent_id,
                    "error_type": run.error_type,
                    "error_message": (run.error_message or "")[:200],
                    "created_at": str(run.created_at) if run.created_at else None,
                })

            # 查询最近的失败 Task
            result = await session.execute(
                select(TaskRecord)
                .where(TaskRecord.status == "failed")
                .order_by(TaskRecord.created_at.desc())
                .limit(50)
            )
            failed_tasks = result.scalars().all()

            for task in failed_tasks:
                warnings.append({
                    "type": "task_failed",
                    "task_name": task.name,
                    "task_type": task.type,
                    "error": (task.error or "")[:200],
                    "created_at": str(task.created_at) if task.created_at else None,
                })

    except Exception as e:
        logger.error(f"查询历史警告失败: {e}")
        return {"status": "error", "reason": str(e)}

    if not warnings:
        return {"status": "no_warnings", "count": 0}

    # 共享给 OpenClaw
    try:
        result = await openclaw_bridge.push_knowledge_to_openclaw([
            {
                "type": "warning_patterns",
                "count": len(warnings),
                "warnings": warnings[:20],  # 限制数量
                "summary": f"自学通系统最近产生了 {len(warnings)} 个警告/错误，请分析模式并提供建议",
            }
        ])
        logger.info(f"已共享 {len(warnings)} 条历史警告给 OpenClaw")
        return {"status": "shared", "count": len(warnings), "result": result}
    except Exception as e:
        logger.error(f"共享历史警告到 OpenClaw 失败: {e}")
        return {"status": "error", "reason": str(e)}
