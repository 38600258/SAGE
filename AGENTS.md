# AGENTS.md — 智能体入口

> 本文件是智能体的 T1 导航入口。保持 ≤50 行。只做地图，不做百科。
> **SAGE** = Steer, Agent Goes Execute | 人类掌舵，智能体执行

## 仓库概述
本仓库定义了一套**工具无关**的智能体优先开发工作流。
核心方法论：人类掌舵，智能体执行。

## 快速导航

**方法论与架构**
- 开发方法论 → [智能体优先的自主编程方法论.md](智能体优先的自主编程方法论.md)
- 项目管理方法论 → [智能体优先的自主项目管理方法论.md](智能体优先的自主项目管理方法论.md)
- 架构总览 → [ARCHITECTURE.md](ARCHITECTURE.md)
- 变更日志 → [CHANGELOG.md](CHANGELOG.md)

**规范（T2 按需加载）**
- 开发规范 → [docs/guides/development-standards.md](docs/guides/development-standards.md)
- 设计原则 → [docs/guides/core-beliefs.md](docs/guides/core-beliefs.md)

**项目状态**
- 项目看板 → [docs/project/PROJECT_BOARD.md](docs/project/PROJECT_BOARD.md)
- 模式库 → [docs/project/KNOWN_PATTERNS.md](docs/project/KNOWN_PATTERNS.md)
- 决策日志 → [docs/project/DECISION_LOG.md](docs/project/DECISION_LOG.md)
- 交接指南 → [docs/project/HANDOVER-GUIDE.md](docs/project/HANDOVER-GUIDE.md)

**模板（物理复制，禁止重建）**
- 任务模板 → [templates/TASK-TEMPLATE.md](templates/TASK-TEMPLATE.md)
- ADR 模板 → [templates/ADR-template.md](templates/ADR-template.md)
- PRD 模板 → [templates/PRD-template.md](templates/PRD-template.md)

**角色提示词（T2 按需加载）**
- 编排器 → [prompts/orchestrator.md](prompts/orchestrator.md)
- 计划员 → [prompts/planner.md](prompts/planner.md)
- 编码员 → [prompts/coder.md](prompts/coder.md)
- 审查员 → [prompts/reviewer.md](prompts/reviewer.md)
- 收尾员 → [prompts/closer.md](prompts/closer.md)
- 文档管家 → [prompts/doc-gardener.md](prompts/doc-gardener.md)

**参考资料（T3 按需加载）**
- 参考文档 → [docs/references/](docs/references/)
- 归档任务 → [docs/architecture/tasks/](docs/architecture/tasks/)

## 六阶段流水线
```
初始化 → 计划盲审 → 编码测试 → 代码盲审 → 收尾归档 → 生产部署
          [L1跳过]              [L1跳过]              [人类触发]
```

## 不可违反的约束
1. 部署阶段必须人类授权，智能体严禁私自触发
2. L3 任务每阶段结束须人工确认后方可流转
3. 任务文档必须通过物理复制模板创建，禁止内存重建
4. 收尾阶段严禁新增功能（scope creep）
5. 合并主干的权力永远属于人类
6. 所有知识沉淀到仓库，不留在聊天或人脑中

- 所有分析、输出、注释使用**中文**
- 任务文档是"单一事实来源"
- 不确定风险等级时，一律按 L2 处理

## 验证入口

工作流的所有不变量规则均由本地静态检查器 [sage_linter.py](scripts/sage_linter.py) 强制执行：

```bash
# 1. 运行一键全量工作流校验（检查分支隔离、模板守护、日志变更等）
python scripts/sage_linter.py --all

# 2. 检查特定活跃任务的结构完整性与范围锁定
python scripts/sage_linter.py --check-task docs/project/ACTIVE_TASK_T-XXX.md
```
