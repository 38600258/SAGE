# SAGE 路径注册表

按以下顺序解析文件：

| 用途 | 项目覆盖路径 | 内置默认路径 |
|------|--------------|--------------|
| 入口 | `AGENTS.override.md`、`AGENTS.md`、工具入口文件 | `skills/sage-workflow/SKILL.md` |
| Orchestrator | `prompts/orchestrator.md` | `core/prompts/orchestrator.md` |
| Planner | `prompts/planner.md` | `core/prompts/planner.md` |
| Reviewer | `prompts/reviewer.md` | `core/prompts/reviewer.md` |
| Coder | `prompts/coder.md` | `core/prompts/coder.md` |
| Closer | `prompts/closer.md` | `core/prompts/closer.md` |
| TASK 模板 | `templates/TASK-TEMPLATE.md` | `core/templates/TASK-TEMPLATE.md` |
| 执行通道 | `docs/guides/execution-channels.md` | `core/guides/execution-channels.md` |
| 开发规范 | `docs/guides/development-standards.md` | `core/guides/development-standards.md` |
| 任务文档规范 | `docs/guides/task-document-standards.md` | `core/guides/task-document-standards.md` |

内置默认文件一旦复制进项目仓库，复制后的项目本地文件就成为该仓库的活跃权威来源。
