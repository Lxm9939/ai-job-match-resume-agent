"""Fail-closed robots.txt checks for public job sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from src.job_sources.base import CRAWLER_USER_AGENT


@dataclass(frozen=True)
class RobotsDecision:
    allowed: bool
    reason: str


class RobotsChecker:
    """Check robots.txt with timeout and safe failure behavior."""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        timeout: float = 8.0,
        user_agent: str = CRAWLER_USER_AGENT,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.user_agent = user_agent
        self._cache: Dict[str, Optional[RobotFileParser]] = {}

    def is_allowed(self, url: str) -> bool:
        return self.check(url).allowed

    def check(self, url: str) -> RobotsDecision:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return RobotsDecision(False, "URL 不是有效的公开 http/https 地址")

        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._cache:
            decision = self._load_robots(origin)
            if not decision.allowed and decision.reason != "robots.txt 已加载":
                return decision

        parser = self._cache.get(origin)
        if parser is None:
            return RobotsDecision(True, "站点未提供 robots.txt（HTTP 404）")
        if parser.can_fetch(self.user_agent, url):
            return RobotsDecision(True, "robots.txt 允许访问")
        return RobotsDecision(False, "robots.txt 不允许访问该 URL")

    def _load_robots(self, origin: str) -> RobotsDecision:
        robots_url = f"{origin}/robots.txt"
        try:
            response = self.session.get(
                robots_url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
        except requests.RequestException as exc:
            return RobotsDecision(False, f"robots.txt 检查失败，安全跳过：{exc}")

        if response.status_code == 404:
            self._cache[origin] = None
            return RobotsDecision(True, "站点未提供 robots.txt（HTTP 404）")
        if response.status_code < 200 or response.status_code >= 300:
            return RobotsDecision(
                False,
                f"robots.txt 返回 HTTP {response.status_code}，安全跳过",
            )

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        self._cache[origin] = parser
        return RobotsDecision(True, "robots.txt 已加载")

