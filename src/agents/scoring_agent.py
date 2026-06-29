"""Job-resume match scoring agent."""

from __future__ import annotations

from typing import List

from src.llm_client import LLMClient
from src.schemas.models import EvidenceMatch, JDAnalysis, KeywordCoverage, ResumeAnalysis, ScoreBreakdown, ScoreItem
from src.utils.text_utils import safe_ratio


class ScoringAgent:
    """Score job fit with the required weight scheme."""

    WEIGHTS = {
        "技能匹配": 0.30,
        "项目经历匹配": 0.25,
        "关键词覆盖": 0.20,
        "岗位职责匹配": 0.15,
        "教育/背景匹配": 0.10,
    }

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(
        self,
        jd: JDAnalysis,
        resume: ResumeAnalysis,
        evidence_matches: List[EvidenceMatch],
        keyword_coverage: KeywordCoverage,
    ) -> ScoreBreakdown:
        fallback = self._heuristic_score(jd, resume, evidence_matches, keyword_coverage)
        data = self.llm.complete_json(
            system_prompt=(
                "你是匹配评分 Agent。请输出 JSON：total_score, categories, strengths, risks, summary。"
                "必须按技能30%、项目25%、关键词20%、职责15%、教育背景10%评分。"
            ),
            user_prompt=(
                f"JD：{jd.model_dump()}\n\n简历：{resume.model_dump()}\n\n"
                f"证据：{[item.model_dump() for item in evidence_matches]}\n\n"
                f"关键词覆盖：{keyword_coverage.model_dump()}"
            ),
            fallback=fallback.model_dump(),
        )
        return ScoreBreakdown(**data)

    def _heuristic_score(
        self,
        jd: JDAnalysis,
        resume: ResumeAnalysis,
        evidence_matches: List[EvidenceMatch],
        keyword_coverage: KeywordCoverage,
    ) -> ScoreBreakdown:
        skill_terms = jd.hard_skills + jd.tools
        covered_skills = [
            term for term in skill_terms if term.lower() in " ".join(resume.skills + resume.keywords).lower()
        ]
        skills_score = round(safe_ratio(len(covered_skills), len(skill_terms) or 1) * 100, 1)
        if not skill_terms:
            skills_score = 70.0

        project_scores = [item.strength_score for item in evidence_matches if item.requirement in jd.responsibilities + jd.hard_skills]
        project_score = round(sum(project_scores) / len(project_scores), 1) if project_scores else 55.0

        keyword_score = round(keyword_coverage.coverage_rate * 100, 1)

        responsibility_related = [
            item for item in evidence_matches if item.requirement in jd.responsibilities or len(item.requirement) > 18
        ]
        responsibility_score = (
            round(sum(item.strength_score for item in responsibility_related) / len(responsibility_related), 1)
            if responsibility_related
            else 55.0
        )

        education_score = self._education_score(jd, resume)

        categories = [
            ScoreItem(
                name="技能匹配",
                weight=self.WEIGHTS["技能匹配"],
                score=skills_score,
                reason=f"JD 技能/工具 {len(skill_terms)} 项，简历强覆盖 {len(covered_skills)} 项。",
            ),
            ScoreItem(
                name="项目经历匹配",
                weight=self.WEIGHTS["项目经历匹配"],
                score=project_score,
                reason="基于岗位要求与项目/实习证据强度均值计算。",
            ),
            ScoreItem(
                name="关键词覆盖",
                weight=self.WEIGHTS["关键词覆盖"],
                score=keyword_score,
                reason=keyword_coverage.notes,
            ),
            ScoreItem(
                name="岗位职责匹配",
                weight=self.WEIGHTS["岗位职责匹配"],
                score=responsibility_score,
                reason="根据 JD 职责在简历中的直接证据强度计算。",
            ),
            ScoreItem(
                name="教育/背景匹配",
                weight=self.WEIGHTS["教育/背景匹配"],
                score=education_score,
                reason="根据 JD 学历要求和简历教育背景粗略判断。",
            ),
        ]
        total = round(sum(item.score * item.weight for item in categories), 1)
        strengths = self._strengths(keyword_coverage, evidence_matches)
        risks = self._risks(keyword_coverage, evidence_matches)
        summary = f"当前匹配分为 {total}/100。建议优先补强未覆盖关键词和弱证据职责。"
        return ScoreBreakdown(total_score=total, categories=categories, strengths=strengths, risks=risks, summary=summary)

    def _education_score(self, jd: JDAnalysis, resume: ResumeAnalysis) -> float:
        requirement = jd.education_requirement
        resume_text = " ".join(resume.education)
        if not requirement:
            return 75.0 if resume.education else 60.0
        if "硕士" in requirement and "硕士" in resume_text:
            return 90.0
        if "本科" in requirement and ("本科" in resume_text or "硕士" in resume_text):
            return 85.0
        if any(token in resume_text.lower() for token in ["master", "bachelor", "university"]):
            return 80.0
        return 55.0

    def _strengths(self, coverage: KeywordCoverage, evidence_matches: List[EvidenceMatch]) -> List[str]:
        strong_evidence = [item.requirement for item in evidence_matches if item.strength == "强"][:5]
        return (coverage.covered_keywords[:5] + strong_evidence)[:8]

    def _risks(self, coverage: KeywordCoverage, evidence_matches: List[EvidenceMatch]) -> List[str]:
        missing = coverage.missing_keywords[:5]
        weak_evidence = [item.requirement for item in evidence_matches if item.strength in {"弱", "缺失"}][:5]
        return (missing + weak_evidence)[:8]

