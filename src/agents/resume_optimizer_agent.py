"""Resume optimization agent."""

from __future__ import annotations

from typing import List

from src.llm_client import LLMClient
from src.schemas.models import JDAnalysis, OptimizationSuggestion, ResumeAnalysis
from src.utils.text_utils import dedupe_keep_order, split_bullets


class ResumeOptimizerAgent:
    """Rewrite resume bullets without inventing experience."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(self, jd: JDAnalysis, resume: ResumeAnalysis) -> List[OptimizationSuggestion]:
        fallback = [item.model_dump() for item in self._heuristic_optimize(jd, resume)]
        data = self.llm.complete_json(
            system_prompt=(
                "你是简历优化 Agent。输出 JSON："
                '{"suggestions":[{"original_bullet":"","optimized_bullet":"","rationale":"","risk_note":""}]}。'
                "必须遵守：不编造经历，不虚构项目，不添加用户没做过的内容。"
            ),
            user_prompt=f"JD：{jd.model_dump()}\n\n简历：{resume.model_dump()}",
            fallback={"suggestions": fallback},
        )
        return [OptimizationSuggestion(**item) for item in data.get("suggestions", fallback)]

    def _heuristic_optimize(self, jd: JDAnalysis, resume: ResumeAnalysis) -> List[OptimizationSuggestion]:
        bullets = dedupe_keep_order(resume.projects + resume.internships + split_bullets(resume.raw_text))[:8]
        target_terms = jd.hard_skills + jd.tools + jd.business_keywords + jd.implicit_capabilities
        suggestions = []
        for bullet in bullets:
            matched = [term for term in target_terms if term.lower() in bullet.lower()][:4]
            if matched:
                optimized = f"{bullet}（投递版：强化 {'、'.join(matched)} 与真实结果的对应关系）"
                rationale = f"该经历已覆盖 {'、'.join(matched)}，建议把动作、方法和结果写得更具体。"
            else:
                optimized = f"{bullet}（投递版：补充真实任务背景、关键动作、使用工具和量化结果）"
                rationale = "原句有经历基础，但与 JD 关键词连接较弱，需要用真实细节补强。"
            suggestions.append(
                OptimizationSuggestion(
                    original_bullet=bullet,
                    optimized_bullet=optimized,
                    rationale=rationale,
                )
            )
        return suggestions

