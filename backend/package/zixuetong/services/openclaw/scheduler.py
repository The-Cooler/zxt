"""学习提醒调度器 - 定期检查用户学习状态并通过 OpenClaw 智能体决策是否提醒"""

from __future__ import annotations

import asyncio
import os

from zixuetong.config.app import config
from zixuetong.utils import logger


class LearningReminderScheduler:
    """定期学习提醒调度器

    调度器不自行判断"是否该提醒"，而是收集用户的学习计划数据和活跃度信息，
    交给 OpenClaw 智能体决策。OpenClaw 根据学习内容难度、进度和用户偏好
    动态决定是否提醒、提醒内容和提醒间隔。
    """

    def __init__(self, interval_minutes: int = 120) -> None:
        self._interval = interval_minutes * 60
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if not config.openclaw_enabled:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info(f"学习提醒调度器已启动，间隔 {self._interval // 60} 分钟")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("学习提醒调度器已停止")

    async def _run(self) -> None:
        """主循环"""
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
                return  # stop_event 被设置，退出
            except asyncio.TimeoutError:
                pass  # 超时，执行检查

            try:
                await self._check_and_remind()
            except Exception as e:
                logger.error(f"学习提醒检查异常: {e}")

    async def _check_and_remind(self) -> None:
        """收集用户学习数据，请求 OpenClaw 智能体决策是否提醒"""
        from zixuetong.services.openclaw.bridge_service import openclaw_bridge

        if not openclaw_bridge.is_connected:
            logger.debug("OpenClaw 未连接，跳过学习提醒检查")
            return

        try:
            users_with_data = await self._collect_user_learning_data()
        except Exception as e:
            logger.error(f"收集用户学习数据失败: {e}")
            return

        if not users_with_data:
            logger.debug("没有需要检查的用户，跳过")
            return

        reminded = 0
        skipped = 0
        for user_id, reminder_request in users_with_data:
            try:
                response = await openclaw_bridge.send_learning_reminder_request(reminder_request)
                if response is None:
                    skipped += 1
                    continue

                if response.should_remind:
                    from zixuetong.services.notification_service import create_notification

                    await create_notification(
                        user_id=user_id,
                        type="learning_reminder",
                        title="学习提醒",
                        body=response.reminder_message or "该继续学习了！",
                        severity="info",
                        source="openclaw",
                        extra_data={
                            "reason": response.reason,
                            "wechat_notify": response.wechat_notify,
                        },
                    )

                    if response.wechat_notify:
                        await openclaw_bridge.send_wechat_notification(
                            user_id=user_id,
                            title="学习提醒",
                            body=response.reminder_message or "该继续学习了！",
                            severity="info",
                        )

                    reminded += 1
                else:
                    skipped += 1

                # 动态调整下次检查间隔
                if response.next_check_hours and response.next_check_hours > 0:
                    new_interval = int(response.next_check_hours * 3600)
                    # 限制在 30 分钟 ~ 24 小时之间
                    new_interval = max(1800, min(86400, new_interval))
                    if new_interval != self._interval:
                        logger.info(f"学习提醒调度器调整间隔: {self._interval // 60}min -> {new_interval // 60}min")
                        self._interval = new_interval

            except Exception as e:
                logger.error(f"处理用户 {user_id} 学习提醒失败: {e}")
                skipped += 1

        logger.info(f"学习提醒检查完成: 已提醒 {reminded} 人, 跳过 {skipped} 人")

    async def _collect_user_learning_data(self) -> list[tuple[str, "LearningReminderRequest"]]:
        """收集所有活跃用户的学习计划和活跃度数据

        Returns:
            [(user_id, LearningReminderRequest), ...] 列表
        """
        from sqlalchemy import select, func

        from zixuetong.services.openclaw.models import LearningPlanInfo, LearningReminderRequest
        from zixuetong.storage.postgres.manager import pg_manager
        from zixuetong.storage.postgres.models_business import Conversation, User
        from zixuetong.utils.datetime_utils import format_utc_datetime

        result_data: list[tuple[str, LearningReminderRequest]] = []

        async with pg_manager.get_async_session_context() as session:
            # 子查询：每个用户的最后对话时间
            last_conv_subq = (
                select(func.max(Conversation.updated_at))
                .where(Conversation.user_id == User.user_id, Conversation.status == "active")
                .correlate(User)
                .scalar_subquery()
            )
            result = await session.execute(
                select(User, last_conv_subq.label("last_conv_at"))
                .where(User.is_deleted == 0, User.role.in_(["user", "admin"]))
            )
            rows = result.all()

        for user, last_conv_at in rows:
            # 读取用户学习计划
            plans = await self._get_user_learning_plans(user)

            reminder_request = LearningReminderRequest(
                user_id=str(user.user_id),
                username=user.username,
                plans=plans,
                last_login=format_utc_datetime(user.last_login) if user.last_login else None,
                last_conversation_at=format_utc_datetime(last_conv_at) if last_conv_at else None,
            )
            result_data.append((str(user.user_id), reminder_request))

        return result_data

    async def _get_user_learning_plans(self, user) -> list[LearningPlanInfo]:
        """读取用户的学习计划 index.md，提取活跃计划信息"""
        from zixuetong.services.openclaw.models import LearningPlanInfo
        from zixuetong.services.learning_plan_service import get_learning_overview

        try:
            overview = get_learning_overview(user)
            raw_plans = overview.get("plans", [])
            # 过滤掉已完成/归档的计划，只保留活跃计划
            active_statuses = {"进行中", "待开始", "暂停", "in_progress", "pending", "paused"}
            return [
                LearningPlanInfo(
                    topic=p.get("topic", ""),
                    status=p.get("status", ""),
                    updated_at=p.get("updated_at"),
                    file_path=p.get("file_path"),
                )
                for p in raw_plans
                if p.get("status", "") in active_statuses
            ]
        except Exception as e:
            logger.debug(f"读取用户 {user.user_id} 学习计划失败: {e}")
            return []


# 全局单例
_reminder_interval = int(os.getenv("OPENCLAW_REMINDER_INTERVAL_MINUTES", "120"))
reminder_scheduler = LearningReminderScheduler(interval_minutes=_reminder_interval)
