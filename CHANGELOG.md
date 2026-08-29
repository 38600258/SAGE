# 变更日志 (Changelog)

> 只增不改。按版本号组织。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。
> 注：历史条目原本只记录日期，迁移到单行标题格式时用 `00:00:00` 作为回溯补齐时间。


## [1.5.1] 🐛 BugFix 清偿遗留技术债 TD-7/TD-8：模板执行通道失效路径与盲审校验 HTML 注释误放行 (T-015) - 2026-08-29 22:44:27
- TD-7 模板失效路径修复（双语境同构）：`TASK-TEMPLATE.md` 执行通道配置默认值从 `docs/guides/execution-channels.md`（本仓库不存在该目录，T-013 起每份 TASK 元数据沿用失效路径）改为 skill 源仓库权威路径 `skills/sage-workflow/core/guides/execution-channels.md`；`bootstrap_sage.py` 新增 `render_template(content)` 转换（`skills/sage-workflow/core/guides/` → `docs/guides/`，与 `render_entry`「源为 skill 语境、复制时转换为目标项目语境」同构），`build_plan` templates 条目携带 `template` 转换、`main()` 新增对应写出分支。临时空仓库真实 bootstrap 实证：落盘模板 L15 已重写、目标项目 `docs/guides/execution-channels.md` 真实存在。
- TD-8 盲审完整性校验修复（含阶段感知伴生修改）：`sage_linter.py` 新增 `_strip_html_comments`（DOTALL 非贪婪，含跨行注释），`check_review_complete` 判定前统一剥离 HTML 注释——模板 2.1/4.1 节内置门禁注释含 OK/WARN/BLOCK 字样，此前既命中结论标记词表、注释行又计为实质内容，空章节恒放行、盲审门禁形同虚设。同函数补阶段感知（T-011 为 `check_evidence_complete` 建立的同构模式）：`init` 阶段两节均未到期跳过，`plan-review`/`dev` 仅 2.1 计划评审报告到期（4.1 未到期在通过消息中提示），`code-review`/`close` 两节均到期，元数据缺失或未知阶段维持强制（fail-safe）——此前早期阶段的空节靠本缺陷恒放行，修复后必须补阶段感知，否则所有后续任务 init/dev 期门禁误报阻断。三态诊断结构、判定词表与披露文案零改动（T-014「判定语义与披露内容严格分离」原则延续）；`dispatch_phase.py` verify 经核查用严格格式正则 `审查结果[：:] OK|WARN|BLOCK`，无同源缺陷，不纳入本次范围。
- 测试与文档同步：`test_sage_linter.py` 新增 7 例（TD-8 三态回归 3 例——模板原样空 2.1 节 FAIL、跨行 HTML 注释 DOTALL 分支 FAIL、真实报告与注释共存 PASS 防误伤；阶段感知 4 例——init 跳过/dev 仅 2.1 到期/code-review 双节到期/元数据缺失 fail-safe）；`test_bootstrap_sage_build_plan.py` 新增 2 例（render_template 路径重写、templates 条目转换标记）；全量单测 53 → 62 例全绿。CODE_WIKI.md 同步四处（检查器清单 13 行、4.3 资产表 +render_template 行与复制计划转换标注、bootstrap 语境备案注、4.5 测试覆盖清单）。

## [1.5.0] ✨ Feature 质量门禁自解释改造：规则 ID 全量标注、命中依据披露与拦截频率日志 (T-014) - 2026-08-29 14:47:42
- 规则 ID 中心化标注（SAGE-01~17）：`ResultCollector.add` 经 `_rule_id_from_label` 从检查器标签编号派生稳定规则 ID（兼容 `[N/16]` 与 `N.` 两种形态，不可解析时降级省略），fail/warn 在 text/json/artifact 三格式统一携带（json 为独立 `rule_id` 字段）；16 个检查器函数签名与判定语义零改动。
- 4 个启发式黑盒检查器命中依据披露（仅披露，判定语义与词表内容不变）：`check_task_risk_sections` AC 表逐单元格报告空列/命中占位词并附判定词表全量、风险矩阵区分表格缺失与数据行占位两类情形；`check_review_complete` 三态诊断（章节不存在/无审查结论标记/有标记但仅占位文本）并列出对应词表；`check_execution_channel_records` 披露要求的标题格式与 `- [x] **标签**: 内容` 行格式；`check_model_metadata` 按类别披露占位符命中。
- 拦截频率运行日志：每次运行向 `.sage/linter-runs.jsonl` 追加单行 JSON（ts/mode/exit_code/fail/warn 规则 ID 列表），供统计各检查器实际拦截频率；best-effort 写入绝不影响退出码；`--no-log` 显式关闭；hook 模式仅记录存在 fail/warn 的运行；`.sage/` 纳入 `_META_PREFIXES` 防止门禁产物误触发范围锁定/CHANGELOG 联动校验。
- 编号歧义修复：提交信息单项检查器标签 "15." → "17."（SAGE-17），消除与全量模式 [15/16] 执行通道记录校验的编号冲突。
- 左移降频率：coder/closer 角色契约质量门禁步骤追加「门禁被拦处置顺序」（规则 ID 与命中依据优先、源码最后）；CODE_WIKI 4.1 同步；单测 35 → 53 例全绿（新增规则 ID 派生/JSON 字段/四项披露/运行日志/元文件判定共 18 例，bootstrap 透传资产可移植性保持）。

