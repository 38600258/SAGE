# SAGE 项目 Code Wiki

> SAGE（**Steer, Agent Goes Execute**，人类掌舵，智能体执行）是一套面向 AI 智能体驱动研发的**工具无关的开发工作流方法论与治理工具链**。
> 本 Wiki 面向开发者，系统梳理项目整体架构、模块职责、关键代码对象、依赖关系与运行方式。
> 文档对象 = 仓库本身（SAGE 1.0 workflow skill 默认发行版）。

---

## 1. 项目整体架构

### 1.1 一句话定位

把「从项目启动到生产部署」的全生命周期治理流程，封装成一个可分发的 **workflow skill**（`skills/sage-workflow/`），
并配套角色提示词、任务模板、指南、质量门禁脚本和跨工具执行派发，供任何 AI 编程工具（Codex、CLI Agent、Cursor 等）复用。

### 1.2 职能架构（三层）

| 层 | 关注点 | 说明 |
|---|---|---|
| 项目治理层 | 启动/章程 → 干系人 → 沟通 → 预算 → 需求 → 验收 | 项目从 0 到立项 |
| 开发运营层 | WBS → 流水线 → 变更控制 → 发布 → 技术债 | 任务的执行与流转 |
| 度量改进层 | KPI → 监控 → 事件 → 复盘 → 回顾 → 知识管理 | 持续沉淀与进化 |

### 1.3 系统分层（运行时视图）

```text
┌──────────────────────────────────────────────┐
│              SAGE Workflow Skill             │  分发的规范包：SKILL.md
│   SKILL.md + core 默认发行版 + adapters      │  + core/{prompts,templates,guides,scripts}...
└──────────────────────┬───────────────────────┘
                       │ bootstrap / fallback  （bootstrap_sage.py 复制到目标仓库）
┌──────────────────────▼───────────────────────┐
│              Project-local SAGE              │  项目本地权威源
│   AGENTS + docs/project + skill core 默认    │  （项目本地文件优先于默认发行版）
└──────────────────────┬───────────────────────┘
                       │ task execution
┌──────────────────────▼───────────────────────┐
│              Execution Channels              │  跨宿主派发（dispatch_phase.py）
│   Dispatcher → Main Agent / subagent / CLI   │
└──────────────────────────────────────────────┘
```

### 1.4 权威来源规则（核心设计约束）

| 场景 | 权威来源 |
|---|---|
| 新项目无 SAGE 文件 | `skills/sage-workflow/core/` 默认发行版，建议 bootstrap |
| 项目已有本地文件 | 本地 `AGENTS.md`、`docs/project/`、`prompts/`、`templates/`、`docs/guides/` **优先** |
| 外包执行阶段 | TASK 文档 + 当前权威角色契约（CLI/subagent 只承载角色，不拥有调度事实） |
| 工具差异 | `adapters/<id>/<id>.json` 或 `core/guides/execution-channels.md` |
| 阶段派发 | `dispatch_phase.py` 回执 + 宿主原生 API/CLI |

### 1.5 任务分级与阶段流转

- **分级**：L0（纯机械修正） / L1（纯文档/测试/重构） / L2（业务逻辑·默认） / L3（DB/API/部署）。
- **阶段链**：`Init → PlanReview → Dev → CodeReview → Close`（L0 精简为 `Init → Dev → Close`）。
- L1+ 必须物理复制 TASK 模板；L2/L3 需两次盲审 + 证据链；部署必须人类授权。

### 1.6 核心哲学

工程师在智能体优先世界中的三类工作：**设计环境**、**明确意图**、**裁决例外**。

---

## 2. 目录结构与模块职责

