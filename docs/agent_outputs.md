# Agent 输出样例

本文基于 `examples/sample_resume.txt` 和 `examples/sample_jd.txt`，展示当前 MVP 中 8 个 Agent 的输入、处理逻辑和输出样例。它适合在 GitHub README 后继续展开说明，也适合面试时讲清楚：这个项目不是简单的“把简历丢给 LLM 改写”，而是一个可解释、可拆解、可测试的多 Agent 工作流。

## 示例输入

### 简历摘要

示例简历是一位 2027 届硕士候选人，方向为数据分析 / AI 产品。经历包括：

- 数据分析实习：SQL、Python、Excel、Power BI、转化漏斗、运营看板、埋点口径。
- AI 求职助手 Demo：Streamlit、OpenAI API、JD 解析、关键词覆盖、投递话术。
- 电商用户增长分析：Python、cohort 分析、复购率、可视化仪表盘。

### JD 摘要

示例 JD 是“AI Agent 产品经理实习生”，要求包括：

- 参与 AI Agent 产品需求分析、用户场景拆解和产品方案设计。
- 搭建指标体系，跟踪留存、转化和任务完成率。
- 推动 Agent 工作流、Prompt 和工具调用能力落地。
- 具备 SQL、Python、数据分析、大模型、RAG、AI Agent、Prompt Engineering 等经验或兴趣。

## 1. JD Parser Agent

**Agent 目标**

把非结构化岗位 JD 拆成结构化岗位画像，帮助后续 Agent 知道“这个岗位真正需要什么”。

**输入字段**

- `jd_text`：岗位 JD 原文。
- `target_role`：用户填写的目标岗位方向，例如 `AI Agent 产品经理`。

**输出字段**

- `job_title`
- `company`
- `location`
- `responsibilities`
- `hard_skills`
- `soft_skills`
- `tools`
- `business_keywords`
- `education_requirement`
- `experience_requirement`
- `implicit_capabilities`

**示例输出**

```json
{
  "job_title": "AI Agent 产品经理实习生",
  "company": "某 AI 应用创业公司",
  "location": "杭州 / 远程",
  "responsibilities": [
    "参与 AI Agent 产品的需求分析、用户场景拆解和产品方案设计。",
    "基于用户反馈和业务数据，搭建指标体系，跟踪留存、转化和任务完成率。",
    "与算法、工程和运营团队协作，推动 Agent 工作流、Prompt 和工具调用能力落地。"
  ],
  "hard_skills": ["Python", "SQL", "大模型", "LLM", "需求分析", "竞品分析", "产品设计", "指标体系", "Prompt Engineering", "RAG", "Agent"],
  "tools": ["Python", "SQL", "OpenAI", "LangChain", "Streamlit"],
  "business_keywords": ["用户增长", "留存", "转化", "SaaS", "BI", "AI Agent", "智能体"],
  "implicit_capabilities": ["需求拆解", "指标设计", "数据驱动决策", "结构化表达", "AI 场景理解", "Prompt/工作流拆解"]
}
```

**为什么有价值**

JD 往往很长，候选人容易只看到“岗位名称”，忽略工具栈、隐含能力和业务关键词。这个 Agent 把岗位要求拆开，后续才能逐项匹配简历证据。

## 2. Resume Parser Agent

**Agent 目标**

从简历文本中提取真实经历和能力资产，形成可匹配的简历结构化信息。

**输入字段**

- `resume_text`：上传文件解析后的文本，或用户粘贴的简历文本。

**输出字段**

- `education`
- `projects`
- `internships`
- `skills`
- `metrics`
- `keywords`
- `transferable_capabilities`

**示例输出**

```json
{
  "education": [
    "悉尼大学 Master of Data Science，主修机器学习、统计建模、数据库系统、数据可视化。",
    "本科阶段学习信息管理与商业分析，GPA 3.7/4.0。"
  ],
  "internships": [
    "某互联网公司 数据分析实习生",
    "使用 SQL 和 Python 清洗 20 万条用户行为数据，搭建转化漏斗分析表，定位注册到首单环节的流失问题。",
    "参与活动复盘，使用 Excel 和 Power BI 制作周度看板，帮助运营团队跟踪留存、转化和客单价指标。"
  ],
  "projects": [
    "AI 求职助手 Demo",
    "基于 Streamlit 和 OpenAI API 搭建简历-JD 匹配原型，支持 JD 解析、关键词覆盖和投递话术生成。",
    "设计 Agent 工作流，将岗位解析、简历证据提取、评分和报告生成拆分为多个模块。"
  ],
  "skills": ["Python", "SQL", "Excel", "Power BI", "Tableau", "Streamlit", "统计分析", "机器学习", "数据可视化", "需求分析"],
  "transferable_capabilities": ["数据处理与分析", "项目推进", "需求理解与产品表达", "数据可视化表达", "AI/模型应用理解"]
}
```

