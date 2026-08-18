# 变更日志 (Changelog)

> 只增不改。按版本号组织。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。
> 注：历史条目原本只记录日期，迁移到单行标题格式时用 `00:00:00` 作为回溯补齐时间。


## [1.1.1] 📚 Docs SAGE 1.0 发布前内容卫生 (T-010) - 2026-08-18 07:27:00
- 两份方法论文档去工具化：移除全部 Antigravity 2.0 专属工具映射（39 处），改为工具无关通用表述，宿主能力要求指向 adapters/ 与执行通道指南。
- 校验项数量对齐：sage_linter.py 输出编号统一为 [X/15]，docstring 与方法论数量表述同步为 15 项。
- 模式库清理：删除 8 条演示 SaaS 项目残留条目（BP-001~003、AP-001~003、DP-001~002），加删除说明。
- CHANGELOG 回溯补正：为 0.1.0/0.2.0 演示条目和 1.0.0 时间戳归属追加补正标注。
- core/VERSION baseline_commit 更新至 7589a91（T-008 最终提交）。
- README 新增"适用场景与流程重量"节，明确目标用户画像。

## [1.1.0] ✨ Feature 注入式子代理通道与 doctor/provision 通道治理 (T-009) - 2026-08-16 21:40:00
- 为 Dispatcher 增加第二等执行通道 `injected_subagent`（宿主注入式子代理），解决不同宿主子代理设置方式不一致导致的派发阻塞：
  - adapter 可声明 `injected_subagent`（supported/isolation/requires_authorization/agent_types）；`auto` 通道选择优先级为 subagent > injected > cli。
  - `prepare --channel injected` 生成 `spawn_subagent` 信封，并在 `injection` 字段记录隔离等级与授权要求；宿主在派发时注入 ROLE_PROMPT，不依赖命名注册。
  - 从更高优先级通道降级 CLI 必须提供理由与授权，规则由原生通道扩展到注入式通道。
- 新增 `doctor` 子命令：逐通道探测可用性（原生=声明、注入式=声明+agent_types 校验、CLI=只探测可执行文件不执行命令），输出推荐通道；建议在 Init 阶段前移探测，避免任务到门禁才发现通道不可用。
- 新增 `provision` 子命令：按宿主生成 agent 注册文件——`toml-directory`（Codex 全局 TOML，模型取自 codex.json）或 `markdown-agents-directory`（项目内 agents 目录，如 Claude Code），默认不覆盖已存在文件，注册生效以宿主实际派发为准。
- `generic-tool.json` 启用注入式通道（isolation=context-fresh），明确每次派发前需人工授权并在 TASK 证据链记录隔离等级；跨宿主审查（执行方与审查方为不同宿主/模型家族）视为合法独立审查通道，禁止伪造隔离等级。
- 新增 6 项 Dispatcher 单测：注入式信封隔离记录、未声明通道阻断、doctor 通道探测与 CLI 无命令探测、provision 两种模板生成与跳过。
- 说明：本变更因工作流运行时阻塞经人工授权以轻量方式落地，未创建 TASK 文档；T-008 代码盲审将使用本通道解除阻塞。

## [1.0.0] ✨ Feature 发布 SAGE workflow skill 默认发行版 (T-008) - 2026-06-01 17:10:00

> ⚠️ **回溯补正（T-010, 2026-08-18）**：本条目标题时间戳为 2026-06-01，但内容包含 2026-07-23 追加的运行时派发与模型路由范围。按 changelog-standards"只增不改"原则不回改历史标题；此处标注实际交付时间线。07-23 追加范围按 BP-005 本应独立为 1.1.0，因与 1.0.0 同属 T-008 任务交付物且已在同一提交中落库，维持当前归属并在本标注中说明。
- 将 SAGE 工作流封装为 `skills/sage-workflow/` 默认发行版：
  - 内置 `core/entry/`、`core/prompts/`、`core/templates/`、`core/guides/` 和 `core/methodology/`，支持新项目 Standalone/bootstrap。
  - 新增 `core/VERSION` 记录 `1.0.0`、基线提交和同步锚点，降低后续迁移漂移风险。
  - 新增 Codex、CLI、通用工具 adapter 和 path registry，明确多工具接入边界。
