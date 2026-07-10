"""Generic parser for explicitly configured public careers HTML pages."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional

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
JOB_TEXT_TERMS = [
    "岗位",
    "职位",
    "招聘",
    "任职要求",
    "岗位职责",
    "工作职责",
    "AI",
    "数据分析",
    "产品经理",
    "商业分析",
    "BI",
    "SQL",
    "Python",
]
CARD_SELECTORS = [
    'a[href*="job"]',
    'a[href*="jobs"]',
    'a[href*="position"]',
    'a[href*="career"]',
    'a[href*="recruit"]',
    'div[class*="job"]',
    'li[class*="job"]',
    'div[class*="position"]',
    'li[class*="position"]',
    'div[class*="career"]',
]
TITLE_KEYS = ("job_title", "jobTitle", "title", "name", "positionName", "position", "jobName")
COMPANY_KEYS = ("company", "companyName", "employerName", "organization")
CITY_KEYS = ("city", "location", "jobLocation", "workLocation")
URL_KEYS = ("url", "jobUrl", "detailUrl", "applyUrl", "link", "href")
DESCRIPTION_KEYS = (
    "jd_text",
    "description",
    "jobDescription",
    "responsibilities",
    "requirements",
    "summary",
    "content",
)


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

        html = response.text
        access_status, access_note = self._inspect_page(html)
        if access_status != "public_accessible":
            raise JobSourceAccessError(access_status, access_note)
        jobs = self._extract_jobs(html, source, preference, max_jobs)
        if not jobs:
            soup = BeautifulSoup(html or "", "html.parser")
            if self._looks_like_dynamic_page(soup, html):
                raise JobSourceAccessError(
                    "parse_failed",
                    (
                        "页面可能由 JavaScript 动态渲染，当前静态解析器无法读取岗位内容。"
                        "请改用 CSV/Excel 导入、手动粘贴 JD，或提供岗位详情页 URL。"
                    ),
                    entered_parser=True,
                )
            raise JobSourceAccessError(
                "parse_failed",
                "页面公开可访问，但未发现岗位关键词或可解析的岗位结构。",
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
        jobs.extend(self._extract_structured_jobs(soup, source, preference, max_jobs))
        if jobs:
            return jobs[:max_jobs]
        jobs.extend(self._extract_card_jobs(soup, source, preference, search_terms, max_jobs))
        if jobs:
            return jobs[:max_jobs]
        if not jobs:
            jobs.extend(self._fallback_text_jobs(soup, source, preference, search_terms, max_jobs))
        return jobs[:max_jobs]

    def _extract_structured_jobs(
        self,
        soup: BeautifulSoup,
        source: JobSource,
        preference: JobSearchPreference,
        max_jobs: int,
    ) -> List[CrawledJob]:
        jobs: List[CrawledJob] = []
        seen = set()
        scripts = soup.find_all("script")
        for script in scripts:
            text = script.string or script.get_text(" ", strip=True)
            if not text:
                continue
            script_type = (script.get("type") or "").lower()
            script_id = (script.get("id") or "").lower()
            lower = text.lower()
            if (
                script_type != "application/ld+json"
                and script_id != "__next_data__"
                and "__nuxt" not in lower
                and not any(term in lower for term in ("job", "jobs", "position", "recruit"))
            ):
                continue
            for payload in self._json_payloads(text):
                for item in self._iter_job_dicts(payload):
                    job = self._job_from_dict(item, source, preference)
                    if job is None:
                        continue
                    key = (job.job_title.lower(), job.source_url.lower(), job.jd_text[:80])
                    if key in seen:
                        continue
                    seen.add(key)
                    jobs.append(job)
                    if len(jobs) >= max_jobs:
                        return jobs
        return jobs

    def _json_payloads(self, text: str) -> List[Any]:
        payloads: List[Any] = []
        raw = text.strip()
        if len(raw) > 1_000_000:
            return payloads
        for candidate in dedupe_keep_order(
            [
                raw,
                self._first_json_like(raw, "{", "}"),
                self._first_json_like(raw, "[", "]"),
            ]
        ):
            if not candidate:
                continue
            try:
                payloads.append(json.loads(candidate))
            except json.JSONDecodeError:
                continue
        return payloads

    def _first_json_like(self, text: str, start: str, end: str) -> str:
        start_index = text.find(start)
        end_index = text.rfind(end)
        if start_index == -1 or end_index == -1 or end_index <= start_index:
            return ""
        return text[start_index : end_index + 1]

    def _iter_job_dicts(self, payload: Any) -> Iterable[dict[str, Any]]:
        if isinstance(payload, dict):
            if self._looks_like_job_dict(payload):
                yield payload
            for value in payload.values():
                yield from self._iter_job_dicts(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_job_dicts(item)

    def _looks_like_job_dict(self, item: dict[str, Any]) -> bool:
        keys = {str(key).lower() for key in item.keys()}
        type_value = str(item.get("@type", "")).lower()
        if "jobposting" in type_value:
            return True
        has_title = bool(keys & {key.lower() for key in TITLE_KEYS})
        has_context = bool(
            keys
            & {
                "description",
                "jobdescription",
                "responsibilities",
                "requirements",
                "url",
                "joburl",
                "company",
                "companyname",
                "joblocation",
                "city",
            }
        )
        return has_title and has_context

    def _job_from_dict(
        self,
        item: dict[str, Any],
        source: JobSource,
        preference: JobSearchPreference,
    ) -> Optional[CrawledJob]:
        title = self._first_string(item, TITLE_KEYS)
        if not title or len(title) > 120:
            return None
        company = self._first_string(item, COMPANY_KEYS) or self._nested_name(
            item.get("hiringOrganization")
        )
        city = self._first_string(item, CITY_KEYS) or self._nested_name(item.get("jobLocation"))
        description = self._first_string(item, DESCRIPTION_KEYS)
        if not description:
            description = self._join_string_values(item)
        source_url = normalize_url(self._first_string(item, URL_KEYS), source.list_url or source.base_url)
        status, note = source_url_status(source_url)
        if not source_url and source.list_url:
            source_url = source.list_url
            status = "fallback"
            note = "使用岗位列表页作为来源"
        return self._build_job(
            title,
            description or title,
            source_url,
            source,
            preference,
            source_url_status_value=status,
            source_url_note=note,
            company=company,
            city=city,
            access_note="从结构化页面数据中解析岗位信息",
        )

    def _first_string(self, item: dict[str, Any], keys: Iterable[str]) -> str:
        for key in keys:
            if key not in item:
                continue
            value = item[key]
            if isinstance(value, str):
                return normalize_text(value)
            if isinstance(value, dict):
                nested = self._nested_name(value)
                if nested:
                    return nested
            if isinstance(value, list):
                text = " ".join(str(part) for part in value if isinstance(part, (str, int, float)))
                if text.strip():
                    return normalize_text(text)
        return ""

    def _nested_name(self, value: Any) -> str:
        if isinstance(value, dict):
            return self._first_string(value, ("name", "addressLocality", "city", "location"))
        if isinstance(value, list):
            for item in value:
                nested = self._nested_name(item)
                if nested:
                    return nested
        if isinstance(value, str):
            return normalize_text(value)
        return ""

    def _join_string_values(self, item: dict[str, Any]) -> str:
        values = [
            normalize_text(value)
            for value in item.values()
            if isinstance(value, str) and len(value.strip()) >= 8
        ]
        return normalize_text(" ".join(values))[:2500]

    def _extract_card_jobs(
        self,
        soup: BeautifulSoup,
        source: JobSource,
        preference: JobSearchPreference,
        search_terms: List[str],
        max_jobs: int,
    ) -> List[CrawledJob]:
        jobs: List[CrawledJob] = []
        seen = set()
        candidates: List[Tag] = []
        for selector in CARD_SELECTORS:
            candidates.extend(
                item for item in soup.select(selector) if isinstance(item, Tag)
            )
        for link in soup.find_all("a", href=True):
            if link not in candidates:
                candidates.append(link)

        for node in candidates:
            title = self._node_title(node)
            context_node = self._job_context(node)
            context = normalize_text(context_node.get_text(" ", strip=True))
            if not self._looks_like_job(title, context, search_terms, node):
                continue
            href = self._node_href(node)
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
        return jobs

    def _node_title(self, node: Tag) -> str:
        if node.name == "a":
            return normalize_text(node.get_text(" ", strip=True))
        title_node = node.find(["h1", "h2", "h3", "h4", "strong", "a"])
        if title_node:
            return normalize_text(title_node.get_text(" ", strip=True))
        return normalize_text(node.get_text(" ", strip=True))[:80]

    def _node_href(self, node: Tag) -> str:
        if node.name == "a":
            return str(node.get("href", ""))
        link = node.find("a", href=True)
        return str(link.get("href", "")) if isinstance(link, Tag) else ""

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
        has_position_class = any(
            term in f"{class_text} {parent_class}".lower()
            for term in ("position", "career", "recruit")
        )
        return has_job_class or has_position_class or self._contains_term(title, terms) or (
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
                    source_url_note="从岗位列表页文本中提取，未找到独立岗位详情链接",
                    access_note="页面公开可访问，但岗位结构为低置信度解析",
                )
            )
            if len(jobs) >= max_jobs:
                break
        if jobs:
            return jobs

        page_text = soup.get_text("\n", strip=True)
        chunks = self._text_job_chunks(page_text, terms)
        for chunk in chunks[:max_jobs]:
            title = chunk.split("\n", 1)[0][:80]
            jobs.append(
                self._build_job(
                    title,
                    normalize_text(chunk),
                    source.list_url,
                    source,
                    preference,
                    source_url_status_value="fallback",
                    source_url_note="从岗位列表页文本中提取，未找到独立岗位详情链接",
                    access_note="页面公开可访问，但岗位结构为低置信度解析",
                )
            )
        return jobs

    def _text_job_chunks(self, text: str, terms: List[str]) -> List[str]:
        lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
        chunks: List[str] = []
        for index, line in enumerate(lines):
            if not self._contains_term(line, terms + JOB_TEXT_TERMS):
                continue
            window = lines[index : index + 6]
            chunk = "\n".join(window)
            if len(chunk) >= 40:
                chunks.append(chunk[:2500])
        return dedupe_keep_order(chunks)

    def _looks_like_dynamic_page(self, soup: BeautifulSoup, html: str) -> bool:
        text = normalize_text(soup.get_text(" ", strip=True))
        lower_html = html.lower()
        if any(term in lower_html for term in ("enable javascript", "请开启 javascript", "请开启javascript")):
            return True
        has_app_root = bool(soup.find(id="root") or soup.find(id="app"))
        scripts = soup.find_all("script", src=True)
        next_data = soup.find(id="__NEXT_DATA__")
        next_empty = isinstance(next_data, Tag) and not normalize_text(next_data.get_text(" ", strip=True))
        return (has_app_root and len(text) < 120) or (len(scripts) >= 5 and len(text) < 120) or next_empty

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
        company: str = "",
        city: str = "",
        job_type: str = "",
        access_note: str = "公开 HTML 可访问，已进入解析",
    ) -> CrawledJob:
        jd_text = context[:2500] or title
        quality = "正常"
        if len(jd_text) < 120:
            quality = "JD 信息不足"
            jd_text = f"JD 信息不足：{jd_text}"
        status, inferred_note = source_url_status(source_url, source_url_status_value)
        return CrawledJob(
            job_title=title,
            company=company or self._company_name(source.source_name),
            city=city or self._detect_city(context, preference.target_cities),
            job_type=job_type or self._detect_job_type(context),
            jd_text=jd_text,
            source_url=source_url,
            source_url_status=status,
            source_url_note=source_url_note or inferred_note,
            source_access_status="public_accessible",
            source_access_note=access_note,
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
