# 🚀 任务执行台 (Task Control Plane)

> **核心原则**：本文件是任务执行期间的"单一事实来源"。

---

## 📌 任务元数据 (Metadata)

- **任务编号 (ID)**: T-XXX
- **任务描述**: (待填入)
- **风险等级**: L1 / L2 / L3（L0 不创建 TASK 文档）
- **当前阶段**: init | plan-review | dev | code-review | close
- **项目根目录**: (绝对路径，如 D:\Dev\Code\your-project)
- **功能分支**: (分支名，如 feat/t-001-add-auth 或 docs/t-001-update-docs)
- **执行通道配置**: docs/guides/execution-channels.md
- **使用模型**: [填写实际使用的模型]
- **工具会话 ID**: [自动填写，如 Antigravity 会话 ID / Codex thread]
- **效能数据**:
  - 开始时间: (自动填入，格式：YYYY-MM-DDTHH:mm:ss+08:00)
  - 结束时间: (任务完结时填入，格式：YYYY-MM-DDTHH:mm:ss+08:00)
  - 返工次数: 0
  - AI 代码生成占比: ~?%

---

## 🛠️ 阶段 1：初始化 (`planner`) — YYYY-MM-DDTHH:mm:ss+08:00

### 1.1 任务背景 (Context)
(此处填入任务背景)

### 1.2 思考与决策 (Thinking & Decision)
(此处填入分析思考过程)

### 1.3 实施计划 (Execution Plan)
(在此处填写详细的原子步骤计划)

### 1.3a 验收标准 (Acceptance Criteria) — L2/L3 必填，L1 可略
> 列出人类可验证的具体行为。每条标准应可通过运行命令、查看输出或操作界面来客观验证。

- [ ] 标准 1: (如 "运行 `pytest tests/` 全部通过")
- [ ] 标准 2: (如 "页面加载时间 < 2s")
- [ ] 标准 3: ...

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

### 2.1 评审意见 (Review Feedback)
- [ ] **评审意见**: (由 reviewer 填写)
- [ ] **修正记录**: (如有修改)

<!-- 盲审按“执行通道配置”调用 CLI 或 subagent；Prompt 必须提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE，并要求 reviewer 写回本节。 -->
<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 3。 -->

---

## 💻 阶段 3：开发与验证 (`coder`) — YYYY-MM-DDTHH:mm:ss+08:00

### 3.1 任务进度追踪 (Progress)
(子任务进度列表)

### 3.2 🧪 证据链 (Evidence Chain)
- [ ] **自动化测试结果**:
- [ ] **Lint 检查结果**:
- [ ] **跨环境验证**（如适用）:

---

## 🔵 阶段 4：代码审查 (`reviewer`) — YYYY-MM-DDTHH:mm:ss+08:00

### 4.1 代码评审 (Code Review Feedback)
- [ ] **核心变更点**:
- [ ] **评审反馈**:
- [ ] **遗留问题与技术债**: (写入 5.1 节)

<!-- 门禁：若本节未出现 OK/WARN/BLOCK 等有效审查报告，流程不得进入阶段 5。 -->

---

## 🧠 阶段 5：收尾与归档 (`closer`) — YYYY-MM-DDTHH:mm:ss+08:00

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
- [ ] CHANGELOG 已更新
- [ ] 相关文档已同步
- [ ] 版本号已更新
- [ ] 任务现场已清理
- [ ] Git 已提交
- [ ] 使用模型已记录在元数据中