- 更新 SAGE 入口、执行通道和方法论文档，将旧的“skill 只能引用不复制”口径升级为“skill 内置默认发行版 + 项目覆盖优先”。
- 更新 README 与架构总览，明确 SAGE 1.0 的 workflow skill 产品形态和权威来源规则。
- 统一 skill 新增文档语言口径，将 `SKILL.md`、`adapters/` 与 `references/` 说明改为中文，仅保留必要英文技术标识。
- 同步 另一真实项目 `3cde17a` 的 SAGE 可证伪契约改造：TASK 模板引入 `AC-ID`、`[auto]/[manual]`、验证方式与证据位置，角色契约和 linter 增加验收映射校验。
- 清理旧 SaaS 示例任务归档与看板示例数据，统一任务归档路径到 `docs/project/tasks/`。
- 补齐 standalone/bootstrap 所需的 CHANGELOG/Git 规范、`sage_linter.py` 和 `.githooks/` 默认发行版资产，并修正默认入口回退与活跃 TASK 路径。
- 删除根目录与 `skills/sage-workflow/core/` 重复的 prompts、templates、guides、方法论、linter 和 hooks，SAGE 源仓库统一从 skill core 读取默认工作流。
- 补齐跨宿主运行时派发：新增 adapter JSON 能力声明、`dispatch_phase.py` 的 prepare/status/verify/cancel/run-cli 协议、原生 subagent 信封和 TASK/Git 产出验证；bootstrap 后复制为项目本地 `scripts/sage_dispatch.py` 与 `docs/guides/execution-adapters/`。
- 新增阶段级模型路由：adapter 可声明默认模型、原生请求级/注册型绑定和 CLI `{model}` 参数绑定；Dispatcher 记录模型信封并阻断未实际消费模型或非法单次覆盖。
## [0.3.2] 📝 Process 沉淀原生 subagent 优先执行通道 (T-007) - 2026-05-30 11:38:30
- 将 SAGE 执行载体策略从 CLI 优先调整为能力优先：工具原生 subagent 可用时优先派发 reviewer/coder/closer，CLI 作为受控 fallback。
- 更新执行通道规范，补充 subagent 派发模板、CLI fallback 规则、失败复核要求和成功标准。
- 更新模型选择指南，明确模型选择与执行载体解耦，并定义 `base_instructions` / `model_messages` / subagent 配置的载体提示边界。
- 更新 Codex 覆盖入口和模式库，沉淀“原生 subagent 优先”和“模型目录不承载角色契约”两条通用实践。
## [0.3.1] 📝 Process 明确覆盖入口与上下文传递契约 (T-005) - 2026-05-28 00:00:00
- 明确工具默认覆盖入口必须自包含通用入口规则；`AGENTS.override.md` 需可替代 `AGENTS.md` 独立启动。
- 明确 L0 由 Main Agent 直接执行，不创建 TASK，不调用 CLI/subagent。
- 收紧 CLI/subagent 上下文传递契约：只传 `REPO_ROOT`、`TASK_PATH`、`ROLE_PROMPT`、`PHASE` 和必要 `DIFF_CMD`，任务等级、当前阶段、项目根目录、功能分支等从 TASK 元数据读取。
- 更新执行通道、模型选择、任务模板、交接指南和模式库，避免把主线程讨论历史或额外隐式上下文传给执行者。

