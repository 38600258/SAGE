---
description: 收尾与归档 (Finalization & Archive)
---

> **核心目标**：完成文档同步、知识沉淀、版本提交与分支合并，确保任务无尾巴地干净关闭。

### 步骤 1：遗留问题与技术债登记 (Technical Debt & Unresolved Issues)
1. 读取 `ACTIVE_TASK_T-XXX.md` 的 **5.1 遗留问题与技术债** 节（如经过 `/4codereview`，强模型已在此节预填内容）。
2. 如该节为空或标注"无"，补充梳理本次任务中**未解决的问题**、**新出现的问题**或**产生的技术债**并填入。
3. 将 5.1 节中的每一条遗留项**逐条登记**到 `dev/docs/project/PROJECT_BOARD.md` 的"待开发"或"阻塞项"列表中，确保问题被持续追踪。

### 步骤 2：知识蒸馏 (Knowledge Distillation)
1. 填写 `ACTIVE_TASK_T-XXX.md` 的 **5.2 核心决策与避坑**：记录本次任务中的关键技术取舍和踩坑经验。
2. **模式库追加**：将本次任务中值得跨任务复用的经验，按分类追加到 `dev/docs/project/KNOWN_PATTERNS.md`：
   - 📗 最佳实践：值得推广的技术模式或工程方法
   - 📕 反模式与踩坑：已验证的错误路径和正确替代方案
   - 📘 架构决策模式：可复用的架构选择逻辑
   - 如本次任务无可沉淀内容，显式标注"无新增模式"

### 步骤 3：任务结算三问 (Final Three Questions)
填写 `ACTIVE_TASK_T-XXX.md` 的 **5.3 节**，逐条回答并执行：
1. **🚢 规则同步**：本次任务是否涉及业务规则的永久性变更？
    - 是 → 同步更新 `references/` 下的对应规则文件
2. **📜 决策存证**：是否有关键的技术方案取舍或重大逻辑调整？
    - 是 → 在 `dev/docs/project/DECISION_LOG.md` 中记录摘要
3. **🛡️ 标准沉淀**：是否有通用的代码陷阱、最佳实践或新的开发模式？
    - 是 → 更新 `dev/docs/guides/development-standards.md`

### 步骤 4：文档同步 (Truth Synchronization)
1. 使用版本升号工具统一更新所有文档中的版本号（参照 `development-standards.md` 7.3节）：
   - **大架构升级**：`uv run python dev/scripts/bump_version.py major`
   - **新功能添加**：`uv run python dev/scripts/bump_version.py minor`
   - **Bug与小更新**：`uv run python dev/scripts/bump_version.py patch`
   - 首次可用 `--dry-run` 预览变更：`uv run python dev/scripts/bump_version.py patch --dry-run`
2. 更新 `CHANGELOG.md`，将所有变更详细记录在案。
3. 更新 `dev/docs/project/PROJECT_BOARD.md`，将任务移入"已完成"并填写完成日期和备注。
4. 如本次任务新增或变更了系统能力，在 `dev/docs/architecture/CAPABILITY_SNAPSHOT.md` 中追加或更新对应条目。
5. 同步更新受影响的其他文档（架构文档、SKILL.md、HANDOVER-GUIDE.md 等）。

### 步骤 4.5：证据驱动验收 (Evidence-Based Acceptance)
> 不接受"我觉得已经完成了"。以下每项必须附带客观证据。

| 验收项 | 证据类型 | 证据 |
|--------|----------|------|
| 核心功能正确 | 测试输出 PASSED | (粘贴终端输出) |
| 无 lint 问题 | ruff check 输出 | (粘贴终端输出) |
| 部署验证(如适用) | CLI 测试/日志 | (粘贴实际结果) |

⚠️ 任何一项缺少客观证据，不得进入步骤 5。

### 步骤 5：自检清单 (Final Checklist)
完成 `ACTIVE_TASK_T-XXX.md` 的 **5.4 节** 逐条确认：
- 遗留问题/技术债已登记到看板
- 代码实现逻辑完整
- 单元测试覆盖核心分支
- `CHANGELOG.md` 已更新
- `PROJECT_BOARD.md` 状态同步
- 相关文档已同步更新
- 版本号已统一更新（如适用）
- 任务现场清理（临时文件、调试代码）
- 效能数据已填写（开始/结束时间、返工次数、AI代码生成占比）

### 步骤 6：归档准备 (Pre-Commit Archive)
> ⚠️ **本步骤的所有操作必须在 Git 提交之前完成**，以确保归档和提交合并为一次性干净操作。

1. 将 `ACTIVE_TASK_T-XXX.md` 的阶段标记更新为 `✅ 已完成`，填写效能数据（结束时间等）。
2. 归档任务文档：
   - 将 `ACTIVE_TASK_T-XXX.md` 剥离 ACTIVE 前缀，按 kebab-case 重命名为 `t-xxx.md`（如 `t-608.md`），并将其移动至 `dev/docs/architecture/tasks/` 目录中。
   - 若任务包含架构设计或重构方案（如 `TXXX_REFACTOR_PLAN.md` 或 `PLAN_T-XXX.md`），将其按 kebab-case 规范重命名（如 `t-xxx-feature-name.md`）并移至 `dev/docs/architecture/` 目录。

### 步骤 7：Git 提交与分支合并 (Commit & Merge)
1. 在功能分支上暂存所有变更文件（包括步骤 6 归档后的文件）：`git add <文件列表>`
2. 按规范提交（中文描述）：`git commit -m "<类型>(<范围>): <中文描述>"`
    - 类型：feat | fix | docs | refactor | test | chore
    - 示例：`feat(log): 统一日志基建与持久化 (T-701)`
    - **保持提交整洁**：对于同一问题的重复修改，必须优先使用 `git commit --amend` 或者 Squash（压缩提交），避免在主干堆砌细碎无意义的修订记录。
3. 切换到 `dev` 分支：`git checkout dev`
4. 合并功能分支：`git merge feature/T-XXX-xxx`
5. 合并成功后删除功能分支：`git branch -d feature/T-XXX-xxx`

### 步骤 8：关闭确认 (Closure)
1. 向用户输出任务完成总结：变更内容、影响范围、后续注意事项。
2. 询问是否需要同步到测试/生产环境，获得用户授权后使用部署流水线执行：
   - 同步至 WSL 测试环境：`.\dev\scripts\deploy.ps1 -Target wsl`
   - 发版至生产服务器：`.\dev\scripts\deploy.ps1 -Target prod`（内含 Ruff + Pytest 强制卡点）

### 🔙 回滚规则
- **触发条件**：自检清单未通过、文档同步发现遗漏
- **回滚动作**：
  1. 明确缺失项，直接在当前阶段补齐（轻微遗漏）
  2. 如发现代码缺陷 → 返回 `/3dev` 补充测试和修复
- **禁止**：收尾阶段严禁新增功能（scope creep），如有新需求须创建独立任务