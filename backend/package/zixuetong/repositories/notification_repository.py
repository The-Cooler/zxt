"""通知 Repository"""

from __future__ import annotations

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from zixuetong.storage.postgres.models_business import Notification
from zixuetong.utils.datetime_utils import utc_now_naive


class NotificationRepository:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(
        self,
        *,
        user_id: str,
        type: str,
        title: str,
        body: str | None = None,
        severity: str = "info",
        source: str | None = None,
        extra_data: dict | None = None,
    ) -> Notification:
        item = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            severity=severity,
            source=source,
            extra_data=extra_data,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def get_by_id(self, notification_id: int) -> Notification | None:
        result = await self.db.execute(select(Notification).where(Notification.id == notification_id))
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)  # noqa: E712
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, notification_id: int, user_id: str) -> bool:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=utc_now_naive())
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: str) -> int:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=utc_now_naive())
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def delete(self, notification_id: int, user_id: str) -> bool:
        item = await self.db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        obj = item.scalar_one_or_none()
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True

    async def count_unread(self, user_id: str) -> int:
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.is_read == False  # noqa: E712
            )
        )
        return result.scalar() or 0