## [1.4.0] 🛠️ Fix 清偿遗留技术债 TD-2/TD-4/TD-6 (T-013) - 2026-08-19 09:15:50
- TD-2 provision 报错语义区分：`locate_provision_script` 在候选 provision.py 全缺失时先经 `profile_candidates` 探测 adapter JSON——均无 JSON 报「找不到 adapter '<id>'（请检查适配器 id 拼写；若运行在独立环境请确认 skill 已挂载或指定 --repo-root）」，有 JSON 无 provision 报「adapter '<id>' 不提供子代理生成」；删除「cli/generic-tool 无原生 subagent 注册能力」误导后缀（对 claude-code 等有 subagent 能力、仅定位失败的场景构成误导）。新增未知 adapter 用例 + 既有用例断言更新（stderr 独立验证：`--adapter nope`/`--adapter cli` 两种语义各得其所）。
- TD-4 bootstrap 构建产物过滤：`bootstrap_sage.py` 新增模块级 `_is_build_artifact(path)`（任一父目录名 `__pycache__` 或后缀 `.pyc`/`.pyo`），应用于 build_plan 两处 rglob（core 六目录 + adapters 整目录）的 is_file 分支，集中式单一实现保证过滤口径一致（避免 T-001 式两处漂移）；dry-run 实证输出零 `__pycache__`/`.pyc`/`.pyo` 匹配。
- TD-6 bootstrap tests 透传（关闭 T-012 登记「check_unit_tests 恒跳过」盲区）：复制清单追加 `scripts/tests/test_sage_linter.py` + `__init__.py`（复用现有 copy/transform=None 框架）；不透传 `test_dispatch_phase.py`（经 `discover_skill_root` 查找 skill 内置 adapters，bootstrap 项目无 SKILL.md 布局必然 FAIL）。实际 bootstrap 到临时空 git repo 实证：`sage_linter.py --all` 输出 `🟢 [16/16] 单元测试执行: 单元测试执行通过（Ran 10 tests）`，单测门禁在 bootstrap 项目真实生效（此前恒为跳过提示）。
- 测试与文档同步：新建 `tests/test_bootstrap_sage_build_plan.py`（monkeypatch CORE_ROOT/SKILL_ROOT 到临时目录，覆盖 TD-4 过滤/TD-6 透传名单/既有脚本复制不回归 3 用例；断言用 as_posix 归一化保证平台无关）；全量单测 35/35 绿（31 + 新增 4）。CODE_WIKI.md 同步四处：3.1 代码资产表补 tests 两行、模块间关系 bootstrap 复制清单、新增 4.5 节、5.4 模块依赖图。
- 硬约束沉淀：`test_sage_linter.py` 是 TD-6 唯一透传资产，严禁注入任何 `bootstrap_sage`/repository 级依赖（污染将导致 bootstrap 项目 check_unit_tests 恒阻断）；build_plan 用例必须放独立文件承载。

