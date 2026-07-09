from __future__ import annotations

import json

import requests

from src.job_sources.robots_checker import RobotsChecker
from src.job_sources.source_config import load_job_sources


class FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response


def test_robots_allows_public_careers_path() -> None:
    session = FakeSession(FakeResponse(200, "User-agent: *\nAllow: /careers"))
    checker = RobotsChecker(session=session)

    assert checker.is_allowed("https://company.example/careers/jobs")


def test_robots_disallows_blocked_path() -> None:
    session = FakeSession(FakeResponse(200, "User-agent: *\nDisallow: /careers"))
    checker = RobotsChecker(session=session)

    assert not checker.is_allowed("https://company.example/careers/jobs")


def test_robots_network_failure_fails_closed() -> None:
    session = FakeSession(error=requests.ConnectionError("network unavailable"))
    checker = RobotsChecker(session=session)

    decision = checker.check("https://company.example/careers/jobs")

    assert not decision.allowed
    assert "安全跳过" in decision.reason


def test_prohibited_recruiting_platform_is_disabled_by_config_loader() -> None:
    content = json.dumps(
        [
            {
                "source_id": "blocked",
                "source_name": "Blocked Platform",
                "source_type": "public_html",
                "base_url": "https://www.zhipin.com",
                "list_url": "https://www.zhipin.com/jobs",
                "allowed": True,
                "notes": "",
            }
        ]
    ).encode("utf-8")

    source = load_job_sources(content=content)[0]

    assert not source.allowed
    assert "禁止抓取" in source.notes
