# Oh My Pi (OMP) 适配器

当 SAGE 运行在 OMP（Oh My Pi）中时，使用本适配说明；机器能力声明见同目录 `omp.json`。

## 入口加载

- OMP 以项目根 `AGENTS.md` 作为项目入口；SAGE skill 已挂载时，优先加载 `sage-workflow` skill。
- 若目标项目只有内置 core，在规划前加载 `core/prompts/orchestrator.md` 与 `core/prompts/planner.md`。
- 持久事实以 TASK 文档为准，不依赖会话内存。

## 原生子代理映射

OMP 的 `task` 工具可派发命名子代理，子代理启动时无对话历史，天然满足盲审上下文隔离。`omp.json` 将四个 SAGE 阶段映射为**三个自定义 agent**（provision 生成的 `agents/sage-*.md`），与 codex 适配器命名完全一致：

| SAGE 阶段 | agent_type（agent 名） | modelRoles 键（provision 内部） | 路由到的角色用途 |
|-----------|------------------------|-------------------------------|-----------------|
| `plan-review` | `sage_reviewer` | `@sage_reviewer` | 深度推理计划盲审 |
| `code-review` | `sage_reviewer` | `@sage_reviewer` | 深度推理代码盲审 |
| `dev` | `sage_coder` | `@sage_coder` | 通用 task 执行 |
| `close` | `sage_closer` | `@sage_closer` | 收尾归档 |

> - 内置 `reviewer.md` 与 `task` agent（官方 `agents.ts` 为 `task` 注入 `model: "@task"`）虽能路由到 `modelRoles.slow`/`modelRoles.task`，但其 system prompt 是 OMP 协议（"Find bugs…" / "Worker agent: delegated tasks"），**不是 SAGE 角色契约**——行为训导与 SAGE 契约冲突。
> - 自定义 agent 由 provision 生成，正文承载 SAGE 角色契约，frontmatter `model` 显式声明对应 modelRoles 键，模型路由完整闭环。审查两阶段共用 `sage_reviewer` 键，dev/close 各自独立键。

## 模型路由

OMP 是 provider-agnostic 的角色路由架构：模型不按请求指定，而是按角色（role）在配置中路由。模型链路：

```
task 工具派发 agent: "sage_reviewer"
  → agent frontmatter model: "@sage_reviewer"     ← provision 内部生成，用户无需关心
  → modelRoles.sage_reviewer  →  具体 provider/model（来自 omp.json models.<phase>.id）
```

`omp.json` 的 `models.<phase>.id` 填**实际模型标识符**（如 `anthropic/claude-sonnet-4-5`、`litellm/deepseek-v4-flash`），与 codex.json 接口一致——用户在此处指定各阶段用什么模型。plan-review 与 code-review 共用 `sage_reviewer` 键，模型取 plan-review 的 id（首个非空），若 code-review 与 plan-review 不一致则 provision 告警（对齐 codex build_toml_agent 语义）。modelRoles 键名（`sage_reviewer` 等）是 provision 内部实现细节，不出现在 omp.json 中。`subagent_binding = "agent-registration"`：OMP 的 `task` 派发 API 不接受请求级 `model` 参数，模型由角色级配置决定，不能用单次 `--model` 覆盖。

未填写（`null`）时，provision 在 config.yml 对应角色写占位符并告警，用户可在 omp.json 补填后重新 provision，或直接编辑 config.yml 替换占位符。

### 模型路由实际生效范围

> 四阶段均派发，全部 modelRoles 键生效（T-024 落地，编排契约束缚见 orchestrator.md——dev/close 为「coder/closer 必须子代理化」，主代理不得代行执行角色）：
> - ✅ **plan-review**：sage_reviewer → modelRoles.sage_reviewer → 异构模型（**生效**）
> - ✅ **dev**：sage_coder → modelRoles.sage_coder → 异构模型（**生效**，T-024 后）
> - ✅ **code-review**：sage_reviewer → modelRoles.sage_reviewer → 异构模型（**生效**）
> - ✅ **close**：sage_closer → modelRoles.sage_closer → 异构模型（**生效**，T-024 后）
>
> dev/close 阶段同样派发执行型子代理，四阶段跨厂商异构模型路由完整生效。

角色配置位置（OMP settings 文档验证）：

