# SAGE 自动派发协议

本协议定义 SAGE Skill 与不同 Agent 宿主之间的最小运行时边界。角色职责仍以当前权威 `prompts/*.md` 为准，adapter 只声明执行能力、名称映射和模型路由。

## Adapter JSON

解析顺序（子目录结构 `<adapter>/<adapter>.json`，目录内含该适配器的 md 说明与 provision.py）：

1. 项目本地 `docs/guides/execution-adapters/<adapter>/<adapter>.json`
2. Skill 内置 `adapters/<adapter>/<adapter>.json`
3. 显式 `--adapter-file <path>` 覆盖上述查找

最小结构：

```json
{
  "schema_version": 1,
  "id": "tool-name",
  "native_subagent": {
    "supported": true,
    "invoker": "host",
    "agent_types": {
      "plan-review": "reviewer-agent",
      "dev": "coder-agent",
      "code-review": "reviewer-agent",
      "close": "closer-agent"
    }
  },
  "injected_subagent": {
    "supported": false,
    "invoker": "host",
    "isolation": "context-fresh",
    "requires_authorization": true,
    "agent_types": {}
  },
  "models": {
    "dev": {
      "id": "model-id",
      "subagent_binding": "request",
      "cli_binding": "command-argument"
    }
  },
  "cli": {
    "supported": true,
    "command_env": "SAGE_CLI_COMMAND_JSON",
    "stdin": "prompt"
  }
}
```

`models` 按阶段声明默认模型。`id` 可以为 `null`，表示必须由 `prepare --model` 或宿主默认值决定；未声明的阶段等同于未配置模型。绑定方式含义如下：

- `subagent_binding=request`：宿主原生 API 支持在本次派发请求中传入模型；`--model` 可以覆盖 adapter 默认值，Main Agent 必须把信封中的模型传给宿主 API。
- `subagent_binding=agent-registration`：模型由宿主注册的 agent 类型固定；信封只记录期望模型，不能用单次 `--model` 改写。修改模型时必须同步 adapter JSON 与宿主 Agent 注册配置。
- `cli_binding=command-argument`：CLI 命令必须使用 `{model}` 占位符；模型未被命令实际消费时，`run-cli` 直接阻断。
- `none`：该通道不声明模型路由。指定 `--model` 会被拒绝。

模型路由属于执行载体层，不写入角色 prompt，也不改变 TASK 元数据。模型来源按 `prepare` 信封的 `model.source` 记录为 `adapter`、`argument` 或 `unspecified`。

## 注入式子代理通道（injected_subagent）

宿主没有命名 agent 注册、但提供通用子代理或隔离会话能力时，adapter 可声明 `injected_subagent.supported=true`：

- `agent_types`：各阶段使用的通道标识（用于回执追踪，不要求宿主存在同名注册）。
- `isolation`：隔离等级声明。`context-fresh` 表示全新上下文（模型级隔离取决于宿主当前模型与执行方差异）；`unknown` 表示宿主未声明隔离。
- `requires_authorization`：为 `true` 时，Main Agent 派发前必须获得人工确认，并把隔离等级与授权记录写回 TASK 证据链。
- `--channel auto` 的优先级为 subagent > injected > cli；从更高优先级通道降级 CLI 必须提供 `--fallback-reason` 与 `--fallback-authorized`。

信封 `injection` 字段记录隔离信息；`action` 仍为 `spawn_subagent`，宿主用自身原生派发工具创建通用子代理并注入信封 `prompt`。跨宿主审查（审查方与执行方为不同宿主/模型家族）视为合法独立审查通道。

## doctor 与 provision

