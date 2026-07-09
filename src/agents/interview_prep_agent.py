"""Interview preparation agent grounded in resume evidence."""

from __future__ import annotations

from typing import List

from src.llm_client import LLMClient
from src.schemas.models import EvidenceMatch, InterviewPrep, JDAnalysis, ResumeAnalysis, ScoreBreakdown
from src.utils.text_utils import dedupe_keep_order


class InterviewPrepAgent:
    """Generate honest interview preparation prompts from known evidence."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(
        self,
        jd: JDAnalysis,
        resume: ResumeAnalysis,
        evidence_matches: List[EvidenceMatch],
        score: ScoreBreakdown,
    ) -> InterviewPrep:
        fallback = self._heuristic_prepare(jd, resume, evidence_matches, score)
        data = self.llm.complete_json(
            system_prompt=(
                "你是面试准备 Agent。请输出 JSON，字段为 likely_questions、project_talking_points、"
                "technical_preparation、business_preparation、risk_questions、suggested_answer_strategy。"
                "只能使用简历已有证据和 JD 要求，不得编造经历。证据不足时必须提示诚实表达。"
            ),
            user_prompt=(
                f"JD：{jd.model_dump()}\n\n简历：{resume.model_dump()}\n\n"
                f"证据匹配：{[item.model_dump() for item in evidence_matches]}\n\n"
                f"匹配评分：{score.model_dump()}"
            ),
            fallback=fallback.model_dump(),
        )
        return InterviewPrep(**data)

    def _heuristic_prepare(
        self,
        jd: JDAnalysis,
        resume: ResumeAnalysis,
        evidence_matches: List[EvidenceMatch],
        score: ScoreBreakdown,
    ) -> InterviewPrep:
        strong_matches = [item for item in evidence_matches if item.strength in {"强", "中"}]
        weak_matches = [item for item in evidence_matches if item.strength in {"弱", "缺失"}]
        requirements = dedupe_keep_order(
            jd.responsibilities + jd.hard_skills + jd.tools + jd.business_keywords
        )

        likely_questions = [
            f"请结合真实项目说明你如何完成「{requirement}」。"
            for requirement in requirements[:4]
        ] or ["请介绍一段与你申请岗位最相关的真实项目经历。"]
        project_points = [
            f"围绕「{item.requirement}」讲清背景、本人动作、方法和真实结果；可引用：{item.resume_evidence[:80]}"
            for item in strong_matches[:4]
        ] or ["选择简历中最相关项目，按背景、任务、行动、结果四步准备，不补写未做过的内容。"]
        technical = [
            f"复习 JD 中的「{term}」，准备说明自己真实使用过的范围和熟练度。"
            for term in dedupe_keep_order(jd.hard_skills + jd.tools)[:4]
        ]
        business = [
            f"了解「{term}」对应的用户、业务目标和衡量指标。"
            for term in dedupe_keep_order(jd.business_keywords + jd.implicit_capabilities)[:4]
        ]
        risk_questions = [
            f"简历对「{item.requirement}」证据{item.strength}，面试官可能追问你是否真正做过及做到什么程度。"
            for item in weak_matches[:4]
        ]
        strategies = [
            "先给结论，再用 STAR 结构讲真实经历，并明确区分个人贡献与团队成果。",
            "遇到没有做过的内容直接说明边界，再补充相邻经验、学习计划和可迁移能力。",
            "量化信息只使用简历中能够核实的数据；没有数据时描述交付物、范围和反馈。",
        ]
        if score.risks:
            strategies.append(f"优先准备这些风险点的诚实说明：{'、'.join(score.risks[:3])}。")

        return InterviewPrep(
            likely_questions=dedupe_keep_order(likely_questions),
            project_talking_points=dedupe_keep_order(project_points),
            technical_preparation=dedupe_keep_order(technical),
            business_preparation=dedupe_keep_order(business),
            risk_questions=dedupe_keep_order(risk_questions),
            suggested_answer_strategy=dedupe_keep_order(strategies),
        )
