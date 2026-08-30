# CLI 适配器

当 SAGE 运行在通用命令行 Agent 或没有原生 SAGE subagent 能力的工具中时，使用本适配说明；机器能力声明见同目录 `cli.json`。

## 调用契约

`prepare` 生成的 prompt 只包含以下定位字段：

```text
REPO_ROOT=<仓库绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<角色提示词绝对路径>
PHASE=<plan-review|dev|code-review|close>
DIFF_CMD=<代码审查阶段可选 diff 命令>
```

CLI 执行者必须从仓库文件读取角色指令和调度事实，并将结果写回 TASK 文档。

## 自动执行

1. 运行 `prepare --adapter cli` 创建 `action=run_cli` 回执。
2. 使用 `run-cli --receipt <path>` 执行命令。命令来源依次为 `--command-json`、adapter 的 `command_env`、adapter 的 `command`。
3. 命令必须是 JSON 字符串数组，Dispatcher 直接调用 `subprocess.run(list)`，不使用 shell 拼接。
4. 默认通过 UTF-8 stdin 传入 prompt；命令数组可使用 `{repo_root}`、`{task_path}`、`{role_prompt}`、`{phase}`、`{diff_cmd}`、`{prompt}`、`{model}` 占位符。指定模型时必须使用 `{model}`，不能在命令里硬编码另一个模型。
5. CLI 输出写入回执同目录的 `.log` 文件；退出码为 0 仍须通过 TASK/Git 验证。
6. 通过 `prepare --model <model-id>` 指定模型时，`run-cli` 会拒绝不包含 `{model}` 的命令数组。

示例：

```powershell
$env:SAGE_CLI_COMMAND_JSON='["agent-cli","--model","{model}","--prompt","{prompt}"]'
uv run python scripts/sage_dispatch.py prepare --repo-root D:\repo --task-path D:\repo\docs\project\ACTIVE_TASK_T-001.md --phase dev --adapter cli --format json
uv run python scripts/sage_dispatch.py run-cli --receipt <receipt> --format json
```

## Fallback 规则

- CLI stdout、退出码或口头“完成”不能单独作为成功证据。
- 成功必须体现在 TASK 对应章节和 Git 指纹/HEAD 中。
- 失败后切换工具前，必须复核 Git 状态、TASK 内容、进程状态和已有产出。

## 已知踩坑

宿主/CLI 特定陷阱的官方沉淀位；新踩坑随任务收尾沉淀进本节（纳入内容卫生范围）。

- **Qwen CLI：superpowers 残留**——卸载 superpowers extension 后仍出现 `using-superpowers [User]`，来源通常是用户级 `~/.qwen/skills/using-superpowers` 残留；需移走或清空用户级 skills 并重启 Qwen 会话。
- **Qwen CLI（Windows）：printf stderr 噪声**——成功输出后可能附带 `'printf' is not recognized` 的内部脚本 stderr 噪声；调用前临时把 `C:\Program Files\Git\usr\bin` 追加到 `PATH` 可规避；退出码 0 且 TASK/Git 产出符合预期时，不应仅因附带 stderr 判定失败——成功判定回到「TASK/Git 产出为准」的既有原则。
