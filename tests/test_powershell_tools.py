from pathlib import Path

import yaml

from tools.powershell_tools import run_powershell_command


class DummyCompletedProcess:
    def __init__(self, returncode=0, stdout="ok", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_security_file(tmp_path: Path, enabled: bool, allowed_root: Path) -> Path:
    config = tmp_path / "security_config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "experimental_powershell_security": {
                    "enabled": enabled,
                    "executable": "auto",
                    "timeout_seconds": 8,
                    "allowed_roots": [str(allowed_root)],
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
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return config


def test_powershell_tool_disabled(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir(parents=True, exist_ok=True)

    security = _write_security_file(tmp_path, enabled=False, allowed_root=root)
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security))

    result = run_powershell_command("Get-Location", str(root))
    assert result["success"] is False
    assert result["error"]


def test_powershell_tool_blocks_dangerous_command(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir(parents=True, exist_ok=True)

    security = _write_security_file(tmp_path, enabled=True, allowed_root=root)
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security))

    result = run_powershell_command("Remove-Item test.txt", str(root))
    assert result["success"] is False
    assert result["error"]


def test_powershell_tool_success(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir(parents=True, exist_ok=True)

    security = _write_security_file(tmp_path, enabled=True, allowed_root=root)
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security))

    monkeypatch.setattr(
        "tools.powershell_tools._resolve_powershell_executable",
        lambda _: "powershell",
    )
    monkeypatch.setattr(
        "tools.powershell_tools.subprocess.run",
        lambda *args, **kwargs: DummyCompletedProcess(returncode=0, stdout="PS OK"),
    )

    result = run_powershell_command("Get-Location", str(root))
    assert result["success"] is True
    assert result["content"] == "PS OK"
