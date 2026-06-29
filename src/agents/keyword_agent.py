"""Keyword coverage agent."""

from __future__ import annotations

from src.llm_client import LLMClient
from src.schemas.models import JDAnalysis, KeywordCoverage, ResumeAnalysis
from src.utils.text_utils import dedupe_keep_order, dedupe_keyword_groups, extract_keywords, safe_ratio


SYNONYMS = {
    "A/B测试": ["ab test", "实验", "分组实验"],
    "可视化": ["dashboard", "看板", "报表"],
    "数据分析": ["analysis", "analytics", "分析"],
    "需求分析": ["需求", "PRD", "用户故事"],
    "大模型": ["LLM", "生成式AI", "OpenAI"],
    "AI Agent": ["Agent", "智能体", "工作流"],
    "指标体系": ["指标", "metrics", "口径"],
}


class KeywordAgent:
    """Compare JD keywords with resume keywords."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(self, jd: JDAnalysis, resume: ResumeAnalysis) -> KeywordCoverage:
        fallback = self._heuristic_coverage(jd, resume)
        data = self.llm.complete_json(
            system_prompt=(
                "你是关键词覆盖 Agent。请输出 JSON，字段为 covered_keywords, "
                "weak_keywords, missing_keywords, coverage_rate, notes。"
            ),
            user_prompt=f"JD：{jd.model_dump()}\n\n简历：{resume.model_dump()}",
            fallback=fallback.model_dump(),
        )
        return self._normalize_coverage(KeywordCoverage(**data))

    def _heuristic_coverage(self, jd: JDAnalysis, resume: ResumeAnalysis) -> KeywordCoverage:
        jd_keywords = dedupe_keep_order(
            jd.hard_skills
            + jd.tools
            + jd.business_keywords
            + jd.soft_skills
            + jd.implicit_capabilities
            + extract_keywords(" ".join(jd.responsibilities), max_keywords=25)
        )[:50]
        resume_text = resume.raw_text.lower()
        resume_keywords = {keyword.lower() for keyword in resume.keywords + resume.skills}
        covered = []
        weak = []
        missing = []
        for keyword in jd_keywords:
            lower_keyword = keyword.lower()
            if lower_keyword in resume_text or lower_keyword in resume_keywords:
                covered.append(keyword)
            elif self._has_synonym(keyword, resume_text):
                weak.append(keyword)
            else:
                missing.append(keyword)
        covered, weak, missing = dedupe_keyword_groups(covered, weak, missing)
        coverage_rate = safe_ratio(len(covered), len(covered) + len(weak) + len(missing))
        notes = (
            f"JD 关键词共 {len(covered) + len(weak) + len(missing)} 个；强覆盖 {len(covered)} 个，"
            f"弱覆盖 {len(weak)} 个，未覆盖 {len(missing)} 个。"
        )
        return KeywordCoverage(
            covered_keywords=covered,
            weak_keywords=weak,
            missing_keywords=missing,
            coverage_rate=round(coverage_rate, 2),
            notes=notes,
        )

    def _has_synonym(self, keyword: str, resume_text: str) -> bool:
        for synonym in SYNONYMS.get(keyword, []):
            if synonym.lower() in resume_text:
                return True
        return False

    def _normalize_coverage(self, coverage: KeywordCoverage) -> KeywordCoverage:
        covered, weak, missing = dedupe_keyword_groups(
            coverage.covered_keywords,
            coverage.weak_keywords,
            coverage.missing_keywords,
        )
        total = len(covered) + len(weak) + len(missing)
        return KeywordCoverage(
            covered_keywords=covered,
            weak_keywords=weak,
            missing_keywords=missing,
            coverage_rate=round(safe_ratio(len(covered), total), 2) if total else coverage.coverage_rate,
            notes=(
                f"JD 关键词共 {total} 个；强覆盖 {len(covered)} 个，"
                f"弱覆盖 {len(weak)} 个，未覆盖 {len(missing)} 个。"
            )
            if total
            else coverage.notes,
        )
