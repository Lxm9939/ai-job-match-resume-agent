from __future__ import annotations

import pytest

from src.job_sources.public_web_source import JobSourceAccessError, PublicWebSource
from src.schemas.models import JobSearchPreference, JobSource


class FakeResponse:
    def __init__(self, html: str, status_code: int = 200) -> None:
        self.text = html
        self.status_code = status_code
        self.content = html.encode("utf-8")


class FakeSession:
    def __init__(self, html: str) -> None:
        self.html = html

    def get(self, *args, **kwargs) -> FakeResponse:
        return FakeResponse(self.html)


def adapter(html: str, tmp_path):
    return PublicWebSource(session=FakeSession(html), cache_dir=tmp_path)


def source() -> JobSource:
    return JobSource(
        source_id="public_source_test",
        source_name="Company Careers",
        base_url="https://company.com",
        list_url="https://company.com/careers",
    )


def preference() -> JobSearchPreference:
    return JobSearchPreference(target_role="AI 产品经理", keywords=["AI", "SQL"], max_jobs=5)


def test_json_ld_job_posting_can_be_parsed(tmp_path) -> None:
    html = """
    <html><body>
    <script type="application/ld+json">
    {
      "@type": "JobPosting",
      "title": "AI 产品经理",
      "hiringOrganization": {"name": "星云智能"},
      "jobLocation": {"addressLocality": "北京"},
      "description": "负责 AI Agent 产品需求分析、SQL 指标分析和跨团队项目推进。",
      "url": "/jobs/ai-pm"
    }
    </script>
    </body></html>
    """

    jobs = adapter(html, tmp_path).fetch(source(), preference(), 5)

    assert jobs[0].job_title == "AI 产品经理"
    assert jobs[0].company == "星云智能"
    assert jobs[0].source_url == "https://company.com/jobs/ai-pm"


def test_next_data_job_json_can_be_parsed(tmp_path) -> None:
    html = """
    <html><body>
    <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"jobs":[{"jobTitle":"数据分析师","companyName":"云帆电商","city":"上海","jobDescription":"使用 SQL 和 Python 完成业务数据分析。","detailUrl":"/jobs/data-analyst"}]}}}
    </script>
    </body></html>
    """

    jobs = adapter(html, tmp_path).fetch(source(), preference(), 5)

    assert jobs[0].job_title == "数据分析师"
    assert jobs[0].source_url == "https://company.com/jobs/data-analyst"


def test_generic_job_link_can_be_parsed(tmp_path) -> None:
    html = """
    <html><body>
      <div class="opening">
        <a href="/position/pm-001">商业分析师</a>
        <p>岗位职责：负责商业分析、BI 看板、SQL 数据分析和业务复盘。</p>
      </div>
    </body></html>
    """

    jobs = adapter(html, tmp_path).fetch(source(), preference(), 5)

    assert jobs[0].job_title == "商业分析师"
    assert jobs[0].source_url == "https://company.com/position/pm-001"


def test_chinese_job_text_can_be_low_confidence_parsed(tmp_path) -> None:
    html = """
    <html><body>
      <main>
        <h1>招聘岗位</h1>
        <p>AI 产品经理</p>
        <p>岗位职责：负责 AI Agent 产品需求分析、Prompt 测试、SQL 指标分析和项目推进。</p>
        <p>任职要求：熟悉数据分析、产品经理工作流和跨团队沟通。</p>
      </main>
    </body></html>
    """

    jobs = adapter(html, tmp_path).fetch(source(), preference(), 5)

    assert jobs
    assert jobs[0].source_url_status == "fallback"
    assert "低置信度解析" in jobs[0].source_access_note


def test_js_dynamic_page_has_clear_parse_failed_message(tmp_path) -> None:
    html = """
    <html><body>
      <div id="root"></div>
      <script src="/static/app1.js"></script>
      <script src="/static/app2.js"></script>
      <script src="/static/app3.js"></script>
      <script src="/static/app4.js"></script>
      <script src="/static/app5.js"></script>
    </body></html>
    """

    with pytest.raises(JobSourceAccessError) as exc_info:
        adapter(html, tmp_path).fetch(source(), preference(), 5)

    assert exc_info.value.access_status == "parse_failed"
    assert "JavaScript 动态渲染" in exc_info.value.access_note
