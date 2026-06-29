"""Final report generation agent."""

from __future__ import annotations

from typing import List

from src.llm_client import LLMClient
from src.schemas.models import (
    EvidenceMatch,
    FinalReport,
    JDAnalysis,
    KeywordCoverage,
    OptimizationSuggestion,
    OutreachMessages,
    ResumeAnalysis,
    ScoreBreakdown,
)
from src.utils.text_utils import markdown_table


class ReportAgent:
    """Integrate all intermediate outputs into a Markdown report."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(
        self,
        jd: JDAnalysis,
        resume: ResumeAnalysis,
        evidence_matches: List[EvidenceMatch],
        keyword_coverage: KeywordCoverage,
        score: ScoreBreakdown,
        optimization_suggestions: List[OptimizationSuggestion],
        outreach: OutreachMessages,
    ) -> FinalReport:
        fallback = self._build_markdown(
            jd, resume, evidence_matches, keyword_coverage, score, optimization_suggestions, outreach
        )
        data = self.llm.complete_json(
            system_prompt="你是最终报告 Agent。请输出 JSON：{'markdown':'完整 Markdown 报告'}。",
            user_prompt=(
                f"JD：{jd.model_dump()}\n\n简历：{resume.model_dump()}\n\n"
                f"证据：{[item.model_dump() for item in evidence_matches]}\n\n"
                f"关键词：{keyword_coverage.model_dump()}\n\n评分：{score.model_dump()}\n\n"
                f"优化建议：{[item.model_dump() for item in optimization_suggestions]}\n\n"
                f"话术：{outreach.model_dump()}"
            ),
            fallback={"markdown": fallback},
        )
        return FinalReport(markdown=data.get("markdown", fallback))

    def _build_markdown(
        self,
        jd: JDAnalysis,
        resume: ResumeAnalysis,
        evidence_matches: List[EvidenceMatch],
        keyword_coverage: KeywordCoverage,
        score: ScoreBreakdown,
        optimization_suggestions: List[OptimizationSuggestion],
        outreach: OutreachMessages,
    ) -> str:
        score_rows = [
            [item.name, f"{int(item.weight * 100)}%", item.score, item.reason] for item in score.categories
        ]
        evidence_rows = [
            [item.requirement, item.resume_evidence, item.strength, item.suggested_expression]
            for item in evidence_matches[:12]
        ]
        optimize_rows = [
            [item.original_bullet, item.optimized_bullet, item.rationale] for item in optimization_suggestions[:8]
        ]
        return "\n\n".join(
            [
                "# AI 秋招岗位匹配报告",
                f"## 1. 结论\n当前岗位：**{jd.job_title or '未识别'}**；匹配分：**{score.total_score}/100**。\n\n{score.summary}",
                "## 2. JD 解析\n"
                f"- 公司：{jd.company or '未识别'}\n"
                f"- 地点：{jd.location or '未识别'}\n"
                f"- 硬技能：{', '.join(jd.hard_skills) or '未明显提及'}\n"
                f"- 工具栈：{', '.join(jd.tools) or '未明显提及'}\n"
                f"- 业务关键词：{', '.join(jd.business_keywords) or '未明显提及'}\n"
                f"- 隐含能力：{', '.join(jd.implicit_capabilities) or '未明显提及'}",
                "## 3. 简历概览\n"
                f"- 教育背景：{'; '.join(resume.education[:3]) or '未识别'}\n"
                f"- 技能栈：{', '.join(resume.skills[:12]) or '未识别'}\n"
                f"- 可迁移能力：{', '.join(resume.transferable_capabilities) or '未识别'}",
                "## 4. 证据匹配\n" + markdown_table(["岗位要求", "简历证据", "强度", "建议"], evidence_rows),
                "## 5. 关键词覆盖\n"
                f"- 已覆盖：{', '.join(keyword_coverage.covered_keywords) or '无'}\n"
                f"- 弱覆盖：{', '.join(keyword_coverage.weak_keywords) or '无'}\n"
                f"- 未覆盖：{', '.join(keyword_coverage.missing_keywords) or '无'}",
                "## 6. 评分明细\n" + markdown_table(["维度", "权重", "得分", "原因"], score_rows),
                "## 7. 简历优化建议\n"
                + markdown_table(["修改前", "修改后", "理由"], optimize_rows),
                "## 8. 投递话术\n"
                f"### Boss 直聘\n{outreach.boss_zhipin}\n\n"
                f"### 邮件正文\n{outreach.email_body}\n\n"
                f"### LinkedIn 私信\n{outreach.linkedin_dm}\n\n"
                f"### 内推请求\n{outreach.referral_request}\n\n"
                f"### 面试自我介绍\n{outreach.interview_intro}",
            ]
        )

