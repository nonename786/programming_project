import asyncio
import json
from typing import Awaitable, Callable, Optional

import websockets

from utils.logger import get_logger

logger = get_logger("QQ-Client")


class OneBotClient:
    """基于 OneBot WebSocket 的 QQ 客户端（长连接版）"""

    def __init__(self, config: dict):
        self.ws_url = config.get("ws_url", "ws://127.0.0.1:3002")
        self.qq_number = str(config.get("qq_number", "")).strip()
        self.access_token = config.get("access_token", "")
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_running = False
        self._message_handler: Optional[Callable[[dict], Awaitable[None]]] = None
        self._pending_echo_futures: dict[str, asyncio.Future] = {}
        self._listen_task: Optional[asyncio.Task] = None

    def set_message_handler(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        self._message_handler = handler

    async def connect(self) -> None:
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        logger.info(f"正在连接 OneBot WebSocket: {self.ws_url}")
        self.ws = await websockets.connect(
            self.ws_url,
            additional_headers=headers if headers else None,
            ping_interval=20,
            open_timeout=10,
            close_timeout=5,
        )
        self.is_running = True
        logger.info("✅ OneBot 长连接建立成功")

    async def start_listener(self) -> None:
        if not self.ws:
            raise RuntimeError("WebSocket 未连接，无法启动监听")

        if self._listen_task and not self._listen_task.done():
            return

        self._listen_task = asyncio.create_task(self.listen_forever())
        logger.info("✅ QQ 事件监听任务已启动")

    async def close(self) -> None:
        self.is_running = False

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()
            self.ws = None

        logger.info("👋 OneBot 连接已关闭")

    async def _send_action(self, action: str, params: dict, timeout: float = 15.0) -> dict:
        if not self.ws:
            raise RuntimeError("WebSocket 未连接")

        echo = f"{action}-{int(asyncio.get_running_loop().time() * 1000)}"
        future = asyncio.get_running_loop().create_future()
        self._pending_echo_futures[echo] = future

        payload = {
            "action": action,
            "params": params,
            "echo": echo,
        }

        await self.ws.send(json.dumps(payload, ensure_ascii=False))

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            if result.get("status") != "ok":
                raise RuntimeError(f"OneBot 调用失败: {result}")
            return result.get("data", {})
        finally:
            self._pending_echo_futures.pop(echo, None)

    async def send_private_msg(self, user_id: str, message: str) -> bool:
        logger.info(f"📤 正在发送私聊消息到 QQ {user_id}")
        await self._send_action(
            "send_private_msg",
            {
                "user_id": int(user_id),
                "message": message,
                "auto_escape": False,
            },
        )
        logger.info("✅ 私聊消息发送成功")
        return True

    async def send_group_msg(self, group_id: str, message: str) -> bool:
        logger.info(f"📤 正在发送群消息到群 {group_id}")
        await self._send_action(
            "send_group_msg",
            {
                "group_id": int(group_id),
                "message": message,
                "auto_escape": False,
            },
        )
        logger.info("✅ 群消息发送成功")
        return True

    async def _handle_event(self, data: dict) -> None:
        post_type = data.get("post_type")
        if post_type != "message":
            return

        message_type = str(data.get("message_type", "")).strip()
        user_id = str(data.get("user_id", "")).strip()
        self_id = str(data.get("self_id", "")).strip()
        raw_message = str(data.get("raw_message", "")).strip()

        if user_id and (user_id == self.qq_number or user_id == self_id):
            return

        if not raw_message:
            return

        if message_type == "private":
            logger.info(f"📩 收到私聊消息，来自 {user_id}: {raw_message}")
            if self._message_handler:
                await self._message_handler(data)
            return

        if message_type == "group":
            group_id = str(data.get("group_id", "")).strip()
            logger.info(f"📩 收到群聊消息，群 {group_id}，用户 {user_id}: {raw_message}")
            if self._message_handler:
                await self._message_handler(data)
            return

    async def listen_forever(self) -> None:
        if not self.ws:
            raise RuntimeError("WebSocket 未连接")

        logger.info("👂 开始监听 QQ 消息事件...")

        while self.is_running:
            try:
                raw = await self.ws.recv()
                data = json.loads(raw)

                if "echo" in data and data["echo"] in self._pending_echo_futures:
                    future = self._pending_echo_futures[data["echo"]]
                    if not future.done():
                        future.set_result(data)
                    continue

                if "post_type" in data:
                    await self._handle_event(data)

            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed:
                logger.error("❌ WebSocket 连接已断开")
                self.is_running = False
                break
            except Exception as exc:
                logger.error(f"❌ 监听消息异常: {exc}")


def create_qq_client(config: dict) -> Optional[OneBotClient]:
    if config.get("enabled", False):
        logger.info("📌 使用 OneBot 协议连接 QQ")
        return OneBotClient(config)

    logger.warning("⚠️ 没有启用 OneBot 配置")
    return None