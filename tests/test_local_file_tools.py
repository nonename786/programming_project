from pathlib import Path

import yaml

from tools.local_file_tools import list_local_directory, read_local_file


def _write_security_file(tmp_path: Path, enabled: bool, allowed_root: Path) -> Path:
    config = tmp_path / "security_config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "experimental_local_file_security": {
                    "enabled": enabled,
                    "max_read_bytes": 1048576,
                    "max_entries": 200,
                    "allowed_roots": [str(allowed_root)],
                    "blocked_extensions": [
                        ".exe",
                        ".dll",
                        ".sys",
                        ".bat",
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


def test_local_file_tools_disabled(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir(parents=True, exist_ok=True)

    security = _write_security_file(tmp_path, enabled=False, allowed_root=root)
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security))

    result = list_local_directory(str(root))
    assert result["success"] is False
    assert result["error"]


def test_local_file_tools_read_success(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir(parents=True, exist_ok=True)

    file_path = root / "note.txt"
    file_path.write_text("hello local file", encoding="utf-8")

    security = _write_security_file(tmp_path, enabled=True, allowed_root=root)
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security))

    result = read_local_file(str(file_path))
    assert result["success"] is True
    assert result["content"] == "hello local file"


def test_local_file_tools_block_outside_root(monkeypatch, tmp_path):
    root = tmp_path / "allowed"
    root.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside.txt"
    outside.write_text("blocked", encoding="utf-8")

    security = _write_security_file(tmp_path, enabled=True, allowed_root=root)
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security))

    result = read_local_file(str(outside))
    assert result["success"] is False
    assert result["error"]
