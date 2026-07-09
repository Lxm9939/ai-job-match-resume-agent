"""Compliance-first crawler agent for configured public job sources."""

from __future__ import annotations

import time
from typing import List, Optional

from src.job_sources.public_web_source import PublicWebSource
from src.job_sources.robots_checker import RobotsChecker
from src.schemas.models import CrawlResult, JobSearchPreference, JobSource


class JobCrawlerAgent:
    """Crawl enabled public sources with robots checks and rate limiting."""

    def __init__(
        self,
        *,
        robots_checker: Optional[RobotsChecker] = None,
        public_source: Optional[PublicWebSource] = None,
        request_interval_seconds: float = 1.0,
    ) -> None:
        self.robots_checker = robots_checker or RobotsChecker()
        self.public_source = public_source or PublicWebSource()
        self.request_interval_seconds = max(1.0, request_interval_seconds)
        self._last_source_request_at = 0.0

    def run(
        self,
        sources: List[JobSource],
        preference: JobSearchPreference,
    ) -> List[CrawlResult]:
        results: List[CrawlResult] = []
        max_jobs = max(1, min(int(preference.max_jobs), 100))
        collected_count = 0

        for source in sources:
            if collected_count >= max_jobs:
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason="已达到最大抓取岗位数量",
                    )
                )
                continue
            if not source.allowed:
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason=source.notes or "该岗位源未启用",
                    )
                )
                continue
            if source.source_type != "public_html":
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason=f"当前不支持 source_type={source.source_type}",
                    )
                )
                continue

            self._wait_for_rate_limit()
            robots = self.robots_checker.check(source.list_url)
            self._last_source_request_at = time.monotonic()
            if not robots.allowed:
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason=robots.reason,
                    )
                )
                continue

            try:
                self._wait_for_rate_limit()
                remaining = max_jobs - collected_count
                jobs = self.public_source.fetch(source, preference, remaining)
                self._last_source_request_at = time.monotonic()
                collected_count += len(jobs)
                results.append(
                    CrawlResult(
                        source=source,
                        jobs=jobs,
                        crawled_count=len(jobs),
                    )
                )
            except Exception as exc:
                self._last_source_request_at = time.monotonic()
                results.append(
                    CrawlResult(
                        source=source,
                        error_message=f"抓取失败，已跳过：{exc}",
                    )
                )
        return results

    def _wait_for_rate_limit(self) -> None:
        if not self._last_source_request_at:
            return
        elapsed = time.monotonic() - self._last_source_request_at
        remaining = self.request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
