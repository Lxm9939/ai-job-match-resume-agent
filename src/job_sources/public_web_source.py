"""Generic parser for explicitly configured public careers HTML pages."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

from src.job_sources.base import BaseJobSource, CRAWLER_USER_AGENT
from src.schemas.models import CrawledJob, JobSearchPreference, JobSource
from src.url_utils import normalize_url, source_url_status
from src.utils.text_utils import dedupe_keep_order, normalize_text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "cache"
ROLE_TERMS = [
    "产品",
    "分析",
    "数据",
    "算法",
    "工程师",
    "运营",
    "实习",
    "manager",
    "analyst",
    "engineer",
    "product",
    "data",
    "intern",
    "ai",
    "agent",
]
LOGIN_REQUIRED_TERMS = ["请登录", "登录后查看", "login required", "sign in"]
CAPTCHA_OR_BLOCKED_TERMS = ["验证码", "captcha", "security check", "verify", "访问过于频繁"]


class JobSourceAccessError(RuntimeError):
    """Structured, UI-safe crawl/access error."""

    def __init__(
        self,
        access_status: str,
        access_note: str,
        *,
        entered_parser: bool = False,
    ) -> None:
        super().__init__(access_note)
        self.access_status = access_status
        self.access_note = access_note
        self.entered_parser = entered_parser


class PublicWebSource(BaseJobSource):
    """Fetch one public HTML list page and extract conservative job candidates."""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        timeout: float = 10.0,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.cache_dir = cache_dir
        self.cache_ttl_seconds = cache_ttl_seconds

    def fetch(
        self,
        source: JobSource,
        preference: JobSearchPreference,
        max_jobs: int,
    ) -> List[CrawledJob]:
        cache_path = self._cache_path(source, preference)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return [CrawledJob(**item) for item in cached[:max_jobs]]

        response = self.session.get(
            source.list_url,
            timeout=self.timeout,
            headers={
                "User-Agent": CRAWLER_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        status_code = getattr(response, "status_code", 200)
        if status_code in {401, 403}:
            raise JobSourceAccessError("login_required", f"HTTP {status_code}，页面可能需要登录")
        if status_code == 429:
            raise JobSourceAccessError("captcha_or_blocked", "HTTP 429，访问过于频繁或被限制")
        if status_code < 200 or status_code >= 300:
            raise JobSourceAccessError("http_error", f"HTTP {status_code}，已跳过")
        if len(response.content) > 5_000_000:
            raise JobSourceAccessError("http_error", "页面超过 5 MB，已停止解析以避免过度下载。")

        access_status, access_note = self._inspect_page(response.text)
        if access_status != "public_accessible":
            raise JobSourceAccessError(access_status, access_note)
        jobs = self._extract_jobs(response.text, source, preference, max_jobs)
        if not jobs:
            raise JobSourceAccessError(
                "parse_failed",
                "页面公开可访问，但未解析到岗位卡片或岗位文本",
                entered_parser=True,
            )
        self._write_cache(cache_path, jobs)
        return jobs

    def _inspect_page(self, html: str) -> tuple[str, str]:
        text = normalize_text(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))
        lower = text.lower()
        if any(term.lower() in lower for term in LOGIN_REQUIRED_TERMS):
            return "login_required", "页面包含登录后查看提示"
        if any(term.lower() in lower for term in CAPTCHA_OR_BLOCKED_TERMS):
            return "captcha_or_blocked", "页面包含验证码或访问限制提示"
        if len(text) < 40:
            return "parse_failed", "页面内容过短，无法提取岗位"
        return "public_accessible", "公开 HTML 可访问，已进入解析"

    def _extract_jobs(
        self,
        html: str,
        source: JobSource,
        preference: JobSearchPreference,
        max_jobs: int,
    ) -> List[CrawledJob]:
        soup = BeautifulSoup(html, "html.parser")
        search_terms = dedupe_keep_order(
            [preference.target_role]
            + preference.keywords
            + ROLE_TERMS
        )
        jobs: List[CrawledJob] = []
        seen = set()

        for link in soup.find_all("a", href=True):
            title = normalize_text(link.get_text(" ", strip=True))
            context_node = self._job_context(link)
            context = normalize_text(context_node.get_text(" ", strip=True))
            if not self._looks_like_job(title, context, search_terms, link):
                continue
            href = str(link.get("href", ""))
            source_url = normalize_url(href, source.list_url or source.base_url)
            status, note = source_url_status(source_url)
            if not source_url and source.list_url:
                source_url = source.list_url
                status = "fallback"
                note = "使用岗位列表页作为来源"
            key = (title.lower(), source_url.lower())
            if key in seen:
                continue
            seen.add(key)
            jobs.append(
                self._build_job(
                    title,
                    context,
                    source_url,
                    source,
                    preference,
                    source_url_status_value=status,
                    source_url_note=note,
                )
            )
            if len(jobs) >= max_jobs:
                break

        if not jobs:
            jobs.extend(self._fallback_text_jobs(soup, source, preference, search_terms, max_jobs))
        return jobs[:max_jobs]

    def _job_context(self, link: Tag) -> Tag:
        return (
            link.find_parent("article")
            or link.find_parent("li")
            or link.find_parent("tr")
            or link.find_parent("div")
            or link
        )

    def _looks_like_job(
        self,
        title: str,
        context: str,
        terms: Iterable[str],
        link: Tag,
    ) -> bool:
        if len(title) < 2 or len(title) > 100:
            return False
        blocked_titles = {"careers", "career", "jobs", "job", "招聘", "职位列表", "了解更多"}
        if title.lower() in blocked_titles:
            return False
        class_text = " ".join(link.get("class", []))
        parent_class = " ".join((link.parent.get("class", []) if isinstance(link.parent, Tag) else []))
        has_job_class = "job" in f"{class_text} {parent_class}".lower()
        return has_job_class or self._contains_term(title, terms) or (
            len(context) >= 40 and self._contains_term(context, terms)
        )

    def _contains_term(self, text: str, terms: Iterable[str]) -> bool:
        lower = text.lower()
        for term in terms:
            term = term.strip().lower()
            if not term:
                continue
            if re.fullmatch(r"[a-z0-9+#. -]+", term):
                if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lower):
                    return True
            elif term in text:
                return True
        return False

    def _fallback_text_jobs(
        self,
        soup: BeautifulSoup,
        source: JobSource,
        preference: JobSearchPreference,
        terms: List[str],
        max_jobs: int,
    ) -> List[CrawledJob]:
        jobs = []
        for node in soup.find_all(["article", "li", "section", "div"]):
            text = normalize_text(node.get_text(" ", strip=True))
            if len(text) < 40 or len(text) > 2500 or not self._contains_term(text, terms):
                continue
            title_node = node.find(["h1", "h2", "h3", "h4", "strong"])
            title = normalize_text(title_node.get_text(" ", strip=True)) if title_node else text[:60]
            jobs.append(
                self._build_job(
                    title,
                    text,
                    source.list_url,
                    source,
                    preference,
                    source_url_status_value="fallback",
                    source_url_note="使用岗位列表页作为来源",
                )
            )
            if len(jobs) >= max_jobs:
                break
        return jobs

    def _build_job(
        self,
        title: str,
        context: str,
        source_url: str,
        source: JobSource,
        preference: JobSearchPreference,
        *,
        source_url_status_value: str = "",
        source_url_note: str = "",
    ) -> CrawledJob:
        jd_text = context[:2500] or title
        quality = "正常"
        if len(jd_text) < 120:
            quality = "JD 信息不足"
            jd_text = f"JD 信息不足：{jd_text}"
        status, inferred_note = source_url_status(source_url, source_url_status_value)
        return CrawledJob(
            job_title=title,
            company=self._company_name(source.source_name),
            city=self._detect_city(context, preference.target_cities),
            job_type=self._detect_job_type(context),
            jd_text=jd_text,
            source_url=source_url,
            source_url_status=status,
            source_url_note=source_url_note or inferred_note,
            source_access_status="public_accessible",
            source_access_note="公开 HTML 可访问，已进入解析",
            publish_date=self._detect_date(context),
            crawled_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source_name=source.source_name,
            jd_quality=quality,
        )

    def _company_name(self, source_name: str) -> str:
        name = re.sub(r"\b(careers?|jobs?)\b", "", source_name, flags=re.I).strip(" -_|")
        return name or source_name

    def _detect_city(self, text: str, preferred_cities: List[str]) -> str:
        candidates = dedupe_keep_order(
            preferred_cities
            + ["北京", "上海", "杭州", "成都", "深圳", "广州", "南京", "武汉", "西安", "远程", "remote"]
        )
        found = [city for city in candidates if city.lower() in text.lower()]
        return "、".join(found[:2]) if found else "城市未知"

    def _detect_job_type(self, text: str) -> str:
        for job_type in ("可转正实习", "实习", "校招", "全职", "兼职", "internship", "full-time"):
            if job_type.lower() in text.lower():
                return job_type
        return "岗位类型未知"

    def _detect_date(self, text: str) -> str:
        match = re.search(r"\b(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)\b", text)
        return match.group(1) if match else ""

    def _cache_path(self, source: JobSource, preference: JobSearchPreference) -> Path:
        key_data = json.dumps(
            {
                "source": source.model_dump(),
                "role": preference.target_role,
                "keywords": preference.keywords,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(key_data.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{source.source_id}-{digest}.json"

    def _read_cache(self, path: Path) -> Optional[List[dict]]:
        try:
            if not path.exists():
                return None
            age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
            if age > self.cache_ttl_seconds:
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("jobs", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return None

    def _write_cache(self, path: Path, jobs: List[CrawledJob]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "jobs": [job.model_dump() for job in jobs],
            }
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            return
