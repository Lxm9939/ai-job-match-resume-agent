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
# AI 岗位匹配与求职优化报告

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

## V2 新增 Agent 输出样例

V2 在上述 8 个 Agent 之外增加岗位列表解析、批量匹配和面试准备三个 Agent。它们不替换 V1，而是把单岗位分析能力组合成批量推荐流程。

### 9. Job List Parser Agent

**Agent 目标**

把 CSV、Excel 或使用 `---JOB---` 分隔的多段 JD 统一为可批处理的岗位对象，并对缺失字段做局部兜底。

**输入字段**

- 文件名与文件字节，或多 JD 文本。
- 表格建议字段：`job_title`、`company`、`city`、`job_type`、`jd_text`、`source_url`、`publish_date`。
- 可选链接字段：`source_url_status`、`source_url_note`、`source_access_status`、`source_access_note`。

**输出字段**

- `List[JobPosting]`
- 每个岗位包含稳定的 `job_id` 和规范化岗位字段。

**示例输出**

```json
{
  "job_id": "job-001",
  "job_title": "AI 产品经理",
  "company": "星云智能科技",
  "city": "北京",
  "job_type": "校招",
  "jd_text": "参与大模型产品需求调研、PRD 编写和 Agent 功能上线……",
  "source_url": "",
  "source_url_status": "demo_data",
  "source_url_note": "示例数据，无真实岗位链接",
  "publish_date": "2026-07-01"
}
```

**为什么有价值**

真实岗位数据格式并不统一。先做输入标准化，可以让后续 Agent 只关心匹配任务；某个岗位缺少公司或城市时，也不会导致整批分析失败。链接字段会额外判断 demo、example、localhost 等占位内容，避免示例数据被展示成可点击真实岗位。

### 10. Batch Matching Agent

**Agent 目标**

复用 V1 单 JD Agent，对多个岗位逐一生成证据、关键词和五维评分，并按总分降序输出推荐结果。

**输入字段**

- `ResumeAnalysis`
- `List[JobPosting]`
- 目标岗位方向

**输出字段**

- `List[JobMatchResult]`
- 总分与五项分数、优势、风险、缺失关键词、推荐结论。
- 逐岗位证据、优化建议、面试准备和投递话术。

**示例输出**

```json
{
  "job": {"job_title": "AI Agent 产品助理", "company": "启元 AI 实验室"},
  "total_score": 72.4,
  "skill_score": 75.0,
  "project_score": 68.0,
  "keyword_score": 70.0,
  "recommendation": "建议投递，可针对性优化简历",
  "missing_keywords": ["RAG", "模型效果评估"]
}
```

**为什么有价值**

候选人面对多个岗位时，需要先决定投递优先级。批量匹配把同一评分口径应用到所有岗位，减少凭感觉筛选，也保留每个分数的证据来源。

### 11. Interview Prep Agent

**Agent 目标**

根据 JD 要求、简历证据和匹配风险生成面试准备清单，不补写简历中不存在的经历。

**输入字段**

- `JDAnalysis`
- `ResumeAnalysis`
- `List[EvidenceMatch]`
- `ScoreBreakdown`

**输出字段**

- `likely_questions`
- `project_talking_points`
- `technical_preparation`
- `business_preparation`
- `risk_questions`
- `suggested_answer_strategy`

**示例输出**

```text
可能问题：请结合真实项目说明你如何完成 AI Agent 工作流拆解。
项目讲解：按背景、本人动作、工具、真实结果说明 Streamlit 原型。
技术准备：复习 Prompt、RAG 和模型效果评估的基本概念。
风险追问：简历对 RAG 的直接证据不足，可能被追问是否实际使用过。
回答策略：明确说明没有完整落地 RAG，再介绍已完成的 Agent 工作流和学习计划。
```

**为什么有价值**

匹配分析只有转化为面试准备才真正进入求职下一阶段。这个 Agent 把强证据变成项目讲解重点，把弱证据变成风险预案，并持续强调诚实表达边界。

## V3 新增 Agent 与工作流样例

### 12. Job Crawler Agent

**Agent 目标**

读取用户配置或自动生成的公开岗位源，在 robots.txt 允许时低频访问公开页面，并将各来源的成功、跳过或失败状态结构化记录。默认来源选项包括常见招聘平台和公司官网 Careers，但不会因为平台名称一刀切拒绝；Boss、猎聘、LinkedIn、Indeed、Seek 等可根据关键词和城市生成搜索 URL。

**输入字段**

- `List[JobSource]`
- `JobSearchPreference`
- 最大岗位数量、请求间隔、超时和缓存配置

**输出字段**

- `List[CrawlResult]`
- 每个结果包含来源、岗位列表、跳过原因、错误信息、抓取数量、`source_access_status`、`source_access_note` 和 `entered_parser`

**示例输出**

```json
{
  "source": {"source_name": "Company Careers", "allowed": true},
  "source_access_status": "public_accessible",
  "source_access_note": "公开 HTML 可访问，已进入解析",
  "entered_parser": true,
  "jobs": [
    {
      "job_title": "AI Product Intern",
      "city": "北京",
      "source_url": "https://company.com/careers/ai-product-intern",
      "source_url_status": "valid",
      "source_url_note": "真实岗位来源链接"
    }
  ],
  "skipped_reason": "",
  "error_message": "",
  "crawled_count": 1
}
```

