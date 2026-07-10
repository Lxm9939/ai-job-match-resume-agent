"""Build public job search URLs from source templates and user preferences."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, quote_plus

from src.schemas.models import JobSearchPreference, JobSource
from src.url_utils import normalize_url


BOSS_CITY_CODES = {
    "全国": "100010000",
    "北京": "101010100",
    "上海": "101020100",
    "杭州": "101210100",
    "深圳": "101280600",
    "广州": "101280100",
    "成都": "101270100",
    "南京": "101190100",
    "苏州": "101190400",
    "远程": "100010000",
    "海外": "100010000",
}
LIEPIN_CITY_CODES = {
    "全国": "",
    "北京": "010",
    "上海": "020",
    "杭州": "070020",
    "深圳": "050090",
    "广州": "050020",
    "成都": "280020",
    "南京": "060020",
    "苏州": "060080",
    "远程": "",
    "海外": "",
}
SEEK_LOCATION_SLUGS = {
    "全国": "all-australia",
    "北京": "all-australia",
    "上海": "all-australia",
    "杭州": "all-australia",
    "深圳": "all-australia",
    "广州": "all-australia",
    "成都": "all-australia",
    "南京": "all-australia",
    "苏州": "all-australia",
    "远程": "work-from-home",
    "海外": "all-australia",
}


@dataclass(frozen=True)
class SearchUrlBuildResult:
    url: str = ""
    note: str = ""
    auto_generated: bool = False


def build_search_url(
    source: JobSource,
    preference: JobSearchPreference | None = None,
) -> SearchUrlBuildResult:
    """Build a search URL from an explicit URL or template."""

    if source.list_url.strip():
        url = normalize_url(source.list_url, source.base_url)
        return SearchUrlBuildResult(
            url=url,
            note="使用配置中的公开列表 URL" if url else "配置的 list_url 不是有效公开 URL",
            auto_generated=False,
        )

    template = source.list_url_template.strip()
    if not template:
        return SearchUrlBuildResult(
            note=(
                "该来源未配置稳定公开搜索 URL，请在“自定义公开 URL”中提供具体页面，"
                "或使用 CSV/Excel/JD 文本导入。"
            ),
            auto_generated=False,
        )

    preference = preference or JobSearchPreference()
    keyword = _keyword(preference)
    city = _city(preference)
    values = _template_values(source, keyword, city)
    try:
        resolved = template.format(**values)
    except KeyError as exc:
        return SearchUrlBuildResult(
            note=f"搜索 URL 模板缺少参数：{exc}",
            auto_generated=False,
        )

    url = normalize_url(resolved, source.base_url)
    note = _build_note(source, city, values)
    return SearchUrlBuildResult(url=url, note=note, auto_generated=bool(url))


def _keyword(preference: JobSearchPreference) -> str:
    return (
        preference.target_role
        or (preference.keywords[0] if preference.keywords else "")
        or "AI"
    )


def _city(preference: JobSearchPreference) -> str:
    return preference.target_cities[0] if preference.target_cities else "全国"


def _template_values(source: JobSource, keyword: str, city: str) -> dict[str, str]:
    source_id = source.source_id.lower()
    city_code = ""
    location_slug = _slug(city)
    if "boss" in source_id or "zhipin" in source_id:
        city_code = BOSS_CITY_CODES.get(city, BOSS_CITY_CODES["全国"])
    elif "liepin" in source_id:
        city_code = LIEPIN_CITY_CODES.get(city, "")
    elif "seek" in source_id:
        location_slug = SEEK_LOCATION_SLUGS.get(city, "all-australia")

    return {
        "keyword": quote_plus(keyword),
        "query": quote_plus(keyword),
        "city": quote_plus(city),
        "city_code": city_code,
        "location": quote_plus(city),
        "location_slug": location_slug,
    }


def _slug(value: str) -> str:
    normalized = "-".join(part for part in value.lower().split() if part)
    return quote(normalized or "all", safe="-")


def _build_note(source: JobSource, city: str, values: dict[str, str]) -> str:
    source_id = source.source_id.lower()
    if "seek" in source_id and city not in SEEK_LOCATION_SLUGS:
        return "已生成搜索 URL；城市无法映射到 Seek location，使用默认地区。"
    if "liepin" in source_id and not values.get("city_code"):
        return "已生成搜索 URL；城市无法映射到猎聘 dqs，使用不限地区。"
    if ("boss" in source_id or "zhipin" in source_id) and city not in BOSS_CITY_CODES:
        return "已生成搜索 URL；城市无法映射到 Boss city_code，使用全国。"
    return "已根据关键词和城市生成公开搜索 URL。"
