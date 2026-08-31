---
name: sage-workflow
description: 运行并 bootstrap SAGE 智能体优先开发工作流，按阶段自动生成跨宿主派发信封并调用可用的原生 subagent 或安全 CLI fallback，适用于 Codex、Claude Code、Cursor、CLI agent 等工具。用户要求启动、规划、执行、审查、收尾、初始化、适配、迁移或升级 SAGE 任务/工作流/项目时使用，涵盖 TASK 文档、角色契约、执行通道、项目覆盖、质量门禁和 SAGE skill 封装。
---

# SAGE Workflow

SAGE 是一套智能体优先开发工作流。本 skill 封装 SAGE 1.0 默认发行版，使工具在目标项目尚未放置本地 SAGE 文件前，也能启动并引导工作流。

## 运行模式

1. **项目覆盖模式**：目标仓库已有 `AGENTS.md`、`prompts/`、`templates/` 或 `docs/guides/` 时，这些项目本地文件就是该项目权威来源。
2. **独立启动模式**：目标仓库没有本地 SAGE 文件时，先加载 `core/entry/AGENTS.md`，再使用 `core/` 文件作为默认权威来源，并将其 bootstrap 到项目仓库。
3. **迁移升级模式**：升级 SAGE 本身时，对照 `core/VERSION` 比较项目文件与内置默认发行版，显式更新 docs/templates/prompts。

若内置 core 规则与项目本地规则冲突，项目本地规则对该项目优先。内置 core 是默认发行版，不是静默覆盖层。

## 启动流程

1. 从用户请求或当前工作区定位 `REPO_ROOT`。
2. 按顺序检查项目本地入口：`AGENTS.md`；不存在时，回退到 `core/entry/AGENTS.md`。
3. 加载当前有效入口文件，并加载 `prompts/orchestrator.md` 与 `prompts/planner.md`；独立启动模式下使用 `core/entry/` 与 `core/prompts/` 中的对应文件。
4. 判定 `TASK_LEVEL`：L0/L1/L2/L3；缺失或不确定时按 L2。
5. L1 及以上必须先物理复制当前有效的 `TASK-TEMPLATE.md` 到活跃任务路径，再填写内容。
6. 按当前有效 SAGE 规则流转 Init → PlanReview → Dev → CodeReview → Close。
7. 对外部执行者只传定位信息：`REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE`，以及可选 `DIFF_CMD`。
8. 使用项目 `scripts/sage_linter.py` 和 Git hooks 验证；项目缺少这些文件时，先执行 bootstrap，或从 skill 目录运行 `core/scripts/sage_linter.py`，不得把“没有本地门禁”当成通过。
9. L1 及以上阶段派发前运行 `core/scripts/dispatch_phase.py prepare`；宿主支持原生 subagent 时，Main Agent 读取 `action=spawn_subagent` 信封并立即调用宿主 API，完成后运行 `verify`；宿主不支持时，按 adapter 能力使用 `run-cli`。

## 自动派发运行时

`dispatch_phase.py` 是跨宿主的协议层，不越过宿主权限伪造 subagent。它统一生成派发上下文、记录派发前快照，并验证执行者是否真实回写 TASK 和产生 Git 产出：

```text
capabilities → prepare → [宿主 spawn_subagent 或 run-cli] → verify
                                      └──────────────→ status / cancel
```

常用命令：

```powershell
uv run python <skill-root>/core/scripts/dispatch_phase.py capabilities --adapter codex
uv run python <skill-root>/core/scripts/dispatch_phase.py doctor --adapter codex --repo-root <repo>
uv run python <skill-root>/core/scripts/dispatch_phase.py prepare --repo-root <repo> --task-path <task> --phase dev --adapter codex --model deepseek-v4-pro --format json
uv run python <skill-root>/core/scripts/dispatch_phase.py verify --receipt <receipt> --format json
uv run python <skill-root>/core/scripts/dispatch_phase.py run-cli --receipt <receipt> --command-json '["agent-cli","--prompt","{prompt}"]'
uv run python <skill-root>/core/scripts/dispatch_phase.py provision --adapter codex --target-dir <agents 目录>
```
> 命令执行口径：默认推荐 `uv run python`（uv 自动优先使用项目虚拟环境）；无 uv 环境时，优先运行项目虚拟环境中的 python（例如 `.venv`），没有项目虚拟环境再使用系统 python——下同，全文命令示例均按此口径执行。

