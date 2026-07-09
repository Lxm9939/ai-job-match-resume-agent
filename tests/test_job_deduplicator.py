from __future__ import annotations

from src.job_sources.job_deduplicator import JobDeduplicator
from src.schemas.models import CrawledJob


def make_job(
    *,
    title: str = "AI 产品经理",
    company: str = "示例科技",
    city: str = "北京",
    jd_text: str = "负责 AI Agent 产品设计。",
    source_url: str = "",
    publish_date: str = "",
) -> CrawledJob:
    return CrawledJob(
        job_title=title,
        company=company,
        city=city,
        job_type="校招",
        jd_text=jd_text,
        source_url=source_url,
        publish_date=publish_date,
        source_name="示例 Careers",
    )


def test_same_source_url_is_deduplicated_and_longer_version_is_kept() -> None:
    jobs = [
        make_job(
            jd_text="短 JD",
            source_url="https://company.example/jobs/123?utm_source=test",
        ),
        make_job(
            jd_text="负责 AI Agent 产品需求分析、PRD、原型设计和 SQL 效果评估。" * 5,
            source_url="https://company.example/jobs/123",
            publish_date="2026-07-09",
        ),
    ]

    result = JobDeduplicator().run(jobs)

    assert result.input_count == 2
    assert result.output_count == 1
    assert result.duplicate_count == 1
    assert "SQL" in result.jobs[0].jd_text
    assert result.jobs[0].is_duplicate
    assert result.jobs[0].duplicate_group == "duplicate-001"


def test_missing_url_uses_company_title_city_composite_key() -> None:
    jobs = [
        make_job(jd_text="较短版本"),
        make_job(jd_text="更完整的岗位职责和技能要求。" * 10, publish_date="2026-07-09"),
    ]

    result = JobDeduplicator().run(jobs)

    assert result.output_count == 1
    assert result.jobs[0].publish_date == "2026-07-09"
    assert len(result.jobs[0].jd_text) > 20

