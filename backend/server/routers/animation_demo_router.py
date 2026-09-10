from fastapi import APIRouter, Depends

from server.utils.auth_middleware import get_system_owner
from zixuetong.animation import AnimationDemoRequest, AnimationDemoResponse, create_animation_demo
from zixuetong.storage.postgres.models_business import User

animation_demos = APIRouter(prefix="/animation-demos", tags=["animation-demos"])


@animation_demos.post("", response_model=AnimationDemoResponse)
async def create_animation_demo_view(
    payload: AnimationDemoRequest,
    current_user: User = Depends(get_system_owner),
):
    """Create a structured animation demo artifact for chat rendering."""
    demo = create_animation_demo(payload)
    return AnimationDemoResponse(success=True, demo=demo)