| 路径 | 类型 | 职责 |
|---|---|---|
| `AGENTS.md` | 入口 | 工具无关 SAGE 入口规则 |
| `ARCHITECTURE.md` | 文档 | 顶层架构地图 |
| `CHANGELOG.md` | 文档 | 只增不改的变更日志（Keep a Changelog） |
| `README.md` | 文档 | 产品定位与快速开始 |
| `docs/project/` | 状态 | 看板、模式库、决策日志、交接指南、归档任务 |
| `docs/references/` | 参考 | 外部参考文章与 API 模板 |
| `skills/sage-workflow/SKILL.md` | 入口 | skill 触发、模式选择、启动流程、红线 |
| `skills/sage-workflow/core/VERSION` | 元数据 | 发行版本 + 基线提交同步锚点 |
| `skills/sage-workflow/core/entry/` | 规范 | 默认入口文件（AGENTS.md） |
| `skills/sage-workflow/core/prompts/` | 规范 | 6 个角色契约默认发行版 |
| `skills/sage-workflow/core/templates/` | 规范 | TASK / ADR / PRD 物理复制模板 |
| `skills/sage-workflow/core/guides/` | 规范 | 开发/任务/CHANGELOG/Git/执行通道/模型选择等规范 |
| `skills/sage-workflow/core/methodology/` | 规范 | 开发方法论、项目管理方法论 |
| `skills/sage-workflow/core/scaffold/` | 规范 | standalone 项目初始骨架 |
| `skills/sage-workflow/core/scripts/` | **代码** | 三个可执行 Python 工具（核心实现） |
| `skills/sage-workflow/core/githooks/` | 门禁 | commit-msg 硬门禁默认发行版 |
| `skills/sage-workflow/adapters/` | 配置 | Codex / CLI / 通用工具的 JSON 能力声明 |
| `skills/sage-workflow/references/` | 规范 | 派发协议、路径注册表 |

> 注：仓库的核心**代码资产**集中在 `skills/sage-workflow/core/scripts/` 与 `skills/sage-workflow/core/scripts/tests/`；
> 其余为 Markdown 规范文档，是 SAGE 方法论本身。

---

## 3. 核心代码模块：`core/scripts/`

### 3.1 模块总览

| 文件 | 定位 | 依赖 |
|---|---|---|
| `sage_linter.py` | 质量门禁（17 个检查器） | 仅 Python 标准库 + git |
| `dispatch_phase.py` | 跨宿主阶段派发协议层 | 仅 Python 标准库 + git |
| `bootstrap_sage.py` | 将默认发行版复制进新项目 | 仅 Python 标准库 + git |
| `tests/test_dispatch_phase.py` | dispatch 的 `unittest` 测试 | unittest |
| `tests/test_sage_linter.py` | linter 的 `unittest` 测试（bootstrap 透传资产） | unittest |
| `tests/test_bootstrap_sage_build_plan.py` | bootstrap 复制计划的 `unittest` 测试 | unittest |

三者均**零第三方依赖**，只用标准库与本地 `git` 命令，保证可在任何智能体环境独立运行。

**模块间关系**：
`bootstrap_sage.py` 把 `sage_linter.py`、`dispatch_phase.py`（重命名为 `sage_dispatch.py`）、adapters 以及 tests 透传资产（`test_sage_linter.py` + `__init__.py`）复制到目标项目
→ 项目运行时由 `sage_linter.py` 做质量门禁、由 `dispatch_phase.py` 做阶段派发与实际产出验证。

---

## 4. 模块详解（关键类与函数）

### 4.1 `sage_linter.py` — 质量门禁

**作用**：集中了方法论要求的 **17 个检查器**，用于校验任务文档、分支隔离、提交信息、文档健康度等。

#### 全局常量

| 常量 | 说明 |
|---|---|
| `_META_PREFIXES` | 元文件前缀（.sage/、docs/、templates/、scripts/、prompts/ 等），范围锁定/CHANGELOG 校验中排除；`.sage/` 为 linter 运行日志目录 |
| `_META_EXACT` | 精确元文件名（AGENTS.md、CHANGELOG.md 等） |
| `_IS_HOOK` | 由环境变量 `ANTIGRAVITY_HOOK=1` 触发，精简输出为 JSON |

#### 工具函数

