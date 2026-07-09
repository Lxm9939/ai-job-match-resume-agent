"""Load and validate user-managed public job source configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from src.schemas.models import JobSource


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_CONFIG = PROJECT_ROOT / "configs" / "job_sources.example.json"
FORBIDDEN_SOURCE_DOMAINS = {
    "zhipin.com",
    "www.zhipin.com",
    "zhaopin.com",
    "www.zhaopin.com",
    "liepin.com",
    "www.liepin.com",
    "51job.com",
    "www.51job.com",
    "lagou.com",
    "www.lagou.com",
}
SUPPORTED_SOURCE_TYPES = {"public_html"}


def load_job_sources(
    *,
    content: Optional[bytes] = None,
    path: Optional[Path] = None,
) -> List[JobSource]:
    """Load source JSON while disabling unsupported or prohibited sources."""

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
        if source.source_type not in SUPPORTED_SOURCE_TYPES:
            reasons.append(f"当前不支持 source_type={source.source_type}")
        for url in (source.base_url, source.list_url):
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                reasons.append("仅允许公开 http/https URL")
                break
            if parsed.netloc.lower() in FORBIDDEN_SOURCE_DOMAINS:
                reasons.append("该域名属于禁止抓取的登录或强反爬招聘平台")
                break
        if reasons:
            note = "；".join(filter(None, [source.notes, *reasons]))
            source = source.model_copy(update={"allowed": False, "notes": note})
        sources.append(source)
    return sources

