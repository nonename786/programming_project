import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

import yaml

from core.tool_registry import register_tool


def _load_powershell_security() -> Dict:
    config_path = os.getenv(
        "MINI_OPENCLAW_SECURITY_CONFIG",
        "config/security_config.yaml",
    )
    path = Path(config_path)

    if not path.exists():
        return {
            "enabled": False,
            "executable": "auto",
            "timeout_seconds": 8,
            "allowed_roots": [],
            "allowed_command_prefixes": [
                "Get-ChildItem",
                "Get-Location",
                "Get-Content",
                "Select-String",
                "Test-Path",
            ],
            "blocked_keywords": [
                "Remove-Item",
                "Set-Content",
                "Add-Content",
                "New-Item",
                "Copy-Item",
                "Move-Item",
                "Rename-Item",
                "Invoke-WebRequest",
                "Invoke-RestMethod",
                "Invoke-Expression",
                "Start-Process",
                "Stop-Process",
                ".ps1",
            ],
        }

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("experimental_powershell_security", {})


def _resolve_powershell_executable(config_value: str) -> str:
    if config_value and config_value != "auto":
        found = shutil.which(config_value)
        if not found:
            raise ValueError(f"找不到 PowerShell 可执行文件：{config_value}")
        return found

    for candidate in ["powershell", "pwsh"]:
        found = shutil.which(candidate)
        if found:
            return found

    raise ValueError("未在当前系统中找到 powershell 或 pwsh。")


def _get_allowed_roots() -> List[Path]:
    security = _load_powershell_security()
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


def _validate_working_directory(path: str) -> Path:
    if not path.strip():
        raise ValueError("working_directory 不能为空。")

    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raise ValueError("working_directory 必须是绝对路径。")

    target = raw.resolve()
    allowed_roots = _get_allowed_roots()

    if not allowed_roots:
        raise ValueError("未配置 allowed_roots，无法启用受限 PowerShell。")

    if not _is_allowed_path(target, allowed_roots):
        raise ValueError("working_directory 不在允许访问的目录白名单内。")

    if not target.exists() or not target.is_dir():
        raise ValueError("working_directory 不存在或不是目录。")

    return target


def _validate_command(command: str, allowed_prefixes: List[str], blocked_keywords: List[str]) -> None:
    if not command.strip():
        raise ValueError("PowerShell 命令不能为空。")

    lowered = command.lower()

    dangerous_fragments = [";", "|", ">", "<", "\n", "\r", "`"]
    for frag in dangerous_fragments:
        if frag in command:
            raise ValueError(f"命令包含被禁止的字符或操作符：{frag}")

    if ".." in command:
        raise ValueError("命令中不允许出现 .. 路径跳转。")

    if re.search(r"[A-Za-z]:\\", command):
        raise ValueError("命令中不允许直接写绝对 Windows 路径，请改为相对 working_directory 的路径。")

    if re.search(r"(^|\\s)/", command):
        raise ValueError("命令中不允许直接写绝对路径。")

    for keyword in blocked_keywords:
        if keyword.lower() in lowered:
            raise ValueError(f"命令包含被禁止的关键字：{keyword}")

    if not any(lowered.startswith(prefix.lower()) for prefix in allowed_prefixes):
        raise ValueError(
            "该 PowerShell 命令不在允许前缀中。当前仅允许："
            + ", ".join(allowed_prefixes)
        )


@register_tool(
    name="run_powershell_command",
    description="实验性工具：在受限模式下执行只读 PowerShell 命令。默认关闭，只允许在白名单目录下执行只读命令。",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "PowerShell 命令，仅允许只读命令，例如 Get-ChildItem、Get-Content、Test-Path",
            },
            "working_directory": {
                "type": "string",
                "description": "执行命令的本地绝对目录，必须位于安全配置允许的目录白名单内",
            },
        },
        "required": ["command", "working_directory"],
    },
)
def run_powershell_command(command: str, working_directory: str) -> Dict:
    security = _load_powershell_security()
    if not security.get("enabled", False):
        return {
            "success": False,
            "content": "",
            "error": "实验性 PowerShell 工具未启用。请先在 security_config.yaml 和 config.yaml 中显式开启。",
        }

    try:
        cwd = _validate_working_directory(working_directory)
        _validate_command(
            command=command,
            allowed_prefixes=security.get("allowed_command_prefixes", []),
            blocked_keywords=security.get("blocked_keywords", []),
        )
        executable = _resolve_powershell_executable(
            str(security.get("executable", "auto"))
        )
    except Exception as exc:
        return {"success": False, "content": "", "error": str(exc)}

    timeout_seconds = int(security.get("timeout_seconds", 8))

    try:
        completed = subprocess.run(
            [
                executable,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        output = completed.stdout.strip() or completed.stderr.strip() or "(无输出)"
        return {
            "success": completed.returncode == 0,
            "content": output,
            "error": None if completed.returncode == 0 else f"命令退出码：{completed.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "content": "", "error": "PowerShell 命令执行超时。"}
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"PowerShell 执行失败：{type(exc).__name__}: {exc}",
        }