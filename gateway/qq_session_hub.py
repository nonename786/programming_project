import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.app_factory import build_agent, load_yaml_config
from core.message_history import MessageHistory
from utils.logger import get_logger

logger = get_logger("QQ-SessionHub")


class QQSessionHub:
    def __init__(self, config_path: str = "config/config.yaml") -> None:
        self.config_path = config_path
        self.config = load_yaml_config(config_path)
        self._agents: Dict[str, object] = {}

        qq_history_dir = self.config.get("paths", {}).get(
            "qq_history_dir", "history/qq_sessions"
        )
        self.qq_history_dir = Path(qq_history_dir)
        self.qq_history_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_persona_prompt(self) -> str:
        qq_prompt = str(self.config.get("qq", {}).get("persona_prompt", "")).strip()
        if qq_prompt:
            return qq_prompt
        return str(self.config.get("agent", {}).get("system_prompt", "")).strip()

    def _resolve_allowed_tools(self) -> Optional[List[str]]:
        qq_config = self.config.get("qq", {})
        if not qq_config.get("tool_whitelist_enabled", False):
            return None

        allowed_tools = [
            str(x).strip()
            for x in qq_config.get("allowed_tools", [])
            if str(x).strip()
        ]
        return allowed_tools

    def get_agent(self, session_id: str):
        if session_id not in self._agents:
            agent = build_agent()

            persona_prompt = self._resolve_persona_prompt()
            full_prompt = agent.long_term_memory.build_system_prompt(persona_prompt)
            agent.message_history = MessageHistory(system_prompt=full_prompt)

            allowed_tools = self._resolve_allowed_tools()
            agent.set_allowed_tools(allowed_tools)

            self._agents[session_id] = agent
            logger.info(f"✅ 已创建 QQ 会话 Agent: {session_id}")

        return self._agents[session_id]

    def clear_session(self, session_id: str) -> None:
        if session_id in self._agents:
            del self._agents[session_id]
            logger.info(f"🧹 已清空 QQ 会话: {session_id}")

    def list_sessions(self) -> List[str]:
        return list(self._agents.keys())

    def get_conversation_summary(self, session_id: str, limit: int = 8) -> str:
        agent = self._agents.get(session_id)
        if agent is None:
            return "（暂无对话历史）"

        messages = agent.message_history.get_messages()
        visible = [m for m in messages if m.get("role") in {"user", "assistant"}]
        if not visible:
            return "（暂无对话历史）"

        lines: List[str] = []
        for msg in visible[-limit:]:
            role = msg.get("role", "")
            emoji = "👤" if role == "user" else "🤖"
            text = str(msg.get("content", "")).strip()
            short_text = text[:80] + ("..." if len(text) > 80 else "")
            lines.append(f"{emoji} [{role}] {short_text}")

        return "\n".join(lines)

    def get_model_info(self, session_id: str) -> str:
        agent = self.get_agent(session_id)
        return (
            f"Provider: {agent.llm_client.get_provider_name()}\n"
            f"Model: {agent.llm_client.get_model_name()}"
        )

    def get_tool_names(self, session_id: str) -> List[str]:
        agent = self.get_agent(session_id)
        return agent.get_current_tool_names()

    def ask_terminal(self, question: str) -> str:
        agent = self.get_agent("qq-terminal")
        return agent.handle_user_message(question)

    def export_session_log(self, session_id: str) -> str:
        agent = self._agents.get(session_id)
        if agent is None:
            raise ValueError("当前会话不存在，无法导出。")

        safe_session_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", session_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.qq_history_dir / f"qq_session_{timestamp}_{safe_session_id}.md"

        lines: List[str] = []
        lines.append(f"# QQ 会话导出")
        lines.append("")
        lines.append(f"- session_id: `{session_id}`")
        lines.append(f"- provider: `{agent.llm_client.get_provider_name()}`")
        lines.append(f"- model: `{agent.llm_client.get_model_name()}`")
        lines.append(f"- exported_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
        lines.append("")

        for msg in agent.message_history.get_messages():
            role = msg.get("role", "unknown")
            content = str(msg.get("content", "")).strip()

            if role == "system":
                continue

            lines.append(f"## {role}")
            lines.append("")
            lines.append(content if content else "（空内容）")
            lines.append("")

        file_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"📦 QQ 会话已导出: {file_path}")
        return str(file_path)