# 执行通道配置（Execution Channels）

> T2 级配置文档 | 状态：[CURRENT]
> 本文档定义 reviewer / coder / closer 等阶段使用哪个 subagent、CLI 或主代理执行。
> 导航入口 → [AGENTS.md](../entry/AGENTS.md) | 模型策略 → [model-selection.md](model-selection.md)

---

## 一、核心原则

项目化角色规则写在当前权威 `prompts/*.md` 中；SAGE skill 可内置默认发行版用于 Standalone/bootstrap，执行通道只写在本文档、项目覆盖文件或 skill adapter 中。

- **角色契约**：`prompts/reviewer.md`、`prompts/coder.md`、`prompts/closer.md`
- **调度事实来源**：TASK 文档元数据（风险等级、当前阶段、项目根目录、功能分支）
- **执行通道**：subagent / CLI / Main Agent，只负责承载当前权威角色规则；不得把项目化角色规则再复制到载体提示层
- **能力优先**：工具原生支持 subagent 且已验证可用时，优先使用角色 subagent；不可用时按降级链切换注入式 subagent 或 CLI fallback
- **修改通道**：优先只改本文档的“默认通道矩阵”和“派发模板”
- **L0 快速通道**：L0 不创建 TASK 文档，不调用 CLI/subagent，由 Main Agent 直接执行

---

## 二、默认通道矩阵

| 角色 | L0 | L1 | L2 | L3 | 默认通道 | 备选通道 |
|------|----|----|----|----|----------|----------|
| `planner` | Main Agent | Main Agent | Main Agent | Main Agent | 主线程 | research subagent 仅做调研/草拟 |
| `reviewer` | 不触发 | 默认跳过 | 必须触发 | 必须触发 | reviewer subagent | 注入式 reviewer → reviewer CLI |
| `coder` | Main Agent | coder subagent | coder subagent | coder subagent | coder subagent | 注入式 coder → coder CLI → 人工确认后的 Main Agent fallback |
| `closer` | Main Agent | closer subagent | closer subagent | closer subagent | closer subagent | 注入式 closer → closer CLI → 人工确认后的 Main Agent fallback |

> 项目可按工具能力覆盖默认通道，但不得绕过 TASK、角色提示词和质量门禁。
> 若默认 subagent 未注册、无法启动、工具调用失败或无法产生 TASK/Git 有效产出，必须先复核 Git/TASK/进程/已有产出状态，记录失败现象和修复尝试，再按下一节降级链切换备选通道。

---

## 二·补 通道降级链与熔断条款

通道按优先级降级，每次降级必须在 TASK 证据链记录原因、时间戳和授权人：

| 级别 | 通道 | 适用条件 |
|------|------|----------|
| 1 | 原生注册子代理（`spawn_subagent`） | 宿主支持命名 agent 注册且实际派发成功 |
| 2 | 注入式子代理（`--channel injected`） | 宿主有通用子代理/后台任务能力但无命名注册；派发时注入 ROLE_PROMPT |
| 3 | CLI 进程（`run-cli`） | 宿主无子代理能力；命令数组必须消费 `{model}` |
| 4 | 人工授权降级审查 | 仅 reviewer；1~3 级全部失败且累计 ≥3 次后，由人类授权 Main Agent 在隔离会话中审查 |

降级链规则：

1. **注入式通道使用要求**：`prepare` 信封 `injection.requires_authorization=true` 时，Main Agent 必须把隔离等级（`injection.isolation`）写回 TASK 证据链，不得静默使用；注入式盲审/coder/closer 派发**不要求逐次人工授权**（T-018 用户裁决：人工确认点收敛为计划放行门（planner.md 第 8 节）、L3 每阶段人工确认与 merge/push/deploy 授权）。
2. **跨宿主审查是合法独立通道**：盲审隔离单位是"模型 + 上下文"，不是"同一宿主进程"。审查方与执行方为不同宿主或不同模型家族时，天然满足隔离要求，按注入式通道记录即可，不属于自审。
3. **熔断条款**：独立审查通道（级别 1~3）对同一阶段累计失败 ≥3 次后，停止自动重试。合法出口只有三个：人类接管审查；人工授权级别 4 降级审查（TASK 中标注隔离等级与授权）；任务挂起并登记技术债。禁止伪造 OK/WARN/BLOCK。
4. **探测前移**：L1 及以上任务进入 Init 前，应运行 `doctor` 探测通道可用性，避免任务推进到盲审门禁才发现通道不可用。

---

## 三、上下文传递契约

L1 及以上使用 subagent/CLI 时，Prompt 只显式传递必要定位信息；其他调度信息必须从 TASK 文档元数据读取。

