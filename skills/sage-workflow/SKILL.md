---
name: sage-workflow
description: 运行 SAGE 智能体优先开发工作流，适用于 Codex、Claude Code、Cursor、CLI agent 等工具。用户要求启动、规划、执行、审查、收尾、初始化、适配或升级 SAGE 任务/工作流/项目时使用，涵盖 TASK 文档、角色契约、执行通道、项目覆盖和 SAGE skill 封装。
---

# SAGE Workflow

SAGE 是一套智能体优先开发工作流。本 skill 封装 SAGE 1.0 默认发行版，使工具在目标项目尚未放置本地 SAGE 文件前，也能启动并引导工作流。

## 运行模式

1. **项目覆盖模式**：目标仓库已有 `AGENTS.md`、`prompts/`、`templates/` 或 `docs/guides/` 时，这些项目本地文件就是该项目权威来源。
2. **独立启动模式**：目标仓库没有本地 SAGE 文件时，使用本 skill 内置的 `core/` 文件作为默认权威来源，并建议将其 bootstrap 到项目仓库。
3. **迁移升级模式**：升级 SAGE 本身时，对照 `core/VERSION` 比较项目文件与内置默认发行版，显式更新 docs/templates/prompts。

若内置 core 规则与项目本地规则冲突，项目本地规则对该项目优先。内置 core 是默认发行版，不是静默覆盖层。

## 启动流程

1. 从用户请求或当前工作区定位 `REPO_ROOT`。
2. 按顺序检查项目本地入口：`AGENTS.override.md`、`AGENTS.md`、工具专用入口文件。
3. 加载当前有效入口文件，并加载 `prompts/orchestrator.md` 与 `prompts/planner.md`；独立启动模式下使用 `core/prompts/` 中的对应文件。
4. 判定 `TASK_LEVEL`：L0/L1/L2/L3；缺失或不确定时按 L2。
5. L1 及以上必须先物理复制当前有效的 `TASK-TEMPLATE.md` 到活跃任务路径，再填写内容。
6. 按当前有效 SAGE 规则流转 Init → PlanReview → Dev → CodeReview → Close。
7. 对外部执行者只传定位信息：`REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE`，以及可选 `DIFF_CMD`。
8. 使用项目质量门禁验证；项目缺少门禁时，按内置 linter 指南作为检查清单。

## 内置核心

- `core/VERSION`：SAGE 发行版本与基线同步锚点。
- `core/entry/`：通用、Codex、Antigravity/Gemini 类工具的默认入口文件。
- `core/prompts/`：orchestrator、planner、reviewer、coder、closer、doc-gardener 的默认角色契约。
- `core/templates/`：TASK、ADR、PRD 默认模板。
- `core/guides/`：工作流默认操作指南，包含任务文档规范 `task-document-standards.md`。
- `core/methodology/`：SAGE 默认方法论文档。
- `adapters/`：工具专用执行说明。
- `references/path-registry.md`：项目覆盖与内置默认文件的路径查找顺序。

## Bootstrap 规则

当项目缺少 SAGE 文件时，应将内置文件复制进仓库，而不是长期从 skill 目录运行：

- `core/prompts/*` → `prompts/`
- `core/templates/*` → `templates/`
- `core/guides/*` → `docs/guides/`
- `core/methodology/*` → 项目方法论文档位置
- `core/entry/*` → 项目入口文件，例如 `AGENTS.md`、`AGENTS.override.md` 或工具专用等价文件

完成 bootstrap 后，复制到项目中的本地文件成为该仓库的权威来源。

## 红线

- 未经人类明确授权，不执行 merge、push、deploy，也不触碰生产系统。
- 后续阶段不得重写已经冻结的 TASK 上游章节。
- 不把聊天历史作为唯一证据源；决策、证据和交接必须写入仓库文件。
- 不静默维护两套活跃权威来源；若内置规则与项目本地规则同时存在，必须说明当前采用哪一套。
- 未确认 `core/VERSION` 与项目文档同步前，不对外发布本 skill。
