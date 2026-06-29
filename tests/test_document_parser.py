from __future__ import annotations

import pytest

from src.document_parser import parse_document


def test_parse_txt_utf8_content() -> None:
    text = "姓名：李同学\r\n技能：Python、SQL\r\n\r\n项目：AI 求职助手"

    parsed = parse_document("resume.txt", text.encode("utf-8"))

    assert "姓名：李同学" in parsed
    assert "Python、SQL" in parsed
    assert "\r" not in parsed


def test_parse_empty_txt_returns_empty_string() -> None:
    assert parse_document("empty.txt", b"") == ""
    assert parse_document("blank.txt", "   \n\n".encode("utf-8")) == ""


def test_parse_unsupported_file_type_has_clear_error() -> None:
    with pytest.raises(ValueError, match="Unsupported file type: .xlsx"):
        parse_document("resume.xlsx", b"not supported")


def test_parse_file_without_extension_has_clear_error() -> None:
    with pytest.raises(ValueError, match="Unsupported file type: unknown"):
        parse_document("resume", b"not supported")