- 全局（用户）：`~/.omp/agent/config.yml`（`--user` 部署目标）
- 项目：`<repo>/.omp/config.yml`（默认部署目标；加载时与全局深度合并，缺失键自然 fallback）

### 异构模型盲审配置

实现跨厂商异构审查的方法：在 `omp.json` 中将 `plan-review`/`code-review` 阶段的 `models.id` 设为与 `default`（主会话编写模型）不同厂商的模型：

```json
{
  "models": {
    "plan-review": { "id": "anthropic/claude-sonnet-4-5" },
    "dev": { "id": "litellm/deepseek-v4-flash" },
    "code-review": { "id": "openai/gpt-5.6" },
    "close": { "id": "litellm/sensenova-6.8-flash-lite" }
  }
}
```

provision 将上述值写入 `config.yml` 的 `modelRoles.sage_reviewer`（取 plan-review 值，code-review 不一致时告警）/`sage_coder`/`sage_closer`。`default` 角色由 OMP 运行时设置，不在 omp.json 中。

`advisor` 是 OMP 固定角色键。启用后，OMP 会在主会话/子代理完成后自动运行第二遍审查；将 `advisor` 设为第三厂商可实现三重异构审查。启用条件：在对应 sage-*.md frontmatter 加入 `advisor: true`，并在 config.yml 补 `advisor: <provider-C>/model-Z`（provision 不自动生成 advisor 值）。

## 自动派发

1. L1 及以上进入 reviewer/coder/closer 阶段前，运行项目本地 `scripts/sage_dispatch.py prepare`；尚未 bootstrap 时运行 Skill 内置 `core/scripts/dispatch_phase.py prepare`。
2. `omp.json` 将四个阶段各映射为 `sage_reviewer`/`sage_coder`/`sage_closer`（审查共用 sage_reviewer）。当 `prepare` 返回 `action=spawn_subagent` 时，Main Agent 必须立即调用 OMP 的 `task` 工具派发 `agent_type` 指定的子代理，并只传信封中的 `prompt`。
3. subagent 完成后运行 `verify --receipt <path>`；只有 TASK 对应章节和 Git 状态出现有效产出才算成功。
4. `status` 读取协议状态；`cancel` 只标记 `host_cancel_required`，Main Agent 仍须通过 `hub` 取消或关闭子代理。

示例：

```powershell
uv run python scripts/sage_dispatch.py prepare --repo-root D:\repo --task-path D:\repo\docs\project\ACTIVE_TASK_T-001.md --phase code-review --adapter omp --format json
uv run python scripts/sage_dispatch.py verify --receipt <receipt> --format json
```

## 子代理配置生成（provision）

OMP 自定义 agent 需要配置文件才能被 `task` 工具派发。`provision` 生成 `.omp/` 目录（config.yml + 三角色 agent）：

```powershell
# 不带参数：默认生成到 <当前目录>/.omp（项目目录），config.yml 增量合并（保留已有非 modelRoles 段）
uv run python docs/guides/execution-adapters/omp/provision.py

# 指定目标目录
uv run python docs/guides/execution-adapters/omp/provision.py --target-dir D:\repo\.omp

# 部署到宿主用户注册目录（~/.omp/agent），与 --target-dir 互斥
uv run python docs/guides/execution-adapters/omp/provision.py --user

# --force：强制覆盖所有文件（config.yml 整文件覆盖，agent 文件覆盖）
uv run python docs/guides/execution-adapters/omp/provision.py --force

# 经主入口委托执行（bootstrap 后的项目内必须带 --repo-root）
uv run python scripts/sage_dispatch.py provision --repo-root D:\repo --adapter omp --target-dir D:\repo\.omp

# 只生成 reviewer 角色（生成 1 个 sage_reviewer agent）
uv run python docs/guides/execution-adapters/omp/provision.py --role reviewer
```

复制/部署方式（给 AI 看的一句话自动部署）：

- **项目目录（默认）**：在仓库根运行 `provision.py`（不带参数），生成 `<repo>/.omp/`（config.yml + agents/sage_reviewer.md、sage_coder.md、sage_closer.md），随仓库版本管理。
- **用户目录（--user）**：运行 `provision.py --user`，生成 `~/.omp/agent/`（config.yml + agents/），全局配置、多项目共享，不污染仓库。
- 手动复制：把项目生成的 `config.yml` 的 `modelRoles` 段合并到 `~/.omp/agent/config.yml`（全局）或 `<repo>/.omp/config.yml`（项目），把 `agents/*.md` 放到对应 `agents/` 目录。OMP 从该目录发现自定义 agent（项目优先于用户级与内置，first-wins 按 name 去重）。

