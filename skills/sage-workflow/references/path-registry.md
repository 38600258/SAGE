# SAGE 路径注册表

按以下顺序解析文件：

| 用途 | 项目覆盖路径 | 内置默认路径 |
|------|--------------|--------------|
| 触发入口 | 工具加载的 skill `SKILL.md` | 当前 skill 的 `SKILL.md` |
| 项目入口 | `AGENTS.override.md`、`AGENTS.md`、工具入口文件 | `core/entry/AGENTS.override.md`、`core/entry/AGENTS.md`、`core/entry/GEMINI.md` |
| Orchestrator | `prompts/orchestrator.md` | `core/prompts/orchestrator.md` |
| Planner | `prompts/planner.md` | `core/prompts/planner.md` |
| Reviewer | `prompts/reviewer.md` | `core/prompts/reviewer.md` |
| Coder | `prompts/coder.md` | `core/prompts/coder.md` |
| Closer | `prompts/closer.md` | `core/prompts/closer.md` |
| Doc Gardener | `prompts/doc-gardener.md` | `core/prompts/doc-gardener.md` |
| TASK 模板 | `templates/TASK-TEMPLATE.md` | `core/templates/TASK-TEMPLATE.md` |
| ADR 模板 | `templates/ADR-template.md` | `core/templates/ADR-template.md` |
| PRD 模板 | `templates/PRD-template.md` | `core/templates/PRD-template.md` |
| 执行通道 | `docs/guides/execution-channels.md` | `core/guides/execution-channels.md` |
| 开发规范 | `docs/guides/development-standards.md` | `core/guides/development-standards.md` |
| 任务文档规范 | `docs/guides/task-document-standards.md` | `core/guides/task-document-standards.md` |
| CHANGELOG 规范 | `docs/guides/changelog-standards.md` | `core/guides/changelog-standards.md` |
| Git 规范 | `docs/guides/git-standards.md` | `core/guides/git-standards.md` |
| 质量门禁 | `scripts/sage_linter.py` | `core/scripts/sage_linter.py` |
| 阶段派发器 | `scripts/sage_dispatch.py` | `core/scripts/dispatch_phase.py` |
| 执行 adapter | `docs/guides/execution-adapters/*.json` | `adapters/*.json` |
| 派发协议 | 项目执行通道指南 | `references/dispatch-protocol.md` |
| Bootstrap 工具 | skill 提供的 bootstrap 命令 | `core/scripts/bootstrap_sage.py` |
| 提交 hooks | `.githooks/*` | `core/githooks/*` |
| 编程方法论 | 项目方法论文档 | `core/methodology/智能体优先的自主编程方法论.md` |
| 项目管理方法论 | 项目方法论文档 | `core/methodology/智能体优先的自主项目管理方法论.md` |

内置默认文件一旦复制进项目仓库，复制后的项目本地文件就成为该仓库的活跃权威来源；`SKILL.md` 只负责触发与路由，不替代项目入口。