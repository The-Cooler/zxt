"""OpenClaw Gateway WebSocket + RPC 客户端

通过 WebSocket 连接 OpenClaw Gateway，发送 RPC 请求并接收响应/事件。
参考 OpenClaw Gateway 协议文档实现。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from zixuetong.utils import logger

# 连接重试参数
_INITIAL_BACKOFF = 1.0  # 秒
_MAX_BACKOFF = 60.0
_BACKOFF_MULTIPLIER = 2.0


class OpenClawGatewayClient:
    """OpenClaw Gateway WebSocket 客户端"""

    def __init__(self, gateway_url: str, api_key: str = ""):
        self._gateway_url = gateway_url
        self._api_key = api_key
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._connected = False
        self._receive_task: asyncio.Task | None = None
        self._request_id_counter = 0
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._event_handlers: list[Any] = []  # callable(event_dict)
        self._stop_event = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._connected

    def on_event(self, handler: Any) -> None:
        """注册事件处理器（callable 接收 event dict）"""
        self._event_handlers.append(handler)

    async def connect(self) -> None:
        """建立 WebSocket 连接并启动接收循环"""
        try:
            import websockets
        except ImportError as e:
            raise ImportError("websockets 库未安装，请运行: pip install websockets") from e

        self._stop_event.clear()
        backoff = _INITIAL_BACKOFF

        while not self._stop_event.is_set():
            try:
                headers = {}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"

                self._ws = await websockets.connect(
                    self._gateway_url,
                    additional_headers=headers,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                )
                self._connected = True
                backoff = _INITIAL_BACKOFF
                logger.info(f"OpenClaw Gateway 已连接: {self._gateway_url}")

                # 启动接收循环
                self._receive_task = asyncio.create_task(self._receive_loop())
                return

            except Exception as e:
                self._connected = False
                if self._stop_event.is_set():
                    return
                logger.warning(f"OpenClaw Gateway 连接失败 ({backoff:.0f}s 后重试): {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * _BACKOFF_MULTIPLIER, _MAX_BACKOFF)

    async def disconnect(self) -> None:
        """断开连接"""
        self._stop_event.set()
        self._connected = False

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        # 取消所有挂起的请求
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        logger.info("OpenClaw Gateway 已断开")

    async def rpc_call(self, method: str, params: dict | None = None, timeout: float = 30.0) -> Any:
        """发送 RPC 请求并等待响应"""
        if not self._connected or not self._ws:
            raise ConnectionError("OpenClaw Gateway 未连接")

        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        try:
            await self._ws.send(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise ConnectionError(f"发送 RPC 请求失败: {e}") from e

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"RPC 请求超时: {method}")

    async def _receive_loop(self) -> None:
        """后台接收消息循环"""
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"OpenClaw Gateway 收到无效 JSON: {raw[:200]}")
                    continue

                # RPC 响应
                if "id" in data:
                    request_id = data["id"]
                    future = self._pending_requests.pop(request_id, None)
                    if future and not future.done():
                        if "error" in data:
                            future.set_exception(RuntimeError(data["error"].get("message", str(data["error"]))))
                        else:
                            future.set_result(data.get("result"))
                    continue

                # Gateway 事件
                if "method" in data or "event" in data:
                    event = data.get("params", data)
                    event_type = data.get("method", data.get("event", "unknown"))
                    event["_event_type"] = event_type
                    for handler in self._event_handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                        except Exception as e:
                            logger.error(f"OpenClaw 事件处理器异常: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"OpenClaw Gateway 接收循环异常: {e}")
                self._connected = False
                # 自动重连
                asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """断线重连"""
        if self._stop_event.is_set():
            return
        logger.info("OpenClaw Gateway 尝试重新连接...")
        try:
            await self.disconnect()
        except Exception:
            pass
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"OpenClaw Gateway 重连失败: {e}")
