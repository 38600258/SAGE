# 通用工具适配器

当 SAGE 运行在 Cursor、Claude Code、Windsurf、Copilot Agent 或其他 AI 编程工具中时，使用本适配说明；默认机器能力声明见同目录 `generic-tool.json`。

## 必备能力

- 能读取和写入仓库文件。
- 能运行本地验证命令，或清楚说明验证不可用原因。
- 能保留 TASK 文档作为跨会话、跨工具的持久交接物。
- 能通过原生 subagent、隔离会话或 CLI 承载 reviewer/coder/closer 角色。

## 能力覆盖

`generic-tool.json` 不假设宿主一定支持原生 subagent，默认选择 CLI。若工具实际提供原生 Worker/Subagent API，应在项目创建 `docs/guides/execution-adapters/<tool>.json`：

1. 将 `native_subagent.supported` 设为 `true`。
2. 为 `plan-review`、`dev`、`code-review`、`close` 配置实际 `agent_types`。
3. 将 `native_subagent.invoker` 设为 `host`，表示 Main Agent 负责调用宿主 API。
4. 使用 `prepare --adapter <tool>` 生成 `spawn_subagent` 信封；完成后必须运行 `verify`。

如果宿主只提供后台任务但不能保证隔离上下文，不能将其声明为 reviewer subagent；计划/代码盲审必须避免继承主线程讨论历史。模型选择不写入角色 prompt，而是通过 adapter 的 `models.<phase>` 和宿主请求参数/CLI `{model}` 传递。

## 适配模式

1. 将该工具的项目入口文件映射到 SAGE 入口规则。
2. 将后台 Worker、子任务或隔离会话能力映射到 reviewer/coder/closer。
3. bootstrap 后，角色契约保留在项目本地 `prompts/`；仅在项目初始化前使用内置 `core/prompts/`。
4. 工具专用 UX 产物不进入 SAGE 权威链，除非项目明确将其版本化。
5. 宿主没有原生 API 时，使用 `cli.json` 或项目 CLI adapter；Skill 不能凭空创建宿主未提供的子代理。
6. 若宿主原生 API 支持请求级模型，在项目 adapter 中将 `subagent_binding` 设为 `request`；若模型固定在宿主注册，则设为 `agent-registration` 并保持 adapter 与注册配置同步。
