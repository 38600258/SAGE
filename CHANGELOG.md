# 变更日志 (Changelog)

> 只增不改。按版本号组织。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。
> 注：历史条目原本只记录日期，迁移到单行标题格式时用 `00:00:00` 作为回溯补齐时间。

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
- T-001: 用户注册接口（`POST /api/v1/auth/register`）
- T-001: 用户登录接口（`POST /api/v1/auth/login`）
- T-001: JWT 认证中间件（Access Token 15min + Refresh Token 7d）
- T-001: 统一错误响应格式 `{ code, data, message }`
- T-001: ESLint + Prettier 代码规范配置
- T-001: 密码使用 bcrypt (cost=12) 哈希存储
- T-001: Refresh Token 使用 httpOnly + Secure Cookie

---

## [0.1.0] ✨ Feature 项目初始化与基础脚手架 (INIT) - 2026-05-10 00:00:00
- 项目初始化：Express.js + TypeScript + Prisma 脚手架
- PostgreSQL 数据库连接与基础配置
- Docker Compose 开发环境配置
- 基础目录结构（Controller / Service / Repository 分层）