**为什么有价值**

简历不是为了“好看”而解析，而是为了让后续匹配有事实依据。这个 Agent 只提取简历中已有内容，为“不编造经历”的优化原则打基础。

## 3. Evidence Mapping Agent

**Agent 目标**

把 JD 要求和简历中的项目、实习、技能进行映射，回答“这个岗位要求在简历里有没有证据”。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`

**输出字段**

- `requirement`
- `resume_evidence`
- `strength`
- `strength_score`
- `suggested_expression`

**示例输出**

| 岗位要求 | 简历证据 | 强度 | 建议补充表达 |
| --- | --- | --- | --- |
| Python | 使用 SQL 和 Python 清洗 20 万条用户行为数据；使用 Python 对订单和用户行为数据进行 cohort 分析 | 强 | 补成“动作 + 工具/方法 + 量化结果 + 业务影响” |
| SQL | 使用 SQL 和 Python 清洗 20 万条用户行为数据 | 强 | 强化数据处理规模、口径和结果 |
| 指标体系 | 参与活动复盘，使用 Excel 和 Power BI 制作周度看板，帮助运营团队跟踪留存、转化和客单价指标 | 中 | 用 STAR 结构说明指标口径和业务决策 |
| RAG | 未在简历中找到直接证据 | 缺失 | 如确实做过，请补充真实项目；不要虚构 |

**为什么有价值**

很多简历优化失败，是因为只堆关键词，没有证据。这个 Agent 直接暴露强证据、弱证据和缺失证据，帮助候选人知道该补哪里。

## 4. Keyword Coverage Agent

**Agent 目标**

比较 JD 关键词与简历关键词，输出强覆盖、弱覆盖和未覆盖情况。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`

**输出字段**

- `covered_keywords`
- `weak_keywords`
- `missing_keywords`
- `coverage_rate`
- `notes`

**示例输出**

```json
{
  "covered_keywords": ["Python", "SQL", "LLM", "需求分析", "指标体系", "Agent", "OpenAI", "Streamlit", "用户增长", "留存", "转化", "BI"],
  "weak_keywords": ["大模型", "可视化"],
  "missing_keywords": ["RAG", "Prompt Engineering", "LangChain", "SaaS", "智能体"],
  "coverage_rate": 0.46,
  "notes": "JD 关键词共 26 个；强覆盖 12 个，弱覆盖 2 个，未覆盖 12 个。"
}
```

**为什么有价值**

关键词覆盖不是为了机械堆词，而是帮助候选人发现 JD 里高频出现、但简历表达不足的能力点。当前实现会对关键词保持原有顺序并去重，避免报告里重复刷屏。

## 5. Scoring Agent

**Agent 目标**

用固定权重生成可解释匹配分，而不是给一个黑盒结论。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`
- `List[EvidenceMatch]`
- `KeywordCoverage`

**输出字段**

- `total_score`
- `categories`
- `strengths`
- `risks`
- `summary`

**示例输出**

| 维度 | 权重 | 示例得分 | 解释 |
| --- | --- | --- | --- |
| 技能匹配 | 30% | 约 60-80 | JD 技能/工具中，Python、SQL、OpenAI、Streamlit 等被简历覆盖 |
| 项目经历匹配 | 25% | 约 60-75 | AI 求职助手 Demo 与 Agent 工作流、报告生成相关 |
| 关键词覆盖 | 20% | 约 40-60 | RAG、Prompt Engineering、LangChain 等仍需补强 |
| 岗位职责匹配 | 15% | 约 55-70 | 需求分析、指标跟踪和协作有证据，但产品方案细节还可加强 |
| 教育/背景匹配 | 10% | 约 80-90 | 数据科学硕士背景与 JD 要求匹配 |

**为什么有价值**

面试或作品集展示时，可以解释评分来自哪些维度，而不是“AI 觉得你匹配”。这让系统更像一个分析工具，而不是一次性文本生成器。

## 6. Resume Optimizer Agent

**Agent 目标**

基于已有经历给出简历 bullet 改写建议，强调真实动作、工具、结果和业务影响。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`

