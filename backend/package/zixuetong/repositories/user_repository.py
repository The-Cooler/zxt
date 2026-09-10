"""系统 owner 数据访问层。"""

from sqlalchemy import select

from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_business import User


class UserRepository:
    """单用户系统 owner 数据访问层。"""

    async def get_by_id(self, id: int) -> User | None:
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.id == id))
            return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> User | None:
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).where(User.user_id == user_id))
            return result.scalar_one_or_none()

    async def get_system_owner(self) -> User | None:
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User).order_by(User.id).limit(1))
            return result.scalar_one_or_none()

    async def get_all_user_ids(self) -> list[str]:
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(User.user_id))
            return [uid for (uid,) in result.all()]
