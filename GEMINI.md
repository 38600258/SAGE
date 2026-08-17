# GEMINI.md — Antigravity 2.0 专用规则

> 本文件优先级高于 AGENTS.md，仅包含 Antigravity 2.0 特有的行为约束。
> 通用规则见 AGENTS.md，本文件仅补充 Antigravity 原生能力的使用规范。

## 核心行为约束

### 任务文档策略
- 仓库 `docs/project/ACTIVE_TASK_T-XXX.md` 是活跃任务唯一事实来源（Single Source of Truth）；完成后归档到 `docs/project/tasks/T-XXX.md`
- Antigravity artifact（implementation_plan/task/walkthrough）仅作为展示辅助层
- 每个阶段结束时必须写入仓库 TASK 文档，artifact 从 TASK 文档派生
- 会话中断时 TASK 文档必须完好保存在仓库中

### 盲审规范
- L1 及以上 reviewer/coder/closer 派发前运行 `uv run python skills/sage-workflow/core/scripts/dispatch_phase.py prepare`，adapter 使用项目实际工具配置。
- `action=spawn_subagent` 时由 main agent 调用宿主原生 API；`action=run_cli` 时使用回执执行 `run-cli`。
- L0 不调用 CLI/subagent，由 main agent 直接执行。
- 派发 prompt 只包含 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE` 和可选 `DIFF_CMD`；其他调度信息从 TASK 元数据读取。
- 执行完成后必须运行 `verify`；CLI/subagent 回复、stdout 或退出码不能单独作为成功依据。

### Subagent 使用规范
- Orchestrator 角色由 main agent 天然承担，不创建独立 subagent
- 研究任务使用 research subagent（Workspace: inherit）
- reviewer/coder/closer 的实际通道和阶段模型由 adapter profile 决定；原生 subagent 可用时 main agent 按模型绑定自动调用，否则使用受控 CLI `{model}` 参数

### Artifact 使用规范
- artifact 是展示辅助层，不是工作流的必需依赖
- 各阶段完成时，从 TASK 文档派生生成对应 artifact：
  - 初始化完成 → `implementation_plan.md`（从 TASK 1.1~1.5 派生）
  - 编码完成 → `task.md`（从 TASK 3.1 派生）
  - 收尾完成 → `walkthrough.md`（从 TASK 3.2 + 5.x 派生）
- Artifact 存放于 Antigravity 工作区，不进入 Git 仓库
- Artifact 仅用于人类阅读，不是工作流的必需依赖

### 质量门禁
- 每阶段退出前执行：`uv run python skills/sage-workflow/core/scripts/sage_linter.py --all`
- 文件写入后自动校验（如 hooks 可用）：`uv run python skills/sage-workflow/core/scripts/sage_linter.py --check-scope`

### 模型选择
- Orchestrator/Planner: 强推理模型（Opus/Pro-high），UI 选择
- Reviewer/Coder/Closer: 按 `skills/sage-workflow/core/guides/execution-channels.md` 配置的 CLI 或备选 subagent
- Doc-gardener/Schedule: 低成本文档模型或工具默认模型
- L1 任务: Flash 全流程 | L3 任务: Opus 全流程
- 详细指南 → [core/guides/model-selection.md](skills/sage-workflow/core/guides/model-selection.md)

## 不可违反的约束
1. 部署阶段必须人类授权（ask_permission），智能体严禁私自触发
2. L3 任务每阶段结束须人工确认后方可流转
3. 任务文档必须通过物理复制模板创建，禁止内存重建
4. 收尾阶段严禁新增功能（scope creep）
5. 合并到 `dev` 和 `main` 的权力永远属于人类
6. 所有知识沉淀到仓库，不留在聊天或人脑中