| 函数 | 职责 |
|---|---|
| `_is_meta_file(filepath)` | 判定是否为工作流元文件（非项目源码） |
| `_rule_id_from_label(label)` | 从检查器标签提取稳定规则 ID（SAGE-XX），兼容 `[N/17]` 与 `N.` 两种形态，不可解析返回 None（`ResultCollector.add` 支持显式 rule_id 覆盖派生，用于保留段冲突） |
| `write_run_log(...)` | 运行结果单行 JSON 追加至 `.sage/linter-runs.jsonl`（拦截频率统计；best-effort 不影响退出码；hook 模式仅记录存在 fail/warn 的运行） |
| `run_git_cmd(args, cwd)` | 运行 git 命令，失败静默返回空串 |
| `get_git_diff_files(cwd)` | 收集变更文件（已暂存+未暂存+未跟踪），兼容 porcelain 全状态码 |
| `get_file_lines(path)` | UTF-8 容错读取文件行 |
| `resolve_workflow_path(...)` | 项目本地文件优先，缺失回退 skill 默认发行版 |
| `find_active_task(sage_root)` | 定位 `docs/project/ACTIVE_TASK_T-*.md` |

#### 类

**`CheckResult`**（单个检查结果）
- 属性：`checker`（名称）、`status`（pass/warn/fail）、`message`、`rule_id`（稳定规则 ID，由标签编号派生，无法解析时为 None 并在输出中省略）。
- 方法：`to_dict()` / `to_json()` 供多格式输出。

**`ResultCollector`**（结果收集 + 格式化）
- 入口：`add(checker_name, ok, message)` — `ok=True` 且含 `⚠️` 判定为 warn；同时从标签派生 `rule_id`。
- 属性：`has_fail` / `has_warn` / `exit_code()`（0=通过,1=警告,2=阻断）。
- 输出：`flush_text()` / `flush_json()` / `flush_artifact()`（Markdown 报告）/ `flush()`；fail/warn 在三种格式中统一携带 `[SAGE-XX]` 规则 ID（json 为独立 `rule_id` 字段）。
- 启发式判定披露：风险扩展/盲审完整性/执行通道记录/模型元数据四个检查器的 fail 消息自述命中依据（命中的占位词、完整判定词表、要求的标题/行格式）；判定语义与词表内容不变（T-014）。

#### 17 个检查器（模块的"大脑"）

| # | 函数 | 校验内容 |
|---|---|---|
| 1 | `check_template_copy` | TASK 是从模板物理复制且结构完整 |
| 2 | `check_task_structure` | 任务 5 阶段大节齐全有序 |
| 3 | `check_task_risk_sections` | L2/L3 必须有 1.3a 验收标准（AC-ID 可证伪契约）+ 1.3b 风险矩阵 |
| 4 | `check_git_branch_isolation` | 禁在受保护分支开发；分支名符合 `feat/t-XXX-*` 等规范 |
| 17 | `check_commit_message` | Conventional Commit + 描述含中文（commit-msg 门禁核心；hook 专属检查器，编号 17 为 hook 保留段——任务级检查器 rule ID 不占用，计划放行标签 [17/17] 显式映射 SAGE-18 即此原因） |
| 5 | `check_t2_document_lines` | guides 下规范文档 ≤500 行 |
| 6 | `check_document_freshness` | 文档 ≤30 天未更新（警告级，不阻塞） |
| 7 | `check_templates_pristine` | 模板目录被篡改即阻断 |
| 8 | `check_changelog_update` | 有代码变更时 CHANGELOG 必须同步 |
| 9 | `check_append_only` | 决策/变更日志只增不改（区分真实删除与换行误报） |
| 10 | `check_scope_lock` | 实际改动文件落在 TASK 1.4 Writeable 白名单 |
| 11 | `check_cross_links` | 本地 md 相对链接有效 |
| 12 | `check_evidence_complete` | 3.2 证据链的测试/Lint 已勾选（阶段解析经 `_parse_current_stage`——TD-9：元数据为模板默认值时阻断并披露） |
| 13 | `check_review_complete` | L2/L3 必须写入 2.1/4.1 盲审报告（判定前剥离 HTML 注释——TD-8：模板门禁注释含 OK/WARN/BLOCK，不剥离则空章节恒放行；元数据为模板默认值时阻断——TD-9） |
| 14 | `check_model_metadata` | 任务元数据"使用模型"非占位符 |
| 15 | `check_execution_channel_records` | L1+ 已到达阶段必须记录角色契约/执行通道/偏离（阶段解析经 `_parse_current_stage`——TD-9：元数据为模板默认值时阻断并披露） |
| 16 | `check_unit_tests` | `--all` 场景以子进程真实执行单测套件（TD-3：失败/超时即阻断；无 tests 目录则跳过） |
| 18 | `check_plan_clearance` | L1/L2 任务 dev 及之后必须元数据「计划放行」=已放行（T-018 人类掌舵点；阶段感知：init/plan-review 未到期、L0/L3 豁免、模板默认阶段跳过——「待放行」为合法初始值、缺失/未放行 fail-safe 阻断；解析经 `_parse_plan_clearance` 整行捕获。rule ID 契约：标签 [17/17] 显式映射 SAGE-18、场景 A 标 "18."，SAGE-17 为 hook 保留段；--all 输出序号 [17/17] 先于 [16/17] 单元测试出现（task_checkers 块在单测之前执行）属注册序错位，备案知悉） |

