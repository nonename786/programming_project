# tools\todo_tools.py
import json
import os
from pathlib import Path
from typing import Dict, List

from core.tool_registry import register_tool


def _get_todo_file() -> Path:
    workspace = Path(os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    todo_file = workspace / "todo.json"
    if not todo_file.exists():
        todo_file.write_text("[]", encoding="utf-8")
    return todo_file


def _load_todos() -> List[Dict]:
    return json.loads(_get_todo_file().read_text(encoding="utf-8"))


def _save_todos(todos: List[Dict]) -> None:
    _get_todo_file().write_text(
        json.dumps(todos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@register_tool(
    name="manage_todo",
    description="管理本地待办事项，支持 add/list/complete/delete 四种操作。",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "complete", "delete"],
                "description": "待办操作类型"
            },
            "title": {"type": "string", "description": "待办标题，add 时使用"},
            "todo_id": {"type": "integer", "description": "待办编号，complete/delete 时使用"},
        },
        "required": ["action"],
    },
)
def manage_todo(action: str, title: str = "", todo_id: int = -1) -> Dict:
    todos = _load_todos()

    if action == "add":
        if not title.strip():
            return {"success": False, "content": "", "error": "add 操作需要 title"}
        new_id = max([item["id"] for item in todos], default=0) + 1
        todos.append({"id": new_id, "title": title.strip(), "completed": False})
        _save_todos(todos)
        return {"success": True, "content": f"已添加待办 #{new_id}: {title.strip()}", "error": None}

    if action == "list":
        if not todos:
            return {"success": True, "content": "(暂无待办)", "error": None}
        lines = []
        for item in todos:
            status = "✅" if item["completed"] else "⬜"
            lines.append(f"{item['id']}. {status} {item['title']}")
        return {"success": True, "content": "\n".join(lines), "error": None}

    if action == "complete":
        for item in todos:
            if item["id"] == todo_id:
                item["completed"] = True
                _save_todos(todos)
                return {"success": True, "content": f"已完成待办 #{todo_id}", "error": None}
        return {"success": False, "content": "", "error": f"未找到待办 #{todo_id}"}

    if action == "delete":
        new_todos = [item for item in todos if item["id"] != todo_id]
        if len(new_todos) == len(todos):
            return {"success": False, "content": "", "error": f"未找到待办 #{todo_id}"}
        _save_todos(new_todos)
        return {"success": True, "content": f"已删除待办 #{todo_id}", "error": None}

    return {"success": False, "content": "", "error": f"不支持的 action: {action}"}