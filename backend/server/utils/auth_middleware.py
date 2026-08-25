import re

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_business import User

# 公开路径列表，无需登录即可访问
PUBLIC_PATHS = [
    r"^/api/auth/token$",  # 登录
    r"^/api/auth/check-first-run$",  # 检查是否首次运行
    r"^/api/auth/initialize$",  # 初始化系统
    r"^/api$",  # Health Check
    r"^/api/system/health$",  # Health Check
    r"^/api/system/info$",  # 获取系统信息配置
    r"^/api/system/logo$",  # 获取系统 Logo
]


# 获取数据库会话（异步版本）
async def get_db():
    async with pg_manager.get_async_session_context() as db:
        yield db


# 获取单人模式下的唯一系统用户（异步版本）
async def get_current_user(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.role == "superadmin", User.is_deleted == 0).limit(1))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未找到单人模式系统用户")
    return user


async def get_required_user(current_user: User = Depends(get_current_user)):
    return current_user


async def get_admin_user(current_user: User = Depends(get_current_user)):
    return current_user


async def get_superadmin_user(current_user: User = Depends(get_current_user)):
    return current_user


# 检查路径是否为公开路径
def is_public_path(path: str) -> bool:
    path = path.rstrip("/")  # 去除尾部斜杠以便于匹配
    for pattern in PUBLIC_PATHS:
        if re.match(pattern, path):
            return True
    return False
