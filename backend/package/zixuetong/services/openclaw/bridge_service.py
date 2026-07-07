"""OpenClaw 桥接服务 - 连接 OpenClaw Gateway 与自学通系统

职责：
- 管理 Gateway 客户端生命周期
- 将 OpenClaw 事件转换为自学通通知
- 提供知识查询/推送的 RPC 调用封装
- 处理学习提醒请求（使用 Pydantic 模型封装消息）
- 通过 OpenClaw ClawBot 插件发送微信推送
"""

from __future__ import annotations

import asyncio
from typing import Any

from zixuetong.config.app import config
from zixuetong.services.openclaw.gateway_client import OpenClawGatewayClient
from zixuetong.services.openclaw.models import (
    LearningReminderRequest,
    LearningReminderResponse,
    WechatNotificationRequest,
    WechatNotificationResponse,
)
from zixuetong.utils import logger


class OpenClawBridge:
    """OpenClaw 与自学通的桥接服务（单例）"""

    def __init__(self) -> None:
        self._client: OpenClawGatewayClient | None = None
        self._scheduler_task: Any | None = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.connected

    async def start(self) -> None:
        """启动桥接服务"""
        if not config.openclaw_enabled:
            logger.info("OpenClaw 集成未启用，跳过启动")
            return

        gateway_url = config.openclaw_gateway_url
        if not gateway_url:
            logger.warning("OpenClaw Gateway URL 未配置，跳过启动")
            return

        self._client = OpenClawGatewayClient(gateway_url, config.openclaw_api_key)
        self._client.on_event(self._handle_event)

        try:
            await self._client.connect()
            logger.info("OpenClaw Bridge 已启动")
        except Exception as e:
            logger.error(f"OpenClaw Bridge 启动失败: {e}")
            self._client = None

    async def stop(self) -> None:
        """停止桥接服务"""
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.disconnect()
            self._client = None
        logger.info("OpenClaw Bridge 已停止")

    async def send_learning_reminder_request(
        self, request: LearningReminderRequest
    ) -> LearningReminderResponse | None:
        """向 OpenClaw 发送学习提醒请求，由智能体决策是否提醒

        Args:
            request: 包含用户学习计划和活跃度数据的请求对象

        Returns:
            LearningReminderResponse 或 None（连接失败时）
        """
        if not self._client or not self._client.connected:
            logger.warning("OpenClaw 未连接，无法发送学习提醒请求")
            return None

        try:
            result = await self._client.rpc_call("agent", {
                "prompt": (
                    f"请根据以下用户学习数据，判断是否需要发送学习提醒，"
                    f"并按照 expected_response_format 中指定的格式返回结果。"
                ),
                "context": request.model_dump(),
            })

            if not isinstance(result, dict):
                logger.warning(f"OpenClaw 学习提醒返回非 dict: {type(result)}")
                return None

            return LearningReminderResponse.model_validate(result)

        except Exception as e:
            logger.error(f"发送学习提醒请求失败: {e}")
            return None

    async def send_wechat_notification(
        self, *, user_id: str, title: str, body: str, severity: str = "info"
    ) -> WechatNotificationResponse | None:
        """通过 OpenClaw ClawBot 插件发送微信通知

        Args:
            user_id: 目标用户ID
            title: 通知标题
            body: 通知内容
            severity: 严重程度

        Returns:
            WechatNotificationResponse 或 None（连接失败时）
        """
        if not self._client or not self._client.connected:
            logger.warning("OpenClaw 未连接，无法发送微信通知")
            await self._report_wechat_failure(user_id, title, "OpenClaw 未连接")
            return None

        request = WechatNotificationRequest(
            user_id=user_id,
            title=title,
            body=body,
            severity=severity,
        )

        try:
            result = await self._client.rpc_call("sessions.message", {
                "content": request.model_dump_json(),
                "channel": "wechat",
            })

            if not isinstance(result, dict):
                logger.warning(f"OpenClaw 微信推送返回非 dict: {type(result)}")
                await self._report_wechat_failure(user_id, title, f"返回格式异常: {type(result)}")
                return None

            response = WechatNotificationResponse.model_validate(result)

            if not response.success:
                await self._report_wechat_failure(user_id, title, response.error or "未知错误")

            return response

        except Exception as e:
            logger.error(f"微信推送 RPC 调用失败: {e}")
            await self._report_wechat_failure(user_id, title, str(e))
            return None

    async def _report_wechat_failure(self, user_id: str, title: str, error: str) -> None:
        """微信推送失败时创建站内通知告知管理员"""
        try:
            from zixuetong.services.notification_service import create_notification

            await create_notification(
                user_id=user_id,
                type="wechat_push_failed",
                title="微信提醒发送失败",
                body=f"无法通过 OpenClaw ClawBot 推送微信通知。原始通知: 「{title}」，失败原因: {error}",
                severity="warning",
                source="openclaw",
                extra_data={"original_title": title, "error": error},
            )
        except Exception as e:
            logger.error(f"创建微信推送失败通知异常: {e}")

    async def query_openclaw_knowledge(self, query: str) -> str | None:
        """查询 OpenClaw 知识（调用 sessions.message RPC）"""
        if not self._client or not self._client.connected:
            logger.warning("OpenClaw 未连接，无法查询知识")
            return None

        try:
            result = await self._client.rpc_call("sessions.message", {
                "content": query,
            })
            return result
        except Exception as e:
            logger.error(f"查询 OpenClaw 知识失败: {e}")
            return None

    async def push_knowledge_to_openclaw(self, knowledge_items: list[dict]) -> dict | None:
        """推送知识到 OpenClaw（调用 sessions.message RPC）"""
        if not self._client or not self._client.connected:
            logger.warning("OpenClaw 未连接，无法推送知识")
            return None

        try:
            result = await self._client.rpc_call("sessions.message", {
                "content": f"请学习以下知识: {knowledge_items}",
                "role": "system",
            })
            return result
        except Exception as e:
            logger.error(f"推送知识到 OpenClaw 失败: {e}")
            return None

    async def _handle_event(self, event: dict) -> None:
        """处理从 OpenClaw Gateway 接收的事件"""
        event_type = event.get("_event_type", "unknown")
        logger.info(f"收到 OpenClaw 事件: {event_type}")

        try:
            if event_type in ("notification", "learning_reminder", "agent.completed"):
                await self._handle_notification_event(event)
            elif event_type in ("warning", "alert"):
                await self._handle_warning_event(event)
            else:
                logger.debug(f"未处理的 OpenClaw 事件类型: {event_type}")
        except Exception as e:
            logger.error(f"处理 OpenClaw 事件异常: {e}")

    async def _handle_notification_event(self, event: dict) -> None:
        """将 OpenClaw 通知事件转换为自学通通知，并尝试微信推送"""
        from zixuetong.services.notification_service import create_notification

        # 提取目标用户
        user_id = event.get("user_id") or event.get("userId")
        if not user_id:
            logger.warning("OpenClaw 通知事件缺少 user_id，跳过")
            return

        title = event.get("title", "OpenClaw 学习提醒")
        body = event.get("body") or event.get("message") or event.get("content", "")
        severity = event.get("severity", "info")

        # 创建站内通知
        await create_notification(
            user_id=str(user_id),
            type="learning_reminder",
            title=title,
            body=body,
            severity=severity,
            source="openclaw",
            extra_data=event.get("extra_data") or {
                "event_type": event.get("_event_type"),
                "agent_id": event.get("agent_id"),
            },
        )

        # 尝试通过 ClawBot 推送到微信
        wechat_result = await self.send_wechat_notification(
            user_id=str(user_id),
            title=title,
            body=body,
            severity=severity,
        )
        if wechat_result is not None:
            logger.info(f"微信推送结果: success={wechat_result.success}, error={wechat_result.error}")

    async def _handle_warning_event(self, event: dict) -> None:
        """处理 OpenClaw 警告事件"""
        from zixuetong.services.notification_service import create_notification

        user_id = event.get("user_id") or event.get("userId")
        if not user_id:
            logger.warning("OpenClaw 警告事件缺少 user_id，跳过")
            return

        title = event.get("title", "OpenClaw 警告")
        body = event.get("body") or event.get("message", "")

        await create_notification(
            user_id=str(user_id),
            type="warning",
            title=title,
            body=body,
            severity=event.get("severity", "warning"),
            source="openclaw",
            extra_data=event.get("extra_data") or {
                "event_type": event.get("_event_type"),
                "warning_type": event.get("warning_type"),
            },
        )

        # 警告事件也尝试微信推送
        wechat_result = await self.send_wechat_notification(
            user_id=str(user_id),
            title=title,
            body=body,
            severity=event.get("severity", "warning"),
        )
        if wechat_result is not None:
            logger.info(f"警告微信推送结果: success={wechat_result.success}")


# 全局单例
openclaw_bridge = OpenClawBridge()