- Codex 等原生宿主：`prepare` 输出 `spawn_subagent`、`sage_reviewer`/`sage_coder`/`sage_closer` 和最小上下文；Main Agent 必须用当前宿主的原生派发工具执行，不能只把信封打印给用户。
- CLI 宿主：命令必须是 JSON 字符串数组，禁止 shell 拼接；CLI 输出只作为日志，成功必须由 `verify` 根据 TASK/Git 回执判定。
- 从已声明支持原生 subagent 的 adapter 切换 CLI 时，必须提供 `--fallback-reason` 和 `--fallback-authorized`，避免静默降级。
- 宿主无命名注册但有通用子代理能力时，adapter 可声明 `injected_subagent`；`prepare --channel injected` 生成的信封带 `injection` 隔离字段，派发前必须人工授权并记录隔离等级。通道优先级为 subagent > injected > cli；独立审查通道累计失败 ≥3 次触发熔断，合法出口为人类接管、人工授权降级审查或任务挂起。
- `doctor` 在 Init 前探测各通道可用性并给出推荐通道；`provision` 生成宿主 agent 注册文件（Codex TOML 或项目内 Markdown agents），注册生效以宿主实际派发为准。
- `cancel` 对原生宿主只记录 `host_cancel_required`，实际取消由宿主 API 完成；脚本不能假装拥有宿主进程控制权。
- 模型配置位于 adapter 的 `models.<phase>`；`prepare --model <id>` 只覆盖声明为 `request` 或 CLI 参数型的通道，注册型 agent 必须同步宿主配置。
- CLI 使用模型时，命令数组必须包含 `{model}`；模型不会写入角色 prompt，也不能依赖 prompt 中的模型占位符。

## 内置核心

- `core/VERSION`：SAGE 发行版本与基线同步锚点。
- `core/entry/`：通用默认入口文件（`AGENTS.md`）。
- `core/prompts/`：orchestrator、planner、reviewer、coder、closer、doc-gardener 的默认角色契约。
- `core/templates/`：TASK、ADR、PRD 默认模板。
- `core/guides/`：工作流默认操作指南，包含任务文档、CHANGELOG、Git、执行通道和开发规范。
- `core/methodology/`：SAGE 默认方法论文档。
- `core/scaffold/`：standalone 项目架构、CHANGELOG、看板、决策日志和交接初始骨架。
- `core/scripts/sage_linter.py`：可移植的质量门禁脚本。
- `core/scripts/dispatch_phase.py`：生成跨宿主派发信封、执行受控 CLI 并验证 TASK/Git 产出。
- `core/scripts/bootstrap_sage.py`：将默认发行版复制到新项目并重写项目相对链接。
- `core/githooks/`：提交信息硬门禁及启用说明。
- `adapters/`：工具专用执行说明。
- `references/dispatch-protocol.md`：adapter JSON、派发状态、宿主职责和回执验证协议。
- `references/path-registry.md`：项目覆盖与内置默认文件的路径查找顺序。

## Bootstrap 规则

当项目缺少 SAGE 文件时，优先运行：`uv run python <skill-root>/core/scripts/bootstrap_sage.py --repo-root <项目绝对路径>`。需要预览时追加 `--dry-run`；已有本地规则时不加 `--force`，避免静默覆盖。bootstrap 会将内置文件复制进仓库并重写入口/指南的项目相对链接，而不是长期从 skill 目录运行：

- `core/prompts/*` → `prompts/`
- `core/templates/*` → `templates/`
- `core/guides/*` → `docs/guides/`
- `core/methodology/*` → 项目方法论文档位置
- `core/entry/AGENTS.md` → 项目 `AGENTS.md` 入口文件
- `core/scripts/sage_linter.py` → `scripts/sage_linter.py`
- `core/scripts/bootstrap_sage.py` 仅作为 bootstrap 工具保留在 skill 目录，不复制到项目运行时文件；
- `core/githooks/*` → `.githooks/*`；若目标是 Git 仓库且未配置 `core.hooksPath`，bootstrap 会自动设置为 `.githooks`；若已有配置则提示来源和路径并保持不变；使用 `--skip-hooks` 可显式跳过这一步。
- `core/scripts/dispatch_phase.py` → `scripts/sage_dispatch.py`；`adapters/<id>/`（含 `<id>.json`、`<id>.md` 与子代理生成脚本 `provision.py`）整目录 → `docs/guides/execution-adapters/<id>/`，使 bootstrap 后项目可脱离 skill 目录运行派发协议与子代理生成。
- `references/*` → `docs/guides/references/`：派发协议全文与路径注册表随 bootstrap 落盘，脱离 skill 目录处理信封字段、回执格式与路径查找争议时有据可查。

完成 bootstrap 后，复制到项目中的本地文件成为该仓库的权威来源。Bootstrap 至少应同时带入角色契约、TASK 模板、任务/CHANGELOG/Git 规范、质量 linter 和提交 hooks；只复制 `SKILL.md` 不算完成。`--dry-run` 只预览文件复制和 hooks 配置，不修改仓库；非 Git 目录会提示并跳过 hooks 配置。

## 红线

- 未经人类明确授权，不执行 merge、push、deploy，也不触碰生产系统。
- 后续阶段不得重写已经冻结的 TASK 上游章节。
- 不把聊天历史作为唯一证据源；决策、证据和交接必须写入仓库文件。
- 不静默维护两套活跃权威来源；若内置规则与项目本地规则同时存在，必须说明当前采用哪一套。
- 未确认 `core/VERSION` 与项目文档同步前，不对外发布本 skill。
