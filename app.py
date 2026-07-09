"""Streamlit UI for single and batch AI job-match analysis."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import streamlit as st

from src.agents.job_list_parser_agent import JobListParserAgent
from src.batch_workflow import BatchMatchWorkflow
from src.config import get_settings
from src.document_parser import parse_uploaded_file
from src.report_exporter import DOCX_MIME_TYPE, export_workflow_result_to_docx
from src.schemas.models import InterviewPrep, JobPreferences
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


def collect_resume_text(uploaded_file: Any, pasted_resume: str) -> Optional[str]:
    resume_parts: List[str] = []
    if uploaded_file is not None:
        try:
            resume_parts.append(parse_uploaded_file(uploaded_file))
        except Exception as exc:
            st.error(f"简历文件解析失败：{exc}")
            return None
    if pasted_resume.strip():
        resume_parts.append(pasted_resume)
    resume_text = "\n\n".join(part for part in resume_parts if part.strip())
    if not resume_text.strip():
        st.error("请上传简历文件或粘贴简历文本。")
        return None
    return resume_text


def render_jd_analysis(jd: Any) -> None:
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


def render_keyword_coverage(coverage: Any) -> None:
    st.metric("关键词强覆盖率", f"{coverage.coverage_rate:.0%}")
    col1, col2, col3 = st.columns(3)
    with col1:
        render_list("已覆盖", coverage.covered_keywords)
    with col2:
        render_list("弱覆盖", coverage.weak_keywords)
    with col3:
        render_list("未覆盖", coverage.missing_keywords)
    st.info(coverage.notes)


def render_score(score: Any) -> None:
    score_df = as_dataframe(score.categories)
    if not score_df.empty:
        score_df["weight"] = score_df["weight"].map(lambda value: f"{value:.0%}")
    st.dataframe(score_df, use_container_width=True, hide_index=True)
    col1, col2 = st.columns(2)
    with col1:
        render_list("优势", score.strengths)
    with col2:
        render_list("风险/短板", score.risks)
    st.success(score.summary)


def render_outreach(outreach: Any, key_prefix: str) -> None:
    st.markdown("#### Boss 直聘打招呼")
    st.write(outreach.boss_zhipin)
    st.markdown("#### 邮件投递正文")
    st.text_area("邮件正文", outreach.email_body, height=180, key=f"{key_prefix}_email")
    st.markdown("#### LinkedIn 私信")
    st.write(outreach.linkedin_dm)
    st.markdown("#### 内推请求话术")
    st.write(outreach.referral_request)
    st.markdown("#### 面试自我介绍初稿")
    st.write(outreach.interview_intro)


def render_interview_prep(prep: InterviewPrep) -> None:
    col1, col2 = st.columns(2)
    with col1:
        render_list("可能面试问题", prep.likely_questions)
        render_list("项目讲解重点", prep.project_talking_points)
        render_list("技术准备方向", prep.technical_preparation)
    with col2:
        render_list("业务准备方向", prep.business_preparation)
        render_list("风险追问", prep.risk_questions)
        render_list("建议回答策略", prep.suggested_answer_strategy)


def render_single_mode() -> None:
    st.title("AI 秋招岗位匹配与简历优化助手")
    st.caption("上传或粘贴简历，再粘贴岗位 JD，自动生成匹配评分、证据表、优化建议和投递话术。")

    resume_col, jd_col = st.columns(2)
    with resume_col:
        st.subheader("1. 简历输入区")
        uploaded_file = st.file_uploader(
            "上传简历文件",
            type=["txt", "pdf", "docx"],
            key="single_resume_file",
        )
        pasted_resume = st.text_area(
            "或直接粘贴简历文本",
            height=320,
            placeholder="粘贴你的教育背景、项目经历、实习经历、技能栈等...",
            key="single_resume_text",
        )

    with jd_col:
        st.subheader("2. JD 输入区")
        target_role = st.text_input(
            "目标岗位方向",
            value="AI 产品经理",
            placeholder="例如 AI 产品经理、数据分析师、商业分析师、数据产品经理、AI Agent 产品经理",
            key="single_target_role",
        )
        jd_text = st.text_area(
            "粘贴岗位 JD",
            height=320,
            placeholder="粘贴岗位职责、任职要求、加分项、地点、公司等信息...",
            key="single_jd_text",
        )

    if st.button("开始分析", type="primary", use_container_width=True, key="single_analyze"):
        resume_text = collect_resume_text(uploaded_file, pasted_resume)
        if resume_text is None:
            return
        if not jd_text.strip():
            st.error("请粘贴岗位 JD。")
            return

        with st.spinner("Agent 工作流分析中..."):
            try:
                st.session_state["analysis_result"] = ResumeMatchWorkflow().run(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    target_role=target_role,
                )
            except Exception as exc:
                st.error(f"分析失败：{exc}")
                return

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
        render_jd_analysis(result.jd)
    with tabs[1]:
        st.dataframe(as_dataframe(result.evidence_matches), use_container_width=True, hide_index=True)
    with tabs[2]:
        render_keyword_coverage(result.keyword_coverage)
    with tabs[3]:
        render_score(result.score)
    with tabs[4]:
        st.warning("优化建议遵守不编造原则：只改写已有经历，缺失内容会提示用真实信息补充。")
        st.dataframe(as_dataframe(result.optimization_suggestions), use_container_width=True, hide_index=True)
    with tabs[5]:
        render_outreach(result.outreach, "single")
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


def render_batch_mode() -> None:
    st.title("批量岗位匹配推荐")
    st.caption("导入一份简历和多个岗位，生成可解释的匹配排行榜、逐岗位优化建议与面试准备清单。")

    resume_col, preference_col = st.columns(2)
    with resume_col:
        st.subheader("1. 简历输入")
        uploaded_resume = st.file_uploader(
            "上传 PDF / DOCX / TXT 简历",
            type=["txt", "pdf", "docx"],
            key="batch_resume_file",
        )
        pasted_resume = st.text_area(
            "或粘贴简历文本",
            height=230,
            placeholder="粘贴教育、项目、实习、技能和成果...",
            key="batch_resume_text",
        )
    with preference_col:
        st.subheader("2. 求职偏好")
        target_role = st.text_input(
            "目标岗位方向",
            value="AI 产品经理",
            placeholder="AI 产品经理、数据分析师、商业分析师...",
            key="batch_target_role",
        )
        target_city = st.text_input(
            "目标城市",
            placeholder="北京、上海、杭州、成都、深圳、远程",
            key="batch_target_city",
        )
        job_type = st.text_input(
            "岗位类型",
            placeholder="实习、校招、全职、可转正实习",
            key="batch_job_type",
        )
        company_preference = st.text_input(
            "公司偏好",
            placeholder="外企、互联网、国企、制造业、AI 公司、数据平台类公司",
            key="batch_company_preference",
        )

    st.subheader("3. 岗位列表输入")
    job_file_col, job_text_col = st.columns(2)
    with job_file_col:
        job_file = st.file_uploader(
            "方式 A：上传 CSV / Excel 岗位列表",
            type=["csv", "xlsx"],
            key="batch_job_file",
            help="建议字段：job_title、company、city、job_type、jd_text、source_url、publish_date",
        )
        st.caption("可直接使用 `examples/sample_jobs.csv` 体验。")
    with job_text_col:
        multi_jd_text = st.text_area(
            "方式 B：粘贴多个 JD",
            height=180,
            placeholder="多个岗位之间使用 ---JOB--- 分隔",
            key="batch_multi_jd",
        )

    if st.button("开始批量匹配", type="primary", use_container_width=True, key="batch_analyze"):
        resume_text = collect_resume_text(uploaded_resume, pasted_resume)
        if resume_text is None:
            return
        try:
            jobs = JobListParserAgent().run(
                file_name=job_file.name if job_file else "",
                content=job_file.getvalue() if job_file else b"",
                multi_jd_text=multi_jd_text,
            )
        except Exception as exc:
            st.error(f"岗位列表解析失败：{exc}")
            return
        if not jobs:
            st.error("未识别到有效岗位，请检查文件中的 jd_text 字段或多 JD 分隔符。")
            return

        preferences = JobPreferences(
            target_role=target_role,
            target_city=target_city,
            job_type=job_type,
            company_preference=company_preference,
        )
        with st.spinner(f"正在分析并排序 {len(jobs)} 个岗位..."):
            try:
                st.session_state["batch_analysis_result"] = BatchMatchWorkflow().run(
                    resume_text=resume_text,
                    jobs=jobs,
                    preferences=preferences,
                )
            except Exception as exc:
                st.error(f"批量分析失败：{exc}")
                return

    result = st.session_state.get("batch_analysis_result")
    if not result:
        st.markdown("### 输出结果区")
        st.info("导入简历和岗位列表后点击“开始批量匹配”，排行榜和岗位详情会显示在这里。")
        return

    st.markdown("### 岗位匹配排行榜")
    metric_cols = st.columns(3)
    metric_cols[0].metric("已分析岗位", len(result.ranked_jobs))
    metric_cols[1].metric("建议投递", len(result.best_matches))
    metric_cols[2].metric("最高匹配分", f"{result.ranked_jobs[0].total_score}/100")
    st.caption(result.preference_summary)

    ranking_rows = []
    for rank, item in enumerate(result.ranked_jobs, start=1):
        ranking_rows.append(
            {
                "排名": rank,
                "岗位名称": item.job.job_title,
                "公司": item.job.company,
                "城市": item.job.city,
                "岗位类型": item.job.job_type,
                "匹配总分": item.total_score,
                "技能分": item.skill_score,
                "项目经历分": item.project_score,
                "关键词分": item.keyword_score,
                "推荐结论": item.recommendation,
                "来源链接": item.job.source_url,
            }
        )
    st.dataframe(
        pd.DataFrame(ranking_rows),
        use_container_width=True,
        hide_index=True,
        column_config={"来源链接": st.column_config.LinkColumn("来源链接")},
    )
    st.download_button(
        "下载批量 Markdown 报告",
        result.report_markdown,
        file_name="batch_job_match_report.md",
        mime="text/markdown",
        use_container_width=True,
    )

    st.markdown("### 岗位详情")
    selected_job_id = st.selectbox(
        "选择岗位",
        options=[item.job.job_id for item in result.ranked_jobs],
        format_func=lambda job_id: next(
            (
                f"{index}. {item.job.job_title}｜{item.job.company}｜{item.total_score} 分"
                for index, item in enumerate(result.ranked_jobs, start=1)
                if item.job.job_id == job_id
            ),
            job_id,
        ),
        key="batch_selected_job",
    )
    selected = next(item for item in result.ranked_jobs if item.job.job_id == selected_job_id)
    st.info(f"{selected.recommendation}。来源：{selected.job.source_url or '未提供'}")
    tabs = st.tabs(
        [
            "JD 解析结果",
            "简历证据匹配",
            "关键词覆盖",
            "匹配评分解释",
            "简历优化建议",
            "面试注意事项",
            "投递话术",
        ]
    )
    with tabs[0]:
        render_jd_analysis(selected.jd_analysis)
    with tabs[1]:
        st.dataframe(as_dataframe(selected.evidence_matches), use_container_width=True, hide_index=True)
    with tabs[2]:
        render_keyword_coverage(selected.keyword_coverage)
    with tabs[3]:
        render_score(selected.score_breakdown)
    with tabs[4]:
        st.warning("只优化简历中已有经历，不编造项目、工具或成果。")
        st.dataframe(as_dataframe(selected.optimization_suggestions), use_container_width=True, hide_index=True)
    with tabs[5]:
        render_interview_prep(selected.interview_prep)
    with tabs[6]:
        render_outreach(selected.outreach_messages, f"batch_{selected.job.job_id}")

    st.markdown("### 批量分析结论")
    st.success(result.final_summary)


def main() -> None:
    settings = get_settings()
    with st.sidebar:
        st.subheader("功能模式")
        mode = st.radio(
            "选择分析方式",
            ["单个 JD 匹配分析", "批量岗位匹配推荐"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.subheader("运行设置")
        st.write(f"LLM 模式：`{settings.effective_llm_mode}`")
        if settings.effective_llm_mode == "mock":
            st.info("当前为 mock/规则模式，无需 API Key，适合本地演示。")
        else:
            st.success(f"OpenAI 模型：{settings.openai_model}")
        st.markdown("---")
        st.markdown("API Key 请写入 `.env`，不要提交到 GitHub。")

    if mode == "单个 JD 匹配分析":
        render_single_mode()
    else:
        render_batch_mode()


if __name__ == "__main__":
    main()
