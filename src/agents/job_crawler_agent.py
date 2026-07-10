"""Compliance-first crawler agent for configured public job sources."""

from __future__ import annotations

import time
from typing import List, Optional

from src.job_sources.public_web_source import JobSourceAccessError, PublicWebSource
from src.job_sources.robots_checker import RobotsChecker
from src.job_sources.source_config import resolve_source_search_url
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
                        source_access_status="unknown",
                        source_access_note="已达到最大抓取岗位数量",
                    )
                )
                continue
            if not source.allowed:
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason=source.notes or "该岗位源未启用",
                        source_access_status="unknown",
                        source_access_note=source.notes or "该岗位源未启用",
                    )
                )
                continue
            if source.source_type != "public_html":
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason=f"当前不支持 source_type={source.source_type}",
                        source_access_status="unknown",
                        source_access_note=f"当前不支持 source_type={source.source_type}",
                    )
                )
                continue

            url_result = resolve_source_search_url(source, preference)
            list_url = url_result.url
            if not list_url:
                note = url_result.note or (
                    "该来源未配置稳定公开搜索 URL，请在“自定义公开 URL”中提供具体页面，"
                    "或使用 CSV/Excel/JD 文本导入。"
                )
                results.append(
                    CrawlResult(
                        source=source,
                        skipped_reason=note,
                        source_access_status="no_public_url",
                        source_access_note=note,
                    )
                )
                continue
            active_source = source.model_copy(
                update={
                    "list_url": list_url,
                    "source_access_status": "unknown",
                    "source_access_note": url_result.note,
                }
            )

            self._wait_for_rate_limit()
            robots = self.robots_checker.check(active_source.list_url)
            self._last_source_request_at = time.monotonic()
            if not robots.allowed:
                results.append(
                    CrawlResult(
                        source=active_source,
                        skipped_reason=robots.reason,
                        source_access_status="robots_disallowed",
                        source_access_note=robots.reason,
                    )
                )
                continue

            try:
                self._wait_for_rate_limit()
                remaining = max_jobs - collected_count
                jobs = self.public_source.fetch(active_source, preference, remaining)
                self._last_source_request_at = time.monotonic()
                collected_count += len(jobs)
                success_note = "；".join(
                    part
                    for part in [url_result.note, "公开 HTML 可访问，已进入解析"]
                    if part
                )
                results.append(
                    CrawlResult(
                        source=active_source,
                        jobs=jobs,
                        crawled_count=len(jobs),
                        source_access_status="public_accessible",
                        source_access_note=success_note,
                        entered_parser=True,
                    )
                )
            except JobSourceAccessError as exc:
                self._last_source_request_at = time.monotonic()
                results.append(
                    CrawlResult(
                        source=active_source,
                        skipped_reason=exc.access_note,
                        source_access_status=exc.access_status,
                        source_access_note=exc.access_note,
                        entered_parser=exc.entered_parser,
                    )
                )
            except Exception as exc:
                self._last_source_request_at = time.monotonic()
                results.append(
                    CrawlResult(
                        source=active_source,
                        error_message=f"抓取失败，已跳过：{exc}",
                        source_access_status="unknown",
                        source_access_note=f"抓取失败，已跳过：{exc}",
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
