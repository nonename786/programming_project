import ipaddress
import os
import re
from typing import Dict, List, Tuple
from urllib.parse import quote, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

from core.tool_registry import register_tool


DEFAULT_HEADERS = {
    "User-Agent": "Mini-OpenClaw/1.0 (+local-agent)",
}


def _load_web_security() -> Dict:
    path = os.getenv("MINI_OPENCLAW_SECURITY_CONFIG", "config/security_config.yaml")
    config_path = os.path.abspath(path)

    if not os.path.exists(config_path):
        return {
            "enabled": True,
            "timeout_seconds": 12,
            "max_results": 5,
            "default_provider": "auto",
            "allowed_domains": [],
            "blocked_domains": ["localhost", "127.0.0.1", "0.0.0.0", "::1"],
        }

    data = yaml.safe_load(open(config_path, "r", encoding="utf-8")) or {}
    return data.get("web_security", {})


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower()


def _domain_matches(host: str, domain: str) -> bool:
    host = _normalize_domain(host)
    domain = _normalize_domain(domain)
    return host == domain or host.endswith("." + domain)


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        return False


def _validate_remote_url(url: str) -> Tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "仅允许访问 http/https 链接。"

    host = parsed.hostname or ""
    if not host:
        return False, "URL 缺少合法主机名。"

    security = _load_web_security()
    blocked_domains = security.get("blocked_domains", [])
    allowed_domains = security.get("allowed_domains", [])

    if _is_private_ip(host):
        return False, "禁止访问内网或本机 IP。"

    for domain in blocked_domains:
        if _domain_matches(host, domain):
            return False, f"域名被安全策略阻止：{domain}"

    if allowed_domains:
        ok = any(_domain_matches(host, domain) for domain in allowed_domains)
        if not ok:
            return False, "该域名不在允许访问名单中。"

    return True, ""


def _clean_html_snippet(text: str) -> str:
    snippet = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet.strip()


def _search_via_wikipedia(query: str, limit: int, timeout_seconds: int) -> Dict:
    endpoint = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "utf8": 1,
    }

    response = requests.get(
        endpoint,
        params=params,
        timeout=timeout_seconds,
        headers=DEFAULT_HEADERS,
    )
    response.raise_for_status()

    data = response.json()
    items = data.get("query", {}).get("search", [])

    if not items:
        return {
            "success": True,
            "content": f"未搜索到与“{query}”相关的网页结果（provider=wikipedia）。",
            "error": None,
        }

    lines: List[str] = [f"联网搜索结果（provider=wikipedia）:"]
    for idx, item in enumerate(items, start=1):
        title = item.get("title", "(无标题)")
        snippet = _clean_html_snippet(item.get("snippet", ""))
        url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        lines.append(
            f"[{idx}] {title}\nURL: {url}\n摘要: {snippet if snippet else '(无摘要)'}"
        )

    return {
        "success": True,
        "content": "\n\n".join(lines),
        "error": None,
    }


def _search_via_serpapi(query: str, limit: int, timeout_seconds: int) -> Dict:
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return {
            "success": False,
            "content": "",
            "error": "未检测到 SERPAPI_API_KEY，无法使用 serpapi 搜索。",
        }

    endpoint = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "num": limit,
        "hl": "zh-cn",
        "api_key": api_key,
    }

    response = requests.get(
        endpoint,
        params=params,
        timeout=timeout_seconds,
        headers=DEFAULT_HEADERS,
    )
    response.raise_for_status()

    data = response.json()
    items = data.get("organic_results", [])

    if not items:
        return {
            "success": True,
            "content": f"未搜索到与“{query}”相关的网页结果（provider=serpapi）。",
            "error": None,
        }

    lines: List[str] = [f"联网搜索结果（provider=serpapi）:"]
    for idx, item in enumerate(items[:limit], start=1):
        title = item.get("title", "(无标题)")
        link = item.get("link", "")
        snippet = item.get("snippet", "(无摘要)")
        lines.append(f"[{idx}] {title}\nURL: {link}\n摘要: {snippet}")

    return {
        "success": True,
        "content": "\n\n".join(lines),
        "error": None,
    }


@register_tool(
    name="search_web",
    description="联网搜索网页信息。默认优先用 serpapi；如果没有配置 SERPAPI_API_KEY，则自动回退到 wikipedia 搜索。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "要搜索的关键词"},
            "limit": {
                "type": "integer",
                "description": "返回结果条数，默认 5",
            },
            "provider": {
                "type": "string",
                "enum": ["auto", "wikipedia", "serpapi"],
                "description": "搜索提供商，默认 auto",
            },
        },
        "required": ["query"],
    },
)
def search_web(query: str, limit: int = 5, provider: str = "auto") -> Dict:
    security = _load_web_security()
    if not security.get("enabled", True):
        return {"success": False, "content": "", "error": "web 工具已被禁用。"}

    timeout_seconds = int(security.get("timeout_seconds", 12))
    max_results = int(security.get("max_results", 5))
    limit = max(1, min(limit, max_results))

    selected_provider = provider
    if selected_provider == "auto":
        config_default = security.get("default_provider", "auto")
        if config_default != "auto":
            selected_provider = config_default
        else:
            selected_provider = "serpapi" if os.getenv("SERPAPI_API_KEY") else "wikipedia"

    try:
        if selected_provider == "serpapi":
            return _search_via_serpapi(query, limit, timeout_seconds)

        if selected_provider == "wikipedia":
            return _search_via_wikipedia(query, limit, timeout_seconds)

        return {
            "success": False,
            "content": "",
            "error": f"不支持的 provider: {selected_provider}",
        }
    except requests.RequestException as exc:
        return {
            "success": False,
            "content": "",
            "error": f"联网搜索失败：{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"联网搜索异常：{type(exc).__name__}: {exc}",
        }


@register_tool(
    name="fetch_webpage_text",
    description="抓取指定网页正文文本。出于安全考虑，默认禁止访问 localhost、127.0.0.1 和内网 IP。",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "网页 URL"},
            "max_chars": {
                "type": "integer",
                "description": "最多返回多少字符，默认 4000",
            },
        },
        "required": ["url"],
    },
)
def fetch_webpage_text(url: str, max_chars: int = 4000) -> Dict:
    security = _load_web_security()
    if not security.get("enabled", True):
        return {"success": False, "content": "", "error": "web 工具已被禁用。"}

    ok, reason = _validate_remote_url(url)
    if not ok:
        return {"success": False, "content": "", "error": reason}

    timeout_seconds = int(security.get("timeout_seconds", 12))
    max_chars = max(200, max_chars)

    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers=DEFAULT_HEADERS,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" in content_type or "application/xhtml+xml" in content_type:
            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            title = soup.title.get_text(" ", strip=True) if soup.title else url
            text = soup.get_text("\n", strip=True)
        else:
            title = url
            text = response.text

        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n...(已截断)"

        content = f"标题: {title}\nURL: {url}\n\n{text}"
        return {"success": True, "content": content, "error": None}

    except requests.RequestException as exc:
        return {
            "success": False,
            "content": "",
            "error": f"网页抓取失败：{type(exc).__name__}: {exc}",
        }
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"网页解析失败：{type(exc).__name__}: {exc}",
        }