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


class JobPosting(BaseModel):
    """A normalized job posting imported from tabular data or pasted text."""

    job_id: str
    job_title: str = "未知岗位"
    company: str = "公司未知"
    city: str = "城市未知"
    job_type: str = "岗位类型未知"
    jd_text: str
    source_url: str = ""
    publish_date: str = ""


class JobPreferences(BaseModel):
    """User preferences used to explain and contextualize batch ranking."""

    target_role: str = ""
    target_city: str = ""
    job_type: str = ""
    company_preference: str = ""


class InterviewPrep(BaseModel):
    likely_questions: List[str] = Field(default_factory=list)
    project_talking_points: List[str] = Field(default_factory=list)
    technical_preparation: List[str] = Field(default_factory=list)
    business_preparation: List[str] = Field(default_factory=list)
    risk_questions: List[str] = Field(default_factory=list)
    suggested_answer_strategy: List[str] = Field(default_factory=list)


class JobMatchResult(BaseModel):
    job: JobPosting
    total_score: float = 0.0
    skill_score: float = 0.0
    project_score: float = 0.0
    keyword_score: float = 0.0
    responsibility_score: float = 0.0
    education_score: float = 0.0
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    recommendation: str = ""
    evidence_matches: List[EvidenceMatch] = Field(default_factory=list)
    optimization_suggestions: List[OptimizationSuggestion] = Field(default_factory=list)
    interview_prep: InterviewPrep = Field(default_factory=InterviewPrep)
    outreach_messages: OutreachMessages = Field(default_factory=OutreachMessages)
    jd_analysis: JDAnalysis = Field(default_factory=JDAnalysis)
    keyword_coverage: KeywordCoverage = Field(default_factory=KeywordCoverage)
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)


class BatchMatchResult(BaseModel):
    resume_summary: str = ""
    preference_summary: str = ""
    ranked_jobs: List[JobMatchResult] = Field(default_factory=list)
    best_matches: List[JobMatchResult] = Field(default_factory=list)
    risky_matches: List[JobMatchResult] = Field(default_factory=list)
    final_summary: str = ""
    report_markdown: str = ""


class JobSource(BaseModel):
    source_id: str
    source_name: str
    source_type: str = "public_html"
    base_url: str
    list_url: str
    allowed: bool = False
    notes: str = ""


class CrawledJob(BaseModel):
    job_title: str = "未知岗位"
    company: str = "公司未知"
    city: str = "城市未知"
    job_type: str = "岗位类型未知"
    jd_text: str
    source_url: str
    publish_date: str = ""
    crawled_at: str = ""
    source_name: str = ""
    jd_quality: str = "正常"


class CrawlResult(BaseModel):
    source: JobSource
    jobs: List[CrawledJob] = Field(default_factory=list)
    skipped_reason: str = ""
    error_message: str = ""
    crawled_count: int = 0


class JobSearchPreference(BaseModel):
    target_role: str = ""
    target_cities: List[str] = Field(default_factory=list)
    job_types: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    company_preferences: List[str] = Field(default_factory=list)
    max_jobs: int = 20


class JobFilterResult(BaseModel):
    filtered_jobs: List[CrawledJob] = Field(default_factory=list)
    removed_jobs: List[CrawledJob] = Field(default_factory=list)
    filter_reason_summary: str = ""


class CrawlWorkflowResult(BaseModel):
    crawl_results: List[CrawlResult] = Field(default_factory=list)
    raw_jobs: List[CrawledJob] = Field(default_factory=list)
    filter_result: JobFilterResult = Field(default_factory=JobFilterResult)
    batch_result: BatchMatchResult
    source_count: int = 0
    skipped_source_count: int = 0
    demo_mode: bool = False
