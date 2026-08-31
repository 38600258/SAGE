# AGENTS.md — 智能体入口
> T1 导航入口 + 常驻防线；目标 ≤50 行，超过 80 行必须拆到 T2，禁止为压缩行数删除行为规则。规则权威在 SAGE skill（`skills/sage-workflow/`）。

## 仓库概述
本仓库定义工具无关的智能体优先开发工作流（SAGE）；角色契约、模板、规范与脚本以 skill 内置 `core/` 为默认发行版，项目本地覆盖优先。

## 快速导航
- 开发方法论 → [智能体优先的自主编程方法论.md](../methodology/智能体优先的自主编程方法论.md)；项目管理方法论 → [智能体优先的自主项目管理方法论.md](../methodology/智能体优先的自主项目管理方法论.md)
- 开发/任务文档/变更日志/Git 规范 → [development-standards](../guides/development-standards.md) / [task-document-standards](../guides/task-document-standards.md) / [changelog-standards](../guides/changelog-standards.md) / [git-standards](../guides/git-standards.md)
- 设计原则 / 模型选择 / 执行通道 → [core-beliefs](../guides/core-beliefs.md) / [model-selection](../guides/model-selection.md) / [execution-channels](../guides/execution-channels.md)
- 架构总览 → [ARCHITECTURE.md](../scaffold/ARCHITECTURE.md)；变更日志 → [CHANGELOG.md](../scaffold/CHANGELOG.md)
- 看板 / 模式库 / 决策 / 交接 → [PROJECT_BOARD](../scaffold/docs/project/PROJECT_BOARD.md) / [KNOWN_PATTERNS](../scaffold/docs/project/KNOWN_PATTERNS.md) / [DECISION_LOG](../scaffold/docs/project/DECISION_LOG.md) / [HANDOVER](../scaffold/docs/project/HANDOVER-GUIDE.md)
- 任务模板 → [TASK-TEMPLATE.md](../templates/TASK-TEMPLATE.md)（L1 及以上必须物理复制模板）；ADR / PRD → [core/templates/](../templates/)
- 角色提示词 → [prompts/](../prompts/)；质量门禁 → `uv run python scripts/sage_linter.py --all`

## 任务入口规则（常驻防线）
1. **强制加载**：开发类任务启动时，Main Agent 必须加载 `prompts/orchestrator.md` + `prompts/planner.md`，同时承担 orchestrator 与 planner 角色；宿主已接入 SAGE skill 时，优先加载 `sage-workflow` skill。
2. **分级判定**：先判定 `TASK_LEVEL`，缺失或不确定按 L2；触发信号、阶段链与门禁见 orchestrator.md 等级表。
3. **派发门禁**：L1 及以上，TASK 1.1~1.5 冻结且计划放行后，方可派发 coder/closer 等执行型子代理；派发只传必要定位信息（TASK 路径、角色提示词路径、阶段、仓库根目录），调度信息以 TASK 元数据为准。
4. **失败恢复前现场复核**：修复失败或切换通道前，必须先复核现场（Git 状态、TASK 写入、进程状态、已有产出），确认「已经做了什么」再行动；禁止盲目重试。
5. **角色契约权威**：`prompts/` 是项目内角色契约权威；SAGE skill 内置 `core/` 默认发行版用于 Standalone/bootstrap，项目本地 `prompts/`、`templates/`、`docs/guides/` 覆盖默认发行版，CLI/subagent 只读取当前权威版本。

## 不可违反的约束
1. 部署阶段必须人类授权，智能体严禁私自触发。
2. L1 及以上，任务文档必须通过物理复制模板创建，禁止内存重建。
3. 收尾阶段严禁新增功能（scope creep）。
4. 合并到 `dev` 和 `main` 的权力永远属于人类。
5. 所有知识沉淀到仓库，不留在聊天或人脑中。
