# 🚀 任务执行台 (Task Control Plane)

> **核心原则**：本文件是任务执行期间的"单一事实来源"。

---

## 📌 任务元数据 (Metadata)

- **任务编号 (ID)**: T-XXX
- **任务描述**: (待填入)
- **风险等级**: L1 / L2 / L3（L0 不创建 TASK 文档）
- **当前阶段**: init | plan-review | dev | code-review | close
- **计划放行**: 待放行
- **项目根目录**: (绝对路径，如 D:\Dev\Code\your-project)
- **功能分支**: (分支名，如 feat/t-001-add-auth 或 docs/t-001-update-docs)
- **执行通道配置**: skills/sage-workflow/core/guides/execution-channels.md
- **使用模型**: [填写实际使用的模型]
- **工具会话 ID**: [自动填写，如 Antigravity 会话 ID / Codex thread]
- **效能数据**:
  - 开始时间: (自动填入，格式：YYYY-MM-DDTHH:mm:ss+08:00)
  - 结束时间: (任务完结时填入，格式：YYYY-MM-DDTHH:mm:ss+08:00)
  - 返工次数: 0（口径：盲审退回、门禁未过重跑、格式试错每轮计 1，含微返工）
  - AI 代码生成占比: ~?%

---

## 🛠️ 阶段 1：初始化 (`planner`) — YYYY-MM-DDTHH:mm:ss+08:00

### 1.0 执行通道记录 (Execution Channel)
- [ ] **角色契约**: `prompts/planner.md` 已加载并遵循
- [ ] **执行通道**: Main Agent
- [ ] **偏离处理**: N/A；若规范通道无法执行，必须先复核现场状态（Git/TASK/进程/已有产出），再尝试修复；无法修复时停止并报告，等待人工处理

### 1.1 任务背景 (Context)
(此处填入任务背景)

### 1.2 思考与决策 (Thinking & Decision)
(此处填入分析思考过程)

### 1.3 实施计划 (Execution Plan)
> 只描述接口契约、行为约束、边界条件和必要的文件/函数定位；避免伪代码级实现蓝图。

(在此处填写原子步骤计划；每步关联至少一个 AC-ID)

### 1.3a 验收标准 (Acceptance Criteria) — L2/L3 必填，L1 可略
> TASK 是可证伪的意图契约，不是 PRD，也不是实现蓝图。每条验收标准必须能通过命令、输出、日志、截图或明确人工步骤客观验证，并在阶段 3 证据链按 AC-ID 回填。

| AC-ID | 类型 | 可证伪验收标准 | 验证方式 | 证据位置 |
|-------|------|----------------|----------|----------|
| AC-1 | [auto] | (如：运行 `pytest tests/` 全部通过) | `pytest tests/` | `3.2` |
| AC-2 | [manual] | (如：用户可在设置页完成导出操作) | 操作路径：设置 → 导出 → 确认下载文件 | `3.2` |

### 1.3b 风险矩阵 (Risk Matrix) — L2/L3 必填，L1 可略
> 列出已识别的风险及缓解措施。

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| (风险描述) | 低/中/高 | 低/中/高 | (缓解方案) |

### 1.4 🛡️ 范围锁定 (Scope Lock)
- **可写文件 (Writable)**: (列出)
- **只读参考 (Read-only)**: (列出)
- **严禁修改 (Forbidden)**: (列出)

### 1.5 ❌ 非目标 (Non-Goals)
- (明确不做的事)

---

## 🔍 阶段 2：计划评审 (`reviewer`) — YYYY-MM-DDTHH:mm:ss+08:00

### 2.0 执行通道记录 (Execution Channel)
- [ ] **角色契约**: `prompts/reviewer.md` 已加载并遵循 / L1 跳过填写 N/A
- [ ] **执行通道**: CLI / subagent / N/A
- [ ] **偏离处理**: N/A；若规范通道无法执行，必须先复核现场状态（Git/TASK/进程/已有产出），再尝试修复；无法修复时停止并报告，等待人工处理

### 2.1 评审意见 (Review Feedback)
- [ ] **评审意见**: (由 reviewer 填写)
- [ ] **修正记录**: (如有修改)

<!-- 盲审按“执行通道配置”调用 CLI 或 subagent；Prompt 只提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE 等必要定位信息，其他调度信息从 TASK 元数据读取，并要求 reviewer 写回本节。 -->
<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 3。 -->

---

## 💻 阶段 3：开发与验证 (`coder`) — YYYY-MM-DDTHH:mm:ss+08:00

### 3.0 执行通道记录 (Execution Channel)
- [ ] **角色契约**: `prompts/coder.md` 已加载并遵循
- [ ] **执行通道**: CLI / Main Agent / subagent
- [ ] **偏离处理**: N/A；若规范通道无法执行，必须先复核现场状态（Git/TASK/进程/已有产出），再尝试修复；无法修复时停止并报告，等待人工处理

### 3.1 任务进度追踪 (Progress)
(子任务进度列表)

### 3.2 🧪 证据链 (Evidence Chain)
- [ ] **AC-1**:
- [ ] **AC-2**:
- [ ] **自动化测试结果**:
- [ ] **Lint 检查结果**:
- [ ] **跨环境验证**（如适用）:

---

## 🔵 阶段 4：代码审查 (`reviewer`) — YYYY-MM-DDTHH:mm:ss+08:00

### 4.0 执行通道记录 (Execution Channel)
- [ ] **角色契约**: `prompts/reviewer.md` 已加载并遵循 / L1 跳过填写 N/A
- [ ] **执行通道**: CLI / subagent / N/A
- [ ] **偏离处理**: N/A；若规范通道无法执行，必须先复核现场状态（Git/TASK/进程/已有产出），再尝试修复；无法修复时停止并报告，等待人工处理

### 4.1 代码评审 (Code Review Feedback)
- [ ] **核心变更点**:
- [ ] **评审反馈**:
- [ ] **遗留问题与技术债**: (写入 5.1 节)

<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 5。 -->

---

## 🧠 阶段 5：收尾与归档 (`closer`) — YYYY-MM-DDTHH:mm:ss+08:00

### 5.0 执行通道记录 (Execution Channel)
- [ ] **角色契约**: `prompts/closer.md` 已加载并遵循
- [ ] **执行通道**: CLI / Main Agent / subagent
- [ ] **偏离处理**: N/A；若规范通道无法执行，必须先复核现场状态（Git/TASK/进程/已有产出），再尝试修复；无法修复时停止并报告，等待人工处理

### 5.1 遗留问题与技术债 (Technical Debt)
(如有，记录并确认已登记)

### 5.2 核心决策与避坑 (Lessons Learned)
(关键架构思考与避坑指南)

### 5.3 🏁 任务结算三问 (Final Three Questions)
1. **🚢 规则同步**：是否涉及业务规则永久性变更？ [ ] 是 / [ ] 否
2. **📜 决策存证**：是否有关键技术取舍？ [ ] 是 / [ ] 否
3. **🛡️ 标准沉淀**：是否有通用代码陷阱/最佳实践？ [ ] 是 / [ ] 否

### 5.4 自检清单 (Final Checklist)
- [ ] 遗留问题/技术债已登记
- [ ] 代码实现逻辑完整
- [ ] 测试覆盖核心分支
- [ ] CHANGELOG 已按 `docs/guides/changelog-standards.md` 更新
- [ ] 相关文档已同步
- [ ] 版本号已更新
- [ ] 任务现场已清理，完成任务已归档到 `docs/project/tasks/T-XXX.md`
- [ ] Git 已提交
- [ ] 使用模型已记录在元数据中
