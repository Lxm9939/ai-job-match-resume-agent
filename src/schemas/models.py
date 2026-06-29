"""Pydantic models shared by agents and the Streamlit UI."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class JDAnalysis(BaseModel):
    job_title: str = ""
    company: str = ""
    location: str = ""
    responsibilities: List[str] = Field(default_factory=list)
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    business_keywords: List[str] = Field(default_factory=list)
    education_requirement: str = ""
    experience_requirement: str = ""
    implicit_capabilities: List[str] = Field(default_factory=list)
    raw_text: str = ""


class ResumeAnalysis(BaseModel):
    education: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    internships: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    transferable_capabilities: List[str] = Field(default_factory=list)
    raw_text: str = ""


class EvidenceMatch(BaseModel):
    requirement: str
    resume_evidence: str
    strength: str
    strength_score: int = 0
    suggested_expression: str


class KeywordCoverage(BaseModel):
    covered_keywords: List[str] = Field(default_factory=list)
    weak_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    coverage_rate: float = 0.0
    notes: str = ""


class ScoreItem(BaseModel):
    name: str
    weight: float
    score: float
    reason: str


class ScoreBreakdown(BaseModel):
    total_score: float = 0.0
    categories: List[ScoreItem] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    summary: str = ""


class OptimizationSuggestion(BaseModel):
    original_bullet: str
    optimized_bullet: str
    rationale: str
    risk_note: str = "未编造经历；请只补充真实做过的工具、规模和结果。"


class OutreachMessages(BaseModel):
    boss_zhipin: str = ""
    email_body: str = ""
    linkedin_dm: str = ""
    referral_request: str = ""
    interview_intro: str = ""


class FinalReport(BaseModel):
    markdown: str = ""


class WorkflowResult(BaseModel):
    jd: JDAnalysis
    resume: ResumeAnalysis
    evidence_matches: List[EvidenceMatch] = Field(default_factory=list)
    keyword_coverage: KeywordCoverage
    score: ScoreBreakdown
    optimization_suggestions: List[OptimizationSuggestion] = Field(default_factory=list)
    outreach: OutreachMessages
    final_report: FinalReport

