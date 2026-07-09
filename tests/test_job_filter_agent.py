from __future__ import annotations

from src.agents.job_filter_agent import JobFilterAgent
from src.schemas.models import CrawledJob, JobSearchPreference


def make_job(title: str, city: str, job_type: str, jd_text: str) -> CrawledJob:
    return CrawledJob(
        job_title=title,
        company="示例公司",
        city=city,
        job_type=job_type,
        jd_text=jd_text,
        source_url=f"https://careers.example.com/{title}",
        source_name="示例 Careers",
    )


def test_keyword_match_is_kept_and_city_match_is_prioritized() -> None:
    jobs = [
        make_job("AI 产品经理", "城市未知", "实习", "负责 Agent 产品需求和 Prompt 评测。"),
        make_job("AI 产品助理", "北京", "实习", "负责 AI 产品原型和数据分析。"),
    ]
    preference = JobSearchPreference(
        target_role="AI 产品",
        target_cities=["北京"],
        job_types=["实习"],
        keywords=["Agent", "Prompt"],
        max_jobs=10,
    )

    result = JobFilterAgent().run(jobs, preference)

    assert len(result.filtered_jobs) == 2
    assert result.filtered_jobs[0].city == "北京"


def test_irrelevant_and_wrong_city_jobs_are_removed() -> None:
    jobs = [
        make_job("行政支持专员", "北京", "实习", "负责会议和办公用品管理。"),
        make_job("AI 产品经理", "广州", "实习", "负责 AI Agent 产品设计。"),
        make_job("AI 产品经理", "北京", "全职", "负责 AI Agent 产品设计。"),
    ]
    preference = JobSearchPreference(
        target_role="AI 产品经理",
        target_cities=["北京"],
        job_types=["实习"],
        keywords=["AI", "Agent"],
        max_jobs=10,
    )

    result = JobFilterAgent().run(jobs, preference)

    assert result.filtered_jobs == []
    assert len(result.removed_jobs) == 3


def test_empty_job_list_returns_empty_result() -> None:
    result = JobFilterAgent().run([], JobSearchPreference())

    assert result.filtered_jobs == []
    assert result.removed_jobs == []
    assert "输入岗位为空" in result.filter_reason_summary

