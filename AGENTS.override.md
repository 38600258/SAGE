# AGENTS.override.md — Codex app 覆盖入口
> Codex app 项目级入口；目标 ≤120 行，超过 150 行必须拆到 T2；覆盖规则优先。

## 快速导航
- 开发方法论 → [智能体优先的自主编程方法论.md](智能体优先的自主编程方法论.md)
- 项目管理方法论 → [智能体优先的自主项目管理方法论.md](智能体优先的自主项目管理方法论.md)
- 看板 / 模式 / 决策 / 交接 → [PROJECT_BOARD](docs/project/PROJECT_BOARD.md) / [KNOWN_PATTERNS](docs/project/KNOWN_PATTERNS.md) / [DECISION_LOG](docs/project/DECISION_LOG.md) / [HANDOVER](docs/project/HANDOVER-GUIDE.md)
- 任务 / ADR / PRD 模板 → [TASK](templates/TASK-TEMPLATE.md)（L1+） / [ADR](templates/ADR-template.md) / [PRD](templates/PRD-template.md)
- 角色提示词 → [planner](prompts/planner.md) / [coder](prompts/coder.md) / [closer](prompts/closer.md) / [reviewer](prompts/reviewer.md)
- 执行通道 → [execution-channels](docs/guides/execution-channels.md)
- 质量门禁 → `python scripts/sage_linter.py --all`

## 任务入口规则

1. **强制加载**：开发类任务启动时，Main Agent 必须加载 `prompts/orchestrator.md` + `prompts/planner.md`；Main Agent 同时承担 orchestrator 和 planner 角色。

2. **分级判定**：先判定 `TASK_LEVEL`（L0/L1/L2/L3），缺失或不确定按 L2。

   | 等级 | 触发信号 | 阶段链 | 门禁 |
   |------|---------|--------|------|
   | L0 | 纯机械修正、格式化、极小文案修补 | Init → Dev → Close | 最小验证 + 中文提交 |
   | L1 | 纯文档/纯测试/纯重构/不涉及外部系统 | Init → Dev → Close | 质量门禁 |
   | L2 | 业务逻辑变更/新增功能/修复 Bug | Init → PlanReview → Dev → CodeReview → Close | 两次盲审 + 证据链 |
   | L3 | 数据库 Schema 变更/外部 API 对接/部署配置 | Init → PlanReview → Dev → CodeReview → Close | 每阶段人工确认 |

3. **阶段-角色映射**：L0 不适用本表；L1 及以上各阶段对应唯一的角色契约与 TASK 输出章节。

   | 阶段 | 角色 prompt | TASK 输出节 |
   |------|------------|-------------|
   | 初始化 | `prompts/planner.md` | 1.1~1.5 |
   | 计划盲审 | `prompts/reviewer.md` 流程A | 2.x |
   | 编码实现 | `prompts/coder.md` | 3.x |
   | 代码盲审 | `prompts/reviewer.md` 流程B | 4.x |
   | 收尾归档 | `prompts/closer.md` | 5.x |

4. **角色契约**：`prompts/` 是角色契约唯一来源；skill/CLI/subagent 只能引用，不复制。

5. **子代理派发门禁**：L1 及以上，TASK 文档 1.1~1.5 冻结后，方可派发 coder/closer 等执行型子代理；派发时必须传递 TASK 文档路径和对应角色提示词路径，任务等级以 TASK 元数据为准。L0 免除 TASK 文档，主代理直接执行。

6. **执行通道协议**：L1 及以上，CLI/subagent 通过 TASK 文档元数据（风险等级、当前阶段、项目根目录、功能分支）获取调度信息；具体 CLI 命令从 `docs/guides/execution-channels.md` 读取，缺省按 L2。

7. **编排校准**：阶段流转、外包边界不确定时，参考 `prompts/orchestrator.md` 编排细节。

## Codex 覆盖规则
1. 不另建 `CODEX.md`；本文件就是 Codex app 专用入口。
2. 分支从项目开发基线分支切出：L1+ 使用 `feat|fix|docs|chore|refactor/t-XXX-*`；L0 可用 `fix|docs|chore|style/l0-*`；禁止工具名前缀。
3. reviewer/coder/closer 可交给 CLI；优先按 `docs/guides/execution-channels.md` 的命令模板调用，项目可只改该文档替换 CLI。
4. CLI Prompt 必须提供 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE` 绝对信息，并要求回写 TASK 对应章节。
5. CLI 成功标准是 TASK/Git 状态出现有效产出；stdout 或退出码不能单独作为依据。CLI 不可用时，可用 Codex subagent 备选。
6. Codex hooks 只作软防护；提交/推送前硬门禁以 Git hooks 和 `scripts/sage_linter.py` 为准。
7. 越权命令、部署、外部网络或写出工作区，必须通过 Codex app 审批。

## 不可违反的约束
1. 部署必须人类授权；合并到 `dev`/`main` 永远属于人类。
2. L1 及以上，任务文档必须物理复制模板创建；收尾阶段严禁新增功能。
3. 所有知识沉淀到仓库，不留在聊天或人脑中。
