# 模型选择指南（Model Selection Guide）

> T2 级规范文档 | 状态：[CURRENT]
> 本文档定义 SAGE 工作流的模型/执行通道选择原则。
> 导航入口 → [AGENTS.md](../entry/AGENTS.md) | 执行通道 → [execution-channels.md](execution-channels.md)

---

## 一、核心原则

**模型选择的本质是推理深度、隔离性、速度与成本的权衡。**

- 计划和审查需要深度推理，错误的计划或遗漏的缺陷代价远高于模型成本。
- 编码执行需要速度和上下文长度，在已审查计划约束下快速实现。
- 文档维护需要效率，通常是结构化整理，无需深度推理。
- 盲审优先追求上下文隔离和模型隔离，执行命令以 [execution-channels.md](execution-channels.md) 为准。

---

## 二、角色-能力选择矩阵

| 角色 | 推荐能力 | 选择方式 | 推理需求 | 备注 |
|------|---------|---------|---------|------|
| **Orchestrator** | 强推理模型 | 工具 UI / 主会话模型 | 高 | 需求解构、风险分级、任务拆解 |
| **Planner** | 强推理模型 | 工具 UI / 主会话模型 | 高 | 原子步骤设计、影响分析 |
| **Reviewer** | 独立 reviewer 载体，最好不同模型族 | 执行通道配置 | 高 | 盲审隔离，优先原生 subagent，CLI fallback |
| **Coder** | 快速稳定的编码模型 | 执行通道配置或主会话 | 中 | 按已审查计划执行，优先原生 subagent |
| **Closer** | 快速稳定的整理模型 | 执行通道配置或主会话 | 低 | 结构化收尾和归档，优先原生 subagent |
| **Doc-gardener** | 低成本文档模型 | 定时任务或主会话 | 低 | 文档扫描与更新 |

---

## 三、风险级别覆盖规则

| 风险级别 | 覆盖规则 | 理由 |
|---------|---------|------|
| **L1 轻量** | 可使用快速模型全流程，跳过阶段二/四盲审 | 纯文档、测试、重构风险较低 |
| **L2 标准** | 按角色矩阵分配，必须执行盲审 | 默认策略，平衡质量与成本 |
| **L3 高危** | 全流程使用强推理模型，并在每阶段结束等待人工确认 | 数据库/API/部署/敏感数据变更风险高 |

---

## 四、执行通道

reviewer / coder / closer 的具体 subagent 派发模板和 CLI fallback 模板不在本文维护，统一放在 [execution-channels.md](execution-channels.md)。更换执行载体时优先只修改该文件，保留以下不变量：

- L0 不调用 CLI/subagent，由 Main Agent 直接执行
- L1 及以上 subagent/CLI 必须显式接收 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE`
- 除必要定位信息外，调度信息从 TASK 元数据读取，不传递 Main Agent 主线程讨论历史
- coder/closer 只能处理冻结 TASK 范围
- 成功标准看 TASK 文档和 Git 状态，不只看 stdout、退出码或 subagent 回复


### 4.1 模型目录与载体提示边界

`base_instructions`、`model_messages`、subagent 配置中的 `developer_instructions` 属于执行载体层，只描述模型身份、工具环境和通用行为。角色职责必须从 `ROLE_PROMPT` 指向的 `prompts/*.md` 读取，任务事实必须从 `TASK_PATH` 读取，调度事实必须从 TASK 元数据读取。

- 不要在 model catalog 或 subagent 配置中复制 reviewer/coder/closer 的完整职责规则。
- 不要在 model catalog 中写仓库路径、任务编号、阶段或输出章节。
- 若工具链不能确认模板变量会被渲染，生成 catalog 时应写入已渲染的 `instructions_template`。
- 模型身份与真实路由以 provider/shim 请求日志为准，模型自报仅作参考。
- reviewer/coder/closer 的阶段默认模型写在 adapter `models.<phase>.id`，不写在角色 prompt。
- 原生 API 支持请求级模型时使用 `subagent_binding=request`；模型固定在命名 Agent 注册时使用 `agent-registration`，并同步宿主注册配置。
- CLI 使用 `cli_binding=command-argument`，通过 Dispatcher 的 `{model}` 命令占位符传递；`prepare --model <id>` 可覆盖允许覆盖的阶段默认值。

### 4.2 审查报告回写

Reviewer 执行载体应直接写回 TASK 文档：计划盲审写入 2.1 节，代码盲审写入 4.1 节。若工具只返回报告文本，则由 Main Agent 捕获后写入对应章节。

| 判定 | 动作 |
|------|------|
| OK | 流转到下一阶段 |
| WARN | 记录建议后可流转 |
| BLOCK | 回到上一阶段修正并重新审查 |

`scripts/sage_linter.py` 会对 L2/L3 任务执行盲审结果完整性检查；检查失败时必须补齐审查报告或重新触发 reviewer。

---

## 五、工具适配示例

| 工具 | 主流程 | 盲审首选 | 盲审备选 | 覆盖文件 |
|------|--------|----------|----------|----------|
| Antigravity | UI 主 agent + subagent/CLI | 执行通道配置 | reviewer CLI | `AGENTS.md` |
| Codex app | Codex 主会话 + SAGE subagent | 执行通道配置 | CLI fallback | `AGENTS.md` |
| OMP | 主会话 + 自定义 agent（agent-registration，provision 生成 .omp/agents/sage-*.md） | native_subagent（sage_reviewer via @sage_reviewer / sage_coder、sage_closer via @sage_coder、@sage_closer） | generic-tool injected | `AGENTS.md` + `omp.json` + `.omp/` |

---

## 六、效能数据收集

### 6.1 TASK 元数据中记录模型

```markdown
- **模型配置**:
  - 初始化/计划: 强推理模型（填写实际模型名）
  - 盲审: reviewer subagent 或 CLI fallback（填写实际通道 / 模型名）
  - 编码/收尾: coder/closer subagent、CLI fallback 或主会话模型（填写实际通道 / 模型名）
- **效能数据**:
  - 返工次数: 1
  - 盲审阻塞次数: 0
  - AI 代码生成占比: ~85%
```

### 6.2 收集维度与趋势分析

| 维度 | 记录内容 | 用途 |
|------|---------|------|
| **模型组合** | 各阶段使用的具体模型 | 分析最优模型组合 |
| **返工次数** | 盲审打回导致的返工 | 评估计划/编码质量 |
| **盲审阻塞次数** | 阻塞级问题数量 | 评估模型的缺陷检出能力 |
| **总耗时** | 各阶段的时间消耗 | 评估模型速度对效率的影响 |

每完成 10 个任务后回顾：L1 返工率是否低于 5%？盲审阻塞是否有效发现真实缺陷？L3 强推理成本是否可接受？

---

## 七、成本考量

| 层级 | 策略 | 适用场景 |
|------|------|---------|
| **节约模式** | 快速模型全流程 | L1 任务、原型验证、文档维护 |
| **均衡模式** | 按角色矩阵分配 | L2 标准任务（默认） |
| **质量优先** | 强推理模型全流程 | L3 高危任务、核心架构变更 |

**优化建议**：
1. **盲审不可省**：盲审成本远低于生产事故修复成本。
2. **编码可用快速模型**：在已审查计划约束下，快速模型通常足够。
3. **L1 可轻量化**：纯文档、测试、重构任务风险较低。
4. **不确定时按 L2 处理**：宁可多一次盲审，也不要跳过质量门控。

