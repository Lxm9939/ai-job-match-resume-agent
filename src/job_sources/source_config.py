"""Load and validate user-managed public job source configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from src.job_sources.search_url_builder import SearchUrlBuildResult, build_search_url
from src.schemas.models import JobSearchPreference
from src.schemas.models import JobSource
from src.url_utils import is_valid_http_url, normalize_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_CONFIG = PROJECT_ROOT / "configs" / "job_sources.example.json"
SUPPORTED_SOURCE_TYPES = {"public_html"}


def load_job_sources(
    *,
    content: Optional[bytes] = None,
    path: Optional[Path] = None,
) -> List[JobSource]:
    """Load source JSON without banning sources solely by platform domain."""

    if content is not None:
        raw = content.decode("utf-8-sig")
    else:
        config_path = path or DEFAULT_SOURCE_CONFIG
        raw = config_path.read_text(encoding="utf-8")

    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("岗位源配置必须是 JSON 数组。")

    sources: List[JobSource] = []
    for item in data:
        source = JobSource(**item)
        reasons = []
        if not source.allowed:
            reasons.append("该岗位源未启用")
        if not source.enabled:
            reasons.append("该岗位源未启用")
        if source.access_policy != "public_only":
            reasons.append("仅支持 access_policy=public_only")
        if source.source_type not in SUPPORTED_SOURCE_TYPES:
            reasons.append(f"当前不支持 source_type={source.source_type}")
        for url in (source.base_url, source.list_url):
            if not url.strip():
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                reasons.append("仅允许公开 http/https URL")
                break
        if reasons:
            note = "；".join(filter(None, [source.notes, *reasons]))
            source = source.model_copy(update={"allowed": False, "notes": note})
        sources.append(source)
    return sources


def resolve_source_list_url(
    source: JobSource,
    preference: Optional[JobSearchPreference] = None,
) -> str:
    """Resolve a configured list URL or safe search URL template."""

    return resolve_source_search_url(source, preference).url


def resolve_source_search_url(
    source: JobSource,
    preference: Optional[JobSearchPreference] = None,
) -> SearchUrlBuildResult:
    """Resolve a source URL with an explanatory note for UI/status output."""

    return build_search_url(source, preference or JobSearchPreference())


def build_custom_url_sources(urls: List[str]) -> List[JobSource]:
    """Build public source configs from user-provided one-URL-per-line input."""

    sources: List[JobSource] = []
    for index, raw_url in enumerate(urls, start=1):
        url = normalize_url(raw_url)
        if not is_valid_http_url(url):
            continue
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        sources.append(
            JobSource(
                source_id=f"custom_public_url_{index:03d}",
                source_name=f"自定义公开 URL {index}",
                source_type="public_html",
                base_url=base_url,
                list_url=url,
                enabled=True,
                access_policy="public_only",
                allowed=True,
                notes="仅尝试公开可访问页面；如需登录、验证码或 robots 不允许则跳过。",
            )
        )
    return sources
