# SAGE Git Hooks

启用方式：

```bash
git config core.hooksPath .githooks
```

- `commit-msg`：执行 `scripts/sage_linter.py --check-commit-msg`，要求提交标题符合 Conventional Commit 且描述包含中文字符。
- `commit-msg.bat`：Windows 手动或工具集成时可直接调用的等价脚本。

Git hooks 是提交前的稳定硬门禁；智能体工具内 hooks 如可用，仅作为实时提醒或软防护。
