# Hermes Kanban API 速查

> 供 Worker 技能包快速查阅 Kanban 工具的调用方式。
> 最后更新: 2026-05-20

## 任务生命周期状态

```
triage → todo → ready → in_progress → done
                  ↓
               blocked (需人工介入)
```

- `triage`: 分诊队列，待编排器处理
- `todo`: 已创建但依赖未满足
- `ready`: 依赖已满足，等待 Worker 拾取
- `in_progress`: Worker 正在执行
- `blocked`: 执行受阻，需人工介入
- `done`: 已完成

## 核心工具

### kanban_create

创建新任务。

```
kanban_create(
  title="任务标题",
  assignee="planner|coder|reviewer|closer|gemini",
  tenant="项目名",                    # 命名空间隔离
  workspace="dir:/path/to/project",   # 项目目录
  body="任务正文详情",                 # 可选
  parents=["t_123"],                  # 依赖的上游任务ID列表
  priority=2,                         # 1(最高) - 5(最低)
  triage=true                         # 进入分诊队列而非直接创建
)
```

### kanban_show

读取当前任务信息（标题、正文、父任务交接信息）。

```
kanban_show()  # Worker 启动时调用，获取任务上下文
```

返回:
- `title`: 任务标题
- `body`: 任务正文
- `metadata`: 父任务的交接数据（summary + metadata）
- `workspace`: 项目目录路径

### kanban_complete

标记当前任务为完成。

```
kanban_complete(
  summary="完成摘要（供下游 Worker 读取）",
  metadata={                          # 传递给下游 Worker 的结构化数据
    "task_doc": "相对路径",
    "branch": "feature/xxx",
    "changed_files": ["file1.py"],
    "tests_passed": 5,
    "lint_clean": true
  }
)
```

### kanban_block

标记当前任务为阻塞。

```
kanban_block(
  reason="具体原因描述"               # 会通知人类
)
```

### kanban_heartbeat

发送心跳，防止 Dispatcher 判定 Worker 超时。

```
kanban_heartbeat(
  note="正在分析项目结构..."           # 进度说明
)
```

建议每 2-3 分钟调用一次，尤其在长时间操作期间。

## 环境变量

| 变量 | 说明 |
|------|------|
| `$HERMES_KANBAN_WORKSPACE` | 当前任务关联的项目目录路径 |
| `$HERMES_KANBAN_TENANT` | 当前任务的租户名称 |
| `$HERMES_KANBAN_TASK_ID` | 当前任务的 ID |

## 常见模式

### L3 门禁模式
```
if risk_level == "L3":
    kanban_block(reason="[L3 门禁] 阶段已完成。请人工确认后手动 complete。")
else:
    kanban_complete(summary="...", metadata={...})
```

### 自动重试闭环
```
for attempt in range(3):
    result = run_tests()
    if result.passed:
        break
    fix_issues(result.errors)
else:
    kanban_block(reason="测试持续失败: {描述}")
```
