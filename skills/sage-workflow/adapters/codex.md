# Codex 适配器

当 SAGE 运行在 Codex CLI 或 Codex desktop 中时，使用本适配说明；机器能力声明见同目录 `codex.json`。

## 入口加载

- 项目存在 `AGENTS.override.md` 时优先加载，因为 Codex 可能将其作为项目入口。
- 若目标项目只有内置 core，在规划前加载 `core/prompts/orchestrator.md` 与 `core/prompts/planner.md`。
- Codex 的 plan 工具只向用户展示执行进度；持久事实仍以 TASK 文档为准。

## 自动派发

1. L1 及以上进入 reviewer/coder/closer 阶段前，运行项目本地 `scripts/sage_dispatch.py prepare`；尚未 bootstrap 时运行 Skill 内置 `core/scripts/dispatch_phase.py prepare`。
2. `codex.json` 将四个阶段映射为 `sage_reviewer`、`sage_coder`、`sage_reviewer`、`sage_closer`。当 `prepare` 返回 `action=spawn_subagent` 时，Main Agent 必须立即调用 Codex 当前可用的原生 subagent API，并只传信封中的 `prompt`。
3. subagent 完成后运行 `verify --receipt <path>`；只有 TASK 对应章节和 Git 状态出现有效产出才算成功。
4. `status` 读取协议状态；`cancel` 只标记 `host_cancel_required`，Main Agent 仍须调用 Codex 原生取消/关闭能力。
5. `codex.json` 的模型绑定为 `agent-registration`：`plan-review`/`code-review` 使用 `claude-opus-4-7`，`dev` 使用 `deepseek-v4-pro`，`close` 使用 `deepseek-v4-flash`。这些值必须与宿主 `sage-reviewer`、`sage-coder`、`sage-closer` 注册配置一致，单次 `--model` 不能覆盖。

示例：

```powershell
uv run python scripts/sage_dispatch.py prepare --repo-root D:\repo --task-path D:\repo\docs\project\ACTIVE_TASK_T-001.md --phase dev --adapter codex --model deepseek-v4-pro --format json
uv run python scripts/sage_dispatch.py verify --receipt <receipt> --format json
```

## 失败恢复

- 原生 subagent 未注册、无法启动或未产生有效回写时，先复核 Git、TASK、进程和已有产出，再尝试修复原生通道。
- 只有失败现象、修复尝试和授权已经记录后，才可使用 `--channel cli --fallback-reason <记录> --fallback-authorized` 创建 CLI 回执。
- Main Agent fallback 仍需人工确认；不得因为 Dispatcher 存在就绕过执行通道门禁。

## Git 边界

- L1 及以上任务分支使用 `feat|fix|docs|chore|refactor/t-XXX-*`，不得使用工具名前缀。
- 未经用户明确授权，不执行 merge、push 或 deploy。
