from __future__ import annotations

from pathlib import Path

from src.config import Settings
from src.crawl_workflow import CrawlWorkflow
from src.job_sources.public_web_source import PublicWebSource
from src.llm_client import LLMClient
from src.schemas.models import JobSearchPreference, JobSource


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeHtmlResponse:
    def __init__(self, html: str) -> None:
        self.text = html
        self.content = html.encode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeHtmlSession:
    def __init__(self, html: str) -> None:
        self.html = html

    def get(self, *args, **kwargs) -> FakeHtmlResponse:
        return FakeHtmlResponse(self.html)


def test_public_html_source_extracts_job_and_absolute_url(tmp_path: Path) -> None:
    html = """
    <html><body>
      <article class="job-card">
        <h2><a href="/careers/ai-product-intern">AI 产品实习生</a></h2>
        <p>北京实习，参与 Agent 产品需求分析、Prompt 测试、SQL 数据分析和原型设计。</p>
      </article>
    </body></html>
    """
    adapter = PublicWebSource(
        session=FakeHtmlSession(html),
        cache_dir=tmp_path,
    )
    source = JobSource(
        source_id="public_test",
        source_name="Example Company Careers",
        base_url="https://company.example",
        list_url="https://company.example/careers",
        allowed=True,
    )

    jobs = adapter.fetch(
        source,
        JobSearchPreference(target_role="AI 产品", keywords=["Agent"], max_jobs=5),
        5,
    )

    assert len(jobs) == 1
    assert jobs[0].job_title == "AI 产品实习生"
    assert jobs[0].source_url == "https://company.example/careers/ai-product-intern"


def test_demo_crawl_enters_batch_matching_workflow() -> None:
    resume_text = (PROJECT_ROOT / "examples" / "sample_resume.txt").read_text(encoding="utf-8")
    workflow = CrawlWorkflow(LLMClient(Settings(llm_mode="mock")))
    preference = JobSearchPreference(
        target_role="AI 产品",
        target_cities=["北京", "成都", "远程"],
        job_types=["校招", "实习"],
        keywords=["AI", "Agent", "LLM", "Prompt"],
        company_preferences=["AI 公司"],
        max_jobs=6,
    )

    result = workflow.run(
        resume_text=resume_text,
        preference=preference,
        use_demo=True,
    )

    assert result.demo_mode
    assert result.raw_jobs
    assert result.filter_result.filtered_jobs
    assert result.batch_result.ranked_jobs
    assert all(item.job.source_url.startswith("https://") for item in result.batch_result.ranked_jobs)
    assert all(item.recommendation for item in result.batch_result.ranked_jobs)
    assert result.statistics.raw_job_count == len(result.raw_jobs)
    assert result.statistics.deduplicated_job_count == result.deduplication.output_count
    assert result.statistics.filtered_job_count == len(result.filter_result.filtered_jobs)
    quality_total = (
        result.statistics.high_quality_count
        + result.statistics.medium_quality_count
        + result.statistics.low_quality_count
    )
    assert quality_total == result.statistics.filtered_job_count
