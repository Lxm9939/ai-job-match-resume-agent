"""Analytics helpers for V2/V3 job matching dashboard and exports."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence

from src.schemas.models import BatchMatchResult, JobMatchResult
from src.utils.text_utils import dedupe_keep_order, markdown_table


def build_job_match_analytics(
    data: BatchMatchResult | Sequence[JobMatchResult],
) -> Dict[str, Any]:
    """Build dashboard-ready metrics from batch job match results."""

    matches = list(data.ranked_jobs if isinstance(data, BatchMatchResult) else data)
    scores = [float(item.total_score) for item in matches]
    recommendation_categories = [_recommendation_category(item) for item in matches]
    quality_labels = [item.job.quality_label or "未评分" for item in matches]

    city_distribution = _category_distribution(
        value
        for item in matches
        for value in _split_values(item.job.city or "城市未知")
    )
    job_type_distribution = _category_distribution(
        value
        for item in matches
        for value in _split_values(item.job.job_type or "岗位类型未知")
    )
    recommendation_distribution = _category_distribution(
        item.recommendation or _recommendation_label(item.total_score)
        for item in matches
    )
    quality_label_distribution = _category_distribution(quality_labels)

    missing_keywords = _count_terms(
        dedupe_keep_order(item.missing_keywords)
        for item in matches
    )
    common_skills = _count_terms(
        dedupe_keep_order(item.jd_analysis.hard_skills + item.jd_analysis.tools)
        for item in matches
    )
    risk_keywords = _count_terms(
        dedupe_keep_order(item.risks)
        for item in matches
    )

    return {
        "total_jobs": len(matches),
        "average_match_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "max_match_score": round(max(scores), 1) if scores else 0.0,
        "min_match_score": round(min(scores), 1) if scores else 0.0,
        "recommended_count": recommendation_categories.count("recommended"),
        "cautious_count": recommendation_categories.count("cautious"),
        "not_priority_count": recommendation_categories.count("not_priority"),
        "high_quality_count": quality_labels.count("高"),
        "medium_quality_count": quality_labels.count("中"),
        "low_quality_count": quality_labels.count("低"),
        "low_confidence_count": len(
            [
                item
                for item in matches
                if item.job.quality_label == "低"
                or "低置信度岗位" in item.job.quality_warnings
            ]
        ),
        "city_distribution": city_distribution,
        "job_type_distribution": job_type_distribution,
        "recommendation_distribution": recommendation_distribution,
        "quality_label_distribution": quality_label_distribution,
        "top_matched_jobs": build_ranking_rows(matches)[:10],
        "top_missing_keywords": _top_rows(missing_keywords, "keyword"),
        "top_common_skills": _top_rows(common_skills, "skill"),
        "top_risk_keywords": _top_rows(risk_keywords, "risk"),
    }


def build_ranking_rows(matches: Sequence[JobMatchResult]) -> List[Dict[str, Any]]:
    """Return full ranking rows shared by dashboard CSV exports."""

    sorted_matches = sorted(matches, key=lambda item: item.total_score, reverse=True)
    return [
        {
            "rank": rank,
            "job_title": item.job.job_title,
            "company": item.job.company,
            "city": item.job.city,
            "job_type": item.job.job_type,
            "total_score": item.total_score,
            "skill_score": item.skill_score,
            "project_score": item.project_score,
            "keyword_score": item.keyword_score,
            "recommendation": item.recommendation,
            "quality_score": item.job.quality_score,
            "quality_label": item.job.quality_label or "未评分",
            "low_confidence": item.job.quality_label == "低",
            "source_url": item.job.source_url,
        }
        for rank, item in enumerate(sorted_matches, start=1)
    ]


def build_analytics_summary_markdown(analytics: Dict[str, Any]) -> str:
    """Render a concise, portable dashboard summary."""

    overview = [
        ["岗位总数", analytics["total_jobs"]],
        ["平均匹配分", analytics["average_match_score"]],
        ["最高匹配分", analytics["max_match_score"]],
        ["最低匹配分", analytics["min_match_score"]],
        ["推荐投递", analytics["recommended_count"]],
        ["谨慎投递", analytics["cautious_count"]],
        ["不优先投递", analytics["not_priority_count"]],
        ["高/中/低质量", (
            f"{analytics['high_quality_count']} / "
            f"{analytics['medium_quality_count']} / "
            f"{analytics['low_quality_count']}"
        )],
        ["低置信度", analytics["low_confidence_count"]],
    ]
    top_jobs = [
        [
            row["rank"],
            row["job_title"],
            row["company"],
            row["city"],
            row["total_score"],
            row["recommendation"],
        ]
        for row in analytics["top_matched_jobs"]
    ]
    missing = [
        [index, row["keyword"], row["count"]]
        for index, row in enumerate(analytics["top_missing_keywords"], start=1)
    ]
    skills = [
        [index, row["skill"], row["count"]]
        for index, row in enumerate(analytics["top_common_skills"], start=1)
    ]
    return "\n".join(
        [
            "# 岗位匹配分析 Dashboard 摘要",
            "",
            "## 总览指标",
            markdown_table(["指标", "数值"], overview),
            "",
            "## 高匹配岗位 Top 10",
            markdown_table(
                ["排名", "岗位", "公司", "城市", "匹配分", "推荐结论"],
                top_jobs,
            ),
            "",
            "## 缺失关键词 Top 10",
            markdown_table(["排名", "关键词", "出现岗位数"], missing),
            "",
            "## 常见技能关键词 Top 10",
            markdown_table(["排名", "技能", "出现岗位数"], skills),
        ]
    )


def _recommendation_category(item: JobMatchResult) -> str:
    recommendation = item.recommendation
    if recommendation.startswith("强烈建议") or recommendation.startswith("建议投递"):
        return "recommended"
    if recommendation.startswith("谨慎"):
        return "cautious"
    if recommendation.startswith("不优先"):
        return "not_priority"
    if item.total_score >= 65:
        return "recommended"
    if item.total_score >= 50:
        return "cautious"
    return "not_priority"


def _recommendation_label(score: float) -> str:
    if score >= 80:
        return "强烈建议投递"
    if score >= 65:
        return "建议投递，可针对性优化简历"
    if score >= 50:
        return "谨慎投递，需要补强关键词或项目表达"
    return "不优先投递"


def _split_values(value: str) -> List[str]:
    values = [item.strip() for item in re.split(r"[,，、/|]+", value) if item.strip()]
    return values or ["未知"]


def _category_distribution(values: Iterable[str]) -> Dict[str, int]:
    return dict(Counter(value or "未知" for value in values))


def _count_terms(groups: Iterable[Iterable[str]]) -> Counter[str]:
    display_names: Dict[str, str] = {}
    counter: Counter[str] = Counter()
    for group in groups:
        for term in group:
            normalized = " ".join(term.lower().split())
            if not normalized:
                continue
            display_names.setdefault(normalized, term)
            counter[normalized] += 1
    return Counter({display_names[key]: count for key, count in counter.items()})


def _top_rows(counter: Counter[str], field: str) -> List[Dict[str, Any]]:
    return [
        {field: term, "count": count}
        for term, count in counter.most_common(10)
    ]
