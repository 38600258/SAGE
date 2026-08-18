# SAGE Git Hooks

SAGE 源仓库启用：

```bash
git config core.hooksPath skills/sage-workflow/core/githooks
```

Bootstrap 到项目后启用：

```bash
git config core.hooksPath .githooks
```

运行 `core/scripts/bootstrap_sage.py` 时，bootstrap 默认会检查目标仓库的
`core.hooksPath`：

- 未配置时，自动设置为 `.githooks`。
- 已配置且指向 `.githooks` 时，提示已启用，不重复修改。
- 已配置但指向其他路径时，提示配置来源和路径，不覆盖现有设置。
- 使用 `--skip-hooks` 可跳过 hooks 配置；使用 `--dry-run` 只预览，不修改配置。
- 目标不是 Git 仓库时，复制文件仍会继续，但 hooks 配置会被跳过并提示。

- `commit-msg`：优先使用项目本地 `scripts/sage_linter.py`，缺失时回退到 `skills/sage-workflow/core/scripts/sage_linter.py`；Python 解释器按 `.venv` → `python3` → `python` → `python.cmd` → `py` 顺序探测，兼容 Windows 商店占位 stub 场景。
- `commit-msg.bat`：Windows 手动或工具集成时可直接调用的等价脚本。

Git hooks 是提交前的稳定硬门禁；智能体工具内 hooks 如可用，仅作为实时提醒或软防护。