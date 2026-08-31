# 架构总览

> 本文件提供 SAGE 1.0 的顶层架构地图。
> 详细规范参见 [development-standards.md](skills/sage-workflow/core/guides/development-standards.md) 与 [execution-channels.md](skills/sage-workflow/core/guides/execution-channels.md)。

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
│  AGENTS + docs/project + skill core defaults  │
└──────────────────────┬───────────────────────┘
                       │ task execution
┌──────────────────────▼───────────────────────┐
│              Execution Channels              │
│  Dispatcher → Main Agent / subagent / CLI      │
└──────────────────────────────────────────────┘
```

## 2. 权威来源规则

| 场景 | 权威来源 | 说明 |
|------|----------|------|
| 新项目无 SAGE 文件 | `skills/sage-workflow/core/` | 使用默认发行版启动，并建议 bootstrap 到项目 |
| 项目已有 SAGE 文件 | 项目本地 `AGENTS.md`、`docs/project/` 与必要覆盖文件 | 项目覆盖优先；默认角色、模板、指南和门禁从 skill core 读取 |
| 外包执行阶段 | TASK 文档 + 当前权威角色契约 | CLI/subagent 只承载角色，不拥有调度事实 |
| 工具差异 | `skills/sage-workflow/adapters/` 或 `skills/sage-workflow/core/guides/execution-channels.md` | 只处理执行载体差异，不改写角色契约 |
| 阶段派发 | `dispatch_phase.py` 回执 + 宿主原生 API/CLI | 统一生成最小上下文、模型路由和回执验证，不伪造宿主能力 |

## 3. 目录结构与职责

| 路径 | 类型 | 职责 |
|------|------|------|
| `AGENTS.md` | 入口 | 工具无关 SAGE 入口规则 |
| `skills/sage-workflow/core/prompts/` | 角色契约默认发行版 | orchestrator、planner、reviewer、coder、closer、doc-gardener |
| `skills/sage-workflow/core/templates/` | 模板默认发行版 | TASK、ADR、PRD 物理复制模板 |
| `skills/sage-workflow/core/guides/` | 规范默认发行版 | 开发、任务、CHANGELOG、Git、执行通道、模型选择和核心信念 |
| `docs/project/` | 项目状态 | 看板、模式库、决策日志、交接指南、归档任务 |
| `skills/sage-workflow/core/scripts/` | 工具默认发行版 | `sage_linter.py`、`bootstrap_sage.py`、`dispatch_phase.py` |
| `skills/sage-workflow/core/githooks/` | 提交门禁默认发行版 | commit-msg 硬门禁及启用说明 |
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
| `skills/sage-workflow/core/scaffold/` | standalone 项目初始骨架 |
| `skills/sage-workflow/core/scripts/` | 默认 linter、bootstrap 与阶段派发脚本 |
| `skills/sage-workflow/core/githooks/` | 默认提交 hooks |
| `skills/sage-workflow/adapters/` | Codex、CLI、通用工具适配说明与 JSON 能力声明 |
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
  │
  ▼
Dispatcher prepare 生成最小上下文与派发前回执
  │
  ├─ action=spawn_subagent → Main Agent 调用宿主原生 API，并按 binding 传递/校验模型
  └─ action=run_cli → Dispatcher 执行无 shell 命令数组，校验 `{model}` 消费
  │
  ▼
verify 检查 TASK 阶段章节 + Git 指纹/HEAD
  │
  ▼
TASK 证据链 + CHANGELOG + 项目看板 + Git 提交
```

## 6. 已知演进方向

- 增加 `sage doctor`：检查 skill 默认发行版与项目本地覆盖的同步状态。
- 增加 diff/migration 工具：辅助项目从旧版 SAGE 升级到新版 skill core。
- 为更多工具补充 adapter：Claude Code、Cursor、Windsurf 等可在 `adapters/` 中扩展，并声明各阶段模型绑定方式。
