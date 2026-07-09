"""V2 batch job matching workflow."""

from __future__ import annotations

from typing import List, Optional

from src.agents.batch_matching_agent import BatchMatchingAgent
from src.agents.resume_parser_agent import ResumeParserAgent
from src.llm_client import LLMClient
from src.schemas.models import (
    BatchMatchResult,
    JobMatchResult,
    JobPosting,
    JobPreferences,
    ResumeAnalysis,
)
from src.utils.text_utils import dedupe_keep_order, markdown_table, normalize_text


class BatchMatchWorkflow:
    """Parse one resume once, then rank and explain multiple job matches."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.resume_parser = ResumeParserAgent(self.llm_client)
        self.batch_matching_agent = BatchMatchingAgent(self.llm_client)

    def run(
        self,
        resume_text: str,
        jobs: List[JobPosting],
        preferences: Optional[JobPreferences] = None,
    ) -> BatchMatchResult:
        resume_text = normalize_text(resume_text)
        if not resume_text:
            raise ValueError("简历文本为空，请上传简历或粘贴简历文本。")
        if not jobs:
            raise ValueError("岗位列表为空，请上传 CSV/Excel 或粘贴多个 JD。")

        preferences = preferences or JobPreferences()
        resume = self.resume_parser.run(resume_text)
        ranked_jobs = self.batch_matching_agent.run(
            resume,
            jobs,
            target_role=preferences.target_role,
            candidate_type=preferences.candidate_type,
        )
        ranked_jobs = [self._add_preference_context(item, preferences) for item in ranked_jobs]
        resume_summary = self._resume_summary(resume)
        preference_summary = self._preference_summary(preferences)
        best_matches = [item for item in ranked_jobs if item.total_score >= 65][:5]
        risky_matches = [item for item in ranked_jobs if item.total_score < 50]
        final_summary = self._final_summary(ranked_jobs)
        report = self._build_markdown_report(
            resume_summary,
            preference_summary,
            ranked_jobs,
            final_summary,
        )
        return BatchMatchResult(
            resume_summary=resume_summary,
            preference_summary=preference_summary,
            ranked_jobs=ranked_jobs,
            best_matches=best_matches,
            risky_matches=risky_matches,
            final_summary=final_summary,
            report_markdown=report,
        )

    def _add_preference_context(
        self,
        result: JobMatchResult,
        preferences: JobPreferences,
    ) -> JobMatchResult:
        strengths = list(result.strengths)
        risks = list(result.risks)
        if preferences.target_role:
            if self._matches_preference(result.job.job_title, preferences.target_role):
                strengths.append(f"目标方向匹配：{result.job.job_title}")
        if preferences.target_city:
            if self._matches_preference(result.job.city, preferences.target_city):
                strengths.append(f"城市偏好匹配：{result.job.city}")
            elif result.job.city != "城市未知":
                risks.append(f"城市与偏好不一致：岗位在{result.job.city}")
        if preferences.job_type:
            if self._matches_preference(result.job.job_type, preferences.job_type):
                strengths.append(f"岗位类型偏好匹配：{result.job.job_type}")
            elif result.job.job_type != "岗位类型未知":
                risks.append(f"岗位类型与偏好不一致：{result.job.job_type}")
        if preferences.company_preference and self._matches_company_preference(
            result.job,
            preferences.company_preference,
        ):
            strengths.append(f"公司偏好匹配：{preferences.company_preference}")
        return result.model_copy(
            update={
                "strengths": dedupe_keep_order(strengths),
                "risks": dedupe_keep_order(risks),
            }
        )

    def _matches_preference(self, actual: str, preferred: str) -> bool:
        preferred_values = [
            value.strip().lower()
            for value in preferred.replace("，", ",").replace("、", ",").split(",")
            if value.strip()
        ]
        actual_lower = actual.lower()
        return any(value in actual_lower or actual_lower in value for value in preferred_values)

    def _matches_company_preference(self, job: JobPosting, preferred: str) -> bool:
        text = f"{job.company} {job.jd_text}".lower()
        preference_rules = {
            "ai 公司": ("ai", "人工智能", "大模型"),
            "互联网": ("互联网", "电商", "平台", "用户增长"),
            "国企": ("国企", "国有"),
            "制造业": ("制造", "工业", "供应链"),
            "数据平台": ("数据平台", "数据仓库", "bi"),
        }
        values = [
            value.strip().lower()
            for value in preferred.replace("，", ",").replace("、", ",").split(",")
            if value.strip()
        ]
        for value in values:
            if value in text:
                return True
            terms = preference_rules.get(value, ())
            if any(term in text for term in terms):
                return True
        return False

    def _resume_summary(self, resume: ResumeAnalysis) -> str:
        skill_text = "、".join(resume.skills[:8]) or "未识别明确技能"
        return (
            f"识别到教育经历 {len(resume.education)} 条、项目经历 {len(resume.projects)} 条、"
            f"实习/工作经历 {len(resume.internships)} 条；主要技能：{skill_text}。"
        )

    def _preference_summary(self, preferences: JobPreferences) -> str:
        entries = [
            f"求职阶段：{preferences.candidate_type or '未限定'}",
            f"目标方向：{preferences.target_role or '未限定'}",
            f"目标城市：{preferences.target_city or '未限定'}",
            f"岗位类型：{preferences.job_type or '未限定'}",
            f"公司偏好：{preferences.company_preference or '未限定'}",
        ]
        return "；".join(entries)

    def _final_summary(self, ranked_jobs: List[JobMatchResult]) -> str:
        top = ranked_jobs[0]
        recommend_count = len([item for item in ranked_jobs if item.total_score >= 65])
        return (
            f"本次共分析 {len(ranked_jobs)} 个岗位，{recommend_count} 个达到建议投递区间。"
            f"当前最高匹配为 {top.job.company} 的 {top.job.job_title}（{top.total_score}/100）。"
            "建议优先处理高分岗位，并在投递前核对缺失关键词与证据边界。"
        )

    def _build_markdown_report(
        self,
        resume_summary: str,
        preference_summary: str,
        ranked_jobs: List[JobMatchResult],
        final_summary: str,
    ) -> str:
        ranking_rows = [
            [
                index,
                item.job.job_title,
                item.job.company,
                item.job.city,
                item.job.job_type,
                item.total_score,
                item.skill_score,
                item.project_score,
                item.keyword_score,
                item.recommendation,
            ]
            for index, item in enumerate(ranked_jobs, start=1)
        ]
        sections = [
            "# 批量岗位匹配推荐报告",
            "",
            "## 简历能力摘要",
            resume_summary,
            "",
            "## 求职偏好",
            preference_summary,
            "",
            "## 岗位匹配排行榜",
            markdown_table(
                [
                    "排名",
                    "岗位",
                    "公司",
                    "城市",
                    "类型",
                    "总分",
                    "技能",
                    "项目",
                    "关键词",
                    "推荐结论",
                ],
                ranking_rows,
            ),
            "",
        ]
        for index, item in enumerate(ranked_jobs, start=1):
            sections.extend(self._job_detail_markdown(index, item))
        sections.extend(["## 最终结论", final_summary])
        return "\n".join(sections)

    def _job_detail_markdown(self, rank: int, result: JobMatchResult) -> List[str]:
        evidence_rows = [
            [
                item.requirement,
                item.resume_evidence,
                item.strength,
                item.suggested_expression,
            ]
            for item in result.evidence_matches
        ]
        optimization_rows = [
            [item.original_bullet, item.optimized_bullet, item.rationale]
            for item in result.optimization_suggestions
        ]
        prep = result.interview_prep
        return [
            f"## {rank}. {result.job.job_title}｜{result.job.company}",
            "",
            f"- 匹配总分：{result.total_score}/100",
            f"- 推荐结论：{result.recommendation}",
            f"- 城市/类型：{result.job.city} / {result.job.job_type}",
            f"- 来源链接：{result.job.source_url or '未提供'}",
            f"- 已覆盖关键词：{'、'.join(result.keyword_coverage.covered_keywords) or '无'}",
            f"- 未覆盖关键词：{'、'.join(result.missing_keywords) or '无'}",
            "",
            "### 简历证据匹配",
            markdown_table(["岗位要求", "简历证据", "强度", "建议表达"], evidence_rows),
            "",
            "### 简历优化建议",
            markdown_table(["修改前", "修改后", "原因"], optimization_rows),
            "",
            "### 面试准备",
            f"- 可能问题：{'；'.join(prep.likely_questions) or '暂无'}",
            f"- 项目讲解：{'；'.join(prep.project_talking_points) or '暂无'}",
            f"- 技术准备：{'；'.join(prep.technical_preparation) or '暂无'}",
            f"- 业务准备：{'；'.join(prep.business_preparation) or '暂无'}",
            f"- 风险追问：{'；'.join(prep.risk_questions) or '暂无'}",
            f"- 回答策略：{'；'.join(prep.suggested_answer_strategy) or '暂无'}",
            "",
            "### 投递话术",
            result.outreach_messages.boss_zhipin,
            "",
        ]
