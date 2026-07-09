"""V3 public job source crawling and matching workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from src.agents.job_crawler_agent import JobCrawlerAgent
from src.agents.job_filter_agent import JobFilterAgent
from src.batch_workflow import BatchMatchWorkflow
from src.job_sources.job_deduplicator import JobDeduplicator
from src.job_sources.job_quality import JobQualityScorer
from src.job_sources.source_config import DEFAULT_SOURCE_CONFIG, load_job_sources
from src.llm_client import LLMClient
from src.schemas.models import (
    CrawledJob,
    CrawlResult,
    CrawlStatistics,
    CrawlWorkflowResult,
    JobPosting,
    JobPreferences,
    JobSearchPreference,
    JobSource,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_JOBS = PROJECT_ROOT / "examples" / "sample_crawled_jobs.json"


class CrawlWorkflow:
    """Fetch or load demo jobs, filter them, then reuse the V2 workflow."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        *,
        crawler_agent: Optional[JobCrawlerAgent] = None,
        filter_agent: Optional[JobFilterAgent] = None,
        deduplicator: Optional[JobDeduplicator] = None,
        quality_scorer: Optional[JobQualityScorer] = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.crawler_agent = crawler_agent or JobCrawlerAgent()
        self.filter_agent = filter_agent or JobFilterAgent()
        self.deduplicator = deduplicator or JobDeduplicator()
        self.quality_scorer = quality_scorer or JobQualityScorer()
        self.batch_workflow = BatchMatchWorkflow(self.llm_client)

    def run(
        self,
        *,
        resume_text: str,
        preference: JobSearchPreference,
        use_demo: bool = True,
        source_config_content: Optional[bytes] = None,
    ) -> CrawlWorkflowResult:
        if use_demo:
            crawl_results = self._load_demo_results(preference.max_jobs)
        else:
            sources = load_job_sources(
                content=source_config_content,
                path=None if source_config_content is not None else DEFAULT_SOURCE_CONFIG,
            )
            if not sources:
                raise ValueError("岗位源配置为空，请添加公开 Careers 页面或使用示例抓取结果。")
            crawl_results = self.crawler_agent.run(sources, preference)

        raw_jobs = self.quality_scorer.score_jobs(
            [
                job
                for result in crawl_results
                for job in result.jobs
            ][: max(1, preference.max_jobs)]
        )
        deduplication = self.deduplicator.run(raw_jobs)
        filter_result = self.filter_agent.run(deduplication.jobs, preference)
        if not filter_result.filtered_jobs:
            raise ValueError(
                "没有抓取到符合条件的岗位。请检查公开来源配置和筛选条件，"
                "或切换到 V2 上传 CSV/Excel 岗位列表。"
            )

        job_postings = [
            self._to_job_posting(job, index)
            for index, job in enumerate(filter_result.filtered_jobs, start=1)
        ]
        batch_result = self.batch_workflow.run(
            resume_text=resume_text,
            jobs=job_postings,
            preferences=JobPreferences(
                target_role=preference.target_role,
                target_city="、".join(preference.target_cities),
                job_type="、".join(preference.job_types),
                company_preference="、".join(preference.company_preferences),
            ),
        )
        skipped_count = len(
            [
                result
                for result in crawl_results
                if result.skipped_reason or result.error_message
            ]
        )
        statistics = self._build_statistics(
            crawl_results,
            raw_jobs,
            deduplication.output_count,
            filter_result.filtered_jobs,
        )
        return CrawlWorkflowResult(
            crawl_results=crawl_results,
            raw_jobs=raw_jobs,
            deduplication=deduplication,
            filter_result=filter_result,
            statistics=statistics,
            batch_result=batch_result,
            source_count=len(crawl_results),
            skipped_source_count=skipped_count,
            demo_mode=use_demo,
        )

    def _build_statistics(
        self,
        crawl_results: List[CrawlResult],
        raw_jobs: List[CrawledJob],
        deduplicated_count: int,
        filtered_jobs: List[CrawledJob],
    ) -> CrawlStatistics:
        return CrawlStatistics(
            raw_job_count=len(raw_jobs),
            deduplicated_job_count=deduplicated_count,
            filtered_job_count=len(filtered_jobs),
            high_quality_count=len(
                [job for job in filtered_jobs if job.quality_label == "高"]
            ),
            medium_quality_count=len(
                [job for job in filtered_jobs if job.quality_label == "中"]
            ),
            low_quality_count=len(
                [job for job in filtered_jobs if job.quality_label == "低"]
            ),
            robots_skipped_source_count=len(
                [
                    result
                    for result in crawl_results
                    if "robots" in result.skipped_reason.lower()
                ]
            ),
            failed_source_count=len(
                [result for result in crawl_results if result.error_message]
            ),
        )

    def _load_demo_results(self, max_jobs: int) -> List[CrawlResult]:
        data = json.loads(DEFAULT_DEMO_JOBS.read_text(encoding="utf-8"))
        jobs = [CrawledJob(**item) for item in data[: max(1, max_jobs)]]
        source = JobSource(
            source_id="demo_crawled_jobs",
            source_name="V3 示例抓取结果",
            source_type="public_html",
            base_url="https://careers.example.com",
            list_url="https://careers.example.com/jobs",
            allowed=True,
            notes="本地 Demo 数据，不发起网络请求。",
        )
        return [
            CrawlResult(
                source=source,
                jobs=jobs,
                crawled_count=len(jobs),
            )
        ]

    def _to_job_posting(self, job: CrawledJob, index: int) -> JobPosting:
        jd_text = job.jd_text
        if len(jd_text) < 120 and not jd_text.startswith("JD 信息不足"):
            jd_text = f"JD 信息不足：{jd_text}"
        return JobPosting(
            job_id=f"crawl-{index:03d}",
            job_title=job.job_title,
            company=job.company,
            city=job.city,
            job_type=job.job_type,
            jd_text=jd_text,
            source_url=job.source_url,
            publish_date=job.publish_date,
            quality_score=job.quality_score,
            quality_label=job.quality_label,
            quality_warnings=job.quality_warnings,
            duplicate_group=job.duplicate_group,
            is_duplicate=job.is_duplicate,
            jd_length=job.jd_length,
        )
