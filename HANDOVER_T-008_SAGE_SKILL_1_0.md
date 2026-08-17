# T-008 SAGE Skill 1.0 交接文档

本文件记录截至 2026-07-23 的完整工作现场，供新会话直接续接。所有日期均为实际执行日期；未提交、未推送、未部署。

## 1. 当前现场

- **仓库**：`D:\Dev\Code\sage`
- **分支**：`feat/t-008-sage-skill-1-0`
- **基线提交**：`d5722eed795b4f1653f61737b8fe412478e364c4`
- **活跃 TASK**：`docs/project/ACTIVE_TASK_T-008.md`
- **任务等级 / 阶段**：L2 / `code-review`
- **任务约束**：不新建任务；使用 `uv`；文档优先中文；不执行 merge、push、deploy 或自动提交。

T-008 原始目标是将 SAGE 工作流升级为可跨工具使用的 1.0 Skill。用户与 reviewer 的共识是：角色契约、TASK 模板和流程指南与工作流强耦合，应封装为 Skill 默认发行版，而不是只保留薄路由层；项目本地文件可覆盖默认发行版。

## 2. 已完成的 Skill 化改造

- 已建立 `skills/sage-workflow/`，内含 `SKILL.md`、`core/`、`adapters/` 和 `references/`。
- 默认发行版已集中到 `skills/sage-workflow/core/`：角色契约、模板、指南、方法论、linter、bootstrap、githooks 和 scaffold。
- 根目录重复的旧工作流资产已计划删除（`prompts/`、`templates/`、`docs/guides/`、根目录 linter/hooks/方法论）；入口、架构和项目治理文件已改为指向 Skill core。
- bootstrap 会复制 Dispatcher 到项目本地 `scripts/sage_dispatch.py`，并复制 adapter JSON 到 `docs/guides/execution-adapters/`。
- 相关大范围改动均在当前未提交工作树中；不要还原或拆分他人已有的 T-008 变更。

## 3. 本轮新增：阶段级子代理模型路由

### 3.1 设计决策

模型路由属于 **adapter / 执行载体层**，不写入角色 prompt，也不写入 TASK 调度事实。Dispatcher 的 `prepare` 生成模型信封，宿主再按绑定方式消费：

```json
"models": {
  "dev": {
    "id": "model-id",
    "subagent_binding": "request",
    "cli_binding": "command-argument"
  }
}
```

绑定语义：

- `subagent_binding=request`：宿主原生 subagent API 支持请求级 `model` 参数；`prepare --model <id>` 可以覆盖 adapter 默认模型，Main Agent 必须把信封的 `model.requested` 传给宿主 API。
- `subagent_binding=agent-registration`：命名 subagent 的模型在宿主 Agent 注册文件中固定。`--model` 只能传与 adapter 默认值相同的模型以作显式校验；不同模型必须报错，要求同步修改 adapter JSON 与宿主注册配置，不能伪造单次覆盖。
- `cli_binding=command-argument`：CLI 命令数组必须实际包含 `{model}`。当回执解析到模型却未使用占位符、或命令使用 `{model}` 但回执没有模型时，`run-cli` 必须阻断。
- `none`：该通道不支持模型路由；显式 `--model` 必须拒绝。

### 3.2 关键实现

- `skills/sage-workflow/core/scripts/dispatch_phase.py`
  - `prepare` 新增 `--model`。
  - 校验 adapter 的 `models.<phase>` 配置。
  - `resolve_model()` 生成 `{requested, binding, source}` 模型信封。
  - 回执新增 `model`，`capabilities` 文本输出显示阶段模型映射。
  - CLI 命令支持 `{model}`，并强制验证实际消费。
- `skills/sage-workflow/adapters/codex.json`
  - `plan-review` / `code-review`：`claude-opus-4-7`
  - `dev`：`deepseek-v4-pro`
  - `close`：`deepseek-v4-flash`
  - 原生绑定均为 `agent-registration`；CLI fallback 为 `command-argument`。
