# core\message_history.py
from typing import Any, Dict, List, Optional


class MessageHistory:
    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    def add_user(self, content: Any) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(
        self,
        content: Optional[str],
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        message: Dict[str, Any] = {
            "role": "assistant",
            "content": content or "",
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool(
        self,
        tool_call_id: str,
        name: str,
        content: str,
    ) -> None:
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": content,
            }
        )

    def clear(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages

    def get_turn_count(self) -> int:
        return len([m for m in self.messages if m["role"] == "user"])
