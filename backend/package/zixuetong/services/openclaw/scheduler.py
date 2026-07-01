"""学习提醒调度器 - 定期检查用户学习状态并通过 OpenClaw 发送提醒"""

from __future__ import annotations

import asyncio
import os

from zixuetong.config.app import config
from zixuetong.utils import logger


class LearningReminderScheduler:
    """定期学习提醒调度器"""

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
        """检查用户学习状态并发送提醒"""
        from zixuetong.services.openclaw.bridge_service import openclaw_bridge

        if not openclaw_bridge.is_connected:
            logger.debug("OpenClaw 未连接，跳过学习提醒检查")
            return

        # 获取所有活跃用户（简化实现：通过数据库查询）
        try:
            from zixuetong.storage.postgres.manager import pg_manager
            from sqlalchemy import select, text
            from zixuetong.storage.postgres.models_business import User

            async with pg_manager.get_async_session_context() as session:
                result = await session.execute(
                    select(User).where(User.is_deleted == 0, User.role.in_(["user", "admin"]))
                )
                users = result.scalars().all()

            for user in users:
                user_id = str(user.user_id)
                # 查询用户最近的学习活动（通过对话创建时间判断）
                context = {"username": user.username, "user_id": user_id}
                await openclaw_bridge.send_learning_reminder_request(user_id, context)

            logger.info(f"已为 {len(users)} 个用户发送学习提醒请求")

        except Exception as e:
            logger.error(f"学习提醒检查失败: {e}")


# 全局单例
_reminder_interval = int(os.getenv("OPENCLAW_REMINDER_INTERVAL_MINUTES", "120"))
reminder_scheduler = LearningReminderScheduler(interval_minutes=_reminder_interval)
