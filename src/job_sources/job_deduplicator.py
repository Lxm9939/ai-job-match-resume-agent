"""Deterministic deduplication for crawled job records."""

from __future__ import annotations

from collections import OrderedDict
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.schemas.models import CrawledJob, JobDeduplicationResult
from src.url_utils import is_clickable_job_url


class JobDeduplicator:
    """Keep the most complete and descriptive record in each duplicate group."""

    TRACKING_QUERY_KEYS = {"ref", "source", "from"}

    def run(self, jobs: List[CrawledJob]) -> JobDeduplicationResult:
        groups: OrderedDict[str, List[CrawledJob]] = OrderedDict()
        for job in jobs:
            groups.setdefault(self._dedupe_key(job), []).append(job)

        deduplicated: List[CrawledJob] = []
        duplicate_group_count = 0
        for group in groups.values():
            if len(group) == 1:
                deduplicated.append(
                    group[0].model_copy(
                        update={"duplicate_group": "", "is_duplicate": False}
                    )
                )
                continue

            duplicate_group_count += 1
            group_id = f"duplicate-{duplicate_group_count:03d}"
            selected = max(group, key=self._version_rank)
            deduplicated.append(
                selected.model_copy(
                    update={
                        "duplicate_group": group_id,
                        "is_duplicate": True,
                    }
                )
            )

        return JobDeduplicationResult(
            jobs=deduplicated,
            input_count=len(jobs),
            output_count=len(deduplicated),
            duplicate_count=len(jobs) - len(deduplicated),
            duplicate_group_count=duplicate_group_count,
        )

    def _dedupe_key(self, job: CrawledJob) -> str:
        if is_clickable_job_url(job.source_url, job.source_url_status):
            return f"url:{self._canonical_url(job.source_url)}"
        composite = "|".join(
            self._normalize(value)
            for value in (job.company, job.job_title, job.city)
        )
        return f"composite:{composite}"

    def _canonical_url(self, value: str) -> str:
        parsed = urlsplit(value.strip())
        query = [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in self.TRACKING_QUERY_KEYS
        ]
        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                urlencode(query),
                "",
            )
        )

    def _normalize(self, value: str) -> str:
        return " ".join(value.lower().split())

    def _version_rank(self, job: CrawledJob) -> tuple[int, int, int]:
        fields = (
            (job.job_title, "未知岗位"),
            (job.company, "公司未知"),
            (job.city, "城市未知"),
            (job.job_type, "岗位类型未知"),
            (job.publish_date, ""),
            (job.source_name, ""),
        )
        completeness = sum(
            1
            for value, unknown in fields
            if value.strip() and (not unknown or unknown not in value)
        )
        return completeness, len(job.jd_text.strip()), job.quality_score
