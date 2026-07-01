"""OpenClaw 路由 - 连接状态、配置、手动触发提醒、知识共享 API"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_admin_user, get_current_user, get_db
from zixuetong.config.app import config
from zixuetong.services.openclaw.bridge_service import openclaw_bridge
from zixuetong.storage.postgres.models_business import User

openclaw = APIRouter(prefix="/openclaw", tags=["openclaw"])


class OpenClawConfigUpdate(BaseModel):
    gateway_url: str | None = Field(None, description="Gateway WebSocket URL")
    api_key: str | None = Field(None, description="认证 API Key")
    enabled: bool | None = Field(None, description="是否启用")


@openclaw.get("/status")
async def get_status_route(
    _current_user: User = Depends(get_admin_user),
):
    """获取 OpenClaw 连接状态"""
    return {
        "success": True,
        "data": {
            "enabled": config.openclaw_enabled,
            "connected": openclaw_bridge.is_connected,
            "gateway_url": config.openclaw_gateway_url or "",
        },
    }


@openclaw.post("/test-connection")
async def test_connection_route(
    _current_user: User = Depends(get_admin_user),
):
    """测试 OpenClaw Gateway 连接"""
    if not config.openclaw_gateway_url:
        return {"success": False, "data": {"error": "Gateway URL 未配置"}}

    try:
        from zixuetong.services.openclaw.gateway_client import OpenClawGatewayClient

        client = OpenClawGatewayClient(config.openclaw_gateway_url, config.openclaw_api_key)
        await client.connect()
        connected = client.connected
        await client.disconnect()
        return {"success": True, "data": {"connected": connected}}
    except Exception as e:
        return {"success": False, "data": {"error": str(e)}}


@openclaw.post("/trigger-reminder")
async def trigger_reminder_route(
    _current_user: User = Depends(get_admin_user),
):
    """手动触发学习提醒"""
    if not openclaw_bridge.is_connected:
        raise HTTPException(status_code=503, detail="OpenClaw 未连接")

    from zixuetong.services.openclaw.scheduler import reminder_scheduler

    try:
        await reminder_scheduler._check_and_remind()
        return {"success": True, "data": {"message": "学习提醒已触发"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发提醒失败: {e}")


@openclaw.get("/config")
async def get_config_route(
    _current_user: User = Depends(get_admin_user),
):
    """获取 OpenClaw 配置"""
    return {
        "success": True,
        "data": {
            "gateway_url": config.openclaw_gateway_url or "",
            "api_key": "***" if config.openclaw_api_key else "",
            "enabled": config.openclaw_enabled,
        },
    }


@openclaw.put("/config")
async def update_config_route(
    payload: OpenClawConfigUpdate,
    _current_user: User = Depends(get_admin_user),
):
    """更新 OpenClaw 配置"""
    if payload.gateway_url is not None:
        config.openclaw_gateway_url = payload.gateway_url
    if payload.api_key is not None:
        config.openclaw_api_key = payload.api_key
    if payload.enabled is not None:
        config.openclaw_enabled = payload.enabled

    return {
        "success": True,
        "data": {
            "gateway_url": config.openclaw_gateway_url or "",
            "api_key": "***" if config.openclaw_api_key else "",
            "enabled": config.openclaw_enabled,
        },
    }


# ========== 知识共享 API（供 OpenClaw 回调自学通使用）==========


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    db_id: str | None = Field(None, description="知识库 ID（可选，默认查询所有）")
    user_id: str | None = Field(None, description="用户 ID（API Key 认证时使用）")


class KnowledgeListRequest(BaseModel):
    user_id: str | None = Field(None, description="用户 ID（API Key 认证时使用）")


class KnowledgePushRequest(BaseModel):
    db_id: str = Field(..., description="目标知识库 ID")
    content: str = Field(..., description="要索引的知识内容")
    source: str = Field(default="openclaw", description="来源标识")


@openclaw.post("/knowledge/query")
async def knowledge_query_route(
    payload: KnowledgeQueryRequest,
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询自学通知识库（支持用户认证和 API Key 认证）"""
    import os

    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        raise HTTPException(status_code=403, detail="LITE 模式下不可用")

    from zixuetong.knowledge import knowledge_base

    user_id = payload.user_id
    if current_user:
        user_id = str(current_user.user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="需要认证")

    try:
        if payload.db_id:
            result = await knowledge_base.aquery(payload.query, db_id=payload.db_id)
        else:
            accessible = await knowledge_base.get_databases_by_user_id(user_id)
            db_list = accessible.get("databases", [])
            if not db_list:
                return {"success": True, "data": {"results": [], "message": "没有可访问的知识库"}}
            result = await knowledge_base.aquery(payload.query, db_id=str(db_list[0]["db_id"]))

        return {"success": True, "data": {"results": result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询知识库失败: {e}")


@openclaw.post("/knowledge/list")
async def knowledge_list_route(
    payload: KnowledgeListRequest,
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出可访问的知识库"""
    import os

    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        raise HTTPException(status_code=403, detail="LITE 模式下不可用")

    from zixuetong.knowledge import knowledge_base

    user_id = payload.user_id
    if current_user:
        user_id = str(current_user.user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="需要认证")

    try:
        result = await knowledge_base.get_databases_by_user_id(user_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取知识库列表失败: {e}")


@openclaw.post("/knowledge/push")
async def knowledge_push_route(
    payload: KnowledgePushRequest,
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """将 OpenClaw 知识索引到指定知识库"""
    import os

    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        raise HTTPException(status_code=403, detail="LITE 模式下不可用")

    from zixuetong.knowledge import knowledge_base

    try:
        result = await knowledge_base.update_content(
            db_id=payload.db_id,
            content=payload.content,
            source=payload.source,
        )
        return {"success": True, "data": {"message": "知识已索引"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引知识失败: {e}")