- `doctor`：逐通道探测可用性并输出推荐通道。原生通道按声明判定；注入式通道校验 `agent_types` 完整性；CLI 通道只探测可执行文件可否定位，不执行命令。无可用通道时退出码为 1。
- `provision`：委托适配器脚本生成 agent 注册文件，`--adapter <id>` 必填。生成逻辑位于 `adapters/<id>/provision.py`（项目本地 `docs/guides/execution-adapters/<id>/provision.py` 优先），可独立运行，也可由 `dispatch_phase.py provision --adapter <id>` 以 subprocess 委托执行并透传 `--target-dir / --role / --force / --format`（codex 额外透传 `--model-provider`）。`--adapter codex` 生成 TOML 注册（模型取自同目录 codex.json）；`--adapter claude-code` 生成项目内 Markdown agents。cli/generic-tool 无原生 subagent，不提供 provision（报错退出码 2）。默认不覆盖已存在文件；注册是否生效以宿主实际派发为准。

## 派发状态

| 状态 | 含义 |
|------|------|
| `prepared` | 已生成信封和派发前快照，等待宿主或 CLI 执行 |
| `running` | CLI 命令正在执行；原生 subagent 的运行状态由宿主管理 |
| `completed` | `verify` 已确认 TASK/Git 有效产出 |
| `failed` | CLI 失败或 TASK/Git 验证未通过，可保留同一回执复核 |
| `cancelled` | 协议已取消；原生 subagent 仍须宿主实际关闭 |

## 派发信封

`prepare` 返回的核心字段包括：

```json
{
  "action": "spawn_subagent",
  "agent_type": "sage_coder",
  "model": {
    "requested": "deepseek-v4-pro",
    "binding": "agent-registration",
    "source": "adapter"
  },
  "context": {
    "REPO_ROOT": "D:\\repo",
    "TASK_PATH": "D:\\repo\\docs\\project\\ACTIVE_TASK_T-001.md",
    "ROLE_PROMPT": "D:\\repo\\prompts\\coder.md",
    "PHASE": "dev"
  }
}
```

`model` 不属于 `context`，因此不会被拼进角色 prompt。`requested=null` 表示本次没有解析到具体模型，宿主可以使用自身默认值；若绑定方式要求显式模型，Dispatcher 会在执行前阻断。

## 宿主职责

当信封返回 `action=spawn_subagent`：

1. Main Agent 读取 `agent_type`、`model` 和 `prompt`。
2. 使用当前宿主的原生派发 API 创建对应 subagent，不向 prompt 添加聊天历史或额外任务事实。
3. 对 `subagent_binding=request`，按 `model.requested` 传入请求级模型；`requested=null` 时不传模型参数。
4. 对 `subagent_binding=agent-registration`，确认宿主注册配置与 `model.requested` 一致，不声称单次请求已覆盖注册模型。
5. 等待/接收宿主完成状态后运行 `verify`。
6. 若需取消，先运行 `cancel` 留痕，再调用宿主取消 API。

Dispatcher 无法访问宿主内部 API 时不会假装完成调用；这是权限边界，不是 fallback。宿主 Adapter 的价值是让不同工具按同一信封和成功标准实现自己的调用层。

## CLI 命令占位符

CLI 命令必须是 JSON 字符串数组，由 Dispatcher 直接执行，不使用 shell 拼接。除原有定位字段外，可使用 `{model}`：

```json
["codex", "exec", "-m", "{model}", "-C", "{repo_root}", "--ephemeral", "-"]
```

当 `prepare --model <id>` 或 adapter 默认模型解析出具体模型时，命令必须包含 `{model}`；硬编码模型名不能证明配置已被消费。没有具体模型时，命令也不得使用 `{model}`。

## 验证规则

- reviewer：TASK 2.x/4.x 必须在派发后变化，并出现 `OK`、`WARN` 或 `BLOCK`。
- coder：TASK 3.1、3.2 必须出现有效内容，且 Git 内容指纹或 HEAD 必须变化。
- closer：TASK 5.x 必须变化，默认要求产生新提交；只有显式策略允许时才可跳过提交检查。
- 回执默认保存在系统临时目录，不进入项目 Git；长期证据必须写回 TASK。
