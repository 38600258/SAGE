# Antigravity 2.0 本地看板自动化工作流规范

> 基于项目的「开发控制面(Task Control Plane)」与 1-6 阶段物理防错开发流水线。
> 本项目将 `kanban/workflows/` 下的手动流程规范升级为由 Antigravity 2.0 驱动的自动化运作体系。

---

## 📋 1-6 阶段工作流总览

流水线严格遵循以下阶段流转。除特殊情况外，AI 必须逐个阶段依次执行，严禁跨阶段或合并阶段：

```
/1inittask (初始化) ──► /2review (计划审查，强模型盲审) ──► /3dev (编码与自检)
      │
      ▼
/4codereview (代码审查，强模型盲审) ──► /5finish (收尾归档) ──► /6deploy (生产部署，手动授权)
```

---

## 🛠️ 自动化流程与 Antigravity 2.0 机制融合

我们将在项目根目录下建立 `dev/` 目录，以承接整套看板与规范，并开发 `dev/scripts/workflow.py` 作为流程核心控制引擎。

### 阶段一：/1inittask (初始化与设计)
1. **环境对齐**：主代理确保当前位于 `dev` 分支。
2. **需求澄清 (禁止脑补)**：主代理开启苏格拉底式逐个提问（一次只问一个问题，多用选择题），探明需求边界；提出 2-3 种方案对比及优劣权衡；分段向人类呈现设计并分段确认。
3. **任务编号**：设计通过且需求质量自检（目标/约束/范围/可测试性，总分>=14分）通过后，在 `dev/docs/project/PROJECT_BOARD.md` 中登记新任务，获得任务编号 `T-XXX`。
4. **物理复制与防覆盖**：主代理调用 `python dev/scripts/workflow.py init T-XXX "任务名称"`。
   - 脚本会自动将 `dev/templates/TASK-TEMPLATE.md` 物理拷贝为 `dev/docs/project/ACTIVE_TASK_T-XXX.md`。
   - **防覆盖拦截**：脚本将读取已拷贝的文件并进行物理行数验证（行数必须 >= 120 且含收尾标题），如不通过直接报错拦截，**从代码层消灭 AI 用 write_to_file 误覆盖模板结构的致命陷阱**。
5. **创建分支**：脚本基于 `dev` 分支自动创建并切换到对应的功能分支 `feature/T-XXX-xxx`。
6. **知识蒸馏汇报**：输出包括 [业务约束]、[技术约束]、[数据影响] 的摘要，并提问：“初始化完成，是否启动子代理计划评审（/2review）？”

### 阶段二：/2review (计划评审)
*   **强制盲审红线**：根据工作流规范，计划评审必须由盲审角色进行，主代理不得自审。
*   **2.0 子代理实现**：主代理通过 `define_subagent` 派生独立的 `Reviewer` 子代理。
*   *   Reviewer 读取 `ACTIVE_TASK_T-XXX.md` 的 1.1~1.5 节并加载上下文，从逻辑断层、可写范围、副作用、测试覆盖等维度进行红队攻击评审。
*   *   Reviewer 将评审意见写入 2.1 节，标记 ✅/⚠️/🛑 三级反馈并退出。
*   *   系统通过 Reactive Wakeup 自动唤醒主代理。主代理读取 2.1 节，若含 🛑 阻塞则回滚到阶段一重新任务拆解；若仅含 ⚠️ 建议则直通至阶段三。

### 阶段三：/3dev (编码与自检验证)
*   **会话卫生**：强烈建议人类在 Coder 开发此阶段时开启新会话，避免初始化上下文导致 AI 记忆衰减。
*   **隔离开发 (`Workspace: 'branch'`)**：主代理派生 `Coder` 子代理，并配置工作区模式为 `branch`。子代理在隔离的功能分支上安心编码。
*   **Red-Green 循环与证据自动填入**：
    1. **Red Phase**：编写测试，运行 `python dev/scripts/workflow.py run-tests T-XXX`，脚本会自动执行 pytest 并捕获测试失败输出，格式化后自动填入 `ACTIVE_TASK_T-XXX.md` 的 3.2 证据链。
    2. **Green Phase**：编写实现，再次运行 `workflow.py run-tests` 捕获测试通过（PASSED）和 Ruff 静态检查清洁的证据，自动更新任务控制文件中的证据栏。
    3. **多环境/黑盒验证**：在 WSL 测试环境运行兼容测试并保留日志。

