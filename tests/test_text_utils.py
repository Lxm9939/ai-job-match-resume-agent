from __future__ import annotations

from src.utils.text_utils import (
    dedupe_keep_order,
    dedupe_keyword_groups,
    extract_keywords,
    markdown_table,
    normalize_text,
    split_bullets,
)


def test_normalize_text_collapses_spaces_and_blank_lines() -> None:
    raw = "  使用  Python\r\n\r\n\r\n完成\t数据分析  "

    assert normalize_text(raw) == "使用 Python\n\n完成 数据分析"


def test_extract_keywords_finds_curated_terms() -> None:
    text = "使用 Python、SQL 和 Streamlit 搭建 AI Agent 简历匹配工具，支持需求分析。"

    keywords = extract_keywords(text)

    assert "Python" in keywords
    assert "SQL" in keywords
    assert "Streamlit" in keywords
    assert "AI Agent" in keywords
    assert "需求分析" in keywords


def test_dedupe_keep_order_preserves_first_seen_order_case_insensitive() -> None:
    assert dedupe_keep_order(["Python", "SQL", "python", "Excel", "SQL"]) == [
        "Python",
        "SQL",
        "Excel",
    ]


def test_dedupe_keyword_groups_dedupes_across_groups() -> None:
    covered, weak, missing = dedupe_keyword_groups(
        ["Python", "SQL"],
        ["python", "RAG"],
        ["SQL", "Prompt Engineering"],
    )

    assert covered == ["Python", "SQL"]
    assert weak == ["RAG"]
    assert missing == ["Prompt Engineering"]


def test_split_bullets_cleans_markers_and_dedupes() -> None:
    text = """
    - 使用 SQL 分析用户转化
    1. 使用 SQL 分析用户转化
    • 搭建 Power BI 看板
    """

    assert split_bullets(text, min_len=4) == [
        "使用 SQL 分析用户转化",
        "搭建 Power BI 看板",
    ]


def test_markdown_table_renders_header_divider_and_rows() -> None:
    table = markdown_table(["岗位要求", "简历证据"], [["Python", "项目中使用 Python\n处理数据"]])

    assert "| 岗位要求 | 简历证据 |" in table
    assert "| --- | --- |" in table
    assert "项目中使用 Python<br>处理数据" in table
