# tools\file_tools.py
import os
from pathlib import Path
from typing import Dict

import yaml

from core.tool_registry import register_tool


def _get_workspace_root() -> Path:
    workspace = os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")
    path = Path(workspace).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_max_read_bytes() -> int:
    security_config = os.getenv("MINI_OPENCLAW_SECURITY_CONFIG", "config/security_config.yaml")
    path = Path(security_config)
    if not path.exists():
        return 1024 * 1024
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return int(data.get("file_security", {}).get("max_read_bytes", 1024 * 1024))


def _safe_resolve(user_path: str) -> Path:
    workspace_root = _get_workspace_root()
    target = (workspace_root / user_path).resolve()

    if workspace_root not in target.parents and target != workspace_root:
        raise ValueError("非法路径：不允许访问 workspace 目录之外的内容。")
    return target


@register_tool(
    name="read_file",
    description="读取 workspace 目录内指定文件的内容。",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对于 workspace 的文件路径"}
        },
        "required": ["path"],
    },
)
def read_file(path: str) -> Dict:
    target = _safe_resolve(path)
    if not target.exists():
        return {"success": False, "content": "", "error": f"文件不存在：{path}"}
    if not target.is_file():
        return {"success": False, "content": "", "error": f"目标不是文件：{path}"}

    max_bytes = _get_max_read_bytes()
    if target.stat().st_size > max_bytes:
        return {
            "success": False,
            "content": "",
            "error": f"文件超过读取上限 {max_bytes} 字节。",
        }

    content = target.read_text(encoding="utf-8")
    return {"success": True, "content": content, "error": None}


@register_tool(
    name="write_file",
    description="向 workspace 目录中的指定文件写入内容，可覆盖或追加。",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对于 workspace 的文件路径"},
            "content": {"type": "string", "description": "要写入的文本内容"},
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append"],
                "description": "overwrite 表示覆盖写入，append 表示追加写入",
            },
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str, mode: str = "overwrite") -> Dict:
    target = _safe_resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    file_mode = "a" if mode == "append" else "w"
    with target.open(file_mode, encoding="utf-8") as f:
        f.write(content)

    return {
        "success": True,
        "content": f"已成功写入文件：{path}",
        "error": None,
    }


@register_tool(
    name="list_directory",
    description="列出 workspace 中指定目录下的文件和子目录。",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "相对于 workspace 的目录路径，默认 ."}
        },
        "required": [],
    },
)
def list_directory(path: str = ".") -> Dict:
    target = _safe_resolve(path)
    if not target.exists():
        return {"success": False, "content": "", "error": f"目录不存在：{path}"}
    if not target.is_dir():
        return {"success": False, "content": "", "error": f"目标不是目录：{path}"}

    items = []
    for item in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        items.append(f"{prefix} {item.name}")

    return {
        "success": True,
        "content": "\n".join(items) if items else "(空目录)",
        "error": None,
    }


@register_tool(
    name="create_directory",
    description="在 workspace 中创建新目录。",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要创建的目录路径"}
        },
        "required": ["path"],
    },
)
def create_directory(path: str) -> Dict:
    target = _safe_resolve(path)
    target.mkdir(parents=True, exist_ok=True)
    return {
        "success": True,
        "content": f"目录已创建：{path}",
        "error": None,
    }


@register_tool(
    name="delete_file",
    description="删除 workspace 中指定文件。必须显式传入 confirm=true 才允许删除。",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "要删除的文件路径"},
            "confirm": {"type": "boolean", "description": "必须为 true 才执行删除"},
        },
        "required": ["path", "confirm"],
    },
)
def delete_file(path: str, confirm: bool) -> Dict:
    if not confirm:
        return {
            "success": False,
            "content": "",
            "error": "删除文件必须传入 confirm=true。",
        }

    target = _safe_resolve(path)
    if not target.exists():
        return {"success": False, "content": "", "error": f"文件不存在：{path}"}
    if not target.is_file():
        return {"success": False, "content": "", "error": f"目标不是文件：{path}"}

    target.unlink()
    return {
        "success": True,
        "content": f"文件已删除：{path}",
        "error": None,
    }