### 阶段四：/4codereview (代码审查)
*   **强制盲审红线**：代码审查必须由盲审角色执行。
*   **2.0 子代理实现**：主代理派生 `Reviewer` 子代理。
*   *   Reviewer 执行 `git diff`，从正确性、健壮性、一致性、性能、安全性、证据真实性等 8 个维度盲审变动。
*   *   Reviewer 将评审反馈写入 4.1 节，并将识别到的技术债/TODO 逐条预填到 5.1 遗留问题节中。
*   *   如发现 🛑 阻塞问题，主代理调用 `ask_question` 询问人类是打回修改还是直接放行。

### 阶段五：/5finish (收尾与归档)
主代理调用 `python dev/scripts/workflow.py finish T-XXX` 执行最终收尾：
1. **技术债搬运**：脚本自动将 5.1 节预填的技术债提取出来，逐条追加登记到看板 `PROJECT_BOARD.md` 的待开发列表中。
2. **模式库与三问结算**：将避坑经验提取并追加至 `KNOWN_PATTERNS.md`，同步升版并更新开发规范文件。
3. **版本号升级与 CHANGELOG**：脚本自动根据变动大小升级版本号，并为 `CHANGELOG.md` 自动创建新节点写入变更明细。
4. **归档文件**：脚本自动将 `ACTIVE_TASK_T-XXX.md` 剥离前缀并以 kebab-case 风格移动归档至 `dev/docs/architecture/tasks/t-xxx.md`。
5. **提交并保留分支**：在功能分支上暂存并 commit 所有变更（含归档文件）。**⚠️ 严禁 AI 自动合并分支**，将功能分支保留在本地，向人类汇报任务总结，等待人类手动进行最终合并审查。

### 阶段六：/6deploy (生产部署)
*   **授权卡点**：AI 绝不允许私自执行发版。
1. 主代理收到人类明确的祈使句发版命令后，切换到 `main` 分支执行 `git merge dev --no-ff`。
2. 运行最后一次 Ruff 与 Pytest 检查，确认防线未破。
3. 运行部署脚本 `.\dev\scripts\deploy.ps1 -Target prod`。
4. 数据库升级：如涉及 `schema.sql` 变更，主代理向人类呈现增量 SQL，在获取增量授权后，通过 SSH 在远端物理备份数据库后执行迁移更新，并验证完整性。
5. 生产端拨测：运行健康检查探针确认正常。
6. 提示人类发送 `/new` 重载引擎。切换回本地 `dev` 分支，承接下一任务。

---

## 📁 规划的目录布局

```
dev/
├── agents/                         # 2.0 子代理定义 (reviewer.md, closer.md)
├── templates/
│   └── TASK-TEMPLATE.md            # 任务控制面 (Task Control Plane) 模板
├── scripts/
│   ├── workflow.py                 # 看板及流转核心控制脚本 (物理防覆盖/测试捕获/自动升版)
│   ├── validate_task_file.py       # 格式结构验证脚本
│   └── validate_docs_freshness.py  # 周期扫描文档新鲜度脚本
└── docs/
    ├── guides/
    │   └── development-standards.md # 开发规范
    ├── project/
    │   ├── PROJECT_BOARD.md        # 项目主看板 (代替 SQLite DB)
    │   ├── HANDOVER-GUIDE.md       # 交接指南
    │   └── KNOWN_PATTERNS.md       # 模式库 (沉淀避坑与最佳实践)
    └── architecture/
        ├── CAPABILITY_SNAPSHOT.md  # 系统能力全景图
        └── tasks/                  # 历史已归档任务控制面归档区
```
