"""Outreach message generation agent."""

from __future__ import annotations

from src.llm_client import LLMClient
from src.schemas.models import JDAnalysis, OutreachMessages, ResumeAnalysis, ScoreBreakdown


class OutreachAgent:
    """Generate application outreach scripts."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def run(self, jd: JDAnalysis, resume: ResumeAnalysis, score: ScoreBreakdown, target_role: str) -> OutreachMessages:
        fallback = self._heuristic_messages(jd, resume, score, target_role)
        data = self.llm.complete_json(
            system_prompt=(
                "你是求职投递话术 Agent。请输出 JSON，字段为 boss_zhipin, "
                "email_body, linkedin_dm, referral_request, interview_intro。"
                "表达真诚具体，不夸大经历。"
            ),
            user_prompt=f"JD：{jd.model_dump()}\n\n简历：{resume.model_dump()}\n\n评分：{score.model_dump()}",
            fallback=fallback.model_dump(),
        )
        return OutreachMessages(**data)

    def _heuristic_messages(
        self, jd: JDAnalysis, resume: ResumeAnalysis, score: ScoreBreakdown, target_role: str
    ) -> OutreachMessages:
        role = jd.job_title or target_role or "目标岗位"
        company = jd.company or "贵公司"
        highlights = "、".join((score.strengths or resume.skills or ["数据分析", "项目经历"])[:3])
        missing = "、".join(score.risks[:2]) if score.risks else "岗位细节"
        return OutreachMessages(
            boss_zhipin=(
                f"您好，我正在关注{role}机会。我的经历与{highlights}相关，"
                f"已根据 JD 做过初步匹配，当前匹配度约 {score.total_score}/100。"
                "希望有机会进一步沟通，谢谢！"
            ),
            email_body=(
                f"您好，\n\n我想投递{company}的{role}。我的过往经历主要覆盖{highlights}，"
                f"也在针对{missing}继续补充更清晰的项目表达。附件/下方为我的简历，"
                "期待有机会参与后续面试。\n\n谢谢！"
            ),
            linkedin_dm=(
                f"Hi，看到您团队的{role}机会很感兴趣。我有{highlights}相关经历，"
                "希望请教该岗位更看重的能力与项目经验，方便的话期待交流。"
            ),
            referral_request=(
                f"您好，我准备投递{company}的{role}，简历与{highlights}有一定匹配。"
                "如果您方便的话，想请您帮忙评估是否适合内推；我会附上 JD、简历和简要匹配说明。"
            ),
            interview_intro=(
                f"您好，我关注的是{role}方向。我的经历主要集中在{highlights}，"
                "做项目时比较重视从业务问题出发，拆解指标或需求，再通过数据/产品方法推动落地。"
                f"这次岗位里我最想进一步发挥的是与{jd.business_keywords[:2] or ['业务目标']}相关的能力。"
            ),
        )