| 参数 | 含义 |
|------|------|
| `REPO_ROOT` | 仓库根目录绝对路径 |
| `TASK_PATH` | TASK 文档绝对路径（仅 L1+；L0 不调用 CLI/subagent） |
| `ROLE_PROMPT` | 对应 `prompts/*.md` 绝对路径 |
| `PHASE` | `plan-review` / `dev` / `code-review` / `close` |
| `DIFF_CMD` | 代码审查时使用的 diff 命令，如 `git diff dev...HEAD` |

subagent/CLI 不应依赖当前工作目录、聊天上下文或隐式相对路径。启动后应先定位到 `REPO_ROOT`，读取 `ROLE_PROMPT` 和 `TASK_PATH`，再从 TASK 元数据读取风险等级、当前阶段、项目根目录和功能分支。

除 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE`、必要时的 `DIFF_CMD` 外，不要向 subagent/CLI 传递主线程讨论历史、计划生成过程、长篇 diff 或额外调度上下文。确需补充的证据应写入 TASK 文档、证据链或由 `DIFF_CMD`/文件路径让执行者自行读取。

---

## 四、自动派发运行时

L1 及以上进入外部执行阶段前，优先运行项目本地 `scripts/sage_dispatch.py`；尚未 bootstrap 时运行 Skill 内置 `core/scripts/dispatch_phase.py`。

### 4.1 能力探测与通道体检

```powershell
uv run python scripts/sage_dispatch.py capabilities --adapter codex
uv run python scripts/sage_dispatch.py doctor --adapter codex --repo-root <repo>
```

`doctor` 逐通道输出 declared/available/verification 和推荐通道：原生通道按 adapter 声明判定（运行时可用性以实际派发为准）；注入式通道校验 agent_types 完整性；CLI 通道只探测可执行文件可否定位，不执行命令。无可用通道时退出码为 1。

adapter 的机器配置按以下顺序解析：项目本地 `docs/guides/execution-adapters/<adapter>.json`、Skill 内置 `adapters/<adapter>.json`、显式 `--adapter-file`。项目可替换 Agent 名称、模型路由和 CLI 命令，但不得复制角色契约。

`models.<phase>` 是阶段级模型配置：`id` 是默认模型，`subagent_binding=request` 允许 `--model` 请求级覆盖，`agent-registration` 表示模型固定在宿主 Agent 注册，`cli_binding=command-argument` 要求 CLI 命令实际使用 `{model}`。运行 `capabilities` 可查看各阶段模型映射。

### 4.2 准备与原生派发

```powershell
uv run python scripts/sage_dispatch.py prepare --repo-root <repo> --task-path <task> --phase <phase> --adapter <adapter> --model <model-id> --format json
```

- `action=spawn_subagent`：Main Agent 必须立即使用宿主原生 API 创建 `agent_type` 指定的 subagent，并且只传信封中的 `prompt` 与协议允许的模型字段。`request` 绑定按 `model.requested` 传参，`agent-registration` 绑定只能校验宿主注册模型，不能假装单次覆盖。Dispatcher 负责协议和回执，不具备宿主 API 时不会伪造调用成功。
- `action=run_cli`：运行 `run-cli --receipt <receipt>`；命令必须来自 JSON 字符串数组，不允许 shell 拼接。若回执有具体模型，命令必须包含 `{model}`，否则 Dispatcher 阻断。
- 原生 subagent Adapter 切换 CLI 必须同时传入 `--fallback-reason` 与 `--fallback-authorized`，防止静默降级。

### 4.3 状态、验证与取消

```powershell
uv run python scripts/sage_dispatch.py status --receipt <receipt>
uv run python scripts/sage_dispatch.py verify --receipt <receipt> --format json
uv run python scripts/sage_dispatch.py cancel --receipt <receipt> --reason <原因>
```

`verify` 比较派发前后 TASK 阶段章节、Git 内容指纹和 HEAD；reviewer 还必须写入 OK/WARN/BLOCK。`cancel` 对原生 subagent 只生成 `host_cancel_required`，Main Agent 仍须调用宿主取消 API。

回执默认保存在系统临时目录，只用于运行时协调；长期证据必须写回 TASK。完整协议见 Skill 内 `references/dispatch-protocol.md` 或 adapter 文档。

---

## 五、派发模板
以下模板是默认建议，可按项目工具栈替换。若工具支持命名 subagent，建议为三个阶段分别配置 reviewer/coder/closer subagent；若不支持，使用 CLI fallback。

### 5.1 Reviewer Subagent

```text
agent_type = "sage_reviewer"  # 项目可替换为本工具实际 reviewer subagent 名称

REPO_ROOT=<仓库根目录绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<仓库根目录绝对路径>\prompts\reviewer.md
PHASE=plan-review
DIFF_CMD=<代码审查阶段填写；计划审查可省略>

请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取调度信息。按 reviewer 角色契约执行盲审，将报告写回 TASK 对应章节，必须包含 OK/WARN/BLOCK。
```

### 5.2 Coder Subagent

```text
agent_type = "sage_coder"  # 项目可替换为本工具实际 coder subagent 名称

