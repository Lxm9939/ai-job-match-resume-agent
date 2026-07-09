"""Preference-based filter for crawled public jobs."""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from src.schemas.models import CrawledJob, JobFilterResult, JobSearchPreference
from src.utils.text_utils import dedupe_keep_order


class JobFilterAgent:
    """Keep relevant jobs while explaining removals at aggregate level."""

    def run(
        self,
        jobs: List[CrawledJob],
        preference: JobSearchPreference,
    ) -> JobFilterResult:
        if not jobs:
            return JobFilterResult(
                filter_reason_summary="输入岗位为空，没有可筛选内容。",
            )

        terms = self._search_terms(preference)
        kept: List[Tuple[int, int, int, CrawledJob]] = []
        removed: List[CrawledJob] = []
        reason_counts = {"内容不相关": 0, "城市不匹配": 0, "岗位类型不匹配": 0}

        for index, job in enumerate(jobs):
            text = f"{job.job_title} {job.jd_text}"
            title_hits = self._count_hits(job.job_title, terms)
            content_hits = self._count_hits(text, terms)
            if terms and content_hits == 0:
                reason_counts["内容不相关"] += 1
                removed.append(job)
                continue

            city_matches, city_known = self._field_matches(
                job.city,
                preference.target_cities,
                unknown_markers=("城市未知", "未知"),
            )
            if preference.target_cities and city_known and not city_matches:
                reason_counts["城市不匹配"] += 1
                removed.append(job)
                continue

            type_matches, type_known = self._field_matches(
                job.job_type,
                preference.job_types,
                unknown_markers=("岗位类型未知", "未知"),
            )
            if preference.job_types and type_known and not type_matches:
                reason_counts["岗位类型不匹配"] += 1
                removed.append(job)
                continue

            score = title_hits * 3 + content_hits
            if city_matches:
                score += 2
            if type_matches:
                score += 1
            preference_priority = int(city_matches) * 2 + int(type_matches)
            kept.append((preference_priority, score, -index, job))

        kept.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        filtered = [item[3] for item in kept[: max(1, preference.max_jobs)]]
        reasons = "；".join(
            f"{name} {count} 个" for name, count in reason_counts.items() if count
        ) or "没有岗位因偏好条件被移除"
        return JobFilterResult(
            filtered_jobs=filtered,
            removed_jobs=removed,
            filter_reason_summary=(
                f"保留 {len(filtered)} 个岗位，移除 {len(removed)} 个岗位；{reasons}。"
            ),
        )

    def _search_terms(self, preference: JobSearchPreference) -> List[str]:
        role_parts = re.split(r"[\s,，、/|]+", preference.target_role)
        return dedupe_keep_order(
            term.strip()
            for term in [preference.target_role, *role_parts, *preference.keywords]
            if term.strip()
        )

    def _count_hits(self, text: str, terms: Iterable[str]) -> int:
        return sum(1 for term in terms if self._contains(text, term))

    def _contains(self, text: str, term: str) -> bool:
        lower = text.lower()
        term_lower = term.lower()
        if re.fullmatch(r"[a-z0-9+#. -]+", term_lower):
            return bool(
                re.search(
                    rf"(?<![a-z0-9]){re.escape(term_lower)}(?![a-z0-9])",
                    lower,
                )
            )
        return term in text

    def _field_matches(
        self,
        actual: str,
        preferred: List[str],
        unknown_markers: tuple[str, ...],
    ) -> tuple[bool, bool]:
        if any(marker in actual for marker in unknown_markers):
            return False, False
        if not preferred:
            return False, True
        lower = actual.lower()
        matches = any(
            value.strip().lower() in lower or lower in value.strip().lower()
            for value in preferred
            if value.strip()
        )
        return matches, True
