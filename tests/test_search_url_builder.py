from __future__ import annotations

from src.job_sources.search_url_builder import build_search_url
from src.schemas.models import JobSearchPreference, JobSource


def preference() -> JobSearchPreference:
    return JobSearchPreference(target_role="AI 产品经理", target_cities=["北京"])


def test_boss_search_url_uses_keyword_and_city_code() -> None:
    result = build_search_url(
        JobSource(
            source_id="boss_zhipin",
            source_name="Boss 直聘",
            base_url="https://www.zhipin.com",
            list_url_template="https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}",
        ),
        preference(),
    )

    assert result.url.startswith("https://www.zhipin.com/web/geek/job?")
    assert "query=AI" in result.url
    assert "city=101010100" in result.url


def test_liepin_search_url_uses_keyword_and_city_code() -> None:
    result = build_search_url(
        JobSource(
            source_id="liepin",
            source_name="猎聘",
            base_url="https://www.liepin.com",
            list_url_template="https://www.liepin.com/zhaopin/?key={keyword}&dqs={city_code}",
        ),
        preference(),
    )

    assert result.url.startswith("https://www.liepin.com/zhaopin/?")
    assert "key=AI" in result.url
    assert "dqs=010" in result.url


def test_linkedin_indeed_and_seek_search_urls_are_generated() -> None:
    sources = [
        JobSource(
            source_id="linkedin_jobs",
            source_name="LinkedIn Jobs",
            base_url="https://www.linkedin.com",
            list_url_template="https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}",
        ),
        JobSource(
            source_id="indeed",
            source_name="Indeed",
            base_url="https://www.indeed.com",
            list_url_template="https://www.indeed.com/jobs?q={keyword}&l={location}",
        ),
        JobSource(
            source_id="seek",
            source_name="Seek",
            base_url="https://www.seek.com.au",
            list_url_template="https://www.seek.com.au/{keyword}-jobs/in-{location_slug}",
        ),
    ]

    urls = [build_search_url(source, preference()).url for source in sources]

    assert urls[0].startswith("https://www.linkedin.com/jobs/search/?")
    assert urls[1].startswith("https://www.indeed.com/jobs?")
    assert urls[2].startswith("https://www.seek.com.au/")
    assert "jobs/in-" in urls[2]


def test_source_without_template_returns_no_public_url_note() -> None:
    result = build_search_url(
        JobSource(source_id="company_careers", source_name="公司官网 Careers"),
        preference(),
    )

    assert result.url == ""
    assert "未配置稳定公开搜索 URL" in result.note
