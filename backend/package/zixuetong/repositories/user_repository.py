"""用户数据访问层 - Repository"""

from datetime import UTC
from datetime import datetime as dt
from typing import Any

from sqlalchemy import func, select

from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_business import User

# 使用 naive datetime 以兼容 PostgreSQL TIMESTAMP WITHOUT TIME ZONE 列
_utc_now = dt.now(UTC).replace(tzinfo=None)


class UserRepository:
    """用户数据访问层"""

    async def get_by_id(self, id: int) -> User | None:
        """根据 ID 获取用户"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.id == id))
            return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> User | None:
        """根据 user_id 获取用户"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        """根据手机号获取用户"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.phone_number == phone))
            return result.scalar_one_or_none()

    async def create(self, data: dict[str, Any]) -> User:
        """创建用户"""
        async with pg_manager.get_async_session_context() as session:
            user = User(**data)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    async def update(self, id: int, data: dict[str, Any]) -> User | None:
        """更新用户"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.id == id, User.is_deleted == 0))
            user = result.scalar_one_or_none()
            if user is None:
                return None
            for key, value in data.items():
                if key != "id":
                    setattr(user, key, value)
        return user

    async def soft_delete(self, id: int, username: str | None = None, phone_number: str | None = None) -> bool:
        """软删除用户"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.id == id, User.is_deleted == 0))
            user = result.scalar_one_or_none()
            if user is None:
                return False
            user.is_deleted = 1

            user.deleted_at = _utc_now()
            if username:
                import hashlib

                hash_suffix = hashlib.sha256(user.user_id.encode()).hexdigest()[:4]
                user.username = f"已注销用户-{hash_suffix}"
            if phone_number:
                user.phone_number = None
        return True

    async def exists_by_user_id(self, user_id: str) -> bool:
        """检查 user_id 是否存在"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.id).where(User.user_id == user_id))
            return result.scalar_one_or_none() is not None

    async def exists_by_phone(self, phone: str) -> bool:
        """检查手机号是否存在"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.id).where(User.phone_number == phone))
            return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        """统计用户数量"""
        async with pg_manager.get_async_session_context() as session:
            query = select(func.count(User.id)).where(User.is_deleted == 0)
            result = await session.execute(query)
            return result.scalar() or 0

    async def get_all_user_ids(self) -> list[str]:
        """获取所有用户 ID"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.user_id))
            return [uid for (uid,) in result.all()]
