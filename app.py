"""Streamlit UI for AI job-match resume analysis."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd
import streamlit as st

from src.config import get_settings
from src.document_parser import parse_uploaded_file
from src.report_exporter import DOCX_MIME_TYPE, export_workflow_result_to_docx
from src.workflow import ResumeMatchWorkflow


st.set_page_config(
    page_title="AI 秋招岗位匹配与简历优化助手",
    page_icon=":material/description:",
    layout="wide",
)


def as_dict(item: Any) -> Dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    return dict(item)


def as_dataframe(items: Iterable[Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = [as_dict(item) for item in items]
    return pd.DataFrame(rows)


def render_list(title: str, values: List[str]) -> None:
    st.markdown(f"**{title}**")
    if values:
        for value in values:
            st.markdown(f"- {value}")
    else:
        st.caption("未识别")


def main() -> None:
    settings = get_settings()
    st.title("AI 秋招岗位匹配与简历优化助手")
    st.caption("上传或粘贴简历，再粘贴岗位 JD，自动生成匹配评分、证据表、优化建议和投递话术。")

    with st.sidebar:
        st.subheader("运行设置")
        st.write(f"LLM 模式：`{settings.effective_llm_mode}`")
        if settings.effective_llm_mode == "mock":
            st.info("当前为 mock/规则模式，无需 API Key，适合本地演示。")
        else:
            st.success(f"OpenAI 模型：{settings.openai_model}")
        st.markdown("---")
        st.markdown("API Key 请写入 `.env`，不要提交到 GitHub。")

    resume_col, jd_col = st.columns(2)
    with resume_col:
        st.subheader("1. 简历输入区")
        uploaded_file = st.file_uploader("上传简历文件", type=["txt", "pdf", "docx"])
        pasted_resume = st.text_area(
            "或直接粘贴简历文本",
            height=320,
            placeholder="粘贴你的教育背景、项目经历、实习经历、技能栈等...",
        )

    with jd_col:
        st.subheader("2. JD 输入区")
        target_role = st.text_input(
            "目标岗位方向",
            value="AI 产品经理",
            placeholder="例如 AI 产品经理、数据分析师、商业分析师、数据产品经理、AI Agent 产品经理",
        )
        jd_text = st.text_area(
            "粘贴岗位 JD",
            height=320,
            placeholder="粘贴岗位职责、任职要求、加分项、地点、公司等信息...",
        )

    analyze_clicked = st.button("开始分析", type="primary", use_container_width=True)

    if analyze_clicked:
        resume_parts = []
        if uploaded_file is not None:
            try:
                resume_parts.append(parse_uploaded_file(uploaded_file))
            except Exception as exc:
                st.error(f"简历文件解析失败：{exc}")
                st.stop()
        if pasted_resume.strip():
            resume_parts.append(pasted_resume)
        resume_text = "\n\n".join(part for part in resume_parts if part.strip())

        if not resume_text.strip():
            st.error("请上传简历文件或粘贴简历文本。")
            st.stop()
        if not jd_text.strip():
            st.error("请粘贴岗位 JD。")
            st.stop()

        with st.spinner("Agent 工作流分析中..."):
            workflow = ResumeMatchWorkflow()
            try:
                st.session_state["analysis_result"] = workflow.run(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    target_role=target_role,
                )
            except Exception as exc:
                st.error(f"分析失败：{exc}")
                st.stop()

    result = st.session_state.get("analysis_result")
    if not result:
        st.markdown("### 输出结果区")
        st.info("填写简历和 JD 后点击“开始分析”，结果会在这里按 tab 展示。")
        return

    st.markdown("### 输出结果区")
    st.metric("总匹配分", f"{result.score.total_score}/100")
    st.progress(min(int(result.score.total_score), 100))

    tabs = st.tabs(
        [
            "岗位 JD 解析结果",
            "简历证据匹配表",
            "关键词覆盖分析",
            "匹配评分",
            "简历优化建议",
            "投递话术",
            "最终分析报告",
        ]
    )

    with tabs[0]:
        jd = result.jd
        top_cols = st.columns(3)
        top_cols[0].metric("岗位", jd.job_title or "未识别")
        top_cols[1].metric("公司", jd.company or "未识别")
        top_cols[2].metric("地点", jd.location or "未识别")
        col1, col2 = st.columns(2)
        with col1:
            render_list("岗位职责", jd.responsibilities)
            render_list("硬技能", jd.hard_skills)
            render_list("工具栈", jd.tools)
        with col2:
            render_list("软技能", jd.soft_skills)
            render_list("业务关键词", jd.business_keywords)
            render_list("隐含能力", jd.implicit_capabilities)
        st.markdown("**学历/经验要求**")
        st.write(jd.education_requirement or "未识别")
        st.write(jd.experience_requirement or "未识别")

    with tabs[1]:
        df = as_dataframe(result.evidence_matches)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[2]:
        coverage = result.keyword_coverage
        st.metric("关键词强覆盖率", f"{coverage.coverage_rate:.0%}")
        c1, c2, c3 = st.columns(3)
        with c1:
            render_list("已覆盖", coverage.covered_keywords)
        with c2:
            render_list("弱覆盖", coverage.weak_keywords)
        with c3:
            render_list("未覆盖", coverage.missing_keywords)
        st.info(coverage.notes)

    with tabs[3]:
        score_df = as_dataframe(result.score.categories)
        score_df["weight"] = score_df["weight"].map(lambda value: f"{value:.0%}")
        st.dataframe(score_df, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            render_list("优势", result.score.strengths)
        with c2:
            render_list("风险/短板", result.score.risks)
        st.success(result.score.summary)

    with tabs[4]:
        st.warning("优化建议遵守不编造原则：只改写已有经历，缺失内容会提示用真实信息补充。")
        st.dataframe(as_dataframe(result.optimization_suggestions), use_container_width=True, hide_index=True)

    with tabs[5]:
        outreach = result.outreach
        st.markdown("#### Boss 直聘打招呼")
        st.write(outreach.boss_zhipin)
        st.markdown("#### 邮件投递正文")
        st.text_area("邮件正文", outreach.email_body, height=180)
        st.markdown("#### LinkedIn 私信")
        st.write(outreach.linkedin_dm)
        st.markdown("#### 内推请求话术")
        st.write(outreach.referral_request)
        st.markdown("#### 面试自我介绍初稿")
        st.write(outreach.interview_intro)

    with tabs[6]:
        export_col1, export_col2 = st.columns(2)
        with export_col1:
            st.download_button(
                "下载 Markdown 报告",
                result.final_report.markdown,
                file_name="job_match_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with export_col2:
            st.download_button(
                "下载 Word 报告 (.docx)",
                export_workflow_result_to_docx(result),
                file_name="job_match_report.docx",
                mime=DOCX_MIME_TYPE,
                use_container_width=True,
            )
        st.markdown(result.final_report.markdown)


if __name__ == "__main__":
    main()
