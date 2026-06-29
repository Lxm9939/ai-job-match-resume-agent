from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["LLM_MODE"] = "mock"

from src.llm_client import LLMClient
from src.report_exporter import export_workflow_result_to_docx
from src.workflow import ResumeMatchWorkflow


def test_workflow_runs_in_mock_mode() -> None:
    resume_text = (PROJECT_ROOT / "examples" / "sample_resume.txt").read_text(encoding="utf-8")
    jd_text = (PROJECT_ROOT / "examples" / "sample_jd.txt").read_text(encoding="utf-8")

    workflow = ResumeMatchWorkflow(llm_client=LLMClient())
    result = workflow.run(resume_text=resume_text, jd_text=jd_text, target_role="AI Agent 产品经理")

    assert result.jd.job_title
    assert result.resume.skills
    assert result.evidence_matches
    assert 0 <= result.score.total_score <= 100
    assert "AI 秋招岗位匹配报告" in result.final_report.markdown


def test_docx_export_returns_word_file() -> None:
    resume_text = (PROJECT_ROOT / "examples" / "sample_resume.txt").read_text(encoding="utf-8")
    jd_text = (PROJECT_ROOT / "examples" / "sample_jd.txt").read_text(encoding="utf-8")

    workflow = ResumeMatchWorkflow(llm_client=LLMClient())
    result = workflow.run(resume_text=resume_text, jd_text=jd_text, target_role="AI Agent 产品经理")
    docx_bytes = export_workflow_result_to_docx(result)

    assert docx_bytes.startswith(b"PK")
    assert len(docx_bytes) > 10_000
