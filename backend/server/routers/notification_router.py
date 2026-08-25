"""通知路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_current_user, get_db
from zixuetong.services import notification_service
from zixuetong.storage.postgres.models_business import User

notifications = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications.get("")
async def list_notifications_route(
    unread_only: bool = Query(False, description="仅返回未读通知"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的通知列表"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = str(current_user.user_id)
    items = await notification_service.list_notifications(
        user_id, unread_only=unread_only, limit=limit, offset=offset, db=db
    )
    return {"success": True, "data": items}


@notifications.get("/unread-count")
async def unread_count_route(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户未读通知数"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = str(current_user.user_id)
    count = await notification_service.count_unread(user_id, db=db)
    return {"success": True, "data": {"count": count}}


@notifications.post("/{notification_id}/read")
async def mark_read_route(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记通知为已读"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = str(current_user.user_id)
    ok = await notification_service.mark_notification_read(notification_id, user_id, db=db)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在或已读")
    return {"success": True}


@notifications.post("/read-all")
async def mark_all_read_route(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记当前用户所有通知为已读"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = str(current_user.user_id)
    count = await notification_service.mark_all_read(user_id, db=db)
    return {"success": True, "data": {"count": count}}


@notifications.delete("/{notification_id}")
async def delete_notification_route(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除通知"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = str(current_user.user_id)
    ok = await notification_service.delete_notification(notification_id, user_id, db=db)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"success": True}
