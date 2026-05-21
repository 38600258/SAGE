# 架构总览

> 本文件提供整个 Hermes Kanban 仓库的顶层地图。

## 1. 系统架构

```
人类发需求 → Orchestrator 创建任务链 → Dispatcher 自动调度 → Workers 独立执行 → 仅在关键点暂停等人
                                          │
                                          ├── 按 assignee 分配到不同 Profile 进程
                                          ├── 按 parents 依赖链控制执行顺序
                                          └── 按 risk_level 决定是否需要人工门禁
```

## 2. 目录结构与职责

| 路径 | 类型 | 职责 |
|------|------|------|
| `AGENTS.md` | 导航 | 智能体入口，~60行目录 |
| `ARCHITECTURE.md` | 文档 | 本文件，顶层架构地图 |
| `README.md` | 文档 | 人类入口，快速开始指南 |
| `docs/` | 知识库 | 分层的仓库内知识存储 |
| `docs/design-docs/` | 设计 | 核心信念、设计文档索引 |
| `docs/exec-plans/` | 计划 | 执行计划（活跃/已完成/技术债） |
| `docs/references/` | 参考 | API 速查、外部依赖文档 |
| `docs/QUALITY_SCORE.md` | 质量 | 模块级质量评分和差距追踪 |
| `scripts/` | 工具 | 验证脚本、配置脚本、Worker 桥接 |
| `skills/` | 技能 | 各角色 Worker 的 SKILL.md 定义 |
| `templates/` | 模板 | 任务文档和执行计划模板 |

## 3. 依赖流与层次

```
                   ┌─────────────────┐
                   │   飞书 / 企微    │  (消息入口)
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │  Gateway (coder) │  WebSocket 长连接
                   │  + Dispatcher    │  任务调度引擎
                   └────────┬────────┘
                            │
              ┌─────────────┼──────────────┐
              │             │              │
    ┌─────────▼──────┐ ┌───▼────┐ ┌───────▼────────┐
    │ Hermes Workers │ │Reviewer│ │ Gemini CLI     │
    │ (coder profile)│ │(review │ │ (外部 Worker)  │
    │                │ │profile)│ │                │
    │ - planner      │ │        │ │ gemini_worker  │
    │ - coder        │ │        │ │ .sh 桥接脚本   │
    │ - closer       │ │        │ │                │
    │ - doc-gardener │ │        │ │                │
    └────────────────┘ └────────┘ └────────────────┘
              │             │              │
              └─────────────┼──────────────┘
                            │
                   ┌────────▼────────┐
                   │  Kanban DB      │  SQLite 持久化
                   │  ~/.hermes/     │  任务状态追踪
                   │  kanban.db      │
                   └─────────────────┘
```

## 4. 数据流

1. **任务创建**: Orchestrator → `kanban_create()` → Kanban DB
2. **任务调度**: Dispatcher 轮询 → 检查 `parents` 依赖 → 状态提升 `todo → ready`
3. **Worker 执行**: 独立系统进程 → `kanban_show()` 读取上下文 → 执行 → `kanban_complete()` 或 `kanban_block()`
4. **链式反应**: 上游 `done` → 下游 `ready` → 下一个 Worker 自动启动

## 5. 模块质量概览

详见 [docs/QUALITY_SCORE.md](docs/QUALITY_SCORE.md)

## 6. 已知局限

- 无 git worktree 支持（并行任务可能冲突）
- Gemini Worker 缺少心跳和超时控制
- 文档覆盖率不足，多数知识仍在人脑中
- 无自动化 CI/CD 验证（依赖人工部署）
