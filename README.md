# SAGE — Steer, Agent Goes Execute

> **人类掌舵，智能体执行**

SAGE 是一套面向 AI 智能体驱动研发的完整方法论框架与治理工具链。它提供了从项目启动到生产部署的全生命周期管理规范，以及配套的角色提示词、任务模板、跨工具 skill 默认发行版和自动化检查器。


## 1.0 定位

SAGE 1.0 将工作流封装为 `skills/sage-workflow/`：

- **默认发行版**：skill 内置 `core/entry/`、`core/prompts/`、`core/templates/`、`core/guides/` 和 `core/methodology/`，新项目可直接 Standalone/bootstrap。
- **项目覆盖优先**：项目一旦存在本地 `AGENTS.md`、`prompts/`、`templates/` 或 `docs/guides/`，本地文件就是该项目权威来源。
- **跨工具适配**：`adapters/` 记录 Codex、CLI 和通用 AI 编程工具的接入边界；执行者仍以 TASK 文档和当前权威角色契约为准。
- **同步锚点**：`skills/sage-workflow/core/VERSION` 记录内置发行版版本与基线提交，便于后续 diff、升级和迁移。
## 核心哲学

在智能体优先的世界中，工程师的核心工作不再是编写代码，而是：
1. **设计环境** — 构建智能体能高效工作的结构、约束和反馈回路
2. **明确意图** — 将模糊的需求转化为可验证的原子级验收标准
3. **裁决例外** — 在智能体遇到无法自主决策的分歧时做出人类判断

## 三层架构

```
┌─────────────────────────────────────────────────────┐
│                  项目治理层                           │
│  (启动/章程 → 干系人 → 沟通 → 预算 → 需求 → 验收)      │
├─────────────────────────────────────────────────────┤
│                  开发运营层                           │
│  (WBS → 流水线 → 变更控制 → 发布 → 技术债)             │
├─────────────────────────────────────────────────────┤
│                  度量改进层                           │
│  (KPI → 监控 → 事件 → 复盘 → 回顾 → 知识管理)          │
└─────────────────────────────────────────────────────┘
```

## 快速开始

1. 阅读 [AGENTS.md](AGENTS.md) — 智能体入口与快速导航
2. 阅读核心方法论：
   - [智能体优先的自主编程方法论](智能体优先的自主编程方法论.md)
   - [智能体优先的自主项目管理方法论](智能体优先的自主项目管理方法论.md)
3. 运行基线检查：
   ```bash
   uv run python scripts/sage_linter.py --all
   ```

## 目录结构

| 路径 | 用途 |
|------|------|
| `AGENTS.md` | 智能体导航入口 |
| `ARCHITECTURE.md` | 架构总览 |
| `templates/` | 任务/ADR/PRD 模板（物理复制，禁止重建） |
| `prompts/` | 6 个角色提示词 |
| `skills/sage-workflow/` | SAGE 1.0 workflow skill 默认发行版 |
| `scripts/` | sage_linter 自动化检查器 |
| `docs/guides/` | 开发规范、设计原则 |
| `docs/project/` | 看板、模式库、决策日志 |

## 工具无关

SAGE 不绑定任何特定的 AI 编程工具。它可以与 Antigravity、Cursor、Windsurf、Codex、Claude Code、Copilot Agent 等任何智能体环境配合使用。

## 许可证

MIT
