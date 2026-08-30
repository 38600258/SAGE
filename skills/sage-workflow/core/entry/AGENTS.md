# AGENTS.md — 智能体入口
> T1 导航入口；目标 ≤80 行，超过 100 行必须拆到 T2，禁止为压缩行数删除行为规则。

## 仓库概述
本仓库定义工具无关的智能体优先开发工作流（SAGE）；工具覆盖见 `GEMINI.md` / `AGENTS.override.md`。

## 快速导航
**方法论与架构**
- 开发方法论 → [智能体优先的自主编程方法论.md](../methodology/智能体优先的自主编程方法论.md)
- 项目管理方法论 → [智能体优先的自主项目管理方法论.md](../methodology/智能体优先的自主项目管理方法论.md)
- 架构总览 → [ARCHITECTURE.md](../scaffold/ARCHITECTURE.md)
- 变更日志 → [CHANGELOG.md](../scaffold/CHANGELOG.md)

**规范与状态**
- 开发规范 → [docs/guides/development-standards.md](../guides/development-standards.md)
- 任务文档规范 → [docs/guides/task-document-standards.md](../guides/task-document-standards.md)
- 变更日志规范 → [docs/guides/changelog-standards.md](../guides/changelog-standards.md)
- Git 规范 → [docs/guides/git-standards.md](../guides/git-standards.md)
- 设计原则 → [docs/guides/core-beliefs.md](../guides/core-beliefs.md)
- 模型选择 → [docs/guides/model-selection.md](../guides/model-selection.md)
- 执行通道 → [docs/guides/execution-channels.md](../guides/execution-channels.md)
- 项目看板 → [docs/project/PROJECT_BOARD.md](../scaffold/docs/project/PROJECT_BOARD.md)
- 模式库 / 决策 / 交接 → [KNOWN_PATTERNS](../scaffold/docs/project/KNOWN_PATTERNS.md) / [DECISION_LOG](../scaffold/docs/project/DECISION_LOG.md) / [HANDOVER](../scaffold/docs/project/HANDOVER-GUIDE.md)

**模板与质量**
- 任务模板 → [templates/TASK-TEMPLATE.md](../templates/TASK-TEMPLATE.md)（L1 及以上必须物理复制）
- ADR / PRD 模板 → [ADR](../templates/ADR-template.md) / [PRD](../templates/PRD-template.md)
- 角色提示词 → [prompts/](../prompts/)
- 质量门禁 → `uv run python scripts/sage_linter.py --all`

## 阶段必读规范

| 阶段 | 必读规范 |
|------|----------|
| 初始化 | [task-document-standards.md](../guides/task-document-standards.md) |
| 编码实现 | [task-document-standards.md](../guides/task-document-standards.md) |
| 收尾归档 | [changelog-standards.md](../guides/changelog-standards.md)、[git-standards.md](../guides/git-standards.md)、[task-document-standards.md](../guides/task-document-standards.md) |

## 任务入口规则

1. **强制加载**：开发类任务启动时，Main Agent 必须加载 `prompts/orchestrator.md` + `prompts/planner.md`；Main Agent 同时承担 orchestrator 和 planner 角色。

2. **分级判定**：先判定 `TASK_LEVEL`（L0/L1/L2/L3），缺失或不确定按 L2。

   | 等级 | 触发信号 | 阶段链 | 门禁 |
   |------|---------|--------|------|
   | L0 | 纯机械修正、格式化、极小文案修补 | Init → Dev → Close | 免 TASK；最小验证 + 中文提交 |
   | L1 | 纯文档/纯测试/纯重构/不涉及外部系统 | Init → Dev → Close | 物理 TASK + 计划放行 + 质量门禁 |
   | L2 | 业务逻辑变更/新增功能/修复 Bug | Init → PlanReview → 计划放行 → Dev → CodeReview → Close | 两次盲审 + 计划放行 + 证据链 |
   | L3 | 数据库 Schema 变更/外部 API 对接/部署配置 | Init → PlanReview → Dev → CodeReview → Close | 每阶段人工确认 |

3. **阶段-角色映射**：L0 不适用本表；L1 及以上各阶段对应唯一角色契约与 TASK 输出章节。

   | 阶段 | 角色 prompt | TASK 输出节 |
   |------|------------|-------------|
   | 初始化 | `prompts/planner.md` | 1.1~1.5 |
   | 计划盲审 | `prompts/reviewer.md` 流程A | 2.x |
   | 编码实现 | `prompts/coder.md` | 3.x |
   | 代码盲审 | `prompts/reviewer.md` 流程B | 4.x |
   | 收尾归档 | `prompts/closer.md` | 5.x |

4. **角色契约**：`prompts/` 是项目内角色契约权威来源；SAGE skill 可内置 1.0 默认发行版用于 Standalone/bootstrap，项目一旦存在本地 `prompts/`、`templates/`、`docs/guides/`，则项目本地文件优先，CLI/subagent 只能读取并承载当前权威版本。

5. **子代理派发门禁**：L1 及以上，TASK 文档 1.1~1.5 冻结**且计划放行**（元数据「计划放行」=已放行；L0/L3 豁免，见 planner.md 第 8 节）后，方可派发 coder/closer 等执行型子代理；派发时只传递必要定位信息（TASK 文档路径、角色提示词路径、阶段、仓库根目录），任务等级等调度信息以 TASK 元数据为准。L0 免除 TASK 文档，主代理直接执行，不派发 CLI/subagent。

6. **执行通道协议**：L1 及以上，CLI/subagent 通过 TASK 文档元数据（风险等级、当前阶段、项目根目录、功能分支）获取调度信息；不得传递主线程讨论历史或额外隐式上下文；具体 CLI 命令从 [execution-channels](../guides/execution-channels.md) 读取，缺省按 L2；L1 及以上派发前先运行 `../scripts/dispatch_phase.py prepare`，宿主原生能力由 Main Agent 调用，模型按 adapter 信封的 `request` / `agent-registration` 绑定传递或校验，完成后必须运行 `verify`。

7. **编排校准**：阶段流转、外包边界不确定时，参考 `prompts/orchestrator.md` 编排细节。

## 不可违反的约束
1. 部署阶段必须人类授权，智能体严禁私自触发。
2. L1 及以上，任务文档必须通过物理复制模板创建，禁止内存重建。
3. 收尾阶段严禁新增功能（scope creep）。
4. 合并到 `dev` 和 `main` 的权力永远属于人类。
5. 所有知识沉淀到仓库，不留在聊天或人脑中。