#### 主入口 `main()`

- 子命令开关：`--check-task`、`--all`、`--check-branch/scope/commit-msg/freshness/links`。
- 输出格式：`--format text|json|artifact`、`--artifact`（等价 artifact）、`--antigravity`（旧兼容）。
- 运行日志：默认每次运行向 `<sage_root>/.sage/linter-runs.jsonl` 追加单行 JSON（ts/mode/exit_code/fail/warn 规则 ID），`--no-log` 关闭；hook 模式仅记录存在 fail/warn 的运行。
- 自动定位项目根：从 `cwd` 向上找含 `AGENTS.md` 的目录。
- 单项检查模式（供 hooks/cron 高频）与全量模式两套调度路径。

---

### 4.2 `dispatch_phase.py` — 跨宿主阶段派发器

**作用**：为 SAGE 阶段生成**统一派发信封**、执行受控 CLI、并验证对 TASK/Git 的**真实产出**。是 skill 的红线边界——不越权假装拥有宿主进程控制权。

#### 关键常量

| 常量 | 说明 |
|---|---|
| `SCHEMA_VERSION = 1` | adapter/回执 schema 版本 |
| `PHASES` | 阶段→角色/章节/指令映射：plan-review→reviewer/2.x，dev→coder/3.x，code-review→reviewer/4.x，close→closer/5.x |
| `ALLOWED_CONTEXT_FIELDS` | 可传递的唯一上下文白名单：REPO_ROOT/TASK_PATH/ROLE_PROMPT/PHASE/DIFF_CMD |
| `SUBAGENT_MODEL_BINDINGS` | {none, request, agent-registration} |
| `CLI_MODEL_BINDINGS` | {none, command-argument} |
| `CHANNEL_PRIORITY` | subagent=3 > injected=2 > cli=1 |
| `PROVISION_ROLES` | provision 可生成的角色（reviewer/coder/closer），生成逻辑下沉至各适配器 `adapters/<id>/provision.py` |
| `ROLE_PHASES` | 角色→阶段归属（reviewer:coding 两个审查阶段），随 provision 下沉到各适配器脚本 |

#### 异常

`DispatchError(RuntimeError)` — 派发配置、上下文或产出验证不满足契约即抛出。

#### 配置加载与校验

| 函数 | 职责 |
|---|---|
| `discover_skill_root()` | 从脚本向上找含 `SKILL.md` + `adapters/` 的 skill 根 |
| `profile_candidates(adapter, repo_root)` | adapter JSON 候选（项目本地 → skill 内置） |
| `load_profile(adapter, repo_root, adapter_file)` | 加载并 `validate_profile` |
| `validate_profile(profile, path)` | 校验 schema_version、native/injected/cli 能力、agent_types、models 绑定方式 |
| `require_task_gate(content, phase)` | L0 禁派发；TASK 1.1~1.5 必须冻结；code-review 前需有 3.2 证据 |

#### 通道与模型路由

| 函数 | 职责 |
|---|---|
| `choose_channel(...)` | `auto` 按优先级选通道；指定通道时校验能力；降级 CLI 必须带 `--fallback-reason/--fallback-authorized` |
| `resolve_injected_agent_types(profile)` | 解析注入式通道各阶段的 agent_type |
| `resolve_model(profile, phase, channel, requested)` | 解析模型来源（adapter/argument/unspecified）与绑定方式，阻断非法覆盖 |

