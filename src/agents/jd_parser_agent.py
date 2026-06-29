"""JD parsing agent."""

from __future__ import annotations

import re
from typing import List

from src.llm_client import LLMClient
from src.schemas.models import JDAnalysis
from src.utils.text_utils import (
    BUSINESS_KEYWORDS,
    CAPABILITY_KEYWORDS,
    HARD_SKILLS,
    SOFT_SKILLS,
    TOOL_KEYWORDS,
    dedupe_keep_order,
    extract_known_terms,
    extract_section_items,
    normalize_text,
    split_bullets,
    split_lines,
)


class JDParserAgent:
    """Extract structured role requirements from a job description."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(self, jd_text: str, target_role: str = "") -> JDAnalysis:
        text = normalize_text(jd_text)
        fallback = self._heuristic_parse(text, target_role)
        data = self.llm.complete_json(
            system_prompt=(
                "你是招聘 JD 解析 Agent。请只输出 JSON，字段必须包括 "
                "job_title, company, location, responsibilities, hard_skills, "
                "soft_skills, tools, business_keywords, education_requirement, "
                "experience_requirement, implicit_capabilities, raw_text。"
            ),
            user_prompt=f"目标岗位方向：{target_role}\n\n岗位 JD：\n{text}",
            fallback=fallback.model_dump(),
        )
        data.setdefault("raw_text", text)
        return JDAnalysis(**data)

    def _heuristic_parse(self, text: str, target_role: str) -> JDAnalysis:
        lines = split_lines(text)
        responsibilities = self._extract_responsibilities(text)
        hard_skills = extract_known_terms(text, HARD_SKILLS)
        soft_skills = extract_known_terms(text, SOFT_SKILLS)
        tools = extract_known_terms(text, TOOL_KEYWORDS)
        business_keywords = extract_known_terms(text, BUSINESS_KEYWORDS)
        implicit = self._infer_capabilities(text, target_role)
        return JDAnalysis(
            job_title=self._extract_job_title(lines, target_role),
            company=self._extract_field(lines, ["公司", "Company", "企业", "雇主"]),
            location=self._extract_field(lines, ["地点", "工作地点", "Location", "城市"]),
            responsibilities=responsibilities,
            hard_skills=hard_skills,
            soft_skills=soft_skills,
            tools=tools,
            business_keywords=business_keywords,
            education_requirement=self._extract_education(text),
            experience_requirement=self._extract_experience(text),
            implicit_capabilities=implicit,
            raw_text=text,
        )

    def _extract_responsibilities(self, text: str) -> List[str]:
        headings = ["岗位职责", "工作职责", "工作内容", "职责描述", "Responsibilities", "What you will do"]
        items = extract_section_items(text, headings)
        if items:
            return items[:12]
        candidates = []
        for bullet in split_bullets(text):
            if re.search(r"(负责|参与|推动|协同|完成|搭建|分析|设计|优化|支持)", bullet):
                candidates.append(bullet)
        return dedupe_keep_order(candidates)[:12]

    def _extract_job_title(self, lines: List[str], target_role: str) -> str:
        patterns = [r"岗位[:：]\s*(.+)", r"职位[:：]\s*(.+)", r"Job Title[:：]\s*(.+)"]
        for line in lines[:8]:
            for pattern in patterns:
                match = re.search(pattern, line, re.I)
                if match:
                    return match.group(1).strip()
        for line in lines[:5]:
            if any(token in line for token in ["实习", "产品", "分析", "算法", "运营", "工程师"]):
                return line[:40]
        return target_role or "未识别岗位"

    def _extract_field(self, lines: List[str], labels: List[str]) -> str:
        label_pattern = "|".join(re.escape(label) for label in labels)
        pattern = re.compile(rf"({label_pattern})\s*[:：]\s*(.+)", re.I)
        for line in lines[:15]:
            match = pattern.search(line)
            if match:
                return match.group(2).strip()
        return ""

    def _extract_education(self, text: str) -> str:
        snippets = []
        for line in split_lines(text):
            if re.search(r"(本科|硕士|博士|研究生|学历|Bachelor|Master|PhD)", line, re.I):
                snippets.append(line)
        return "；".join(dedupe_keep_order(snippets)[:3])

    def _extract_experience(self, text: str) -> str:
        snippets = []
        for line in split_lines(text):
            if re.search(r"(\d+\s*(年|年以上|年及以上|years?)|经验|实习经历)", line, re.I):
                snippets.append(line)
        return "；".join(dedupe_keep_order(snippets)[:3])

    def _infer_capabilities(self, text: str, target_role: str) -> List[str]:
        inferred = extract_known_terms(text, CAPABILITY_KEYWORDS)
        lower_text = text.lower()
        if "产品" in target_role or "产品" in text:
            inferred.extend(["需求拆解", "跨团队沟通", "PRD/原型表达", "用户价值判断"])
        if "数据" in target_role or "数据" in text:
            inferred.extend(["指标设计", "数据驱动决策", "问题定位", "结果复盘"])
        if "agent" in lower_text or "大模型" in text or "AI" in target_role.upper():
            inferred.extend(["AI 场景理解", "Prompt/工作流拆解", "模型效果评估"])
        return dedupe_keep_order(inferred)[:12]

