import os
from pathlib import Path
from typing import Dict, List

import yaml

from core.tool_registry import register_tool


def _load_local_file_security() -> Dict:
    config_path = os.getenv(
        "MINI_OPENCLAW_SECURITY_CONFIG",
        "config/security_config.yaml",
    )
    path = Path(config_path)

    if not path.exists():
        return {
            "enabled": False,
            "max_read_bytes": 1024 * 1024,
            "max_entries": 200,
            "allowed_roots": [],
            "blocked_extensions": [".exe", ".dll", ".sys", ".bat", ".ps1"],
        }

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("experimental_local_file_security", {})


def _get_allowed_roots() -> List[Path]:
    security = _load_local_file_security()
    roots = security.get("allowed_roots", [])
    return [Path(root).expanduser().resolve() for root in roots if str(root).strip()]


def _is_allowed_path(target: Path, allowed_roots: List[Path]) -> bool:
    for root in allowed_roots:
        try:
            if target.is_relative_to(root):
                return True
        except AttributeError:
            target_str = str(target)
            root_str = str(root)
            if target_str == root_str or target_str.startswith(root_str + os.sep):
                return True
    return False


def _validate_absolute_path(user_path: str) -> Path:
    if not user_path.strip():
        raise ValueError("路径不能为空。")

    raw = Path(user_path).expanduser()
    if not raw.is_absolute():
        raise ValueError("实验性本地文件工具只接受绝对路径。")

    target = raw.resolve()
    allowed_roots = _get_allowed_roots()

    if not allowed_roots:
        raise ValueError("未配置 allowed_roots，无法启用本地文件只读访问。")

    if not _is_allowed_path(target, allowed_roots):
        raise ValueError("目标路径不在允许访问的本地目录白名单内。")

    return target


@register_tool(
    name="list_local_directory",
    description="实验性工具：列出本地电脑指定目录下的文件和子目录。默认关闭，仅支持访问安全配置中允许的绝对路径白名单。",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "本地电脑绝对路径，例如 C:\\Users\\你的用户名\\Documents",
            }
        },
        "required": ["path"],
    },
)
def list_local_directory(path: str) -> Dict:
    security = _load_local_file_security()
    if not security.get("enabled", False):
        return {
            "success": False,
            "content": "",
            "error": "实验性本地文件工具未启用。请先在 security_config.yaml 和 config.yaml 中显式开启。",
        }

    try:
        target = _validate_absolute_path(path)
    except Exception as exc:
        return {"success": False, "content": "", "error": str(exc)}

    if not target.exists():
        return {"success": False, "content": "", "error": f"目录不存在：{path}"}

    if not target.is_dir():
        return {"success": False, "content": "", "error": f"目标不是目录：{path}"}

    max_entries = int(security.get("max_entries", 200))
    items = []
    for idx, item in enumerate(sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))):
        if idx >= max_entries:
            items.append("...(结果过多，已截断)")
            break
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        items.append(f"{prefix} {item.name}")

    return {
        "success": True,
        "content": "\n".join(items) if items else "(空目录)",
        "error": None,
    }


@register_tool(
    name="read_local_file",
    description="实验性工具：读取本地电脑文本文件内容。默认关闭，仅支持访问安全配置中允许的绝对路径白名单。",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "本地电脑绝对文件路径，例如 C:\\Users\\你的用户名\\Documents\\notes.txt",
            }
        },
        "required": ["path"],
    },
)
def read_local_file(path: str) -> Dict:
    security = _load_local_file_security()
    if not security.get("enabled", False):
        return {
            "success": False,
            "content": "",
            "error": "实验性本地文件工具未启用。请先在 security_config.yaml 和 config.yaml 中显式开启。",
        }

    try:
        target = _validate_absolute_path(path)
    except Exception as exc:
        return {"success": False, "content": "", "error": str(exc)}

    if not target.exists():
        return {"success": False, "content": "", "error": f"文件不存在：{path}"}

    if not target.is_file():
        return {"success": False, "content": "", "error": f"目标不是文件：{path}"}

    blocked_extensions = {
        str(ext).lower() for ext in security.get("blocked_extensions", [])
    }
    if target.suffix.lower() in blocked_extensions:
        return {
            "success": False,
            "content": "",
            "error": f"该类型文件被禁止读取：{target.suffix}",
        }

    max_read_bytes = int(security.get("max_read_bytes", 1024 * 1024))
    if target.stat().st_size > max_read_bytes:
        return {
            "success": False,
            "content": "",
            "error": f"文件超过读取上限 {max_read_bytes} 字节。",
        }

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"读取本地文件失败：{type(exc).__name__}: {exc}",
        }

    return {
        "success": True,
        "content": content,
        "error": None,
    }