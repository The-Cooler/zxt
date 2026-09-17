"""根据每个学习计划安排的时间发送站内与微信提醒。"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from zixuetong.services.clawbot.bridge_service import clawbot_bridge
from zixuetong.services.learning_plan_service import build_learning_reminder, get_due_learning_plans
from zixuetong.services.notification_service import create_notification
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_business import LearningReminderDelivery, User
from zixuetong.utils import logger
from zixuetong.utils.datetime_utils import shanghai_now

CHECK_INTERVAL_SECONDS = 30


class LearningReminderScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="learning-reminder-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.check_due_reminders()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"学习提醒检查失败: {exc}")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    async def check_due_reminders(self) -> int:
        now = shanghai_now()
        reminder_date = now.date().isoformat()
        current_time = now.strftime("%H:%M")

        async with pg_manager.get_async_session_context() as db:
            user = await db.scalar(select(User).order_by(User.id).limit(1))
        if user is None:
            logger.warning("学习提醒无法找到单用户系统 owner")
            return 0

        sent_count = 0
        for plan in get_due_learning_plans(user, current_time):
            if await self._send_plan_reminder(user, plan, reminder_date, current_time):
                sent_count += 1
        return sent_count

    async def _send_plan_reminder(
        self,
        user: User,
        plan: dict[str, object],
        reminder_date: str,
        reminder_time: str,
    ) -> bool:
        plan_path = str(plan["file_path"])
        async with pg_manager.get_async_session_context() as db:
            delivery = LearningReminderDelivery(
                user_id=str(user.user_id),
                plan_path=plan_path,
                reminder_date=reminder_date,
                reminder_time=reminder_time,
            )
            db.add(delivery)
            try:
                await db.commit()
                await db.refresh(delivery)
            except IntegrityError:
                await db.rollback()
                return False

        title, body = build_learning_reminder(plan)
        try:
            notification = await create_notification(
                user_id=str(user.user_id),
                type="learning_reminder",
                title=title,
                body=body,
                source="learning_plan",
                extra_data={
                    "topic": plan["topic"],
                    "file_path": plan_path,
                    "reminder_time": reminder_time,
                    "progress_percent": plan["progress_percent"],
                    "next_task": plan["next_task"],
                },
            )
        except Exception:
            async with pg_manager.get_async_session_context() as db:
                persisted = await db.get(LearningReminderDelivery, delivery.id)
                if persisted is not None:
                    await db.delete(persisted)
                    await db.commit()
            raise

        wechat_status = "skipped"
        try:
            if await clawbot_bridge.send_learning_reminder(f"{title}\n{body}"):
                wechat_status = "sent"
        except Exception as exc:
            wechat_status = "failed"
            logger.warning(f"ClawBot 学习提醒发送失败: {exc}")

        async with pg_manager.get_async_session_context() as db:
            persisted = await db.get(LearningReminderDelivery, delivery.id)
            if persisted is not None:
                persisted.notification_id = notification["id"]
                persisted.wechat_status = wechat_status
                await db.commit()
        return True


learning_reminder_scheduler = LearningReminderScheduler()
