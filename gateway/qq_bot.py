import asyncio
import re
import time
from typing import Dict, List, Optional

from core.app_factory import load_yaml_config
from gateway.qq_client import OneBotClient, create_qq_client
from gateway.qq_session_hub import QQSessionHub
from utils.logger import get_logger

logger = get_logger("QQ-Bot")


class QQBotRunner:
    def __init__(self, config_path: str = "config/config.yaml") -> None:
        self.config_path = config_path
        self.config = load_yaml_config(config_path)
        self.qq_config = self.config.get("qq", {})
        onebot_config = self.qq_config.get("onebot", {})

        self.client: Optional[OneBotClient] = create_qq_client(onebot_config)
        if not self.client:
            raise ValueError("QQ OneBot 未启用，请检查 config/config.yaml 中 qq 配置。")

        self.session_hub = QQSessionHub(config_path=config_path)
        self._last_reply_time: Dict[str, float] = {}

    def _cooldown_seconds(self) -> float:
        return float(self.qq_config.get("cooldown_seconds", 3.0))

    def _max_input_length(self) -> int:
        return int(self.qq_config.get("max_input_length", 1200))

    def _max_reply_length(self) -> int:
        return int(self.qq_config.get("max_reply_length", 1200))

    def _group_trigger_mode(self) -> str:
        return str(self.qq_config.get("group_trigger_mode", "at_only")).strip()

    def _group_trigger_prefixes(self):
        return [
            str(x).strip()
            for x in self.qq_config.get("group_trigger_prefixes", [])
            if str(x).strip()
        ]

    def _truncate_text(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "\n\n[提示] 消息过长，已自动截断处理。"

    def _get_session_id(self, event: dict) -> str:
        message_type = str(event.get("message_type", "")).strip()
        user_id = str(event.get("user_id", "")).strip()

        if message_type == "private":
            return f"private:{user_id}"

        if message_type == "group":
            group_id = str(event.get("group_id", "")).strip()
            return f"group:{group_id}:user:{user_id}"

        return "unknown"

    def _is_in_cooldown(self, session_id: str) -> bool:
        now = time.time()
        last_time = self._last_reply_time.get(session_id, 0.0)
        return now - last_time < self._cooldown_seconds()

    def _mark_replied(self, session_id: str) -> None:
        self._last_reply_time[session_id] = time.time()

    def _allow_user(self, user_id: str) -> bool:
        allowed = {
            str(x).strip()
            for x in self.qq_config.get("allowed_user_ids", [])
            if str(x).strip()
        }
        blocked = {
            str(x).strip()
            for x in self.qq_config.get("blocked_user_ids", [])
            if str(x).strip()
        }

        if user_id in blocked:
            return False
        if allowed and user_id not in allowed:
            return False
        return True

    def _allow_group(self, group_id: str) -> bool:
        allowed = {
            str(x).strip()
            for x in self.qq_config.get("allowed_group_ids", [])
            if str(x).strip()
        }
        blocked = {
            str(x).strip()
            for x in self.qq_config.get("blocked_group_ids", [])
            if str(x).strip()
        }

        if group_id in blocked:
            return False
        if allowed and group_id not in allowed:
            return False
        return True

    def _is_at_me(self, event: dict) -> bool:
        self_id = str(event.get("self_id", "")).strip()
        qq_number = str(self.client.qq_number if self.client else "").strip()
        target_ids = {x for x in [qq_number, self_id] if x}

        message = event.get("message", [])
        if isinstance(message, list):
            for seg in message:
                if not isinstance(seg, dict):
                    continue
                if seg.get("type") == "at":
                    qq = str(seg.get("data", {}).get("qq", "")).strip()
                    if qq in target_ids:
                        return True

        raw_message = str(event.get("raw_message", "")).strip()
        for qq in target_ids:
            if qq and f"[CQ:at,qq={qq}]" in raw_message:
                return True
        return False

    def _clean_group_message(self, event: dict) -> str:
        raw_message = str(event.get("raw_message", "")).strip()
        self_id = str(event.get("self_id", "")).strip()
        qq_number = str(self.client.qq_number if self.client else "").strip()

        target_ids = [x for x in [qq_number, self_id] if x]
        for target_id in target_ids:
            raw_message = raw_message.replace(f"[CQ:at,qq={target_id}]", "")

        raw_message = re.sub(r"\[CQ:[^\]]+\]", " ", raw_message)
        raw_message = re.sub(r"\s+", " ", raw_message).strip()
        return raw_message

    def _strip_trigger_prefix(self, text: str) -> Optional[str]:
        cleaned = text.strip()
        for prefix in self._group_trigger_prefixes():
            if cleaned.lower().startswith(prefix.lower()):
                rest = cleaned[len(prefix):].lstrip("，,。.:：;；!?！？ ")
                return rest
        return None

    def _extract_group_message_for_ai(self, event: dict) -> Optional[str]:
        mode = self._group_trigger_mode()
        cleaned = self._clean_group_message(event)
        at_me = self._is_at_me(event)
        prefix_text = self._strip_trigger_prefix(cleaned)

        if mode == "at_only":
            return cleaned if at_me and cleaned else None

        if mode == "prefix_only":
            return prefix_text if prefix_text else None

        if mode == "at_or_prefix":
            if at_me and cleaned:
                return cleaned
            if prefix_text:
                return prefix_text
            return None

        if mode == "all_messages":
            return cleaned if cleaned else None

        return cleaned if at_me and cleaned else None

    async def _send_reply(self, event: dict, text: str) -> None:
        if not self.client:
            return

        message_type = str(event.get("message_type", "")).strip()
        user_id = str(event.get("user_id", "")).strip()

        text = self._truncate_text(text, self._max_reply_length())

        if message_type == "private":
            await self.client.send_private_msg(user_id, text)
            return

        if message_type == "group":
            group_id = str(event.get("group_id", "")).strip()
            final_reply = f"[CQ:at,qq={user_id}] {text}"
            await self.client.send_group_msg(group_id, final_reply)

    def _build_help_text(self) -> str:
        return (
            "🤖 可用命令：\n"
            "/help - 查看帮助\n"
            "/reset - 清空当前会话记忆\n"
            "/history - 查看最近对话摘要\n"
            "/model - 查看当前AI模型\n"
            "/tools - 查看当前QQ入口启用工具\n"
            "/export - 导出当前QQ会话日志\n\n"
            "私聊可直接聊天；群聊请按配置使用 @ 或触发词。"
        )

    async def _handle_chat_command(self, event: dict, content: str, session_id: str) -> bool:
        cmd = content.strip()

        if cmd == "/help":
            await self._send_reply(event, self._build_help_text())
            return True

        if cmd == "/reset":
            self.session_hub.clear_session(session_id)
            await self._send_reply(event, "🧹 当前会话记忆已清空。")
            return True

        if cmd == "/history":
            summary = self.session_hub.get_conversation_summary(session_id=session_id)
            await self._send_reply(event, f"📝 最近对话摘要：\n{summary}")
            return True

        if cmd == "/model":
            info = self.session_hub.get_model_info(session_id=session_id)
            await self._send_reply(event, f"🤖 当前模型信息：\n{info}")
            return True

        if cmd == "/tools":
            tools = self.session_hub.get_tool_names(session_id=session_id)
            await self._send_reply(
                event,
                "🧰 当前 QQ 入口启用工具：\n" + "\n".join(f"- {x}" for x in tools),
            )
            return True

        if cmd == "/export":
            try:
                export_path = self.session_hub.export_session_log(session_id)
                await self._send_reply(event, f"📦 当前会话已导出：\n{export_path}")
            except Exception as exc:
                await self._send_reply(event, f"❌ 导出失败：{exc}")
            return True

        return False

    async def handle_incoming_message(self, event: dict) -> None:
        if not self.client:
            return

        message_type = str(event.get("message_type", "")).strip()
        user_id = str(event.get("user_id", "")).strip()
        group_id = str(event.get("group_id", "")).strip()
        session_id = self._get_session_id(event)

        if not self._allow_user(user_id):
            logger.warning(f"用户 {user_id} 不在允许范围内，忽略。")
            return

        if message_type == "group" and not self._allow_group(group_id):
            logger.warning(f"群 {group_id} 不在允许范围内，忽略。")
            return

        if self._is_in_cooldown(session_id):
            logger.warning(f"⏱️ 会话冷却中，忽略消息: session={session_id}")
            return

        if message_type == "private":
            raw_message = str(event.get("raw_message", "")).strip()
            if not raw_message:
                return

            if await self._handle_chat_command(event, raw_message, session_id):
                self._mark_replied(session_id)
                return

            raw_message = self._truncate_text(raw_message, self._max_input_length())

            try:
                agent = self.session_hub.get_agent(session_id)
                reply = agent.handle_user_message(raw_message)
                await self._send_reply(event, reply)
                self._mark_replied(session_id)
                logger.info(f"✅ 已自动回复私聊用户 {user_id}")
            except Exception as exc:
                logger.error(f"❌ 私聊自动回复失败: {exc}")

            return

        if message_type == "group":
            cleaned_message = self._extract_group_message_for_ai(event)
            if not cleaned_message:
                return

            if await self._handle_chat_command(event, cleaned_message, session_id):
                self._mark_replied(session_id)
                return

            cleaned_message = self._truncate_text(cleaned_message, self._max_input_length())

            try:
                agent = self.session_hub.get_agent(session_id)
                reply = agent.handle_user_message(cleaned_message)
                await self._send_reply(event, reply)
                self._mark_replied(session_id)
                logger.info(f"✅ 已自动回复群 {group_id} 中的用户 {user_id}")
            except Exception as exc:
                logger.error(f"❌ 群聊自动回复失败: {exc}")

    async def start(self) -> None:
        if not self.client:
            raise RuntimeError("QQ 客户端未初始化")

        await self.client.connect()
        self.client.set_message_handler(self.handle_incoming_message)
        await self.client.start_listener()
        logger.info("✅ QQ Bot 已启动")

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def send_private_message(self, user_id: str, message: str) -> None:
        if not self.client:
            raise RuntimeError("QQ 客户端未初始化")
        await self.client.send_private_msg(user_id, message)

    async def send_group_message(self, group_id: str, message: str) -> None:
        if not self.client:
            raise RuntimeError("QQ 客户端未初始化")
        await self.client.send_group_msg(group_id, message)

    def ask_terminal(self, question: str) -> str:
        return self.session_hub.ask_terminal(question)

    def list_session_ids(self) -> List[str]:
        return self.session_hub.list_sessions()

    def get_status_text(self) -> str:
        qq_number = self.client.qq_number if self.client else "未初始化"
        running = self.client.is_running if self.client else False
        return (
            f"QQ Running: {running}\n"
            f"QQ Number: {qq_number}\n"
            f"Trigger Mode: {self._group_trigger_mode()}\n"
            f"Cooldown: {self._cooldown_seconds()} 秒\n"
            f"QQ Sessions: {len(self.session_hub.list_sessions())}"
        )

    async def run_forever(self) -> None:
        await self.start()
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await self.close()