**为什么有价值**

它把网络访问风险隔离在独立模块中。一个来源失败只会产生可解释状态，不会中断 V1、V2 或其他岗位源，同时每条岗位都能回到原始链接核查。若遇到登录、验证码、HTTP 429、robots 不允许或 JS 动态渲染导致静态 HTML 不含岗位文本，会跳过并建议用户改用 CSV/Excel 导入、手动粘贴 JD 或提供岗位详情页 URL。

### 13. Job Filter Agent

**Agent 目标**

根据岗位方向、关键词、城市和岗位类型过滤明显不相关的抓取结果，并优先排列偏好明确匹配的岗位。

**输入字段**

- `List[CrawledJob]`
- `JobSearchPreference`

**输出字段**

- `filtered_jobs`
- `removed_jobs`
- `filter_reason_summary`

**示例输出**

```text
保留 3 个岗位，移除 2 个岗位；
内容不相关 1 个；城市不匹配 1 个。
```

**为什么有价值**

公开页面的通用解析可能提取到导航文本或不相关职位。筛选 Agent 在进入昂贵的逐岗位匹配前先做一层可解释清洗，降低噪声和无效分析。

### 14. Crawl Workflow

**工作流目标**

把公开来源检查、抓取、清洗和偏好筛选串联起来，再将规范化岗位交给已验证的 V2 批量工作流。

**输入字段**

- 简历文本
- `JobSearchPreference`
- 岗位源 JSON，或 `use_demo=true`

**输出字段**

- `crawl_results`
- `raw_jobs`
- `JobFilterResult`
- `BatchMatchResult`
- 来源数量、跳过数量和 Demo 状态

**示例输出**

```text
处理岗位源：1
跳过/失败来源：0
原始岗位：6
筛选后岗位：2
最高匹配：AI Agent 产品助理，建议投递并针对性优化简历
```

**为什么有价值**

V3 没有重写匹配逻辑，而是把“获取岗位”作为 V2 的上游能力。这种设计便于在不影响既有功能的前提下替换来源适配器，也方便面试中说明系统边界和复用策略。

## V3.1 可靠性模块样例

### 15. Job Quality Scorer

**模块目标**

为每条抓取岗位计算可解释的字段质量分，不把抓取完整度与简历匹配分混为一谈。

**输入字段**

- `CrawledJob`

**输出字段**

- `quality_score`：0-100
- `quality_label`：高 / 中 / 低
- `quality_warnings`
- `jd_length`

**示例输出**

```json
{
  "quality_score": 68,
  "quality_label": "中",
  "quality_warnings": ["城市未知", "发布日期缺失"],
  "jd_length": 286
}
```

**为什么有价值**

匹配分回答“候选人与岗位是否相关”，质量分回答“抓取数据是否足够完整”。拆开两个指标，用户更容易判断分析结果是否值得信任。

### 16. Job Deduplicator

**模块目标**

识别多个来源或页面片段中的重复岗位，保留更完整的版本，同时记录去重过程。

**输入字段**

- `List[CrawledJob]`

**输出字段**

- 去重岗位列表
- 去重前/后数量
- 重复记录数量与重复组数量
- `duplicate_group`
- `is_duplicate`

**示例输出**

```json
{
  "input_count": 12,
  "output_count": 9,
  "duplicate_count": 3,
  "duplicate_group_count": 2
}
```

**为什么有价值**

同一岗位可能同时出现在列表卡片、详情入口或带追踪参数的链接中。去重能避免排行榜重复占位，也让抓取统计更诚实。

## V3.2 Analytics 模块输出样例

### 17. Job Matching Analytics

**模块目标**

将 V2/V3 的逐岗位 Agent 输出聚合为数据分析 Dashboard，帮助用户从“看一个岗位”切换到“比较一组岗位”。

**输入字段**

- `BatchMatchResult`，或 `List[JobMatchResult]`

**输出字段**

- 总览：岗位数、平均/最高/最低分、推荐档位和质量档位数量
- 分布：城市、岗位类型、推荐结论、质量标签
- Top 10：高匹配岗位、缺失关键词、常见技能和风险关键词

**示例输出**

```json
{
  "total_jobs": 8,
  "average_match_score": 68.4,
  "recommended_count": 4,
  "cautious_count": 3,
  "not_priority_count": 1,
  "high_quality_count": 5,
  "low_confidence_count": 1,
  "city_distribution": {"北京": 3, "上海": 2, "远程": 3},
  "top_missing_keywords": [
    {"keyword": "RAG", "count": 4},
    {"keyword": "A/B测试", "count": 3}
  ]
}
```

**为什么有价值**

Agent 工作流提供逐岗位解释，Analytics 模块提供跨岗位洞察。两者结合后，项目既能展示 AI 应用设计，也能展示指标定义、数据聚合、分布分析和结果导出能力。
