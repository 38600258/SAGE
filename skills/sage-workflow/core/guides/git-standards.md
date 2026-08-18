# Git 规范 (Git Standards)

> T2 级硬规则 | 状态：[CURRENT]
> 入口路由 → [AGENTS.md](../entry/AGENTS.md) | 总览 → [development-standards.md](development-standards.md)

---

## 一、适用阶段

- 任务初始化阶段：创建功能分支。
- 收尾阶段：暂存、提交、报告等待人类合并。
- L0 可直接在当前授权分支执行；L1 及以上必须使用任务分支。

---

## 二、分支命名

| 类型 | 格式 |
|------|------|
| L0 修复/文档/整理 | `fix/l0-name` / `docs/l0-name` / `chore/l0-name` / `style/l0-name` |
| 功能 | `feat/t-XXX-name` |
| 修复 | `fix/t-XXX-name` |
| 文档 | `docs/t-XXX-name` |
| 整理 | `chore/t-XXX-name` |
| 重构 | `refactor/t-XXX-name` |

Codex app 覆盖：分支禁止使用工具名前缀。

---

## 三、提交信息

提交标题必须满足：

```text
<类型>(<范围>): <中文描述>
<类型>: <中文描述>
```

允许类型：`feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `style`。

硬约束：

- 首行必须符合 Conventional Commit 格式。
- 描述部分必须包含至少一个中文字符（CJK U+4E00-9FFF）。
- `Merge` / `Revert` / `fixup!` / `squash!` 等系统或整理类提交可豁免。
- `.githooks/commit-msg` 与 `python scripts/sage_linter.py --check-commit-msg <提交信息文件>` 负责物理拦截。

---

## 四、提交整洁度

- 一个独立任务应尽量形成一个语义完整提交。
- 同一任务内的收尾补丁优先用 `git commit --amend` 合入任务提交。
- 禁止在主干历史中堆砌 `fix typo`、`update again` 等无语义补丁。
- 合并到开发基线分支和生产主干的权力属于人类；智能体不得自行 merge/push，除非用户明确授权。

---

## 五、收尾自检

- [ ] 当前分支符合任务等级和类型。
- [ ] 仅暂存本任务范围内文件。
- [ ] 提交标题为中文 Conventional Commit。
- [ ] 未执行未授权 merge / push / deploy。