- `skills/sage-workflow/adapters/cli.json`
  - 默认模型为 `null`，可由 `prepare --model` 指定；CLI 绑定为 `command-argument`。
- `skills/sage-workflow/adapters/generic-tool.json`
  - 为未来原生宿主预留 `request` 绑定；当前默认仍选择 CLI。
- 已同步更新 `SKILL.md`、三个 adapter 说明、`references/dispatch-protocol.md`、执行通道指南、模型选择指南、入口文件、README、架构和 CHANGELOG。

### 3.3 Codex 宿主注册一致性

已只读核对工作区外的宿主配置，**不要自动修改它们**：

- `C:\Users\vxie\.codex\agents\sage-reviewer.toml`：`claude-opus-4-7`
- `C:\Users\vxie\.codex\agents\sage-coder.toml`：`deepseek-v4-pro`
- `C:\Users\vxie\.codex\agents\sage-closer.toml`：`deepseek-v4-flash`

它们与 `codex.json` 一致。若用户要更换 Codex 原生 `sage_*` 子代理模型，必须先人工修改对应 TOML，再同步改 adapter JSON；Skill 不应写出工作区修改这些 TOML。

## 4. 使用方式

### 4.1 查看能力

```powershell
$env:UV_CACHE_DIR='D:\Dev\Code\sage\.uv-cache'
uv run python -X utf8 skills/sage-workflow/core/scripts/dispatch_phase.py capabilities --adapter codex --format json
```

### 4.2 原生请求级模型宿主

对 `subagent_binding=request` 的项目 adapter：

```powershell
uv run python -X utf8 scripts/sage_dispatch.py prepare `
  --repo-root <repo> --task-path <task> --phase dev --adapter <adapter> `
  --model <model-id> --format json
```

读取回执的 `agent_type`、`prompt` 与 `model`；调用宿主 spawn API 时传入 `model.requested`。不要把模型写进 prompt。

### 4.3 Codex 注册型子代理

Codex 默认 `sage_reviewer` / `sage_coder` / `sage_closer` 使用 `agent-registration`。例如：

```powershell
uv run python -X utf8 scripts/sage_dispatch.py prepare `
  --repo-root <repo> --task-path <task> --phase dev --adapter codex `
  --model deepseek-v4-pro --format json
```

传入与 adapter 相同的模型是显式校验；传入其他模型会被 Dispatcher 拒绝。Main Agent 使用 `agent_type` 调用原生 subagent，但不应宣称已用单次参数覆盖注册模型。

### 4.4 CLI fallback

```powershell
$commandJson='["codex.cmd","exec","-m","{model}","-C","{repo_root}","--ephemeral","-"]'
uv run python -X utf8 scripts/sage_dispatch.py run-cli `
  --receipt <receipt-path> --command-json $commandJson --format json
