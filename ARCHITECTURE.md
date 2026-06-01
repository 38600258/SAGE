# 架构总览

> 本文件提供 SAGE 1.0 的顶层架构地图。
> 详细规范参见 [development-standards.md](docs/guides/development-standards.md) 与 [execution-channels.md](docs/guides/execution-channels.md)。

## 1. 系统定位

SAGE 是工具无关的智能体优先开发工作流。1.0 版本将流程、角色契约、TASK 模板和核心指南封装为可分发的 workflow skill，同时保留项目本地覆盖能力。

```text
┌──────────────────────────────────────────────┐
│              SAGE Workflow Skill             │
│  SKILL.md + core defaults + adapters         │
└──────────────────────┬───────────────────────┘
                       │ bootstrap / fallback
┌──────────────────────▼───────────────────────┐
│              Project-local SAGE              │
│  AGENTS + prompts + templates + docs/guides  │
└──────────────────────┬───────────────────────┘
                       │ task execution
┌──────────────────────▼───────────────────────┐
│              Execution Channels              │
│  Main Agent / subagent / CLI / tool adapter  │
└──────────────────────────────────────────────┘
```

## 2. 权威来源规则

| 场景 | 权威来源 | 说明 |
|------|----------|------|
| 新项目无 SAGE 文件 | `skills/sage-workflow/core/` | 使用默认发行版启动，并建议 bootstrap 到项目 |
| 项目已有 SAGE 文件 | 项目本地 `AGENTS.md`、`prompts/`、`templates/`、`docs/guides/` | 项目覆盖优先，skill 只作适配和迁移参考 |
| 外包执行阶段 | TASK 文档 + 当前权威角色契约 | CLI/subagent 只承载角色，不拥有调度事实 |
| 工具差异 | `skills/sage-workflow/adapters/` 或项目 `docs/guides/execution-channels.md` | 只处理执行载体差异，不改写角色契约 |

## 3. 目录结构与职责

| 路径 | 类型 | 职责 |
|------|------|------|
| `AGENTS.md` | 入口 | 工具无关 SAGE 入口规则 |
| `AGENTS.override.md` | 入口 | Codex app 自包含覆盖入口 |
| `GEMINI.md` | 入口 | Antigravity/Gemini 类工具覆盖规则 |
| `prompts/` | 角色契约 | orchestrator、planner、reviewer、coder、closer、doc-gardener |
| `templates/` | 模板 | TASK、ADR、PRD 物理复制模板 |
| `docs/guides/` | 规范 | 开发规范、执行通道、模型选择、核心信念 |
| `docs/project/` | 项目状态 | 看板、模式库、决策日志、交接指南、归档任务 |
| `scripts/` | 工具 | `sage_linter.py` 等质量门禁 |
| `skills/sage-workflow/` | Skill 发行版 | SAGE 1.0 默认规范包与跨工具适配层 |

## 4. Skill 内部结构

| 路径 | 职责 |
|------|------|
| `skills/sage-workflow/SKILL.md` | skill 触发、模式选择、启动流程和边界红线 |
| `skills/sage-workflow/core/VERSION` | 默认发行版版本、基线提交和同步锚点 |
| `skills/sage-workflow/core/entry/` | 默认入口文件 |
| `skills/sage-workflow/core/prompts/` | 默认角色契约 |
| `skills/sage-workflow/core/templates/` | 默认 TASK/ADR/PRD 模板 |
| `skills/sage-workflow/core/guides/` | 默认操作指南 |
| `skills/sage-workflow/core/methodology/` | 默认方法论文档 |
| `skills/sage-workflow/adapters/` | Codex、CLI、通用工具适配说明 |
| `skills/sage-workflow/references/` | 路径解析和迁移参考 |

## 5. 阶段数据流

```text
用户需求
  │
  ▼
Main Agent 加载入口 + orchestrator/planner
  │
  ▼
判定 TASK_LEVEL，L1+ 物理复制 TASK 模板
  │
  ▼
PlanReview / Dev / CodeReview / Close
  │       │
  │       └─ subagent/CLI 只接收 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE
  ▼
TASK 证据链 + CHANGELOG + 项目看板 + Git 提交
```

## 6. 已知演进方向

- 增加 `sage doctor`：检查 skill 默认发行版与项目本地覆盖的同步状态。
- 增加 diff/migration 工具：辅助项目从旧版 SAGE 升级到新版 skill core。
- 为更多工具补充 adapter：Claude Code、Cursor、Windsurf 等可在 `adapters/` 中扩展。
