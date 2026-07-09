from __future__ import annotations

from src.job_sources.job_quality import JobQualityScorer
from src.schemas.models import CrawledJob


def test_complete_long_job_has_higher_quality_score() -> None:
    complete = CrawledJob(
        job_title="AI 产品经理",
        company="示例科技",
        city="北京",
        job_type="校招",
        jd_text=(
            "负责 AI Agent 产品需求分析、PRD 和原型设计，使用 SQL、Python 完成效果评估，"
            "协同算法和研发推动版本上线并复盘用户反馈。"
        )
        * 5,
        source_url="https://company.example/jobs/ai-pm",
        publish_date="2026-07-09",
        source_name="示例 Careers",
    )
    incomplete = CrawledJob(
        job_title="未知岗位",
        company="公司未知",
        city="城市未知",
        jd_text="协助工作",
        source_url="",
    )

    scorer = JobQualityScorer()
    complete_result = scorer.score_job(complete)
    incomplete_result = scorer.score_job(incomplete)

    assert complete_result.quality_score > incomplete_result.quality_score
    assert complete_result.quality_label == "高"
    assert incomplete_result.quality_label == "低"


def test_short_jd_and_missing_url_produce_warnings() -> None:
    job = CrawledJob(
        job_title="产品助理",
        company="示例科技",
        city="城市未知",
        jd_text="负责产品工作",
        source_url="",
    )

    result = JobQualityScorer().score_job(job)

    assert "JD 信息不足" in result.quality_warnings
    assert "来源链接缺失" in result.quality_warnings
    assert "城市未知" in result.quality_warnings
    assert result.jd_length == len(job.jd_text)