## [0.3.0] 📝 Process 引入任务等级与多工具编排契约 (T-004) - 2026-05-28 00:00:00
- 新增 L0/L1/L2/L3 分级入口规则：L0 免 TASK 文档直执，L1 及以上必须物理复制 TASK 模板。
- 重写 `AGENTS.md` 任务入口，明确 Main Agent 强制加载 `orchestrator.md` 与 `planner.md`，并内联阶段-角色-TASK 映射。
- 新增 `AGENTS.override.md` 与 `GEMINI.md`，将 Codex app / Antigravity 2.0 工具覆盖规则从通用角色契约中分离。
- 更新 planner/reviewer/coder/closer/doc-gardener 提示词，按任务等级调整行为强度，并统一从 TASK 元数据读取调度信息。
- 更新 TASK 模板，补充当前阶段、项目根目录、功能分支、模型与会话字段，供 CLI/subagent 稳定读取。
- 更新 `sage_linter.py`，支持 L0 分支命名、模板变更显式放行和提交信息中文门禁等通用流程检查。
- 分支命名以 `feat/t-XXX-*` 为推荐格式，同时兼容旧模板的 `feature/T-XXX-*` 功能分支。
- 新增 `docs/guides/execution-channels.md`，集中配置 reviewer/coder/closer 的 CLI/subagent 执行通道，便于替换 CLI。
- 将默认执行通道设为 reviewer 使用 Claude CLI，coder/closer 使用 Qwen CLI。
- 记录 Claude/Qwen CLI 冒烟测试结果：Claude 使用 `-p`，Qwen 使用位置参数，成功标准仍以 TASK/Git 状态为准。
- 新增模型选择指南，说明主代理、盲审 CLI、subagent 和工具覆盖文件的推荐职责边界。

## [0.2.2] 📝 Process 增加中文提交信息质量门禁 (T-003) - 2026-05-23 21:31:08
- 新增 `.githooks/commit-msg` 与 `.githooks/commit-msg.bat`，提交时调用 SAGE linter 检查提交标题。
- 增加 `scripts/sage_linter.py --check-commit-msg <file>`，要求提交标题符合 Conventional Commit 且描述包含中文字符。
- 更新开发规范与交接指南，明确中文提交描述是物理门禁而非软约定。
- 将“提交语言规范必须物理化为 commit-msg 门禁”的经验沉淀到 SAGE 开发方法论与项目管理方法论。
- 修正 Windows hook 的 Python 探测与 UTF-8 输出设置，保证中文提交信息门禁在本地提交路径可执行。
- 统一 SAGE linter 的检查器数量说明与扫描输出口径为 13 项。

## [0.2.1] 📝 Process 沉淀跨项目 SAGE 实战经验 (T-002) - 2026-05-23 20:22:40
- 沉淀跨项目 SAGE 实战经验：版本号判定规则、完整时间戳记录、独立盲审绝对路径规则、收尾补丁版本归属。
- 更新任务模板，要求任务元数据和各阶段标题记录带时区的完整时间戳。
- 更新 reviewer/closer 提示词，明确盲审必须使用 `REPO_ROOT` / `TASK_PATH` 绝对路径，版本号以独立交付物为边界。
- 将 `docs/project/HANDOVER-GUIDE.md` 去业务化，改为 SAGE 通用项目交接指南。
- 修复 `scripts/sage_linter.py` 对带时间阶段标题、标题括号和盲审小标题的兼容性。
- 新增 `--allow-template-changes`，允许模板/流程规范任务显式放行模板变更。

---

## [0.2.0] ✨ Feature 用户认证与基础工程规范 (T-001) - 2026-05-18 00:00:00

> ⚠️ **回溯补正（T-010, 2026-08-18）**：同上，本条目为演示项目历史。
- T-001: 用户注册接口（`POST /api/v1/auth/register`）
- T-001: 用户登录接口（`POST /api/v1/auth/login`）
- T-001: JWT 认证中间件（Access Token 15min + Refresh Token 7d）
- T-001: 统一错误响应格式 `{ code, data, message }`
- T-001: ESLint + Prettier 代码规范配置
- T-001: 密码使用 bcrypt (cost=12) 哈希存储
- T-001: Refresh Token 使用 httpOnly + Secure Cookie

---

## [0.1.0] ✨ Feature 项目初始化与基础脚手架 (INIT) - 2026-05-10 00:00:00

> ⚠️ **回溯补正（T-010, 2026-08-18）**：本条目及 0.2.0 为仓库初始化时的演示脚手架历史，不对应 SAGE 工作流的真实交付。保留仅为版本连续性，不代表当前功能。
- 项目初始化：Express.js + TypeScript + Prisma 脚手架
- PostgreSQL 数据库连接与基础配置
- Docker Compose 开发环境配置
- 基础目录结构（Controller / Service / Repository 分层）


