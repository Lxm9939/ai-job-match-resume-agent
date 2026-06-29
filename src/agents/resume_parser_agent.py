"""Resume parsing agent."""

from __future__ import annotations

import re
from typing import List

from src.llm_client import LLMClient
from src.schemas.models import ResumeAnalysis
from src.utils.text_utils import (
    CAPABILITY_KEYWORDS,
    HARD_SKILLS,
    SOFT_SKILLS,
    TOOL_KEYWORDS,
    dedupe_keep_order,
    extract_keywords,
    extract_known_terms,
    extract_metric_lines,
    extract_section_items,
    normalize_text,
    split_bullets,
    split_lines,
)


class ResumeParserAgent:
    """Extract structured facts from a resume."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(self, resume_text: str) -> ResumeAnalysis:
        text = normalize_text(resume_text)
        fallback = self._heuristic_parse(text)
        data = self.llm.complete_json(
            system_prompt=(
                "你是简历解析 Agent。请只输出 JSON，字段必须包括 education, "
                "projects, internships, skills, metrics, keywords, "
                "transferable_capabilities, raw_text。不要编造简历中没有的信息。"
            ),
            user_prompt=f"简历文本：\n{text}",
            fallback=fallback.model_dump(),
        )
        data.setdefault("raw_text", text)
        return ResumeAnalysis(**data)

    def _heuristic_parse(self, text: str) -> ResumeAnalysis:
        skills = dedupe_keep_order(
            extract_known_terms(text, HARD_SKILLS + TOOL_KEYWORDS + SOFT_SKILLS)
            + extract_section_items(text, ["技能", "技能栈", "专业技能", "Skills"])
        )[:40]
        return ResumeAnalysis(
            education=self._extract_education(text),
            projects=self._extract_projects(text),
            internships=self._extract_internships(text),
            skills=skills,
            metrics=extract_metric_lines(text),
            keywords=extract_keywords(text, max_keywords=60),
            transferable_capabilities=self._infer_transferable_capabilities(text),
            raw_text=text,
        )

    def _extract_education(self, text: str) -> List[str]:
        items = extract_section_items(text, ["教育背景", "教育经历", "Education"])
        if items:
            return items[:8]
        return [
            line
            for line in split_lines(text)
            if re.search(r"(大学|学院|本科|硕士|博士|Master|Bachelor|GPA|专业)", line, re.I)
        ][:8]

    def _extract_projects(self, text: str) -> List[str]:
        items = extract_section_items(text, ["项目经历", "项目经验", "Projects", "Project Experience"])
        if items:
            return items[:15]
        return [line for line in split_bullets(text) if "项目" in line or "Project" in line][:15]

    def _extract_internships(self, text: str) -> List[str]:
        items = extract_section_items(text, ["实习经历", "工作经历", "Internship", "Work Experience"])
        if items:
            return items[:15]
        return [
            line
            for line in split_bullets(text)
            if re.search(r"(实习|公司|负责|参与|分析|产品|运营)", line)
        ][:15]

    def _infer_transferable_capabilities(self, text: str) -> List[str]:
        found = extract_known_terms(text, CAPABILITY_KEYWORDS)
        rules = [
            ("SQL" in text or "Python" in text, "数据处理与分析"),
            ("项目" in text or "Project" in text, "项目推进"),
            ("产品" in text or "需求" in text, "需求理解与产品表达"),
            ("可视化" in text or "Tableau" in text or "Power BI" in text, "数据可视化表达"),
            ("模型" in text or "机器学习" in text or "大模型" in text, "AI/模型应用理解"),
        ]
        found.extend(label for matched, label in rules if matched)
        return dedupe_keep_order(found)[:12]

