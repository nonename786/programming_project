from pathlib import Path

from tools.web_tools import fetch_webpage_text, search_web


class DummyResponse:
    def __init__(self, json_data=None, text="", status_code=200, headers=None):
        self._json_data = json_data or {}
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _prepare_security(monkeypatch, tmp_path: Path):
    security_file = tmp_path / "security_config.yaml"
    security_file.write_text(
        """file_security:
  max_read_bytes: 1048576

shell_security:
  enabled: true
  timeout_seconds: 10
  allowed_commands:
    - echo
  blocked_keywords:
    - rm -rf

web_security:
  enabled: true
  timeout_seconds: 12
  max_results: 5
  default_provider: "auto"
  allowed_domains: []
  blocked_domains:
    - "localhost"
    - "127.0.0.1"
    - "0.0.0.0"
    - "::1"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("MINI_OPENCLAW_SECURITY_CONFIG", str(security_file))


def test_search_web_wikipedia(monkeypatch, tmp_path):
    _prepare_security(monkeypatch, tmp_path)

    def fake_get(url, params=None, timeout=None, headers=None):
        assert "w/api.php" in url
        return DummyResponse(
            json_data={
                "query": {
                    "search": [
                        {
                            "title": "OpenClaw",
                            "snippet": "<span>一个智能体相关条目</span>",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr("tools.web_tools.requests.get", fake_get)

    result = search_web("OpenClaw", provider="wikipedia")
    assert result["success"] is True
    assert "OpenClaw" in result["content"]
    assert "provider=wikipedia" in result["content"]


def test_fetch_webpage_text_success(monkeypatch, tmp_path):
    _prepare_security(monkeypatch, tmp_path)

    html = """
    <html>
      <head><title>Test Page</title></head>
      <body>
        <script>console.log("ignore")</script>
        <h1>Hello</h1>
        <p>This is a test page.</p>
      </body>
    </html>
    """

    def fake_get(url, timeout=None, headers=None):
        return DummyResponse(
            text=html,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    monkeypatch.setattr("tools.web_tools.requests.get", fake_get)

    result = fetch_webpage_text("https://example.com/article", max_chars=1000)
    assert result["success"] is True
    assert "Test Page" in result["content"]
    assert "This is a test page." in result["content"]


def test_fetch_webpage_text_blocks_localhost(monkeypatch, tmp_path):
    _prepare_security(monkeypatch, tmp_path)

    result = fetch_webpage_text("http://127.0.0.1:8000/test")
    assert result["success"] is False
    assert "禁止访问内网或本机 IP" in result["error"] or "域名被安全策略阻止" in result["error"]