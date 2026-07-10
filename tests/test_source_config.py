from __future__ import annotations

from src.job_sources.source_config import (
    DEFAULT_SOURCE_CONFIG,
    build_custom_url_sources,
    load_job_sources,
    resolve_source_list_url,
)
from src.schemas.models import JobSearchPreference, JobSource


def test_default_config_contains_common_platform_options() -> None:
    names = {source.source_name for source in load_job_sources(path=DEFAULT_SOURCE_CONFIG)}

    for expected in ["Boss 直聘", "智联招聘", "猎聘", "前程无忧", "拉勾"]:
        assert expected in names


def test_default_platforms_are_not_rejected_by_domain() -> None:
    sources = load_job_sources(path=DEFAULT_SOURCE_CONFIG)
    domains = ["zhipin", "zhaopin", "liepin", "51job", "lagou"]

    selected = [
        source
        for source in sources
        if any(domain in source.base_url for domain in domains)
    ]

    assert selected
    assert all(source.allowed for source in selected)


def test_resolve_source_list_url_formats_public_template() -> None:
    source = JobSource(
        source_id="indeed",
        source_name="Indeed",
        base_url="https://www.indeed.com",
        list_url_template="https://www.indeed.com/jobs?q={keyword}&l={city}",
    )
    url = resolve_source_list_url(
        source,
        JobSearchPreference(target_role="AI 产品", target_cities=["上海"]),
    )

    assert "AI" in url
    assert "%E4%B8%8A%E6%B5%B7" in url


def test_build_custom_url_sources_keeps_valid_public_urls() -> None:
    sources = build_custom_url_sources(["https://company.com/careers", "not-a-url"])

    assert len(sources) == 1
    assert sources[0].list_url == "https://company.com/careers"
    assert sources[0].access_policy == "public_only"
