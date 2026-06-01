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
- **能力优先**：工具原生支持 subagent 且已验证可用时，优先使用角色 subagent；不可用时按失败恢复协议切换 CLI fallback
- **修改通道**：优先只改本文档的“默认通道矩阵”和“派发模板”
- **L0 快速通道**：L0 不创建 TASK 文档，不调用 CLI/subagent，由 Main Agent 直接执行

---

## 二、默认通道矩阵

| 角色 | L0 | L1 | L2 | L3 | 默认通道 | 备选通道 |
|------|----|----|----|----|----------|----------|
| `planner` | Main Agent | Main Agent | Main Agent | Main Agent | 主线程 | research subagent 仅做调研/草拟 |
| `reviewer` | 不触发 | 默认跳过 | 必须触发 | 必须触发 | reviewer subagent | reviewer CLI |
| `coder` | Main Agent | coder subagent | coder subagent | coder subagent | coder subagent | coder CLI / 人工确认后的 Main Agent fallback |
| `closer` | Main Agent | closer subagent | closer subagent | closer subagent | closer subagent | closer CLI / 人工确认后的 Main Agent fallback |

> 项目可按工具能力覆盖默认通道，但不得绕过 TASK、角色提示词和质量门禁。
> 若默认 subagent 未注册、无法启动、工具调用失败或无法产生 TASK/Git 有效产出，必须先复核 Git/TASK/进程/已有产出状态，记录失败现象和修复尝试，再切换 CLI fallback。

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

## 四、派发模板

以下模板是默认建议，可按项目工具栈替换。若工具支持命名 subagent，建议为三个阶段分别配置 reviewer/coder/closer subagent；若不支持，使用 CLI fallback。

### 4.1 Reviewer Subagent

```text
agent_type = "sage_reviewer"  # 项目可替换为本工具实际 reviewer subagent 名称

REPO_ROOT=<仓库根目录绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<仓库根目录绝对路径>\prompts\reviewer.md
PHASE=plan-review
DIFF_CMD=<代码审查阶段填写；计划审查可省略>

请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取调度信息。按 reviewer 角色契约执行盲审，将报告写回 TASK 对应章节，必须包含 OK/WARN/BLOCK。
```

### 4.2 Coder Subagent

```text
agent_type = "sage_coder"  # 项目可替换为本工具实际 coder subagent 名称

REPO_ROOT=<仓库根目录绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<仓库根目录绝对路径>\prompts\coder.md
PHASE=dev

请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取调度信息。只执行 TASK 1.1~1.5 冻结范围，将进度和证据写回 TASK 3.x。你不是独自在代码库中工作，不得还原或覆盖他人修改。
```

### 4.3 Closer Subagent

```text
agent_type = "sage_closer"  # 项目可替换为本工具实际 closer subagent 名称

REPO_ROOT=<仓库根目录绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<仓库根目录绝对路径>\prompts\closer.md
PHASE=close

请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取调度信息。只做收尾归档、质量门禁和中文提交；严禁新增功能，严禁 merge/push/deploy。你不是独自在代码库中工作，不得还原或覆盖他人修改。
```

### 4.4 CLI Fallback

CLI fallback 只在默认 subagent 不可用、已复核现场、已尝试修复且记录失败处理后使用。CLI prompt 仍必须遵守第 3 节上下文传递契约，并要求回写 TASK 对应章节。

---

## 五、替换执行载体的规则

如需替换为其他 subagent 或 CLI，只改派发模板中的载体名称和参数格式，保留以下不变量：

1. L0 不使用 CLI/subagent；L1 及以上必须传入 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE`
2. 必须要求执行载体回写 TASK 对应章节，而不是只输出 stdout
3. reviewer 不接收主线程讨论历史，只接收 TASK、角色提示词、diff 和证据链
4. coder/closer 只能处理冻结 TASK 范围，不得重写 TASK 1.1~1.5
5. closer 严禁执行 `git merge`、`git push`、部署命令
6. fallback 不是执行者自选项；只有默认通道失败、已完成现场复核、已尝试修复、且人类明确处理或授权后，才允许切换到备选通道

---

## 六、模型目录与载体提示边界

`base_instructions`、`model_messages`、subagent 配置中的 `developer_instructions` 属于执行载体层，不属于角色契约层。

- 允许写入模型身份、工具环境、通用行为和安全边界。
- 禁止写入 reviewer/coder/closer 的项目化完整职责规则，避免与当前权威 `prompts/*.md` 或 skill 默认发行版漂移。
- 禁止写入仓库路径、任务编号、阶段、输出章节等任务事实。
- 如果工具链不能确认模板变量会被渲染，不要依赖 `{model_name}` 等占位符；应直接生成已渲染文本。
- 模型身份与路由以 provider/shim 请求日志为准；模型自报仅作调试参考。
- 修改 model catalog 或 subagent 配置后，必须重启/刷新工具，并用最小 subagent 探针验证注册、模型和工具调用。

---

## 七、成功标准

| 阶段 | 成功标准 |
|------|----------|
| reviewer | TASK 2.x 或 4.x 出现有效 Markdown 报告，包含 OK/WARN/BLOCK |
| coder | TASK 3.1 有进度，3.2 有测试/lint/质量门禁证据 |
| closer | TASK 5.x 完成，必要文档同步，已在功能分支中文提交 |

stdout 为空、退出码为 0 或 subagent 回复“完成”不能单独证明成功；必须检查 TASK 文档或 Git 状态。
