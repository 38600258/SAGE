# Claude Code 适配器

当 SAGE 运行在 Claude Code 中时，使用本适配说明；机器能力声明见同目录 `claude-code.json`。

## 入口加载

- Claude Code 以项目根 `AGENTS.md`（或 `CLAUDE.md`）作为项目入口。
- 若目标项目只有内置 core，在规划前加载 `core/prompts/orchestrator.md` 与 `core/prompts/planner.md`。
- 持久事实仍以 TASK 文档为准，不依赖会话内存。

## 自动派发

1. L1 及以上进入 reviewer/coder/closer 阶段前，运行项目本地 `scripts/sage_dispatch.py prepare`；尚未 bootstrap 时运行 Skill 内置 `core/scripts/dispatch_phase.py prepare`。
2. `claude-code.json` 将四个阶段映射为 `sage-reviewer`、`sage-coder`、`sage-reviewer`、`sage-closer`（项目内 Markdown agents 注册）。当 `prepare` 返回 `action=spawn_subagent` 时，Main Agent 必须立即调用 Claude Code 当前可用的原生 subagent 能力，并只传信封中的 `prompt`。
3. subagent 完成后运行 `verify --receipt <path>`；只有 TASK 对应章节和 Git 状态出现有效产出才算成功。
4. `status` 读取协议状态；`cancel` 只标记 `host_cancel_required`，Main Agent 仍须调用宿主原生取消/关闭能力。

示例：

```powershell
uv run python scripts/sage_dispatch.py prepare --repo-root D:\repo --task-path D:\repo\docs\project\ACTIVE_TASK_T-001.md --phase dev --adapter claude-code --format json
uv run python scripts/sage_dispatch.py verify --receipt <receipt> --format json
```

## 子代理注册（provision）

宿主 agent 注册缺失或漂移时，用 `provision` 生成项目内 Markdown agents 注册文件（随仓库版本化）：

```powershell
# 独立运行（模型取自同目录 claude-code.json，Markdown 注册不消费模型参数）
uv run python docs/guides/execution-adapters/claude-code/provision.py --target-dir D:\repo\.claude\agents

# 或经主入口委托执行（bootstrap 后的项目内必须带 --repo-root，否则脚本定位失败）
uv run python scripts/sage_dispatch.py provision --repo-root D:\repo --adapter claude-code --target-dir D:\repo\.claude\agents
```

生成后必须重启/刷新宿主，并用最小派发探针验证注册生效；注册是否可用以宿主实际派发结果为准。

## 失败恢复

- 原生 subagent 未注册、无法启动或未产生有效回写时，先复核 Git、TASK、进程和已有产出，再尝试修复原生通道。
- 只有失败现象、修复尝试和授权已经记录后，才可使用 `--channel cli --fallback-reason <记录> --fallback-authorized` 创建 CLI 回执（需项目 adapter 声明 CLI 通道）。
- Main Agent fallback 仍需人工确认；不得因为 Dispatcher 存在就绕过执行通道门禁。

## Git 边界

- L1 及以上任务分支使用 `feat|fix|docs|chore|refactor/t-XXX-*`，不得使用工具名前缀。
- 未经用户明确授权，不执行 merge、push 或 deploy。

## 已知踩坑

宿主/CLI 特定陷阱的官方沉淀位；新踩坑随任务收尾沉淀进本节（纳入内容卫生范围）。

- **prompt 被吞（`--add-dir`）**——把 prompt 放在 `--add-dir` 之后会被 `--add-dir <directories...>` 可变参数吞掉，表现为 `Input must be provided either through stdin or as a prompt argument`；prompt 必须放在参数序列最前，或经 stdin 传入。
