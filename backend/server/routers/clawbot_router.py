"""ClawBot 微信 iLink 登录与连接状态接口。"""

from fastapi import APIRouter, Depends, HTTPException

from server.utils.auth_middleware import get_admin_user
from zixuetong import config
from zixuetong.services.clawbot.bridge_service import clawbot_bridge
from zixuetong.storage.postgres.models_business import User

clawbot = APIRouter(prefix="/clawbot", tags=["clawbot"])


@clawbot.get("/status")
async def get_status(_current_user: User = Depends(get_admin_user)):
    return {"success": True, "data": clawbot_bridge.status()}


@clawbot.post("/login")
async def request_login(_current_user: User = Depends(get_admin_user)):
    if not config.clawbot_enabled:
        raise HTTPException(status_code=409, detail="请先启用 ClawBot 微信互通")
    try:
        return {"success": True, "data": await clawbot_bridge.request_login()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取 ClawBot 登录二维码失败: {exc}") from exc
