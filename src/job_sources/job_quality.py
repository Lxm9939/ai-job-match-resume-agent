"""Explainable quality scoring for crawled job records."""

from __future__ import annotations

from typing import List
from urllib.parse import urlparse

from src.schemas.models import CrawledJob
from src.utils.text_utils import (
    BUSINESS_KEYWORDS,
    HARD_SKILLS,
    TOOL_KEYWORDS,
    dedupe_keep_order,
    extract_known_terms,
)


class JobQualityScorer:
    """Score record completeness without removing low-confidence jobs."""

    def score_jobs(self, jobs: List[CrawledJob]) -> List[CrawledJob]:
        return [self.score_job(job) for job in jobs]

    def score_job(self, job: CrawledJob) -> CrawledJob:
        warnings: List[str] = []
        score = 0

        if self._known(job.job_title, ("未知岗位",)):
            score += 15
        else:
            warnings.append("岗位名称缺失")

        if self._known(job.company, ("公司未知",)):
            score += 15
        else:
            warnings.append("公司未知")

        if self._known(job.city, ("城市未知",)):
            score += 10
        else:
            warnings.append("城市未知")

        jd_length = len((job.jd_text or "").strip())
        score += self._jd_length_score(jd_length)
        if jd_length < 120 or job.jd_quality == "JD 信息不足":
            warnings.append("JD 信息不足")

        skill_terms = extract_known_terms(
            job.jd_text,
            HARD_SKILLS + TOOL_KEYWORDS + BUSINESS_KEYWORDS,
        )
        if len(skill_terms) >= 2:
            score += 15
        elif skill_terms:
            score += 8
            warnings.append("技能关键词较少")
        else:
            warnings.append("未识别技能关键词")

        if self._valid_url(job.source_url):
            score += 15
        else:
            warnings.append("来源链接缺失")

        if job.publish_date.strip():
            score += 5
        else:
            warnings.append("发布日期缺失")

        quality_label = "高" if score >= 80 else "中" if score >= 60 else "低"
        if quality_label == "低":
            warnings.append("低置信度岗位")

        return job.model_copy(
            update={
                "quality_score": min(100, score),
                "quality_label": quality_label,
                "quality_warnings": dedupe_keep_order(warnings),
                "jd_length": jd_length,
                "jd_quality": "JD 信息不足" if jd_length < 120 else job.jd_quality,
            }
        )

    def _jd_length_score(self, length: int) -> int:
        if length >= 500:
            return 25
        if length >= 200:
            return 20
        if length >= 120:
            return 14
        if length >= 50:
            return 6
        return 0

    def _known(self, value: str, unknown_markers: tuple[str, ...]) -> bool:
        value = value.strip()
        return bool(value) and not any(marker in value for marker in unknown_markers)

    def _valid_url(self, value: str) -> bool:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

