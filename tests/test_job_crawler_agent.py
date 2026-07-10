from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agents.job_crawler_agent import JobCrawlerAgent
from src.job_sources.public_web_source import PublicWebSource
from src.schemas.models import JobSearchPreference, JobSource


@dataclass
class FakeRobotsDecision:
    allowed: bool
    reason: str


class FakeRobotsChecker:
    def __init__(self, allowed: bool = True, reason: str = "robots.txt 允许访问") -> None:
        self.allowed = allowed
        self.reason = reason

    def check(self, url: str) -> FakeRobotsDecision:
        return FakeRobotsDecision(self.allowed, self.reason)


class FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, *args, **kwargs) -> FakeResponse:
        return self.response


def make_source(url: str = "https://company.com/careers") -> JobSource:
    return JobSource(
        source_id="company",
        source_name="Company Careers",
        base_url="https://company.com",
        list_url=url,
        enabled=True,
        access_policy="public_only",
    )


def make_agent(response: FakeResponse, tmp_path: Path) -> JobCrawlerAgent:
    agent = JobCrawlerAgent(
        robots_checker=FakeRobotsChecker(),
        public_source=PublicWebSource(
            session=FakeSession(response),
            cache_dir=tmp_path,
        ),
    )
    agent._wait_for_rate_limit = lambda: None
    return agent


def test_robots_disallowed_source_is_skipped(tmp_path: Path) -> None:
    agent = JobCrawlerAgent(
        robots_checker=FakeRobotsChecker(False, "robots.txt 不允许访问该 URL"),
        public_source=PublicWebSource(cache_dir=tmp_path),
    )
    agent._wait_for_rate_limit = lambda: None

    result = agent.run([make_source()], JobSearchPreference(max_jobs=3))[0]

    assert result.source_access_status == "robots_disallowed"
    assert result.crawled_count == 0


def test_no_public_url_is_reported() -> None:
    agent = JobCrawlerAgent(robots_checker=FakeRobotsChecker())

    result = agent.run(
        [JobSource(source_id="company", source_name="公司官网 Careers")],
        JobSearchPreference(max_jobs=3),
    )[0]

    assert result.source_access_status == "no_public_url"
    assert "未配置稳定公开搜索 URL" in result.source_access_note


def test_source_without_template_produces_single_no_public_url_result() -> None:
    agent = JobCrawlerAgent(robots_checker=FakeRobotsChecker())

    results = agent.run(
        [JobSource(source_id="zhaopin", source_name="智联招聘", base_url="https://www.zhaopin.com")],
        JobSearchPreference(target_role="AI 产品经理", target_cities=["北京", "上海"], max_jobs=3),
    )

    assert len(results) == 1
    assert results[0].source_access_status == "no_public_url"


def test_http_statuses_are_mapped_to_access_status(tmp_path: Path) -> None:
    cases = [(401, "login_required"), (403, "login_required"), (429, "captcha_or_blocked")]

    for status_code, expected in cases:
        agent = make_agent(FakeResponse(status_code, "blocked page with enough text"), tmp_path)
        result = agent.run([make_source()], JobSearchPreference(max_jobs=3))[0]

        assert result.source_access_status == expected


def test_login_and_captcha_text_are_detected(tmp_path: Path) -> None:
    login_agent = make_agent(FakeResponse(200, "请登录 登录后查看 这里是岗位页面的占位内容"), tmp_path)
    captcha_agent = make_agent(FakeResponse(200, "security check captcha verify 访问过于频繁"), tmp_path)

    login_result = login_agent.run([make_source()], JobSearchPreference(max_jobs=3))[0]
    captcha_result = captcha_agent.run([make_source()], JobSearchPreference(max_jobs=3))[0]

    assert login_result.source_access_status == "login_required"
    assert captcha_result.source_access_status == "captcha_or_blocked"


def test_public_html_enters_parser_and_keeps_jobs(tmp_path: Path) -> None:
    html = """
    <html><body>
      <article class="job-card">
        <h2><a href="/jobs/123">AI 产品经理</a></h2>
        <p>北京全职，负责 AI Agent 产品需求分析、Prompt 测试、SQL 分析和项目推进。</p>
      </article>
    </body></html>
    """
    agent = make_agent(FakeResponse(200, html), tmp_path)

    result = agent.run(
        [make_source("https://company.com/careers")],
        JobSearchPreference(target_role="AI 产品经理", keywords=["Agent"], max_jobs=3),
    )[0]

    assert result.source_access_status == "public_accessible"
    assert result.entered_parser
    assert result.jobs[0].source_url == "https://company.com/jobs/123"
