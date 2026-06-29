"""Evidence mapping agent."""

from __future__ import annotations

from typing import List

from src.llm_client import LLMClient
from src.schemas.models import EvidenceMatch, JDAnalysis, ResumeAnalysis
from src.utils.text_utils import dedupe_keep_order, extract_keywords, find_sentences_with_keywords


class EvidenceAgent:
    """Map JD requirements to concrete resume evidence."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(self, jd: JDAnalysis, resume: ResumeAnalysis) -> List[EvidenceMatch]:
        fallback = [match.model_dump() for match in self._heuristic_match(jd, resume)]
        data = self.llm.complete_json(
            system_prompt=(
                "你是简历证据提取 Agent。请输出 JSON："
                '{"matches":[{"requirement":"","resume_evidence":"","strength":"","strength_score":0,'
                '"suggested_expression":""}]}。必须基于简历原文，不要编造经历。'
            ),
            user_prompt=f"JD 结构化信息：{jd.model_dump()}\n\n简历结构化信息：{resume.model_dump()}",
            fallback={"matches": fallback},
        )
        matches = data.get("matches", fallback)
        return [EvidenceMatch(**item) for item in matches]

    def _heuristic_match(self, jd: JDAnalysis, resume: ResumeAnalysis) -> List[EvidenceMatch]:
        requirements = dedupe_keep_order(
            jd.hard_skills
            + jd.tools
            + jd.business_keywords
            + jd.responsibilities[:8]
            + jd.implicit_capabilities[:8]
        )[:20]
        resume_keywords = {keyword.lower() for keyword in resume.keywords + resume.skills}
        results: List[EvidenceMatch] = []
        for requirement in requirements:
            req_keywords = extract_keywords(requirement, max_keywords=8) or [requirement]
            evidence = find_sentences_with_keywords(resume.raw_text, req_keywords, limit=2)
            exact_hit = any(keyword.lower() in resume_keywords for keyword in req_keywords)
            if evidence and exact_hit:
                strength, score = "强", 85
            elif evidence:
                strength, score = "中", 65
            elif any(capability in requirement for capability in resume.transferable_capabilities):
                strength, score = "弱", 45
            else:
                strength, score = "缺失", 15
            evidence_text = "；".join(evidence) if evidence else "未在简历中找到直接证据"
            suggestion = self._suggest(requirement, evidence_text, strength)
            results.append(
                EvidenceMatch(
                    requirement=requirement,
                    resume_evidence=evidence_text,
                    strength=strength,
                    strength_score=score,
                    suggested_expression=suggestion,
                )
            )
        return results

    def _suggest(self, requirement: str, evidence: str, strength: str) -> str:
        if strength == "缺失":
            return f"如你确实做过，请补充与「{requirement}」相关的真实项目、工具、动作和结果；不要虚构。"
        if strength == "弱":
            return f"将现有经历改写为 STAR：背景、你负责的动作、与「{requirement}」的关系、真实结果。"
        return f"把「{evidence[:40]}」补成可投递表达：动作 + 工具/方法 + 量化结果 + 业务影响。"