```

有具体模型时 `{model}` 是强制项；命令硬编码模型名、但不使用占位符，会被 Dispatcher 视为“未实际消费配置”并拒绝。

## 5. 验证结果

截至 2026-07-23，以下均已通过：

```powershell
$env:UV_CACHE_DIR='D:\Dev\Code\sage\.uv-cache'
$env:PYTHONDONTWRITEBYTECODE='1'
uv run python -X utf8 -m unittest discover -s skills/sage-workflow/core/scripts/tests -v
uv run --with pyyaml python -X utf8 C:\Users\vxie\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills/sage-workflow
git diff --check
uv run python -X utf8 skills/sage-workflow/core/scripts/sage_linter.py --all --allow-template-changes
```

- Dispatcher 单测共 **10 项通过**：原生默认模型信封、请求级覆盖、注册型覆盖冲突、CLI `{model}` 消费、缺少模型/缺少占位符阻断，以及原有派发验证。
- `quick_validate.py` 输出 `Skill is valid!`。
- `git diff --check` 通过。
- SAGE linter 所有阻断项通过；退出码 `1` 仅表示既有文档新鲜度 WARN，不是阻断失败。
- bootstrap 临时项目验证成功复制 35 个文件，项目本地 Dispatcher 能读取复制后的 `codex.json` 模型映射。

## 6. 当前阻塞：独立代码盲审

TASK 当前必须保持 `code-review`，不能进入 close，也不能伪造新的 `OK/WARN/BLOCK`。

已按流程尝试：

1. 原生 Dispatcher 正确生成 `action=spawn_subagent`、`agent_type=sage_reviewer`、`model.requested=claude-opus-4-7`、`binding=agent-registration`。
2. 原生 `sage_reviewer` 仍返回 `agent type is currently not available`，没有 TASK/Git 产出。
3. 现场已复核，且 TASK 内已有用户授权记录，可进行 CLI fallback。
4. 使用 Dispatcher 创建 CLI 回执，命令为 `codex.cmd exec -m {model} -C {repo_root} --ephemeral -`。
5. 日志证明 `{model}` 已被替换为 `claude-opus-4-7`，但 `custom` provider 连续重试后返回 `503 Service Unavailable`。
6. 因原生 subagent 不可用 + CLI 503，审查无法完成；不要改用 Main Agent 自审，除非人类明确授权该 fallback。

本轮派发失败信息及证据已写入 `docs/project/ACTIVE_TASK_T-008.md` 的 4.2、5.10、5.11。临时回执/日志位于系统 Temp，下次会话可能已失效；以 TASK 为长期证据来源。

## 7. 新会话续接步骤

1. 进入 `D:\Dev\Code\sage`，读取 `AGENTS.md`、`AGENTS.override.md`、`docs/project/ACTIVE_TASK_T-008.md` 和本文件。
2. 执行 `git status --short --branch`，确认仍在 `feat/t-008-sage-skill-1-0`，不要丢弃现有大量未提交的 T-008 Skill 化改动。
3. 运行第 5 节的测试与门禁；若只想确认模型配置，先运行 `capabilities --adapter codex --format json`。
4. 若 `sage_reviewer` 已恢复，在 `code-review` 阶段重新运行 `prepare --phase code-review --adapter codex --model claude-opus-4-7`，然后以回执的 `prompt` 调用原生 reviewer，最后执行 `verify --receipt <path>`。
5. 若原生 reviewer 仍不可用，先复核 TASK/Git/进程状态；仅在现有 TASK 授权仍适用且服务恢复后，再用 CLI fallback 和包含 `{model}` 的命令数组重试。不要无限重试 503。
6. 只有 `verify` 确认 TASK 4.x 新增/修改独立 `OK/WARN/BLOCK` 后，才能按审查结论流转；若为 BLOCK/WARN，按 reviewer 结论修复并重新审查。
7. L2 代码审查完成前，不进入 close，不提交、不推送、不 merge。

## 8. 操作注意事项

- 新会话不要创建新 TASK；T-008 已承载全部追加范围。
- 不要修改 `C:\Users\vxie\.codex\agents\sage-*.toml`，除非人类明确授权；修改后必须同步 `skills/sage-workflow/adapters/codex.json`。
- `apply_patch.bat` 在本机当前环境返回 `Access is denied`；若继续编辑，先尝试标准 `apply_patch`，不可用时使用 PowerShell/`uv run python` 精确替换，并立即运行 `git diff --check`。
- 当前工作树包含 Skill 化迁移所需的删除、新增和修改；这些不是临时噪音。已清理 `__pycache__` 和 bootstrap 测试目录，未发现临时测试产物。
- 不要将模型名、项目路径、任务编号或完整角色职责复制到 subagent 的 `base_instructions` / `model_messages`；角色从 `ROLE_PROMPT` 读取，任务事实从 TASK 读取，模型从 adapter/宿主绑定读取。
