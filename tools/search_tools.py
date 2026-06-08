# tools\search_tools.py
import os
from pathlib import Path
from typing import Dict, List

from core.tool_registry import register_tool


@register_tool(
    name="search_workspace_text",
    description="在 workspace 下递归搜索包含指定关键词的文本文件。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "要搜索的关键词"}
        },
        "required": ["keyword"],
    },
)
def search_workspace_text(keyword: str) -> Dict:
    workspace = Path(os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    matches: List[str] = []
    for file_path in workspace.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        if keyword in content:
            matches.append(str(file_path.relative_to(workspace)))

    if not matches:
        return {"success": True, "content": f"未找到包含关键词“{keyword}”的文件。", "error": None}

    return {
        "success": True,
        "content": "找到以下文件：\n" + "\n".join(matches),
        "error": None,
    }