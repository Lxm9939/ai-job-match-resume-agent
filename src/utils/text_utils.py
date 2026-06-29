"""Text processing helpers for the MVP heuristic agents."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence


HARD_SKILLS = [
    "Python",
    "SQL",
    "R",
    "Excel",
    "Tableau",
    "Power BI",
    "数据分析",
    "数据建模",
    "机器学习",
    "深度学习",
    "NLP",
    "大模型",
    "LLM",
    "A/B测试",
    "用户研究",
    "需求分析",
    "竞品分析",
    "产品设计",
    "数据产品",
    "指标体系",
    "可视化",
    "爬虫",
    "统计分析",
    "Prompt Engineering",
    "RAG",
    "Agent",
]

TOOL_KEYWORDS = [
    "Python",
    "SQL",
    "MySQL",
    "PostgreSQL",
    "Hive",
    "Spark",
    "Excel",
    "Power BI",
    "Tableau",
    "Figma",
    "Axure",
    "Jira",
    "Confluence",
    "Git",
    "OpenAI",
    "LangChain",
    "FastAPI",
    "Streamlit",
]

SOFT_SKILLS = [
    "沟通",
    "协作",
    "跨部门",
    "逻辑",
    "学习能力",
    "自驱",
    "owner意识",
    "项目管理",
    "问题拆解",
    "英文",
]

BUSINESS_KEYWORDS = [
    "用户增长",
    "留存",
    "转化",
    "商业化",
    "风控",
    "推荐",
    "搜索",
    "内容",
    "电商",
    "广告",
    "金融",
    "教育",
    "SaaS",
    "B端",
    "C端",
    "CRM",
    "BI",
    "数据中台",
    "AI Agent",
    "智能体",
]

CAPABILITY_KEYWORDS = [
    "需求拆解",
    "指标设计",
    "数据驱动决策",
    "结构化表达",
    "业务理解",
    "实验设计",
    "问题定位",
    "方案落地",
    "结果复盘",
]


def normalize_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str) -> List[str]:
    return [line.strip() for line in normalize_text(text).split("\n") if line.strip()]


def clean_bullet(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\-\*\u2022\u00b7●▪▫◆◇\d\.、\)\s]+", "", line)
    return line.strip()


def split_bullets(text: str, min_len: int = 8) -> List[str]:
    bullets: List[str] = []
    for line in split_lines(text):
        cleaned = clean_bullet(line)
        if len(cleaned) >= min_len:
            bullets.append(cleaned)
    return dedupe_keep_order(bullets)


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        value = str(item).strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def contains_any(text: str, keywords: Sequence[str]) -> bool:
    lower_text = text.lower()
    return any(keyword.lower() in lower_text for keyword in keywords if keyword)


def extract_known_terms(text: str, candidates: Sequence[str]) -> List[str]:
    lower_text = normalize_text(text).lower()
    found = []
    for term in candidates:
        if term.lower() in lower_text:
            found.append(term)
    return dedupe_keep_order(found)


def extract_keywords(text: str, max_keywords: int = 40) -> List[str]:
    text = normalize_text(text)
    curated = extract_known_terms(
        text,
        HARD_SKILLS + TOOL_KEYWORDS + SOFT_SKILLS + BUSINESS_KEYWORDS + CAPABILITY_KEYWORDS,
    )
    english_terms = re.findall(r"\b[A-Za-z][A-Za-z0-9+#./-]{1,}\b", text)
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    noisy = {"岗位", "职责", "要求", "工作", "负责", "相关", "能力", "优先", "参与"}
    selected = []
    for token in english_terms + chinese_chunks:
        if token in noisy:
            continue
        if len(token) <= 1:
            continue
        if len(token) > 16:
            continue
        selected.append(token)
    return dedupe_keep_order(curated + selected)[:max_keywords]


def extract_section_items(text: str, headings: Sequence[str]) -> List[str]:
    lines = split_lines(text)
    items: List[str] = []
    active = False
    heading_pattern = re.compile("|".join(re.escape(h) for h in headings), re.I)
    stop_pattern = re.compile(
        r"(教育|项目|实习|工作经历|技能|证书|自我评价|岗位要求|任职要求|加分项|Qualifications|Requirements|Skills)",
        re.I,
    )
    for line in lines:
        clean = clean_bullet(line)
        if heading_pattern.search(line):
            active = True
            tail = heading_pattern.sub("", clean).strip(":： -")
            if tail and len(tail) > 6:
                items.append(tail)
            continue
        if active and stop_pattern.search(line) and not heading_pattern.search(line):
            break
        if active and len(clean) > 6:
            items.append(clean)
    return dedupe_keep_order(items)


def find_sentences_with_keywords(text: str, keywords: Sequence[str], limit: int = 3) -> List[str]:
    chunks = re.split(r"[\n。；;.!?？]+", normalize_text(text))
    matches = []
    for chunk in chunks:
        cleaned = clean_bullet(chunk)
        if len(cleaned) < 6:
            continue
        if contains_any(cleaned, keywords):
            matches.append(cleaned)
    return dedupe_keep_order(matches)[:limit]


def extract_metric_lines(text: str) -> List[str]:
    metric_pattern = re.compile(r"(\d+(\.\d+)?%|\d+(\.\d+)?\s*(万|千|百|个|人|次|小时|天|周|月|年|k|K|w|W|\+))")
    return [
        line
        for line in split_bullets(text, min_len=6)
        if metric_pattern.search(line) or re.search(r"(提升|降低|增长|节省|覆盖|转化|留存)", line)
    ][:20]


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = []
    for row in rows:
        values = [str(value).replace("\n", "<br>") for value in row]
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header_line, divider] + body)
