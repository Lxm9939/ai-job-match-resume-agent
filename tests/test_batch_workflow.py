from __future__ import annotations

from pathlib import Path

from src.agents.job_list_parser_agent import JobListParserAgent
from src.batch_workflow import BatchMatchWorkflow
from src.config import Settings
from src.llm_client import LLMClient
from src.schemas.models import JobPreferences


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_batch_workflow_ranks_jobs_and_builds_interview_prep() -> None:
    llm_client = LLMClient(Settings(llm_mode="mock"))
    resume_text = (PROJECT_ROOT / "examples" / "sample_resume.txt").read_text(encoding="utf-8")
    jobs_path = PROJECT_ROOT / "examples" / "sample_jobs.csv"
    jobs = JobListParserAgent(llm_client).parse_file(jobs_path.name, jobs_path.read_bytes())

    result = BatchMatchWorkflow(llm_client).run(
        resume_text=resume_text,
        jobs=jobs,
        preferences=JobPreferences(
            target_role="AI 产品经理",
            target_city="北京、上海、远程",
            job_type="校招、实习",
            company_preference="AI 公司、互联网",
        ),
    )

    assert len(result.ranked_jobs) == 5
    assert [item.total_score for item in result.ranked_jobs] == sorted(
        [item.total_score for item in result.ranked_jobs],
        reverse=True,
    )
    assert all(item.recommendation for item in result.ranked_jobs)
    assert all(item.interview_prep.likely_questions for item in result.ranked_jobs)
    assert all(item.interview_prep.suggested_answer_strategy for item in result.ranked_jobs)
    assert "# 批量岗位匹配推荐报告" in result.report_markdown