**输出字段**

- `original_bullet`
- `optimized_bullet`
- `rationale`
- `risk_note`

**示例输出**

| 修改前 | 修改后方向 | 理由 |
| --- | --- | --- |
| 使用 SQL 和 Python 清洗 20 万条用户行为数据，搭建转化漏斗分析表 | 可强化“用户行为数据处理 + 转化漏斗 + 流失定位 + 业务建议” | 与 JD 中数据分析、指标体系、转化跟踪相关 |
| 基于 Streamlit 和 OpenAI API 搭建简历-JD 匹配原型 | 可强化“AI 应用原型 + 工作流拆解 + JD 解析 + 报告生成” | 与 AI Agent 产品、OpenAI、Streamlit 和工作流能力相关 |
| 设计 Agent 工作流，将岗位解析、简历证据提取、评分和报告生成拆分为多个模块 | 可强化“模块化 Agent 设计 + 可解释评分 + 输出报告” | 能直接对应 JD 的 Agent 工作流和产品方案设计 |

**为什么有价值**

这个 Agent 的重点不是“美化文字”，而是把已有经历和目标岗位语言对齐。它明确提示不要补充没有做过的项目、工具或指标。

## 7. Outreach Agent

**Agent 目标**

根据岗位和简历匹配结果，生成不同渠道的投递话术。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`
- `ScoreBreakdown`
- `target_role`

**输出字段**

- `boss_zhipin`
- `email_body`
- `linkedin_dm`
- `referral_request`
- `interview_intro`

**示例输出**

```text
Boss 直聘：
您好，我正在关注 AI Agent 产品经理实习生机会。我的经历与 Python、SQL、OpenAI / Streamlit 原型相关，也做过 JD-简历匹配 Agent 工作流 Demo，希望有机会进一步沟通。

邮件正文：
您好，我想投递贵公司的 AI Agent 产品经理实习生。我的过往经历主要覆盖数据分析、AI 应用原型和 Agent 工作流拆解，也在针对 RAG、Prompt Engineering 等方向继续补充更清晰的项目表达。期待有机会参与后续面试。
```

**为什么有价值**

投递话术经常被忽略，但它决定了候选人能否在招聘方第一眼看到匹配点。这个 Agent 把分析结果转成可直接使用的沟通文本。

## 8. Report Agent

**Agent 目标**

把所有中间结果整合成最终 Markdown 报告，方便下载、复盘和继续优化。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`
- `List[EvidenceMatch]`
- `KeywordCoverage`
- `ScoreBreakdown`
- `List[OptimizationSuggestion]`
- `OutreachMessages`

**输出字段**

- `markdown`

**示例输出结构**

```markdown
# AI 秋招岗位匹配报告

## 1. 结论
当前岗位：AI Agent 产品经理实习生；匹配分：xx/100。

## 2. JD 解析
- 公司
- 地点
- 硬技能
- 工具栈
- 业务关键词
- 隐含能力

## 3. 简历概览
## 4. 证据匹配
## 5. 关键词覆盖
## 6. 评分明细
## 7. 简历优化建议
## 8. 投递话术
```

**为什么有价值**

最终报告是把“分析过程”变成“可交付结果”的关键。它让用户可以保存一次岗位匹配分析，也方便后续导出为 Word 报告或整理成投递复盘记录。

## 面试讲解建议

如果在面试中讲这个项目，可以按下面的逻辑展开：

1. 先讲痛点：JD 复杂、简历证据不清、关键词覆盖不足、投递话术重复劳动。
2. 再讲架构：Streamlit 页面只是入口，核心是 8 个 Agent 的结构化工作流。
3. 强调安全边界：无 API Key 可 mock 演示，真实 API Key 只走 `.env`，不提交到 GitHub。
4. 强调真实性：简历优化 Agent 不编造经历，只基于原始简历做表达优化。
5. 最后讲工程化：Pydantic schema、pytest、GitHub Actions、Markdown/Word 报告导出。
