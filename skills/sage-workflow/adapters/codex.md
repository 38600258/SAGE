# Codex 适配器

当 SAGE 运行在 Codex CLI 或 Codex desktop 中时，使用本适配说明。

## 入口加载

- 项目存在 `AGENTS.override.md` 时优先加载，因为 Codex 可能将其作为项目入口。
- 若目标项目只有内置 core，可在规划前加载 `core/prompts/orchestrator.md` 与 `core/prompts/planner.md`。
- Codex 的 plan 工具只用于向用户展示进度；持久事实仍以 TASK 文档为准。

## 执行通道

- 仅在工具策略允许且原生角色 subagent 可用时，使用 reviewer/coder/closer subagent。
- subagent 不可用或未能写回 TASK/Git 证据时，必须先复核现场状态，再重试或切换 fallback。
- CLI fallback 仍然只传 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE` 和可选 `DIFF_CMD`。

## Git 边界

- L1 及以上任务分支使用 `feat|fix|docs|chore|refactor/t-XXX-*`，不得使用工具名前缀。
- 未经用户明确授权，不执行 merge、push 或 deploy。
