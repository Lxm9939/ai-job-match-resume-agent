from __future__ import annotations

from src.analytics import build_job_match_analytics
from src.schemas.models import JDAnalysis, JobMatchResult, JobPosting


def make_result(
    *,
    title: str,
    city: str,
    score: float,
    recommendation: str,
    quality: str,
    missing: list[str],
    skills: list[str],
) -> JobMatchResult:
    return JobMatchResult(
        job=JobPosting(
            job_id=title,
            job_title=title,
            company="示例公司",
            city=city,
            job_type="实习",
            jd_text="岗位职责和技能要求",
            quality_label=quality,
            quality_warnings=["低置信度岗位"] if quality == "低" else [],
        ),
        total_score=score,
        recommendation=recommendation,
        missing_keywords=missing,
        jd_analysis=JDAnalysis(hard_skills=skills),
    )


def sample_results() -> list[JobMatchResult]:
    return [
        make_result(
            title="AI 产品经理",
            city="北京",
            score=80,
            recommendation="强烈建议投递",
            quality="高",
            missing=["RAG", "Prompt"],
            skills=["SQL", "Python"],
        ),
        make_result(
            title="AI 产品助理",
            city="北京、远程",
            score=60,
            recommendation="谨慎投递，需要补强关键词或项目表达",
            quality="中",
            missing=["RAG"],
            skills=["SQL", "Figma"],
        ),
        make_result(
            title="商业分析师",
            city="上海",
            score=40,
            recommendation="不优先投递",
            quality="低",
            missing=["Tableau"],
            skills=["Excel"],
        ),
    ]


def test_empty_jobs_return_safe_zero_statistics() -> None:
    analytics = build_job_match_analytics([])

    assert analytics["total_jobs"] == 0
    assert analytics["average_match_score"] == 0
    assert analytics["top_matched_jobs"] == []


def test_average_match_score_is_calculated() -> None:
    analytics = build_job_match_analytics(sample_results())

    assert analytics["average_match_score"] == 60.0
    assert analytics["max_match_score"] == 80
    assert analytics["min_match_score"] == 40


def test_recommendation_distribution_is_correct() -> None:
    analytics = build_job_match_analytics(sample_results())

    assert analytics["recommended_count"] == 1
    assert analytics["cautious_count"] == 1
    assert analytics["not_priority_count"] == 1
    assert analytics["recommendation_distribution"]["不优先投递"] == 1


def test_city_distribution_splits_multi_city_values() -> None:
    analytics = build_job_match_analytics(sample_results())

    assert analytics["city_distribution"]["北京"] == 2
    assert analytics["city_distribution"]["远程"] == 1
    assert analytics["city_distribution"]["上海"] == 1


def test_missing_keyword_top_ten_counts_occurrences() -> None:
    analytics = build_job_match_analytics(sample_results())

    assert analytics["top_missing_keywords"][0] == {"keyword": "RAG", "count": 2}


def test_quality_label_distribution_is_correct() -> None:
    analytics = build_job_match_analytics(sample_results())

    assert analytics["quality_label_distribution"] == {"高": 1, "中": 1, "低": 1}
    assert analytics["high_quality_count"] == 1
    assert analytics["medium_quality_count"] == 1
    assert analytics["low_quality_count"] == 1


def test_low_confidence_count_is_correct() -> None:
    analytics = build_job_match_analytics(sample_results())

    assert analytics["low_confidence_count"] == 1