#### 信封生成（核心流程）

`prepare_dispatch(args)` → 生成 `receipt`（回执，JSON）并写盘，包含：
- `action`：`spawn_subagent` 或 `run_cli`
- `agent_type`：如 `sage_coder`；`injection`：注入式隔离信息（仅 injected 通道）
- `model`：`{requested, binding, source}`
- `context`：仅允许白名单字段
- `prompt`：由 `build_prompt()` 拼接的最小上下文指令
- `before`：派发前快照（`snapshot()`，含 task_sha256、阶段 section 哈希、git_head/branch/fingerprint、review_verdicts）

支持函数：`build_context` / `build_prompt` / `sha256_bytes|file` / `run_git` / `git_head|branch|fingerprint` / `extract_phase_section` / `snapshot` / `default_state_dir` / `write_receipt` / `load_receipt`。

#### 产出验证

`verify_receipt(receipt_path, skip_close_commit_check)` — 对比 `before` 与当前快照：
- reviewer：TASK 2.x/4.x 变化，且出现新 **OK/WARN/BLOCK** 结论；
- coder：3.1 进度 + 3.2 证据有效（`subsection_body`+`is_meaningful` 判定），且 Git 指纹/HEAD 变化；
- closer：5.x 有效，默认必须产生新提交。
- 结果写回回执 `status = completed/failed`，并记录 `verification.{success,errors,warnings}`。

#### CLI 执行

- `resolve_cli_command(receipt, command_json)`：命令必须是 JSON 字符串数组（禁 shell 拼接），校验 `{model}` 占位符与模型消费一致；支持 `{prompt}`/`{repo_root}` 等占位符，或 `stdin` 模式。
- `run_cli_dispatch(args)`：执行命令 + 随时 `verify_receipt`，失败记录 `cli_error`。

#### 通道治理

- `doctor_probe(args)`：逐通道探测可用性（原生=声明判定、注入=声明+agent_types、CLI=只探测可执行文件），输出推荐通道。
- `provision_delegate(args)`：委托 `adapters/<id>/provision.py` 生成 agent 注册文件（codex→TOML、claude-code→Markdown），subprocess 透传 `--target-dir / --role / --force / --format`（codex 额外透传 `--model-provider`）；`locate_provision_script` 按项目本地优先定位脚本，无 provision.py 的适配器（cli/generic-tool）报错退出码 2。
- `cancel`：仅标记 `host_cancel_required`，真正取消由宿主 API 完成。

#### 子命令与格式化

子命令：`capabilities` / `prepare` / `verify` / `status` / `cancel` / `run-cli` / `doctor` / `provision`。
格式化：`format_capabilities` / `format_result` / `format_doctor` / `format_provision`（text/json 双输出）。
主入口 `main()` 用子命令分派；`DispatchError`/JSON 错返回退出码 2。

---

### 4.3 `bootstrap_sage.py` — 默认发行版引导

**作用**：将 `skills/sage-workflow/core/` 默认发行版复制进目标项目并重写相对链接，使项目可脱离 skill 目录独立运行。

| 对象 | 职责 |
|---|---|
| `CORE_ROOT` / `SKILL_ROOT` | 基于 `__file__` 解析 skill 目录 |
| `render_entry(content)` | 重写入口文件中的相对路径（`../guides/`→`docs/guides/` 等） |
| `render_project_guide(content)` | 重写指南入口链接 |
| `render_template(content)` | 重写模板中的 skill 仓库权威路径（`skills/sage-workflow/core/guides/`→`docs/guides/`，TD-7：模板默认值在 skill 源仓库与 bootstrap 项目双语境均有效） |
| `build_plan(repo_root)` | 生成「源→目标」复制计划：prompts/templates/guides/methodology/scaffold/githooks/adapters/脚本/入口（templates 条目携带 `template` 转换、guides 携带 `guide` 转换、入口携带 `entry` 转换，其余原样复制） |

