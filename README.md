# SAGE — Steer, Agent Goes Execute

> **人类掌舵，智能体执行**

SAGE 是一套面向 AI 智能体驱动研发的完整方法论框架与治理工具链。它提供了从项目启动到生产部署的全生命周期管理规范，以及配套的角色提示词、任务模板、跨工具 skill 默认发行版和自动化检查器。


## 1.0 定位

SAGE 1.0 将工作流封装为 `skills/sage-workflow/`：

- **默认发行版**：skill 内置 `core/entry/`、`core/prompts/`、`core/templates/`、`core/guides/`、`core/scripts/`、`core/githooks/` 和 `core/methodology/`，新项目可直接 Standalone/bootstrap。
- **项目覆盖优先**：项目一旦存在本地 `AGENTS.md`、`prompts/`、`templates/` 或 `docs/guides/`，本地文件就是该项目权威来源。
- **跨工具适配**：`adapters/` 记录 Codex、CLI 和通用 AI 编程工具的接入边界；执行者仍以 TASK 文档和当前权威角色契约为准。
- **运行时派发**：`dispatch_phase.py` 生成统一派发信封；原生宿主由 Main Agent 调用 subagent API，CLI 宿主使用安全命令数组，最终统一验证 TASK/Git 产出。
- **模型路由**：adapter 按阶段声明默认模型和绑定方式；支持请求级覆盖的宿主使用 `--model`，CLI 必须消费 `{model}`，注册型 Agent 则与宿主配置保持一致。
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
   - [智能体优先的自主编程方法论](skills/sage-workflow/core/methodology/智能体优先的自主编程方法论.md)
   - [智能体优先的自主项目管理方法论](skills/sage-workflow/core/methodology/智能体优先的自主项目管理方法论.md)
3. 运行基线检查：
   ```bash
   uv run python skills/sage-workflow/core/scripts/sage_linter.py --all
   uv run python skills/sage-workflow/core/scripts/dispatch_phase.py capabilities --adapter codex
   ```

> 命令执行口径：默认推荐 `uv run python`（uv 自动优先使用项目虚拟环境）；无 uv 环境时，优先运行项目虚拟环境中的 python（例如 `.venv`），没有项目虚拟环境再使用系统 python。SAGE 全部命令示例均按此口径执行。

## 目录结构

| 路径 | 用途 |
|------|------|
| `AGENTS.md` | 智能体导航入口 |
| `ARCHITECTURE.md` | 架构总览 |
| `skills/sage-workflow/core/templates/` | 任务/ADR/PRD 默认模板（物理复制，禁止重建） |
| `skills/sage-workflow/core/prompts/` | 6 个角色提示词默认发行版 |
| `skills/sage-workflow/` | SAGE 1.0 workflow skill 默认发行版 |
| `skills/sage-workflow/core/scripts/` | linter、bootstrap 与跨宿主派发自动化工具 |
| `skills/sage-workflow/core/githooks/` | 提交信息硬门禁默认发行版 |
| `skills/sage-workflow/core/guides/` | 开发、任务、CHANGELOG、Git、执行通道和设计规范 |
| `skills/sage-workflow/adapters/*.json` | 原生 subagent/CLI 能力、阶段 agent 映射与模型路由 |
| `docs/project/` | 看板、模式库、决策日志 |

## 适用场景与流程重量

SAGE 的流程强度按任务等级（L0~L3）自适应，但**默认偏向 L2**（不确定时按 L2 处理）。这意味着：

| 场景 | 适合度 | 说明 |
|------|--------|------|
| 多人团队 + 智能体协作 | ✅ 最佳 | 盲审隔离、证据链、看板协同发挥最大价值 |
| 高危系统（金融/医疗/基础设施） | ✅ 最佳 | L3 每阶段人工确认 + 回滚演练 |
| 单人 + 智能体的方法论/文档仓库 | ⚠️ 偏重 | T-008 实践：272 行 TASK + 10 条 AC + 两轮盲审，流程开销接近内容本身 |
| 快速原型/一次性脚本 | ❌ 过重 | 建议直接用 L0 或跳过 SAGE |

**单人场景建议**：
- 优先使用 L0/L1 等级，跳过盲审
- 将"不确定按 L2"改为"不确定按 L1"
- TASK 文档可精简到 1.1~1.4（省略 1.3a/1.3b）
- 保留质量门禁（sage_linter）但可放宽新鲜度告警

SAGE 不强制所有项目走完整流程——它是工具箱，不是流水线。选择适合当前项目复杂度的子集即可。

## 工具无关

SAGE 不绑定任何特定的 AI 编程工具。它可以与 Antigravity、Cursor、Windsurf、Codex、Claude Code、Copilot Agent 等任何智能体环境配合使用。

## 许可证

MIT
