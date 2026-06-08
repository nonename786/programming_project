from typing import Dict


def parse_user_input(user_input: str) -> Dict[str, str]:
    text = user_input.strip()

    if not text:
        return {"type": "empty", "value": ""}

    if text == "/exit":
        return {"type": "command", "value": "exit"}

    if text == "/clear":
        return {"type": "command", "value": "clear"}

    if text == "/history":
        return {"type": "command", "value": "history"}

    if text == "/list-sessions":
        return {"type": "command", "value": "list-sessions"}

    if text == "/save":
        return {"type": "command", "value": "save"}

    if text.startswith("/remember "):
        return {
            "type": "command",
            "value": "remember",
            "content": text[len("/remember "):].strip(),
        }

    if text == "/help":
        return {"type": "command", "value": "help"}

    return {"type": "message", "value": text}