from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_business import User

# 获取数据库会话（异步版本）
async def get_db():
    async with pg_manager.get_async_session_context() as db:
        yield db


# 获取单用户模式下的唯一系统 owner（异步版本）
async def get_system_owner(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).order_by(User.id).limit(1)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未找到单人模式系统用户")
    return user