写入语义：
- **agent 文件**：不存在→写入；已存在+不带 `--force`→跳过；已存在+`--force`→覆盖
- **config.yml**：不存在→新建；已存在+不带 `--force`→**增量合并**（保留非 `modelRoles` 段如 `task`/`settings`，只替换 `modelRoles` 段）；已存在+`--force`→整文件覆盖（会丢失非 `modelRoles` 段，有告警）

生成产物：

1. `config.yml` — `modelRoles` 段（`sage_reviewer`/`sage_coder`/`sage_closer`/`advisor`）；模型值来自 omp.json `models.<phase>.id`，未配置时写占位符并告警
2. `agents/sage_reviewer.md` — plan-review + code-review 用（`model: "@sage_reviewer"`）
3. `agents/sage_coder.md` — dev 用（`model: "@sage_coder"`）
4. `agents/sage_closer.md` — close 用（`model: "@sage_closer"`）

生成后：
- 如 omp.json 中某阶段 `models.id` 为 null，config.yml 对应阶段角色为占位符 `<provider/model>`；请在 omp.json 填入实际模型标识符后重新 provision，或直接编辑 config.yml 替换。
- 确认 `agents/sage-*.md` 位于 `<repo>/.omp/agents/` 或 `~/.omp/agent/agents/` 下——OMP 从该目录发现自定义 agent（项目优先于用户级与内置，first-wins 按 name 去重）。
- 重启/刷新 OMP，在 `/agents` 面板确认 `sage_reviewer`/`sage_coder`/`sage_closer` 可见，在 `/model` 的 Roles 视图确认同名角色。
- 旧版（T-023 每阶段独立 4 agent）部署残留的 `sage-plan-review.md`/`sage-dev.md`/`sage-code-review.md`/`sage-close.md` 为孤儿文件，建议清理 `agents/` 目录后重新 provision。
- provision 不写出工作区外配置（`--user` 显式指定除外）；注册是否生效以宿主实际派发结果为准。

## 失败恢复

- 原生子代理无法启动或未产生有效回写时，先复核 Git、TASK、进程和已有产出，再尝试修复原生通道。
- OMP 无 CLI 通道（`cli.supported = false`）。若原生子代理不可用，降级路径为 `generic-tool` 适配器的注入式通道（`prepare --adapter generic-tool --channel injected`），需提供 `--fallback-reason` 和 `--fallback-authorized`。
- Main Agent fallback 仍需人工确认；不得因为 Dispatcher 存在就绕过执行通道门禁。

## Git 边界

- L1 及以上任务分支使用 `feat|fix|docs|chore|refactor/t-XXX-*`，不得使用工具名前缀。
- 未经用户明确授权，不执行 merge、push 或 deploy。

## 已知踩坑

宿主/CLI 特定陷阱的官方沉淀位；新踩坑随任务收尾沉淀进本节（纳入内容卫生范围）。

- **`task` 派发无 `model` 参数**——OMP 的 `task` 工具不接受请求级模型参数，模型由角色级 YAML 配置路由（agent frontmatter `model: "@role"` → `modelRoles.<role>`）。不能用 `prepare --model` 逐次覆盖；修改模型需改 omp.json `models.<phase>.id` 后重新 provision 并合并 config.yml，或直接编辑 config.yml 后重启。
- **agent_type 必须指向实际存在的 agent**——`omp.json` 的 `agent_types` 值必须与 `.omp/agents/*.md` 中的 `name` 一致（或为内置 agent 名）。自定义 agent 文件缺失时派发会报 `Unknown agent`。
- **内置 agent 的 system prompt 是 OMP 协议而非 SAGE 契约**——内置 `task` agent（官方 `agents.ts` 注入 `model: "@task"`）与内置 `reviewer`（`model: "@slow"`）虽能路由 modelRoles，但行为协议是 OMP 的；要用 `@sage-*` 自定义键必须使用自定义 agent（provision 已生成）。
- **agent 名去重**——项目 `.omp/agents` 优先于用户级与内置；自定义 `sage-*` 名不与内置冲突，改名后需同步 omp.json `agent_types`。
