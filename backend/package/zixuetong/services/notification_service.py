"""通知服务 - 创建/查询/标记已读，并发布 Redis 事件用于实时推送"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from zixuetong.repositories.notification_repository import NotificationRepository
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.utils import logger


async def create_notification(
    *,
    user_id: str,
    type: str,
    title: str,
    body: str | None = None,
    severity: str = "info",
    source: str | None = None,
    extra_data: dict | None = None,
    db: AsyncSession | None = None,
) -> dict:
    """创建通知并发布 Redis 事件"""
    if db is not None:
        repo = NotificationRepository(db)
        item = await repo.create(
            user_id=user_id, type=type, title=title, body=body,
            severity=severity, source=source, extra_data=extra_data,
        )
    else:
        async with pg_manager.get_async_session_context() as session:
            repo = NotificationRepository(session)
            item = await repo.create(
                user_id=user_id, type=type, title=title, body=body,
                severity=severity, source=source, extra_data=extra_data,
            )

    # 发布 Redis 事件，供前端实时订阅
    await _publish_notification_event(user_id, item.to_dict())

    return item.to_dict()


async def list_notifications(
    user_id: str,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession | None = None,
) -> list[dict]:
    if db is not None:
        repo = NotificationRepository(db)
        items = await repo.list_by_user(user_id, unread_only=unread_only, limit=limit, offset=offset)
    else:
        async with pg_manager.get_async_session_context() as session:
            repo = NotificationRepository(session)
            items = await repo.list_by_user(user_id, unread_only=unread_only, limit=limit, offset=offset)
    return [item.to_dict() for item in items]


async def mark_notification_read(notification_id: int, user_id: str, db: AsyncSession | None = None) -> bool:
    if db is not None:
        repo = NotificationRepository(db)
        return await repo.mark_read(notification_id, user_id)
    async with pg_manager.get_async_session_context() as session:
        repo = NotificationRepository(session)
        return await repo.mark_read(notification_id, user_id)


async def mark_all_read(user_id: str, db: AsyncSession | None = None) -> int:
    if db is not None:
        repo = NotificationRepository(db)
        return await repo.mark_all_read(user_id)
    async with pg_manager.get_async_session_context() as session:
        repo = NotificationRepository(session)
        return await repo.mark_all_read(user_id)


async def count_unread(user_id: str, db: AsyncSession | None = None) -> int:
    if db is not None:
        repo = NotificationRepository(db)
        return await repo.count_unread(user_id)
    async with pg_manager.get_async_session_context() as session:
        repo = NotificationRepository(session)
        return await repo.count_unread(user_id)


async def delete_notification(notification_id: int, user_id: str, db: AsyncSession | None = None) -> bool:
    if db is not None:
        repo = NotificationRepository(db)
        return await repo.delete(notification_id, user_id)
    async with pg_manager.get_async_session_context() as session:
        repo = NotificationRepository(session)
        return await repo.delete(notification_id, user_id)


async def _publish_notification_event(user_id: str, notification_data: dict) -> None:
    """发布通知事件到 Redis 频道，供前端 SSE/轮询订阅"""
    try:
        import json

        from zixuetong.services.run_queue_service import get_redis_client

        redis = await get_redis_client()
        channel = f"notifications:{user_id}"
        await redis.publish(channel, json.dumps(notification_data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Failed to publish notification event: {e}")