> 注（T-015 计划盲审备案）：本仓库（skill 源仓库）entry/methodology 中出现的 `docs/guides/` 引用属 bootstrap 目标语境设计或禁改范围，非路径失效；skill 源仓库自身以 `skills/sage-workflow/core/guides/` 为权威路径（TD-7 修复口径）。
| `configure_hooks(repo_root, dry_run)` | 检查并（缺省时）设置 `git config core.hooksPath=.githooks`，不覆盖已有配置 |
| `main()` | 执行复制（尊重 `--force`/`--dry-run`/`--skip-hooks`） |

### 4.4 `tests/test_dispatch_phase.py` — 派发器测试

基于 `unittest`，子进程方式驱动 `dispatch_phase.py`，覆盖：
- 原生 subagent 信封 + verify 真实产出（`test_prepare_native_subagent_envelope_and_verify_real_output`）
- reviewer 必须新增/修改 OK/WARN/BLOCK 结论
- `request` 模型单次覆盖记录；`agent-registration` 拒绝单次覆盖
- CLI `{model}` 消费强制；CLI 通道执行 + verify
- codex→CLI 降级需 reason+authorization
- cancel 标记 host 取消
- 注入式信封隔离记录 / 未声明阻断
- doctor 通道探测（generic-tool 推荐 injected；cli 无可定位命令=不可用）
- provision 两种模板生成 + 默认不覆盖已存在文件

### 4.5 `tests/test_bootstrap_sage_build_plan.py` — bootstrap 复制计划测试

基于 `unittest`，以独立模块名加载 `bootstrap_sage.py` 并 monkeypatch `CORE_ROOT`/`SKILL_ROOT` 到临时目录，覆盖：
- TD-4 构建产物过滤：`__pycache__`/`.pyc` 排除在复制计划外
- TD-6 tests 透传名单：含 `test_sage_linter.py` + `__init__.py`，不含 `test_dispatch_phase.py`
- TD-7 模板路径转换：`render_template` 重写 `skills/sage-workflow/core/guides/` → `docs/guides/`；templates 复制条目携带 `template` 转换标记
- 既有脚本复制不回归（`sage_linter.py` / `sage_dispatch.py`）

> 注：`test_sage_linter.py` 是 bootstrap 唯一透传的测试资产，严禁注入 `bootstrap_sage`/repository 级依赖。

---

## 5. 依赖关系

### 5.1 技术栈

- **语言/运行时**：Python 3（`from __future__ import annotations`，标准库）。
- **包管理/运行器**：uv（`uv run`）；仓库**无 `pyproject.toml`**，无第三方 Python 依赖。
- **外部命令**：`git`（分支、diff、提交门禁、指纹）。

### 5.2 Python 依赖（全部为标准库）

`argparse` / `json` / `os` / `re` / `subprocess` / `sys` / `time` / `hashlib` / `shutil` / `tempfile` / `uuid` / `datetime(timezone)` / `pathlib` / `unittest`。

### 5.3 数据依赖

- **adapter JSON**（`adapters/<id>/<id>.json`）：声明宿主能力、阶段 agent 映射、模型路由、CLI 命令环境变量——`dispatch_phase.py` 的解析与校验对象；目录内含适配器说明 `<id>.md` 与子代理生成脚本 `provision.py`。
- **TASK 文档**（`docs/project/`）：派发/校验的事实来源（元数据、1.1~1.5 冻结范围、阶段章节、证据链）。
- **角色提示词**（`prompts/*.md`）：`dispatch_phase` 通过 `resolve_role_prompt` 定位并在信封中传递。

### 5.4 模块依赖图

```text
bootstrap_sage.py ──复制──> [sage_linter.py, sage_dispatch.py(dispatch_phase), adapters/<id>/, tests/{test_sage_linter.py, __init__.py}] 到目标项目
                                 │
        sage_linter.py  ------------------------------------ 质量门禁
        dispatch_phase.py ──读取──> adapters/<id>/<id>.json、TASK、prompts/*.md、git
        dispatch_phase.py ──委托──> adapters/<id>/provision.py（provision 子命令）
        dispatch_phase.py ──驱动──> subagent / injected / CLI 通道
        tests/test_dispatch_phase.py ──子进程──> dispatch_phase.py
        tests/test_bootstrap_sage_build_plan.py ──monkeypatch──> bootstrap_sage.py(build_plan)
```