## [1.3.0] ✨ Feature 质量门禁新增单测执行项与流程规范沉淀 (T-012) - 2026-08-19 08:27:25
- TD-3 落地（T-011 复盘最优先项）：sage_linter.py 新增第 16 个检查器 `check_unit_tests`，`--all` 从纯静态扫描升级为「静态扫描 + 真实执行」双保险——以 `sys.executable -m unittest discover` 子进程执行 linter 同级 `tests/` 套件，测试失败或超时（默认 600 秒，可注入）即阻断退出码 2；tests 目录缺失或无 `test_*.py` 时跳过提示（bootstrap 项目合法布局，非阻断）。tests_dir/timeout 可注入参数化，配套三态 + 超时共 5 例单测（31/31 全绿），关闭 4fac1b7 式断言失配潜伏主干的门禁盲区。代码盲审独立复核：必败探针实证 [16/16] 阻断退出码 2、31/31 复跑、/16 口径 grep 零残留。
- 编号口径全量同步 `/15` → `/16`：sage_linter.py 内 15 处 `[X/15]` 输出标签与 docstring/注释 3 处"15 个检查器"表述、CODE_WIKI.md 3 处数量表述与 4.1 检查器清单（补第 16 项）；1-15 顺序与 `--check-task`（场景 A）行为不变，methodology 编号引用保持有效。
- 流程规范沉淀（T-011 复盘问题 2/3/4）：TASK-TEMPLATE 效能数据"返工次数"行追加口径注释（盲审退回、门禁未过重跑、格式试错每轮计 1，含微返工，随模板物理复制传播）；task-document-standards 第二节新增"先例优先"与"改码前先登记"两条硬约束；KNOWN_PATTERNS 新增 BP-014（先例优先）/AP-006（静态门禁盲区）/AP-007（改码前登记）三条原子条目。
- 已知限制（技术债，语义安全）：bootstrap 复制清单仅含 sage_linter.py 与 sage_dispatch.py、不含 `scripts/tests/`（dry-run 实证），bootstrap 后项目该检查器恒为跳过——后续任务评估是否将 tests/ 纳入复制清单。
- 效能对照：T-012 全程零返工（init 门禁一次通过、计划盲审首审 WARN、coder Red-Green 重试 0、代码盲审首审 WARN），对比 T-011（计划盲审 BLOCK 一轮返工 + 微返工 ≥6 次）——先例优先/批量授权/预置预期结论三项复盘改进的直接验证。

## [1.2.0] ✨ Feature 适配器化子代理生成与 linter 阶段感知 (T-011) - 2026-08-19 06:39:16
- 适配器化子代理生成（provision 下沉到各 IDE 适配器）：适配器目录从平铺 `adapters/*.json|md` 改为整目录 `adapters/<id>/`（cli/codex/generic-tool 迁移 + 新增 claude-code）；生成逻辑（`build_toml_agent`/`build_markdown_agent`/`ROLE_INSTRUCTIONS`）逐字迁入各自 `provision.py`，双入口可用（独立 argparse + `dispatch_phase.py provision --adapter <id>` 委托，项目本地优先、退出码透传）；主入口删除 `--method`/`PROVISIONING_METHODS`/`provision_agents`，新增 `--adapter` 必填，`--model-provider` 保留主入口并仅对 codex 委托透传（非 codex 拒绝退出码 2）；`profile_candidates` 两侧路径联动改子目录结构；bootstrap 复制计划改整目录（含 provision.py）。
- 修复 sage_linter.py `check_evidence_complete` 阶段感知缺陷：按 TASK 元数据 `当前阶段` 判定，仅 code-review/close 强制校验 3.2 证据链，init/plan-review/dev 期跳过并提示；元数据缺失或未知阶段维持强制（fail-safe）。此前 init 期对模板默认未勾选的证据链误报阻断，提前勾选反而属于伪造证据。
- 顺带修复 HEAD 提交 4fac1b7（codex.json 模型切至 GPT-5.6 系列）未同步的 4 处测试断言失配（test_prepare_native_subagent_envelope_and_verify_real_output 与 provision TOML 用例在 HEAD 上本就失败）；同步新增 linter 阶段感知三态单测（test_sage_linter.py，26/26 全绿）。
- 六处文档同步新结构：path-registry.md / dispatch-protocol.md / SKILL.md / execution-channels.md 5.6 / CODE_WIKI.md（含超出 1.4 声明行号的目录结构联动，盲审已核验必要性）/ KNOWN_PATTERNS.md BP-013；provision 委托示例补 `--repo-root`（委托化后 bootstrap 项目内必需，缺省会脚本定位失败，TD-1）。
- 遗留技术债：TD-2（locate_provision_script 报错语义区分）、TD-3（质量门禁不运行单测的系统性盲区）、TD-4（bootstrap rglob 未过滤 `__pycache__`）——详见归档任务 5.1。

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


