from __future__ import annotations

from src.url_utils import (
    format_url_for_display,
    is_placeholder_url,
    is_valid_http_url,
    normalize_url,
)


def test_normalize_url_completes_relative_path() -> None:
    assert (
        normalize_url("/jobs/123", "https://company.com/careers")
        == "https://company.com/jobs/123"
    )


def test_normalize_url_keeps_absolute_url() -> None:
    assert normalize_url("https://company.com/jobs/123") == "https://company.com/jobs/123"


def test_normalize_url_returns_empty_for_blank_or_unresolvable_url() -> None:
    assert normalize_url("") == ""
    assert normalize_url("/jobs/123") == ""


def test_placeholder_urls_are_detected() -> None:
    assert is_placeholder_url("https://careers.example.com/jobs/123")
    assert is_placeholder_url("demo")
    assert is_placeholder_url("http://localhost/jobs")
    assert is_placeholder_url("#")
    assert not is_placeholder_url("https://company.com/jobs/123")


def test_format_url_for_display_marks_demo_data() -> None:
    assert format_url_for_display("") == "未提供"
    assert format_url_for_display("https://example.com/jobs/1") == "示例数据，无真实岗位链接"
    assert is_valid_http_url("https://company.com/jobs/1")
