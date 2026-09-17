"""直接通过微信 iLink Bot 协议与 ClawBot 收发文本消息。"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
import uuid
from pathlib import Path
from urllib.parse import quote

import aiohttp
from sqlalchemy import select

from zixuetong import config as conf
from zixuetong.repositories.agent_config_repository import AgentConfigRepository
from zixuetong.services.chat_service import agent_chat
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_business import User
from zixuetong.utils import logger

ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.4.6"
APP_CLIENT_VERSION = str((2 << 16) | (4 << 8) | 6)
LONG_POLL_TIMEOUT_SECONDS = 40


class ClawBotBridge:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._poll_task: asyncio.Task | None = None
        self._state: dict[str, object] = {}
        self._qr_content = ""
        self._login_task: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        return bool(self._state.get("bot_token")) and self._poll_task is not None and not self._poll_task.done()

    @property
    def qr_content(self) -> str:
        return self._qr_content

    def _state_path(self) -> Path:
        return Path(conf.save_dir) / "clawbot" / "state.json"

    def _load_state(self) -> None:
        path = self._state_path()
        if not path.is_file():
            self._state = {}
            return
        try:
            self._state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"无法读取 ClawBot 状态: {exc}")
            self._state = {}

    def _save_state(self) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _base_info() -> dict[str, str]:
        return {"channel_version": CHANNEL_VERSION, "bot_agent": "zixuetong-clawbot/1.0"}

    @staticmethod
    def _headers(token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": base64.b64encode(str(secrets.randbelow(2**32)).encode()).decode(),
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": APP_CLIENT_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _post(self, path: str, body: dict, *, token: str | None = None, timeout: int = 20) -> dict:
        if self._session is None:
            raise RuntimeError("ClawBot HTTP 会话未启动")
        base_url = str(self._state.get("baseurl") or ILINK_BASE_URL).rstrip("/")
        async with self._session.post(
            f"{base_url}/{path.lstrip('/')}",
            json=body,
            headers=self._headers(token),
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            data = await response.json(content_type=None)
            if not 200 <= response.status < 300 or data.get("ret") not in (None, 0) or data.get("errcode") not in (None, 0):
                raise RuntimeError(data.get("errmsg") or f"ClawBot 请求失败: {response.status}")
            return data

    async def _get(self, path: str, *, timeout: int = 40) -> dict:
        if self._session is None:
            raise RuntimeError("ClawBot HTTP 会话未启动")
        async with self._session.get(
            f"{ILINK_BASE_URL}/{path.lstrip('/')}",
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            data = await response.json(content_type=None)
            if not 200 <= response.status < 300 or data.get("ret") not in (None, 0) or data.get("errcode") not in (None, 0):
                raise RuntimeError(data.get("errmsg") or f"ClawBot 请求失败: {response.status}")
            return data

    async def start(self) -> None:
        if not conf.clawbot_enabled:
            return
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        self._load_state()
        if self._state.get("bot_token"):
            self._start_polling()
        else:
            await self.request_login()

    async def stop(self) -> None:
        for task in (self._poll_task, self._login_task):
            if task and not task.done():
                task.cancel()
        self._poll_task = None
        self._login_task = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def request_login(self) -> dict[str, str]:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        response = await self._post("/ilink/bot/get_bot_qrcode?bot_type=3", {"local_token_list": []}, timeout=30)
        qrcode = str(response.get("qrcode") or "")
        if not qrcode:
            raise RuntimeError("ClawBot 未返回连接二维码")
        self._qr_content = str(response.get("qrcode_img_content") or qrcode)
        if self._login_task and not self._login_task.done():
            self._login_task.cancel()
        self._login_task = asyncio.create_task(self._wait_for_login(qrcode))
        return {"qrcode": qrcode, "qrcode_content": self._qr_content}

    async def _wait_for_login(self, qrcode: str) -> None:
        try:
            while conf.clawbot_enabled:
                response = await self._get(f"/ilink/bot/get_qrcode_status?qrcode={quote(qrcode, safe='')}")
                if response.get("status") == "confirmed" and response.get("bot_token"):
                    self._state = {
                        "bot_token": response["bot_token"],
                        "baseurl": response.get("baseurl") or ILINK_BASE_URL,
                        "get_updates_buf": "",
                        "threads": {},
                        "contexts": {},
                    }
                    self._save_state()
                    self._qr_content = ""
                    self._start_polling()
                    return
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"ClawBot 登录轮询失败: {exc}")

    def _start_polling(self) -> None:
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poll_messages())

    async def _poll_messages(self) -> None:
        while conf.clawbot_enabled and self._state.get("bot_token"):
            try:
                response = await self._post(
                    "/ilink/bot/getupdates",
                    {"get_updates_buf": self._state.get("get_updates_buf", ""), "base_info": self._base_info()},
                    token=str(self._state["bot_token"]),
                    timeout=LONG_POLL_TIMEOUT_SECONDS,
                )
                self._state["get_updates_buf"] = response.get("get_updates_buf") or self._state.get("get_updates_buf", "")
                self._save_state()
                for message in response.get("msgs") or []:
                    await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"ClawBot 消息轮询失败: {exc}")
                await asyncio.sleep(3)

    async def _handle_message(self, message: dict) -> None:
        if message.get("message_type") != 1:
            return
        sender = str(message.get("from_user_id") or "")
        context_token = str(message.get("context_token") or "")
        text = ""
        for item in message.get("item_list") or []:
            if item.get("type") == 1:
                text = str((item.get("text_item") or {}).get("text") or "").strip()
                break
        if not sender or not context_token or not text:
            return

        async with pg_manager.get_async_session_context() as db:
            user = await db.scalar(select(User).order_by(User.id).limit(1))
            if user is None:
                logger.warning("ClawBot 无法找到单人模式系统用户")
                return
            repo = AgentConfigRepository(db)
            config_item = await repo.get_or_create_default_for_agent(
                agent_id=conf.default_agent_id,
                created_by=str(user.id),
            )
            threads = self._state.setdefault("threads", {})
            contexts = self._state.setdefault("contexts", {})
            contexts[sender] = context_token
            self._save_state()
            thread_id = threads.get(sender)
            result = await agent_chat(
                query=text,
                agent_config_id=config_item.id,
                thread_id=thread_id,
                meta={"source": "clawbot", "request_id": str(uuid.uuid4())},
                image_content=None,
                current_user=user,
                db=db,
            )
            if result.get("thread_id"):
                threads[sender] = result["thread_id"]
                self._save_state()
            reply = str(result.get("response") or result.get("error_message") or "暂时无法处理这条消息。")
        await self.send_text(sender, context_token, reply)

    async def send_learning_reminder(self, text: str) -> bool:
        """向最近与 ClawBot 交互过的微信会话主动发送学习提醒。"""
        if not self.is_connected:
            return False
        contexts = self._state.get("contexts")
        if not isinstance(contexts, dict) or not contexts:
            return False
        recipient, context_token = next(reversed(contexts.items()))
        if not recipient or not context_token:
            return False
        await self.send_text(str(recipient), str(context_token), text)
        return True

    async def send_text(self, recipient: str, context_token: str, text: str) -> None:
        token = str(self._state.get("bot_token") or "")
        if not token:
            raise RuntimeError("ClawBot 未登录")
        await self._post(
            "/ilink/bot/sendmessage",
            {
                "msg": {
                    "to_user_id": recipient,
                    "client_id": str(uuid.uuid4()),
                    "message_type": 2,
                    "message_state": 2,
                    "context_token": context_token,
                    "item_list": [{"type": 1, "text_item": {"text": text}}],
                },
                "base_info": self._base_info(),
            },
            token=token,
        )

    def status(self) -> dict[str, object]:
        return {
            "enabled": conf.clawbot_enabled,
            "connected": self.is_connected,
            "awaiting_scan": bool(self._qr_content),
        }


clawbot_bridge = ClawBotBridge()
