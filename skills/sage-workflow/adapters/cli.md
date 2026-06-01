# CLI 适配器

当 SAGE 运行在通用命令行 agent 或没有原生 SAGE 支持的工具中时，使用本适配说明。

## 调用契约

每次派发给 CLI 的 prompt 只提供定位字段：

```text
REPO_ROOT=<仓库绝对路径>
TASK_PATH=<TASK 文档绝对路径>
ROLE_PROMPT=<角色提示词绝对路径>
PHASE=<plan-review|dev|code-review|close>
DIFF_CMD=<代码审查阶段可选 diff 命令>
```

CLI 执行者必须从仓库文件读取角色指令和调度事实，并将结果写回 TASK 文档。

## Fallback 规则

- CLI stdout、退出码或口头“完成”不能单独作为成功证据。
- 成功必须体现在 TASK 章节和 Git 状态中。
- 失败后切换工具前，必须复核 Git 状态、TASK 内容、进程状态和已有产出。
