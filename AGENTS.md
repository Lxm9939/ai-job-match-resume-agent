# AGENTS.md

## 项目定位

这是一个 Streamlit + 多 Agent 求职辅助项目：AI 岗位搜索、匹配评分与求职优化助手。后续 Codex 开发应优先保持项目可运行、结构清晰、无 API Key 泄漏。

## 开发规范

- 不要把真实 API Key、简历隐私信息或投递记录提交到仓库。
- LLM 相关逻辑只放在 `src/llm_client.py` 或调用它的 Agent 中。
- 新增 Agent 时放在 `src/agents/`，输入输出尽量使用 `src/schemas/models.py` 的 Pydantic 模型。
- 简历优化必须遵守“不编造经历、不虚构项目、不添加用户没做过的内容”。
- UI 改动优先保持首页即工具，不做营销落地页。
- 新增功能后至少补充一个测试或一个 `docs/test_cases.md` 手动测试场景。

## 运行命令

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 测试命令

```bash
pytest
```

## 环境变量

复制 `.env.example` 为 `.env`：

```bash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
LLM_MODE=mock
APP_DEBUG=false
```

`LLM_MODE` 可选：

- `mock`：默认本地规则模式，无需 API Key。
- `openai`：强制使用 OpenAI API；无 Key 时自动回退 mock。
- `auto`：有 Key 使用 OpenAI，无 Key 使用 mock。
