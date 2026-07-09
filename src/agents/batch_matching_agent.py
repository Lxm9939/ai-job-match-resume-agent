"""Batch job matching agent built from the existing V1 agents."""

from __future__ import annotations

from typing import List

from src.agents.evidence_agent import EvidenceAgent
from src.agents.interview_prep_agent import InterviewPrepAgent
from src.agents.jd_parser_agent import JDParserAgent
from src.agents.keyword_agent import KeywordAgent
from src.agents.outreach_agent import OutreachAgent
from src.agents.resume_optimizer_agent import ResumeOptimizerAgent
from src.agents.scoring_agent import ScoringAgent
from src.llm_client import LLMClient
from src.schemas.models import JobMatchResult, JobPosting, ResumeAnalysis


class BatchMatchingAgent:
    """Run the established V1 analysis agents for each normalized job."""

    SCORE_NAMES = {
        "技能匹配": "skill_score",
        "项目经历匹配": "project_score",
        "关键词覆盖": "keyword_score",
        "岗位职责匹配": "responsibility_score",
        "教育/背景匹配": "education_score",
    }

    def __init__(self, llm_client: LLMClient) -> None:
        self.jd_parser = JDParserAgent(llm_client)
        self.evidence_agent = EvidenceAgent(llm_client)
        self.keyword_agent = KeywordAgent(llm_client)
        self.scoring_agent = ScoringAgent(llm_client)
        self.resume_optimizer = ResumeOptimizerAgent(llm_client)
        self.outreach_agent = OutreachAgent(llm_client)
        self.interview_agent = InterviewPrepAgent(llm_client)

    def run(
        self,
        resume: ResumeAnalysis,
        jobs: List[JobPosting],
        target_role: str = "",
        candidate_type: str = "",
    ) -> List[JobMatchResult]:
        results = [
            self._match_one(resume, job, target_role, candidate_type)
            for job in jobs
        ]
        return sorted(results, key=lambda item: item.total_score, reverse=True)

    def _match_one(
        self,
        resume: ResumeAnalysis,
        job: JobPosting,
        target_role: str,
        candidate_type: str,
    ) -> JobMatchResult:
        jd = self.jd_parser.run(job.jd_text, target_role=job.job_title or target_role)
        jd = jd.model_copy(
            update={
                "job_title": job.job_title if job.job_title != "未知岗位" else jd.job_title,
                "company": job.company if job.company != "公司未知" else jd.company,
                "location": job.city if job.city != "城市未知" else jd.location,
            }
        )
        evidence = self.evidence_agent.run(jd, resume)
        keyword_coverage = self.keyword_agent.run(jd, resume)
        score = self.scoring_agent.run(jd, resume, evidence, keyword_coverage)
        optimization = self.resume_optimizer.run(jd, resume)
        outreach = self.outreach_agent.run(
            jd,
            resume,
            score,
            target_role=target_role,
            candidate_type=candidate_type,
        )
        interview = self.interview_agent.run(jd, resume, evidence, score)

        category_scores = {
            self.SCORE_NAMES[item.name]: item.score
            for item in score.categories
            if item.name in self.SCORE_NAMES
        }
        return JobMatchResult(
            job=job,
            total_score=score.total_score,
            skill_score=category_scores.get("skill_score", 0.0),
            project_score=category_scores.get("project_score", 0.0),
            keyword_score=category_scores.get("keyword_score", 0.0),
            responsibility_score=category_scores.get("responsibility_score", 0.0),
            education_score=category_scores.get("education_score", 0.0),
            strengths=score.strengths,
            risks=score.risks,
            missing_keywords=keyword_coverage.missing_keywords,
            recommendation=self.recommendation_for_score(score.total_score),
            evidence_matches=evidence,
            optimization_suggestions=optimization,
            interview_prep=interview,
            outreach_messages=outreach,
            jd_analysis=jd,
            keyword_coverage=keyword_coverage,
            score_breakdown=score,
        )

    @staticmethod
    def recommendation_for_score(total_score: float) -> str:
        if total_score >= 80:
            return "强烈建议投递"
        if total_score >= 65:
            return "建议投递，可针对性优化简历"
        if total_score >= 50:
            return "谨慎投递，需要补强关键词或项目表达"
        return "不优先投递"
