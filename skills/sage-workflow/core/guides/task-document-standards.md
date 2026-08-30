# 任务文档规范 (Task Document Standards)

> T2 级硬规则 | 状态：[CURRENT]
> 入口路由 → [AGENTS.md](../entry/AGENTS.md) | 总览 → [development-standards.md](development-standards.md)

---

## 一、路径规则

| 状态 | 路径 |
|------|------|
| 活跃任务 | `docs/project/ACTIVE_TASK_T-XXX.md` |
| 已完成任务归档 | `docs/project/tasks/T-XXX.md` |
| 任务模板 | `templates/TASK-TEMPLATE.md` |

L1 及以上必须通过物理复制模板创建活跃任务文档：

```bash
cp templates/TASK-TEMPLATE.md docs/project/ACTIVE_TASK_T-XXX.md
```

禁止在内存中重建模板结构。

---

## 二、阶段写入边界

| 阶段 | 写入章节 |
|------|----------|
| 初始化 | 1.0~1.5 |
| 计划盲审 | 2.x |
| 编码实现 | 3.x |
| 代码盲审 | 4.x |
| 收尾归档 | 5.x |

约束：

- TASK 是 L1 及以上跨阶段、跨会话、跨智能体的唯一事实来源。
- TASK 是可证伪的意图契约：验收标准必须能映射到自动化命令或明确人工验证步骤；TASK 不应退化为不可验证 PRD，也不应扩张成伪代码级实现蓝图。
- 阶段执行者不得重写已经冻结的上游章节。
- **计划放行（人类掌舵点，T-018 起）**：L1/L2 任务未获用户明确「放行」（元数据「计划放行」= 已放行），不得将当前阶段置为 dev 或派发 coder；放行请求五要素与处置三态见 `planner.md` 第 8 节。元数据默认值「待放行」是**合法初始值**（与「当前阶段」模板默认行不同，后者必须随任务推进更新）；代理不得代填放行记录。
- 每个已到达阶段必须完成 `X.0 执行通道记录`。
- 失败恢复前必须先复核 Git/TASK/进程/已有产出状态，并写入偏离处理。
- 先例优先：填写任何章节前，先检索 `docs/project/tasks/` 归档任务同章节既定格式并沿用，禁止自创未经验证的格式（T-011 复盘：AC 占位符与可写清单子列表两轮格式试错返工，均因未先查先例）。
- 改码前先登记：任何为解锁流程而先行修改工具代码的行为，必须在动码前登记 TASK 偏离处理并在 1.3/AC 显式承接，禁止先改后披露（T-011 复盘：init 期先行改码未披露，被盲审 git 取证揭穿，返工一轮）。

---

## 三、归档规则

收尾完成并提交后，将活跃任务移动到归档路径：

```bash
git mv docs/project/ACTIVE_TASK_T-XXX.md docs/project/tasks/T-XXX.md
```

归档后：

- `docs/project/PROJECT_BOARD.md` 的 Done 表必须指向归档文件。
- 根目录不得保留 `ACTIVE_TASK_T-*.md`。
- `docs/project/` 下不得保留已完成任务的活跃文件。

---

## 四、质量门禁

- 单任务校验：`uv run python scripts/sage_linter.py --check-task docs/project/ACTIVE_TASK_T-XXX.md`
- 全量校验：`uv run python scripts/sage_linter.py --all`
- 在 `main` 上做合并后验证时，必须显式使用受保护分支放行参数：`--allow-protected-branch`。

---

## 五、收尾自检

- [ ] 活跃任务路径正确。
- [ ] 任务文档由模板物理复制创建。
- [ ] 当前阶段对应章节已完成。
- [ ] 完成任务已归档到 `docs/project/tasks/T-XXX.md`。
- [ ] 项目看板 Done 表已指向归档路径。
