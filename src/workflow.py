"""Modular agent workflow orchestration."""

from __future__ import annotations

from typing import Optional

from src.agents.evidence_agent import EvidenceAgent
from src.agents.jd_parser_agent import JDParserAgent
from src.agents.keyword_agent import KeywordAgent
from src.agents.outreach_agent import OutreachAgent
from src.agents.report_agent import ReportAgent
from src.agents.resume_optimizer_agent import ResumeOptimizerAgent
from src.agents.resume_parser_agent import ResumeParserAgent
from src.agents.scoring_agent import ScoringAgent
from src.llm_client import LLMClient
from src.schemas.models import WorkflowResult
from src.utils.text_utils import normalize_text


class ResumeMatchWorkflow:
    """Run the end-to-end JD/resume analysis workflow."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client or LLMClient()
        self.jd_parser = JDParserAgent(self.llm_client)
        self.resume_parser = ResumeParserAgent(self.llm_client)
        self.evidence_agent = EvidenceAgent(self.llm_client)
        self.keyword_agent = KeywordAgent(self.llm_client)
        self.scoring_agent = ScoringAgent(self.llm_client)
        self.resume_optimizer = ResumeOptimizerAgent(self.llm_client)
        self.outreach_agent = OutreachAgent(self.llm_client)
        self.report_agent = ReportAgent(self.llm_client)

    def run(self, resume_text: str, jd_text: str, target_role: str = "") -> WorkflowResult:
        resume_text = normalize_text(resume_text)
        jd_text = normalize_text(jd_text)
        if not resume_text:
            raise ValueError("简历文本为空，请上传简历或粘贴简历文本。")
        if not jd_text:
            raise ValueError("JD 文本为空，请粘贴岗位 JD。")

        jd = self.jd_parser.run(jd_text, target_role=target_role)
        resume = self.resume_parser.run(resume_text)
        evidence_matches = self.evidence_agent.run(jd, resume)
        keyword_coverage = self.keyword_agent.run(jd, resume)
        score = self.scoring_agent.run(jd, resume, evidence_matches, keyword_coverage)
        optimization_suggestions = self.resume_optimizer.run(jd, resume)
        outreach = self.outreach_agent.run(jd, resume, score, target_role=target_role)
        final_report = self.report_agent.run(
            jd,
            resume,
            evidence_matches,
            keyword_coverage,
            score,
            optimization_suggestions,
            outreach,
        )

        return WorkflowResult(
            jd=jd,
            resume=resume,
            evidence_matches=evidence_matches,
            keyword_coverage=keyword_coverage,
            score=score,
            optimization_suggestions=optimization_suggestions,
            outreach=outreach,
            final_report=final_report,
        )