---

## 6. 项目运行方式

> 环境：Windows / PowerShell，Python 3 + uv。项目根为 `d:\Dev\Code\sage`。

### 6.1 质量门禁（Linter）

```powershell
# 一键全量 15 项静态扫描
uv run python skills/sage-workflow/core/scripts/sage_linter.py --all

# 单项（hooks/cron 高频）
uv run python skills/sage-workflow/core/scripts/sage_linter.py --check-branch
uv run python skills/sage-workflow/core/scripts/sage_linter.py --check-scope
uv run python skills/sage-workflow/core/scripts/sage_linter.py --check-commit-msg .git/COMMIT_EDITMSG
uv run python skills/sage-workflow/core/scripts/sage_linter.py --all --format json
```

### 6.2 跨宿主派发（Dispatcher）

```powershell
# 查看 adapter 能力
uv run python skills/sage-workflow/core/scripts/dispatch_phase.py capabilities --adapter codex

# 探测各通道可用性并给出推荐
uv run python skills/sage-workflow/core/scripts/dispatch_phase.py doctor --adapter codex --repo-root <repo>

# 生成派发信封与回执
uv run python skills/sage-workflow/core/scripts/dispatch_phase.py prepare `
  --repo-root <repo> --task-path <task> --phase dev --adapter codex --format json

# 验证 TASK/Git 真实产出
uv run python skills/sage-workflow/core/scripts/dispatch_phase.py verify --receipt <receipt> --format json

# 受控 CLI 执行（命令为 JSON 字符串数组）
uv run python skills/sage-workflow/core/scripts/dispatch_phase.py run-cli `
  --receipt <receipt> --command-json '["agent-cli","--prompt","{prompt}"]'

# 生成宿主 agent 注册文件（委托适配器脚本；codex→TOML，claude-code→Markdown）
uv run python skills/sage-workflow/core/scripts/dispatch_phase.py provision `
  --adapter codex --target-dir <agents目录>
```

### 6.3 运行测试

```powershell
# 只跑 dispatch 相关测试（unittest，无 pytest）
uv run python -m unittest skills.sage-workflow.core.scripts.tests.test_dispatch_phase
# 或直接执行测试文件
uv run python skills/sage-workflow/core/scripts/tests/test_dispatch_phase.py
```

### 6.4 测试全部通过预期

- linter：退出码 `0` = 全部通过；`1` = 有警告；`2` = 有阻断。
- dispatcher：`unittest` 全绿，覆盖 subagent/注入式/CLI 三种通道与模型路由约束。

### 6.5 新建项目引导

```powershell
# 预览将复制的文件（不修改仓库）
uv run python skills/sage-workflow/core/scripts/bootstrap_sage.py --repo-root <项目绝对路径> --dry-run

# 实际复制并配置 .githooks
uv run python skills/sage-workflow/core/scripts/bootstrap_sage.py --repo-root <项目绝对路径>
```

---

## 7. 关键业务概念速查

| 术语 | 含义 |
|---|---|
| TASK 1.1~1.5 | 初始化阶段的 背景/决策/计划/范围/非目标（L1+ 冻结后才可派发） |
| AC-ID 验收标准 | 可证伪验收契约：AC 编号 + `[auto]/[manual]` + 验证方式 + 证据位置 |
| 证据链（3.2） | 阶段三验证证据，测试/Lint 必须勾选 |
| 盲审（2.x / 4.x） | L2+ 的计划/代码独立审查，必须写 OK/WARN/BLOCK |
| adapter 绑定 | `request`（单次可覆盖）/ `agent-registration`（宿主注册固定）/ `command-argument`（CLI `{model}` 消费） |
| 通道 | subagent（原生）> injected（注入式）> cli（受控 fallback） |

### 红线（不可违反）

1. 部署必须人类授权。
2. L1+ 任务文档必须物理复制模板。
3. 收尾阶段严禁新增功能。
4. 合并到 `dev`/`main` 的权力永远属于人类。
5. 所有知识沉淀到仓库，不留在聊天或人脑。