"""Streamlit UI for single, batch, and public-source job matching."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import streamlit as st

from src.agents.job_list_parser_agent import JobListParserAgent
from src.analytics import (
    build_analytics_summary_markdown,
    build_job_match_analytics,
    build_ranking_rows,
)
from src.batch_workflow import BatchMatchWorkflow
from src.config import get_settings
from src.crawl_workflow import CrawlWorkflow
from src.document_parser import parse_uploaded_file
from src.job_sources.source_config import DEFAULT_SOURCE_CONFIG, load_job_sources
from src.report_exporter import DOCX_MIME_TYPE, export_workflow_result_to_docx
from src.schemas.models import BatchMatchResult, InterviewPrep, JobPreferences, JobSearchPreference
from src.url_utils import (
    format_url_for_display,
    is_clickable_job_url,
    source_url_status,
)
from src.utils.preference_utils import resolve_target_role, target_role_error_message
from src.workflow import ResumeMatchWorkflow


st.set_page_config(
    page_title="AI 岗位搜索、匹配评分与求职优化助手",
    page_icon=":material/description:",
    layout="wide",
)

CANDIDATE_TYPE_OPTIONS = [
    "实习",
    "校招 / 应届",
    "社招",
    "转行",
    "在职跳槽",
    "海外留学生回国求职",
    "其他",
]
TARGET_ROLE_OPTIONS = [
    "AI 产品经理",
    "AI Agent 产品",
    "数据分析师",
    "商业分析师",
    "BI 分析师",
    "数据产品经理",
    "NLP / LLM 应用",
    "软件开发 / 测试",
    "其他",
]
TARGET_ROLE_CUSTOM_PLACEHOLDER = (
    "例如 用户增长分析师 / 数据运营 / 算法产品经理 / 安全分析师 / 海外市场分析"
)
JOB_TYPE_OPTIONS = [
    "实习",
    "可转正实习",
    "校招",
    "全职",
    "远程",
    "合同制",
    "兼职",
    "其他",
]
LOCATION_OPTIONS = [
    "北京",
    "上海",
    "杭州",
    "深圳",
    "成都",
    "广州",
    "苏州",
    "南京",
    "远程",
    "海外",
    "其他",
]
DEFAULT_JOB_SOURCE_FALLBACK_OPTIONS = [
    "Boss 直聘",
    "智联招聘",
    "猎聘",
    "前程无忧",
    "拉勾",
    "实习僧",
    "牛客招聘",
    "应届生求职网",
    "LinkedIn Jobs",
    "Indeed",
    "Seek",
    "GradConnection",
    "公司官网 Careers",
    "自定义公开 URL",
]


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


def split_preference_values(value: str) -> List[str]:
    return [
        item.strip()
        for item in re.split(r"[,，、/|]+", value)
        if item.strip()
    ]


def select_single_preference(
    label: str,
    options: List[str],
    key: str,
    default: str,
) -> str:
    selected = st.selectbox(
        label,
        options,
        index=options.index(default),
        key=key,
    )
    if selected != "其他":
        return selected
    custom = st.text_input(
        f"自定义{label}",
        key=f"{key}_other",
        placeholder="请输入自定义内容",
    )
    return custom.strip() or "其他"


def select_target_role(key: str, default: str = "AI 产品经理") -> tuple[str, str, str]:
    st.caption("可以选择常用方向，也可以输入更具体的目标岗位。")
    selected = st.selectbox(
        "目标岗位方向",
        TARGET_ROLE_OPTIONS,
        index=TARGET_ROLE_OPTIONS.index(default),
        key=key,
    )
    custom = st.text_input(
        "自定义目标岗位方向",
        key=f"{key}_custom",
        placeholder=TARGET_ROLE_CUSTOM_PLACEHOLDER,
    )
    return resolve_target_role(selected, custom), selected, custom


def select_multiple_preferences(
    label: str,
    options: List[str],
    key: str,
    default: Optional[List[str]] = None,
) -> List[str]:
    selected = st.multiselect(
        label,
        options,
        default=default or [],
        key=key,
    )
    values = [value for value in selected if value != "其他"]
    if "其他" in selected:
        custom = st.text_input(
            f"自定义{label}",
            key=f"{key}_other",
            placeholder="可输入多个值，用逗号分隔",
        )
        values.extend(split_preference_values(custom))
    return values


def get_default_job_source_options() -> List[str]:
    try:
        return [source.source_name for source in load_job_sources(path=DEFAULT_SOURCE_CONFIG)]
    except Exception:
        return DEFAULT_JOB_SOURCE_FALLBACK_OPTIONS


def job_source_link_fields(job: Any) -> Dict[str, str]:
    status, note = source_url_status(
        getattr(job, "source_url", ""),
        getattr(job, "source_url_status", ""),
    )
    note = getattr(job, "source_url_note", "") or note
    raw_url = getattr(job, "source_url", "")
    display = "示例数据，无真实岗位链接" if status == "demo_data" else format_url_for_display(raw_url)
    return {
        "source_url_display": display,
        "source_url_status": status,
        "source_url_note": note,
        "source_access_status": getattr(job, "source_access_status", ""),
        "source_access_note": getattr(job, "source_access_note", ""),
        "source_url": raw_url if is_clickable_job_url(raw_url, status) else "",
    }


def render_job_source_link(job: Any) -> None:
    fields = job_source_link_fields(job)
    st.markdown("**来源链接**")
    if fields["source_url"]:
        st.markdown(f"[{fields['source_url_display']}]({fields['source_url']})")
    else:
        st.write(fields["source_url_display"] or "无真实链接")
    st.caption(
        f"链接状态：{fields['source_url_status'] or 'unknown'}；"
        f"链接说明：{fields['source_url_note'] or '无'}"
    )
    access_status = fields.get("source_access_status")
    access_note = fields.get("source_access_note")
    if access_status or access_note:
        st.caption(f"访问状态：{access_status or 'unknown'}；访问说明：{access_note or '无'}")


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


def render_job_analytics_dashboard(
    result: BatchMatchResult,
    key_prefix: str,
) -> None:
    analytics = build_job_match_analytics(result)
    st.markdown("### 岗位分析 Dashboard")

    metric_cols = st.columns(5)
    metric_cols[0].metric("岗位总数", analytics["total_jobs"])
    metric_cols[1].metric("平均匹配分", analytics["average_match_score"])
    metric_cols[2].metric("推荐投递数", analytics["recommended_count"])
    metric_cols[3].metric("高质量岗位数", analytics["high_quality_count"])
    metric_cols[4].metric("低置信度岗位数", analytics["low_confidence_count"])

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        render_distribution_chart("城市分布", analytics["city_distribution"])
        render_distribution_chart(
            "推荐结论分布",
            analytics["recommendation_distribution"],
        )
    with chart_col2:
        render_distribution_chart(
            "岗位类型分布",
            analytics["job_type_distribution"],
        )
        render_distribution_chart(
            "岗位质量分布",
            analytics["quality_label_distribution"],
        )

    top_tabs = st.tabs(
        ["高匹配岗位 Top 10", "缺失关键词 Top 10", "常见技能关键词 Top 10"]
    )
    with top_tabs[0]:
        top_jobs = pd.DataFrame(analytics["top_matched_jobs"])
        st.dataframe(
            top_jobs,
            use_container_width=True,
            hide_index=True,
            column_config={"source_url": st.column_config.LinkColumn("source_url")},
        )
    with top_tabs[1]:
        st.dataframe(
            pd.DataFrame(analytics["top_missing_keywords"]),
            use_container_width=True,
            hide_index=True,
        )
    with top_tabs[2]:
        st.dataframe(
            pd.DataFrame(analytics["top_common_skills"]),
            use_container_width=True,
            hide_index=True,
        )

    ranking_csv = pd.DataFrame(
        build_ranking_rows(result.ranked_jobs)
    ).to_csv(index=False).encode("utf-8-sig")
    missing_csv = pd.DataFrame(
        analytics["top_missing_keywords"]
    ).to_csv(index=False).encode("utf-8-sig")
    summary_markdown = build_analytics_summary_markdown(analytics)
    download_cols = st.columns(3)
    with download_cols[0]:
        st.download_button(
            "下载岗位匹配排行榜 CSV",
            ranking_csv,
            file_name="job_match_ranking.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{key_prefix}_ranking_csv",
        )
    with download_cols[1]:
        st.download_button(
            "下载缺失关键词 CSV",
            missing_csv,
            file_name="missing_keywords.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{key_prefix}_missing_csv",
        )
    with download_cols[2]:
        st.download_button(
            "下载岗位分析 Summary",
            summary_markdown,
            file_name="job_analytics_summary.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"{key_prefix}_analytics_md",
        )


def render_distribution_chart(title: str, distribution: Dict[str, int]) -> None:
    st.markdown(f"#### {title}")
    if not distribution:
        st.caption("暂无数据")
        return
    chart_data = pd.DataFrame(
        [{"类别": label, "岗位数量": count} for label, count in distribution.items()]
    ).set_index("类别")
    st.bar_chart(chart_data)


def render_single_mode() -> None:
    st.title("AI 岗位搜索、匹配评分与求职优化助手")
    st.caption(
        "面向实习、校招、社招、转行和在职跳槽等场景，"
        "分析单个岗位 JD 并生成证据匹配、优化建议和投递话术。"
    )

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
        candidate_type = select_single_preference(
            "求职阶段 / 候选人类型",
            CANDIDATE_TYPE_OPTIONS,
            "single_candidate_type",
            "校招 / 应届",
        )
        target_role, selected_target_role, custom_target_role = select_target_role(
            "single_target_role"
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
        role_error = target_role_error_message(selected_target_role, custom_target_role)
        if role_error:
            st.error(role_error)
            return

        with st.spinner("Agent 工作流分析中..."):
            try:
                st.session_state["analysis_result"] = ResumeMatchWorkflow().run(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    target_role=target_role,
                    candidate_type=candidate_type,
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
        candidate_type = select_single_preference(
            "求职阶段 / 候选人类型",
            CANDIDATE_TYPE_OPTIONS,
            "batch_candidate_type",
            "校招 / 应届",
        )
        target_role, selected_target_role, custom_target_role = select_target_role(
            "batch_target_role"
        )
        target_cities = select_multiple_preferences(
            "城市 / 地区偏好",
            LOCATION_OPTIONS,
            key="batch_target_city",
        )
        job_types = select_multiple_preferences(
            "岗位类型",
            JOB_TYPE_OPTIONS,
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
        role_error = target_role_error_message(selected_target_role, custom_target_role)
        if role_error:
            st.error(role_error)
            return

        preferences = JobPreferences(
            candidate_type=candidate_type,
            target_role=target_role,
            target_city="、".join(target_cities),
            job_type="、".join(job_types),
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
        link_fields = job_source_link_fields(item.job)
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
                "source_url_display": link_fields["source_url_display"],
                "source_url_status": link_fields["source_url_status"],
                "source_url_note": link_fields["source_url_note"],
                "source_access_status": link_fields["source_access_status"],
                "source_access_note": link_fields["source_access_note"],
                "来源链接": link_fields["source_url"],
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
    render_job_analytics_dashboard(result, "batch")

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
    st.info(f"{selected.recommendation}。")
    render_job_source_link(selected.job)
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


def render_crawl_mode() -> None:
    st.title("公开岗位源自动抓取")
    st.caption("尝试访问公开岗位页面，合规抓取结果会进入 V2 批量匹配流程。")
    st.info(
        "系统会尝试访问所选岗位来源的公开页面。若页面需要登录、验证码、访问受限或 "
        "robots.txt 不允许，系统会自动跳过，并建议使用 CSV/Excel 导入或手动粘贴 JD。"
    )

    resume_col, preference_col = st.columns(2)
    with resume_col:
        st.subheader("1. 简历输入")
        uploaded_resume = st.file_uploader(
            "上传 PDF / DOCX / TXT 简历",
            type=["txt", "pdf", "docx"],
            key="crawl_resume_file",
        )
        pasted_resume = st.text_area(
            "或粘贴简历文本",
            height=260,
            placeholder="粘贴教育、项目、实习、技能和成果...",
            key="crawl_resume_text",
        )
    with preference_col:
        st.subheader("2. 岗位偏好")
        candidate_type = select_single_preference(
            "求职阶段 / 候选人类型",
            CANDIDATE_TYPE_OPTIONS,
            "crawl_candidate_type",
            "校招 / 应届",
        )
        target_role, selected_target_role, custom_target_role = select_target_role(
            "crawl_target_role"
        )
        target_cities = select_multiple_preferences(
            "城市 / 地区偏好",
            LOCATION_OPTIONS,
            key="crawl_target_cities",
            default=["北京", "上海", "杭州", "深圳", "成都", "远程"],
        )
        job_types = select_multiple_preferences(
            "岗位类型",
            JOB_TYPE_OPTIONS,
            key="crawl_job_types",
            default=["实习", "可转正实习", "校招", "全职"],
        )
        keywords = st.text_input(
            "关键词",
            value="AI、Agent、LLM、数据分析、SQL、BI、产品经理、RAG、Prompt、Data",
            key="crawl_keywords",
        )
        company_preferences = st.text_input(
            "公司偏好",
            placeholder="AI 公司、互联网、数据平台",
            key="crawl_company_preferences",
        )
        max_jobs = st.number_input(
            "最大抓取岗位数量",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="crawl_max_jobs",
        )

    st.subheader("3. 岗位源")
    use_demo = st.checkbox(
        "使用示例抓取结果演示",
        value=True,
        help="读取 examples/sample_crawled_jobs.json，不发起网络请求。",
        key="crawl_use_demo",
    )
    default_source_options = get_default_job_source_options()
    default_sources = st.multiselect(
        "默认岗位来源",
        default_source_options,
        default=["公司官网 Careers", "自定义公开 URL"],
        disabled=use_demo,
        key="crawl_default_sources",
    )
    custom_urls_text = st.text_area(
        "自定义公开岗位 URL",
        height=120,
        placeholder="每行一个公开岗位列表页或岗位详情页 URL",
        disabled=use_demo,
        key="crawl_custom_urls",
    )
    source_col, default_col = st.columns(2)
    with source_col:
        source_config = st.file_uploader(
            "上传岗位源配置 JSON（可选）",
            type=["json"],
            disabled=use_demo,
            key="crawl_source_config",
        )
    with default_col:
        use_default_config = st.checkbox(
            "使用默认示例配置",
            value=True,
            disabled=use_demo,
            help="默认配置提供常见招聘平台与公司 Careers 来源选项；具体可抓取性由访问检查决定。",
            key="crawl_default_config",
        )

    if st.button(
        "开始抓取并匹配岗位",
        type="primary",
        use_container_width=True,
        key="crawl_analyze",
    ):
        resume_text = collect_resume_text(uploaded_resume, pasted_resume)
        if resume_text is None:
            return
        role_error = target_role_error_message(selected_target_role, custom_target_role)
        if role_error:
            st.error(role_error)
            return
        custom_urls = [
            line.strip()
            for line in custom_urls_text.splitlines()
            if line.strip()
        ]
        custom_source_selected = "自定义公开 URL" in default_sources
        selected_default_sources = (
            [source for source in default_sources if source != "自定义公开 URL"]
            if use_default_config
            else []
        )
        if (
            not use_demo
            and source_config is None
            and not selected_default_sources
            and not custom_urls
        ):
            st.error("请选择默认岗位来源、上传公开岗位源配置，或粘贴自定义公开 URL。")
            return
        if not use_demo and custom_source_selected and not custom_urls:
            st.warning("已选择“自定义公开 URL”，请粘贴至少一个公开 URL；本次将只处理其他已选来源。")
        if not use_demo and not use_default_config and source_config is None and custom_urls:
            selected_default_sources = []
        if not use_demo and source_config is not None:
            selected_default_sources = None

        if not use_demo and not use_default_config and source_config is None and not custom_urls:
            st.error("请上传公开岗位源配置，或粘贴自定义公开 URL。")
            return

        preference = JobSearchPreference(
            candidate_type=candidate_type,
            target_role=target_role,
            target_cities=target_cities,
            job_types=job_types,
            keywords=split_preference_values(keywords),
            company_preferences=split_preference_values(company_preferences),
            max_jobs=int(max_jobs),
        )
        with st.spinner("正在检查 robots.txt、抓取公开岗位并执行批量匹配..."):
            try:
                st.session_state["crawl_analysis_result"] = CrawlWorkflow().run(
                    resume_text=resume_text,
                    preference=preference,
                    use_demo=use_demo,
                    source_config_content=source_config.getvalue() if source_config else None,
                    selected_source_names=selected_default_sources,
                    custom_urls=custom_urls,
                )
            except Exception as exc:
                st.error(f"公开岗位流程未完成：{exc}")
                return

    result = st.session_state.get("crawl_analysis_result")
    if not result:
        st.markdown("### 输出结果区")
        st.info("默认可使用本地示例抓取结果完整体验 V3，不需要访问任何真实网站。")
        return

    st.markdown("### 抓取状态")
    statistics = result.statistics
    status_cols = st.columns(4)
    status_cols[0].metric("原始抓取数量", statistics.raw_job_count)
    status_cols[1].metric("去重后数量", statistics.deduplicated_job_count)
    status_cols[2].metric("筛选后数量", statistics.filtered_job_count)
    status_cols[3].metric("高质量岗位", statistics.high_quality_count)
    quality_cols = st.columns(4)
    quality_cols[0].metric("中质量岗位", statistics.medium_quality_count)
    quality_cols[1].metric("低质量岗位", statistics.low_quality_count)
    quality_cols[2].metric("robots 跳过来源", statistics.robots_skipped_source_count)
    quality_cols[3].metric("抓取失败来源", statistics.failed_source_count)
    st.caption(
        f"处理岗位源 {result.source_count} 个；发现重复岗位 "
        f"{result.deduplication.duplicate_count} 条，涉及 "
        f"{result.deduplication.duplicate_group_count} 个重复组。"
    )
    if result.demo_mode:
        st.info("当前使用本地示例抓取结果，没有发起网络请求。")
    st.caption(result.filter_result.filter_reason_summary)

    source_rows = []
    for crawl_result in result.crawl_results:
        source_url_display = format_url_for_display(crawl_result.source.list_url)
        source_url = (
            crawl_result.source.list_url
            if is_clickable_job_url(crawl_result.source.list_url)
            else ""
        )
        if crawl_result.skipped_reason:
            status = "已跳过"
            detail = crawl_result.skipped_reason
        elif crawl_result.error_message:
            status = "抓取失败"
            detail = crawl_result.error_message
        else:
            status = "完成"
            detail = ""
        source_rows.append(
            {
                "岗位源": crawl_result.source.source_name,
                "状态": status,
                "抓取数量": crawl_result.crawled_count,
                "说明": detail,
                "source URL": source_url,
                "source_url_display": source_url_display,
                "access_status": crawl_result.source_access_status,
                "access_note": crawl_result.source_access_note,
                "是否进入解析": "是" if crawl_result.entered_parser else "否",
            }
        )
    with st.expander("查看岗位源处理明细"):
        st.dataframe(
            pd.DataFrame(source_rows),
            use_container_width=True,
            hide_index=True,
            column_config={"source URL": st.column_config.LinkColumn("source URL")},
        )

    st.markdown("### 抓取岗位预览")
    preview_rows = []
    for job in result.filter_result.filtered_jobs:
        link_fields = job_source_link_fields(job)
        preview_rows.append(
            {
                "岗位名称": job.job_title,
                "公司": job.company,
                "城市": job.city,
                "岗位类型": job.job_type,
                "来源": job.source_name,
                "source_url_display": link_fields["source_url_display"],
                "source_url_status": link_fields["source_url_status"],
                "source_url_note": link_fields["source_url_note"],
                "source_access_status": link_fields["source_access_status"],
                "source_access_note": link_fields["source_access_note"],
                "来源链接": link_fields["source_url"],
                "quality_score": job.quality_score,
                "quality_label": (
                    "低（低置信度）" if job.quality_label == "低" else job.quality_label
                ),
                "quality_warnings": "；".join(job.quality_warnings),
                "duplicate_group": job.duplicate_group,
                "is_duplicate": job.is_duplicate,
                "jd_length": job.jd_length,
            }
        )
    st.dataframe(
        pd.DataFrame(preview_rows),
        use_container_width=True,
        hide_index=True,
        column_config={"来源链接": st.column_config.LinkColumn("来源链接")},
    )
    download_col1, download_col2 = st.columns(2)
    with download_col1:
        csv_data = pd.DataFrame(
            [job.model_dump() for job in result.filter_result.filtered_jobs]
        ).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "下载抓取岗位 CSV",
            csv_data,
            file_name="crawled_jobs.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with download_col2:
        st.download_button(
            "下载匹配结果 Markdown 报告",
            result.batch_result.report_markdown,
            file_name="crawled_job_match_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    batch_result = result.batch_result
    st.markdown("### 匹配排行榜")
    if not batch_result.ranked_jobs:
        st.warning(batch_result.final_summary or "未形成可匹配岗位，请使用 CSV/Excel 导入或手动粘贴 JD。")
        return
    ranking_rows = []
    for rank, item in enumerate(batch_result.ranked_jobs, start=1):
        link_fields = job_source_link_fields(item.job)
        ranking_rows.append(
            {
                "排名": rank,
                "岗位名称": item.job.job_title,
                "公司": item.job.company,
                "城市": item.job.city,
                "匹配总分": item.total_score,
                "推荐结论": item.recommendation,
                "岗位质量标签": (
                    "低（低置信度）"
                    if item.job.quality_label == "低"
                    else item.job.quality_label
                ),
                "source_url_display": link_fields["source_url_display"],
                "source_url_status": link_fields["source_url_status"],
                "source_url_note": link_fields["source_url_note"],
                "source_access_status": link_fields["source_access_status"],
                "source_access_note": link_fields["source_access_note"],
                "来源链接": link_fields["source_url"],
            }
        )
    st.dataframe(
        pd.DataFrame(ranking_rows),
        use_container_width=True,
        hide_index=True,
        column_config={"来源链接": st.column_config.LinkColumn("来源链接")},
    )
    render_job_analytics_dashboard(batch_result, "crawl")

    st.markdown("### 岗位详情")
    selected_job_id = st.selectbox(
        "选择抓取岗位",
        options=[item.job.job_id for item in batch_result.ranked_jobs],
        format_func=lambda job_id: next(
            (
                f"{index}. {item.job.job_title}｜{item.job.company}｜{item.total_score} 分"
                for index, item in enumerate(batch_result.ranked_jobs, start=1)
                if item.job.job_id == job_id
            ),
            job_id,
        ),
        key="crawl_selected_job",
    )
    selected = next(
        item for item in batch_result.ranked_jobs if item.job.job_id == selected_job_id
    )
    st.info(f"{selected.recommendation}。")
    render_job_source_link(selected.job)
    if selected.job.quality_label == "低":
        st.warning(
            "该岗位为低置信度抓取结果，请先核对来源页再使用分析结论。"
            f"质量提示：{'；'.join(selected.job.quality_warnings) or '岗位字段不完整'}"
        )
    tabs = st.tabs(
        [
            "JD 解析",
            "简历证据匹配",
            "关键词覆盖",
            "匹配评分",
            "简历优化建议",
            "面试注意事项",
            "投递话术",
        ]
    )
    with tabs[0]:
        render_jd_analysis(selected.jd_analysis)
    with tabs[1]:
        st.dataframe(
            as_dataframe(selected.evidence_matches),
            use_container_width=True,
            hide_index=True,
        )
    with tabs[2]:
        render_keyword_coverage(selected.keyword_coverage)
    with tabs[3]:
        render_score(selected.score_breakdown)
    with tabs[4]:
        st.warning("只优化简历中已有经历，不编造项目、工具或成果。")
        st.dataframe(
            as_dataframe(selected.optimization_suggestions),
            use_container_width=True,
            hide_index=True,
        )
    with tabs[5]:
        render_interview_prep(selected.interview_prep)
    with tabs[6]:
        render_outreach(selected.outreach_messages, f"crawl_{selected.job.job_id}")


def main() -> None:
    settings = get_settings()
    with st.sidebar:
        st.subheader("功能模式")
        mode = st.radio(
            "选择分析方式",
            ["单个 JD 匹配分析", "批量岗位匹配推荐", "公开岗位源自动抓取"],
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
    elif mode == "批量岗位匹配推荐":
        render_batch_mode()
    else:
        render_crawl_mode()


if __name__ == "__main__":
    main()
