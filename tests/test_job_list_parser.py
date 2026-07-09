from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from src.agents.job_list_parser_agent import JobListParserAgent
from src.config import Settings
from src.llm_client import LLMClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def mock_parser() -> JobListParserAgent:
    return JobListParserAgent(LLMClient(Settings(llm_mode="mock")))


def test_parse_sample_jobs_csv() -> None:
    path = PROJECT_ROOT / "examples" / "sample_jobs.csv"
    jobs = mock_parser().parse_file(path.name, path.read_bytes())

    assert len(jobs) == 5
    assert jobs[0].job_title == "AI 产品经理"
    assert jobs[0].jd_text
    assert jobs[0].source_url.startswith("https://")


def test_parse_excel_job_list() -> None:
    buffer = BytesIO()
    pd.DataFrame(
        [{"job_title": "数据产品经理", "jd_text": "负责指标平台需求分析和 SQL 验证。"}]
    ).to_excel(buffer, index=False)

    jobs = mock_parser().parse_file("jobs.xlsx", buffer.getvalue())

    assert len(jobs) == 1
    assert jobs[0].job_title == "数据产品经理"


def test_split_multiple_jd_text() -> None:
    text = """
岗位：AI 产品助理
公司：示例科技
地点：北京
岗位职责：参与 AI 产品需求分析和原型设计。
---JOB---
岗位：数据分析师
公司：示例数据
地点：上海
岗位职责：使用 SQL 完成业务分析。
"""
    jobs = mock_parser().parse_multi_jd_text(text)

    assert len(jobs) == 2
    assert jobs[0].job_title == "AI 产品助理"
    assert jobs[1].company == "示例数据"


def test_missing_columns_use_clear_fallbacks() -> None:
    dataframe = pd.DataFrame(
        [{"job_title": "产品助理", "jd_text": "负责需求分析、PRD 和原型设计。"}]
    )
    jobs = mock_parser().parse_dataframe(dataframe)

    assert len(jobs) == 1
    assert jobs[0].company == "公司未知"
    assert jobs[0].city == "城市未知"
    assert jobs[0].job_type == "岗位类型未知"


def test_empty_job_list_returns_empty_result() -> None:
    parser = mock_parser()

    assert parser.parse_dataframe(pd.DataFrame()) == []
    assert parser.run() == []
