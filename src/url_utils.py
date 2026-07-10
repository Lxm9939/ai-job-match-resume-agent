"""URL normalization and display helpers for job source links."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse


PLACEHOLDER_HOSTS = {
    "example.com",
    "www.example.com",
    "example.org",
    "www.example.org",
    "example.net",
    "www.example.net",
    "localhost",
    "127.0.0.1",
    "::1",
}
PLACEHOLDER_TOKENS = {
    "",
    "#",
    "n/a",
    "na",
    "none",
    "null",
    "demo",
    "sample",
    "示例",
    "未提供",
    "无",
}


def is_valid_http_url(url: str) -> bool:
    """Return True when the value is a complete public http/https URL."""

    parsed = urlparse((url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_url(url: str | None, base_url: str | None = None) -> str:
    """Normalize absolute and relative URLs without guessing missing domains."""

    raw_url = (url or "").strip()
    if not raw_url:
        return ""
    if is_valid_http_url(raw_url):
        return raw_url
    if base_url and is_valid_http_url(base_url):
        joined = urljoin(base_url, raw_url)
        return joined if is_valid_http_url(joined) else ""
    return ""


def is_placeholder_url(url: str) -> bool:
    """Detect demo, local, placeholder, or obviously non-public job links."""

    raw_url = (url or "").strip()
    normalized = raw_url.lower()
    if normalized in PLACEHOLDER_TOKENS:
        return True
    if "demo" in normalized or "sample" in normalized:
        return True
    if not is_valid_http_url(raw_url):
        return True

    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    if host in PLACEHOLDER_HOSTS:
        return True
    return host.endswith(".example.com") or host.endswith(".example.org") or host.endswith(".example.net")


def format_url_for_display(url: str) -> str:
    """Return a user-facing URL label that never disguises demo data as real."""

    raw_url = (url or "").strip()
    if not raw_url:
        return "未提供"
    if is_placeholder_url(raw_url):
        return "示例数据，无真实岗位链接"
    return raw_url


def is_clickable_job_url(url: str, status: str = "") -> bool:
    """Return True when Streamlit may safely render the value as a hyperlink."""

    if status in {"demo_data", "missing", "no_public_url"}:
        return False
    return is_valid_http_url(url) and not is_placeholder_url(url)


def source_url_status(url: str, explicit_status: str = "") -> tuple[str, str]:
    """Infer source URL status and note while preserving explicit metadata."""

    if explicit_status:
        if explicit_status == "demo_data":
            return explicit_status, "示例数据，无真实岗位链接"
        if explicit_status == "missing":
            return explicit_status, "未提供岗位来源链接"
        if explicit_status == "fallback":
            return explicit_status, "使用岗位列表页作为来源"
        return explicit_status, ""

    if not (url or "").strip():
        return "missing", "未提供岗位来源链接"
    if is_placeholder_url(url):
        return "demo_data", "示例数据，无真实岗位链接"
    return "valid", "真实岗位来源链接"
