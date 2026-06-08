# tools\shell_tools.py
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict

import yaml

from core.tool_registry import register_tool


def _load_shell_security() -> Dict:
    path = Path(os.getenv("MINI_OPENCLAW_SECURITY_CONFIG", "config/security_config.yaml"))
    if not path.exists():
        return {
            "enabled": True,
            "timeout_seconds": 10,
            "allowed_commands": ["ls", "pwd", "echo", "cat", "grep", "find"],
            "blocked_keywords": ["rm -rf", "sudo", "chmod", "wget", "curl"],
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("shell_security", {})


@register_tool(
    name="run_shell_command",
    description="在 workspace 沙箱中执行受限 shell 命令，仅允许白名单命令。",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"}
        },
        "required": ["command"],
    },
)
def run_shell_command(command: str) -> Dict:
    security = _load_shell_security()

    if not security.get("enabled", True):
        return {"success": False, "content": "", "error": "shell 工具已被禁用"}

    blocked_keywords = security.get("blocked_keywords", [])
    lowered = command.lower()
    for keyword in blocked_keywords:
        if keyword.lower() in lowered:
            return {"success": False, "content": "", "error": f"命令包含危险关键字：{keyword}"}

    parts = shlex.split(command)
    if not parts:
        return {"success": False, "content": "", "error": "空命令"}

    allowed_commands = security.get("allowed_commands", [])
    if parts[0] not in allowed_commands:
        return {
            "success": False,
            "content": "",
            "error": f"命令 {parts[0]} 不在白名单中",
        }

    workspace = Path(os.getenv("MINI_OPENCLAW_WORKSPACE", "workspace")).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    try:
        completed = subprocess.run(
            parts,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=int(security.get("timeout_seconds", 10)),
        )
        output = completed.stdout.strip() or completed.stderr.strip() or "(无输出)"
        return {
            "success": completed.returncode == 0,
            "content": output,
            "error": None if completed.returncode == 0 else f"命令退出码：{completed.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "content": "", "error": "命令执行超时"}
    except Exception as exc:
        return {"success": False, "content": "", "error": f"shell 执行失败：{exc}"}