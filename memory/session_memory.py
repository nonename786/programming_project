# memory\session_memory.py
from typing import Any, Dict, List


class SessionMemory:
    def __init__(self, max_messages: int = 30) -> None:
        self.max_messages = max_messages

    def trim_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(messages) <= self.max_messages:
            return messages

        system_messages = [m for m in messages if m["role"] == "system"]
        other_messages = [m for m in messages if m["role"] != "system"]

        trimmed = other_messages[-(self.max_messages - len(system_messages)) :]
        return system_messages + trimmed