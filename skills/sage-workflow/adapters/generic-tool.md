# 通用工具适配器

当 SAGE 运行在 Cursor、Claude Code、Windsurf、Copilot Agent 或其他 AI 编程工具中时，使用本适配说明。

## 必备能力

- 能读取和写入仓库文件。
- 能运行本地验证命令，或清楚说明验证不可用原因。
- 能保留 TASK 文档作为跨会话、跨工具的持久交接物。
- 能通过原生 subagent、隔离会话或 CLI fallback 承载 reviewer/coder/closer 角色。

## 适配模式

1. 将该工具的项目入口文件映射到 SAGE 入口规则。
2. 将该工具的后台 worker、子任务或隔离会话能力映射到 SAGE reviewer/coder/closer 执行通道。
3. bootstrap 后，角色契约保留在项目本地 `prompts/`；仅在项目初始化前使用内置 `core/prompts/`。
4. 工具专用 UX 产物不进入 SAGE 权威链，除非项目明确将其版本化。