REPO_ROOT=<仓库根目录绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<仓库根目录绝对路径>\prompts\coder.md
PHASE=dev

请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取调度信息。只执行 TASK 1.1~1.5 冻结范围，将进度和证据写回 TASK 3.x。你不是独自在代码库中工作，不得还原或覆盖他人修改。
```

### 5.3 Closer Subagent

```text
agent_type = "sage_closer"  # 项目可替换为本工具实际 closer subagent 名称

REPO_ROOT=<仓库根目录绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<仓库根目录绝对路径>\prompts\closer.md
PHASE=close

请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取调度信息。只做收尾归档、质量门禁和中文提交；严禁新增功能，严禁 merge/push/deploy。你不是独自在代码库中工作，不得还原或覆盖他人修改。
```

### 5.4 注入式子代理（无命名注册的宿主）

宿主提供通用子代理/后台任务但没有命名注册时，使用 `prepare --adapter generic-tool --channel injected`。Main Agent 用宿主原生派发工具创建通用子代理，把信封 `prompt` 作为任务指令；宿主在派发上下文中注入 ROLE_PROMPT。隔离等级以信封 `injection.isolation` 为准并写回 TASK 证据链；不要求逐次人工授权（T-018 裁决：人工确认点见 planner.md 第 8 节计划放行门）。

### 5.5 CLI Fallback

CLI fallback 只在更高优先级通道不可用、已复核现场、已尝试修复且记录失败处理后使用。CLI prompt 仍必须遵守第 3 节上下文传递契约，并要求回写 TASK 对应章节。

### 5.6 通道 provisioning

宿主 agent 注册缺失或漂移时，用 `provision` 生成注册文件。委托模式（经 sage_dispatch.py 转发到适配器 provision.py）在 bootstrap 后的项目内运行必须带 `--repo-root <repo>`（项目根无 SKILL.md 与 adapters 目录，缺省时脚本定位失败）：

```powershell
# Codex 全局 TOML 注册（生成后人工放置到 ~/.codex/agents，Skill 不代写工作区外配置）
uv run python scripts/sage_dispatch.py provision --repo-root <repo> --adapter codex --target-dir <agents 目录>

# Claude Code 等项目内 agents 目录（随仓库版本化）
uv run python scripts/sage_dispatch.py provision --repo-root <repo> --adapter claude-code --target-dir <repo>\.claude\agents
```

生成后必须重启/刷新宿主，并用最小派发探针验证注册生效；注册是否可用以宿主实际派发结果为准，provision 本身不证明可用。

---

## 六、替换执行载体的规则

如需替换为其他 subagent 或 CLI，只改派发模板中的载体名称和参数格式，保留以下不变量：

1. L0 不使用 CLI/subagent；L1 及以上必须传入 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE`
2. 必须要求执行载体回写 TASK 对应章节，而不是只输出 stdout
3. reviewer 不接收主线程讨论历史，只接收 TASK、角色提示词、diff 和证据链
4. coder/closer 只能处理冻结 TASK 范围，不得重写 TASK 1.1~1.5
5. closer 严禁执行 `git merge`、`git push`、部署命令
6. fallback 不是执行者自选项；只有默认通道失败、已完成现场复核、已尝试修复、且人类明确处理或授权后，才允许切换到备选通道

---

## 七、模型目录与载体提示边界

`base_instructions`、`model_messages`、subagent 配置中的 `developer_instructions` 属于执行载体层，不属于角色契约层。

- 允许写入模型身份、工具环境、通用行为和安全边界。
- 禁止写入 reviewer/coder/closer 的项目化完整职责规则，避免与当前权威 `prompts/*.md` 或 skill 默认发行版漂移。
- 禁止写入仓库路径、任务编号、阶段、输出章节等任务事实。
- 角色 prompt 不使用模型占位符；只有 Dispatcher 执行的 CLI 命令数组使用 `{model}`，并由 `run-cli` 校验实际消费。
- 模型身份与路由以 provider/shim 请求日志为准；模型自报仅作调试参考。修改 `agent-registration` 模型时必须同步宿主 Agent 注册文件，Skill 不自动写出工作区。
- 修改 model catalog 或 subagent 配置后，必须重启/刷新工具，并用最小 subagent 探针验证注册、模型和工具调用。

---

## 八、成功标准

| 阶段 | 成功标准 |
|------|----------|
| reviewer | TASK 2.x 或 4.x 出现有效 Markdown 报告，包含 OK/WARN/BLOCK |
| coder | TASK 3.1 有进度，3.2 有测试/lint/质量门禁证据 |
| closer | TASK 5.x 完成，必要文档同步，已在功能分支中文提交 |

stdout 为空、退出码为 0 或 subagent 回复“完成”不能单独证明成功；必须检查 TASK 文档或 Git 状态。
