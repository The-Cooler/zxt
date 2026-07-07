"""OpenClaw 消息模型 - 与 Gateway 交互的请求/响应结构

所有与 OpenClaw 的消息交互均使用 Pydantic BaseModel 封装，
确保字段类型明确、可序列化、可校验。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# =============================================================================
# === 学习提醒相关 ===
# =============================================================================


class LearningPlanInfo(BaseModel):
    """单个学习计划信息"""

    topic: str = Field(description="学习主题")
    status: str = Field(description="计划状态：进行中/暂停/待开始")
    updated_at: str | None = Field(default=None, description="最近更新时间")
    file_path: str | None = Field(default=None, description="计划文件路径")


class LearningReminderRequest(BaseModel):
    """向 OpenClaw 发送的学习提醒请求

    包含用户学习计划和活跃度信息，由 OpenClaw 智能体根据学习内容难度、
    进度和用户偏好决定是否需要提醒以及提醒内容。
    """

    user_id: str = Field(description="用户ID")
    username: str = Field(description="用户名")
    plans: list[LearningPlanInfo] = Field(default_factory=list, description="用户当前活跃学习计划")
    last_login: str | None = Field(default=None, description="用户最后登录时间")
    last_conversation_at: str | None = Field(default=None, description="用户最后对话时间")
    expected_response_format: dict = Field(
        default={
            "should_remind": "bool - 是否应该发送提醒",
            "reason": "str - 判断理由（如：用户已超过3天未学习数学）",
            "reminder_message": "str - 推荐的提醒消息内容",
            "wechat_notify": "bool - 是否需要微信推送",
            "next_check_hours": "float - 建议下次检查间隔（小时）",
        },
        description="期望 OpenClaw 返回的响应格式",
    )


class LearningReminderResponse(BaseModel):
    """OpenClaw 返回的学习提醒决策"""

    should_remind: bool = Field(description="是否应该发送提醒")
    reason: str = Field(default="", description="判断理由")
    reminder_message: str = Field(default="", description="推荐的提醒消息内容")
    wechat_notify: bool = Field(default=False, description="是否需要微信推送")
    next_check_hours: float | None = Field(default=None, description="建议下次检查间隔（小时）")


# =============================================================================
# === 微信推送相关 ===
# =============================================================================


class WechatNotificationRequest(BaseModel):
    """通过 ClawBot 插件发送微信通知的请求"""

    user_id: str = Field(description="目标用户ID")
    title: str = Field(description="通知标题")
    body: str = Field(description="通知内容")
    severity: str = Field(default="info", description="严重程度：info/warning/error")
    channel: str = Field(default="wechat", description="推送渠道，固定为 wechat")
    expected_response_format: dict = Field(
        default={
            "success": "bool - 是否发送成功",
            "error": "str | null - 失败原因（成功时为 null）",
            "message_id": "str | null - 消息ID（成功时返回）",
        },
        description="期望 OpenClaw 返回的响应格式",
    )


class WechatNotificationResponse(BaseModel):
    """OpenClaw 返回的微信推送结果"""

    success: bool = Field(description="是否发送成功")
    error: str | None = Field(default=None, description="失败原因")
    message_id: str | None = Field(default=None, description="消息ID")
