# 变更日志 (Changelog)

> 只增不改。按版本号组织。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。
> 注：历史条目原本只记录日期，迁移到单行标题格式时用 `00:00:00` 作为回溯补齐时间。


## [1.8.3] ✨ Feature 新增 OMP（Oh My Pi）适配器：omp.json/omp.md/provision.py 三件套，modelRoles+自定义 agent 异构盲审 (T-023) - 2026-09-01 16:40:00
- 动机：SAGE 适配器体系已有 codex/claude-code/generic-tool/cli，但缺少 OMP（Oh My Pi）。OMP 的 `task` 工具可派发命名子代理，模型路由是角色级（modelRoles）而非请求级——先前按请求级语义实现内置 agent 映射（上轮返工），经官方源码（task-agent-discovery.md/settings.md/agents.ts/model-roles.ts）交叉验证后重构为角色路由语义。
- 修复内容（相对上轮的断裂）：①`omp.json` 不用内置 agent 类型名（内置 reviewer/task 的 system prompt 是 OMP 协议非 SAGE 契约），改用自定义 agent 名（sage-reviewer/sage-coder/sage-closer）映射四阶段；`models.<phase>.id` 用自定义角色别名（sage-slow/sage-task）而非内置角色名。②`provision.py` 生成 `.omp/` 三件套：`config.yml`（modelRoles 段：sage-slow/sage-task/advisor 固定键）+ `agents/sage-*.md`（3 个自定义 agent，frontmatter `model: "@sage-slow"/"@sage-task"` 承载 SAGE 角色契约）；幂等默认 skipped、`--force` 覆盖（覆盖前检测非 modelRoles 段并告警）；`--role` 用角色名（reviewer/coder/closer）与 codex/claude-code 一致，`dispatch_phase.py` 零改动。③`omp.md` 说明模型路由链路（agent → frontmatter model → modelRoles → provider/model）、异构盲审配置（sage-slow 设不同厂商）、失败恢复（generic-tool injected 降级）。④`test_dispatch_phase.py` 新增 3 例 OMP 单测（生成+幂等+--force / --role 过滤 / 互证一致性+JSON 结构）。
- 关键决策（详见 DECISION_LOG）：自定义 agent 名承载 SAGE 契约（内置 agent 行为协议不符）；models.id 用角色别名（模型变更只改 config.yml 一处）；advisor 用 OMP 固定键（自定义键是死配置）。
- 接口修正（设计缺陷修复）：`omp.json` 的 `models.<phase>.id` 原先填 OMP 内部角色别名（`sage-slow`/`sage-task`），泄露宿主实现细节——与 codex.json 填实际模型名（如 `gpt-5.6-sol`）的接口不一致。修正为：`models.<phase>.id` 填实际模型标识符（如 `anthropic/claude-sonnet-4-5`）或 `null`，与 codex.json 接口对齐；角色别名降为 provision.py 内部实现细节。`provision.py` 的 `build_config_yml` 从 omp.json 读取模型值直接写入 config.yml（不再生成占位符让用户二次编辑），同别名多阶段模型值不一致时告警；`omp.md` 更新接口说明与异构配置示例。全量单测 99 例 OK 零回归。
- 架构升级（每阶段独立模型，实跑暴露）：用户给 4 阶段配置 4 个不同模型时，旧 2 角色映射（sage-slow/sage-task）导致 close 模型被 dev 覆盖——OMP 的 modelRoles 一个角色只能绑一个模型。升级为**每阶段独立 agent + 独立 modelRoles 键**：`omp.json` `agent_types` 改为 `sage-plan-review`/`sage-dev`/`sage-code-review`/`sage-close`，`provision.py` 按阶段生成 4 个独立 agent（frontmatter `model: "@sage-<phase>"`）+ config.yml 4 个独立 modelRoles 键，每阶段模型互不覆盖，与 codex.json 每阶段独立接口对齐。去除同别名去重/不一致告警（不再存在同组冲突）；`--role` 仍用角色名（reviewer 生成 plan-review+code-review 两个 agent）。全量单测 99 例 OK 零回归；实跑验证 4 模型全写入 config.yml，`prepare` 派发 agent_type=sage-dev、model 来自 omp.json。


## [1.8.2] 🐛 BugFix 修复门禁同类感知缺口两处：SAGE-04 分支隔离补终态/闲置感知（无活跃任务+工作区干净不再误拦）与报错豁免披露，SAGE-08 补 L0 流程感知（l0 分支无活跃任务时不再强制 CHANGELOG） (T-022) - 2026-09-01 10:30:00
- 缺陷暴露（动机）：T-021 修复 SAGE-08 阶段感知（到期点=close）后，对全部 17 个检查器做同类缺口体检，确认 2 项同类感知缺失：①SAGE-04 分支隔离检查器只看分支名，不区分「开发进行中」与「合并后终态/任务间闲置」——T-021 收尾实证：合并回 main 后跑 `--all`，无活跃任务（已归档）+ 工作区干净，仍报 🔴 [4/17]「隔离红线违规」；且阻断消息未披露 `--allow-protected-branch` 豁免参数（AP-009 违例，T-021 已为 SAGE-07 补过同类披露，先例一致）。②SAGE-08 `task_file=None`（无活跃任务）时无条件强制「代码变更必须伴随 CHANGELOG 更新」，但 changelog-standards §一明文「L0 纯机械修正可不新增版本」——l0 分支上修改非元文件（如 skills/ 下交付物，`_META_PREFIXES` 不含 `skills/`）同样命中误拦，缺口在本仓库即真实存在。
- 修复内容：①新增模块级共享常量 `_L0_BRANCH_PATTERNS`（四个 l0 正则），SAGE-04 allowed_patterns 与 SAGE-08 L0 豁免共用同一模式源，防漂移（盲审建议 1）。②`check_git_branch_isolation(cwd=None, allow_protected=False, task_file=None)` 受保护分支命中时按上下文三态判定：有活跃任务→阻断（含任务名判定依据 + `--allow-protected-branch` 豁免披露）；无活跃任务+工作区非干净→阻断（含变更文件数判定依据 + 豁免披露）；无活跃任务+工作区干净→True+💡 终态/闲置跳过说明（对齐 T-021/AP-010 三态语义）；非受保护分支命名校验路径零改动；两处调用点（单项 `--check-branch` 与场景 B `--all`）透传 `task_file`。③`check_changelog_update` 在无活跃任务上下文（`task_file=None` 或文件不存在）时解析分支名匹配 l0 → True+💡 L0 跳过说明（含 changelog-standards §一出处 + 若改变规则仍需记录的提示）；非 l0 分支维持既有强制（fail-safe 最严侧）；有活跃任务时 T-021 阶段感知零改动。
- 验证：新增 9 例单测（SAGE-04 三态×披露断言×命名零回归×allow_protected 放行 6 例 + SAGE-08 l0 四分支跳过/非 l0 维持强制/阶段感知零回归 3 例；临时仓 `git init` 构造），全量单测 87 → 96 例 OK 零回归；`--all` 门禁通过（exit 1=警告级，SAGE-06 新鲜度非阻断既有项）；代码盲审 OK（11 维度全通过）。已知限制：git-standards §一「L0 可直接在当前授权分支执行」场景不属 l0 分支命名形态，不在豁免内、维持既有强制（fail-safe 最严侧，CODE_WIKI 第 8 项声明）。

## [1.8.1] 🐛 BugFix 修复 SAGE-08 CHANGELOG 联动阶段感知缺失:到期点=close,消除 dev 期"阶段预期拦截" (T-021) - 2026-09-01 01:54:03
- 缺陷暴露（动机）：T-016~T-019 连续四个任务在 dev 期运行 `sage_linter.py --all` 被 SAGE-08（[8/17] 日志更新联动）无条件拦截，每次靠人工标注「阶段预期拦截」放行（T-017 AC-3 实录、T-018 首轮 [8/17] 实录、T-019 Lint 证据链实录）。根因：`check_changelog_update` 无阶段感知——只要有代码变更且 CHANGELOG.md 不在变更列表就无条件阻断，而 CHANGELOG 回填是收尾期（close）动作（closer 契约阶段 5 职责），检查器的强制时机被写在了产出时机之前，属「拦截位置写错」：拦截内容符合规则，但到期时机与工作流阶段约定错位。同族披露缺陷一并修复（避免为一句文案单独立项）：`check_templates_pristine` 阻断消息只说「请撤销更改」、不披露 `--allow-template-changes` 豁免参数（T-018 计划盲审实证诱导执行者误回滚交付物一轮返工），是 KNOWN_PATTERNS AP-009 的现存实例。
- 修复内容：①`check_changelog_update(changelog_file, cwd=None, task_file=None)` 接入 `_parse_current_stage` 阶段感知（复用 T-016 单一解析点，与 evidence/review/channel 三检查器同构）——当前阶段 ∈ {init, plan-review, dev, code-review} 时绿色通过 + 一行未到期说明（含阶段值）；close 维持既有强制判定；模板默认行/元数据缺失/未知值 fail-safe 强制并自述判定依据（AP-009）；`task_file=None` 退化既有强制行为（向后兼容，fail-safe 落最严侧）。②唯一调用点（`--all` 场景 B）透传 `task_file`；`--check-task` 场景 A 未注册 SAGE-08 属既有行为维持不变，输出标签与 rule ID 派生机制零改动。③`check_templates_pristine` 阻断消息追加一行豁免指引（`--allow-template-changes` 参数 + 适用条件「交付物本身即模板变更的任务，开发期豁免并记录豁免理由」）；判定分支与返回值语义零改动，属纯披露文案修改。
- 验证：新增 8 例单测（四阶段跳过 subTest、close 期阻断、task_file=None/元数据缺失/未知值/模板默认行四 fail-safe 强制、模板守护披露文案断言 + 模板未改通过对照；临时仓 `git init` 构造「有代码变更」分支），全量单测 79 → 87 例 OK 零回归；双时点活体验证——dev 期（元数据=dev）同一工作区改前必拦、改后跳过，修复效果自证（AC-3）；close 期提交前（元数据=close、变更含 CHANGELOG.md）复跑 `--all`，SAGE-08 真实穿过 close 强制判定输出「CHANGELOG 更新校验通过」，提交后纯 `--all` 整体门禁干净（AC-5）。


## [1.8.0] ✨ Feature 入口收敛：删除 override/GEMINI 四份工具入口，AGENTS.md 瘦身回归 T1 导航+常驻防线，触发信号迁入 orchestrator 等级表 (T-020) - 2026-08-31 23:30:03
- 缺陷暴露（动机）：skills 化后仓库根仍维护三份入口文件（AGENTS.md 77 行、AGENTS.override.md 87 行、GEMINI.md 52 行），本会话逐一审计确认三类结构性问题——①通用规则四副本漂移：AGENTS.md 被 override 整份镜像、被 entry 两份再镜像，红线措辞已实际漂移（「dev 和 main」vs「开发基线分支和生产主干」），override 8 条 Codex 规则约八成为通用规则副本（grep 实证同源）；②专用文件存续理由被证伪或收窄：override 唯一存续理由是 Codex 替换式加载语义，逐条审计 8 条规则删除后全部有归宿（通用化或 adapters/codex/）；GEMINI.md 独有内容仅 artifact 派生映射约 10 行，用户裁决 artifact 机制整体退役（其人类掌舵可见性初衷已被 TASK 文档 + Git + 看板满足，Codex/Antigravity 官方语义均回落主入口）；③AGENTS.md 职责超载：分级判定表/阶段-角色映射/通道协议细节与 orchestrator/planner 重复且缺 skill 触发钩子。
- 落地（用户批准瘦身方案，L2 全流程）：①删除 AGENTS.override.md 与 GEMINI.md（根 + core/entry 共四份）；②根/entry AGENTS.md 按批准草稿重写至各 28 行（阈值 80/100→50/80）：快速导航 + 常驻防线五条（强制加载含 skill 触发钩子、分级判定缺省 L2 指路 orchestrator、派发门禁计划放行、失败恢复现场复核、角色契约权威）+ 不可违反约束 5 条原文；③分级判定触发信号列迁入 orchestrator.md 等级表（L0~L3 逐字迁移）并将 L23 回指改写为本表权威声明；④通用原则下沉：development-standards.md 新增 1.2「载体提示层不承载契约」与 1.3「软防护与硬门禁分层」（含 --check-scope 用法），execution-channels.md 增 research subagent `Workspace: inherit`，adapters/codex/codex.md 新增「载体分层与审批边界」节承接 base_instructions 与审批细节；⑤注册表与 bootstrap 同步：path-registry 项目入口行收敛为单一 AGENTS.md、派发协议行补 `docs/guides/references/` 落点（T-019 遗留 TD 清偿），bootstrap_sage.build_plan 复制清单删至 entry/AGENTS.md，SKILL.md 四处（L13/L21/L63/L85）行内同步；⑥引用清扫 21 处行级命中全清（两轮计划盲审独立普查 21/21 零遗漏），含 sage_linter `_META_EXACT` 单行解禁（82 项静态用例口径存证、unittest 实跑 79 项全 OK）、KNOWN_PATTERNS BP-006 改写为「项目入口单一权威」、两份方法论阈值与 GEMINI 优先级表述同步、model-selection/ARCHITECTURE/CODE_WIKI/HANDOVER 入口表收敛。边界存证（决策 9）：artifact 退役的是入口层派生映射规则，sage_linter `--format artifact` 输出格式与入口机制解耦、保留不改，编程方法论 L402 悬空表述改写为退役口径。
- 验证：AC-1~AC-5 命令级可证伪验证全过并由代码盲审独立重放确认——根/entry 各 28 行 ≤50 且五防线关键词齐备；全仓大小写不敏感 grep（grep 原生排除参数，规避 Git Bash 反斜杠路径过滤器失效）待删文件名零命中；临时空目录真实 bootstrap 复制 44 文件、根目录仅 AGENTS.md 单入口；`--check-scope` 通过。双盲审：计划盲审三轮 BLOCK→BLOCK→WARN（引用普查连续补齐 adapters/codex/codex.md:7、CODE_WIKI.md:77、SKILL.md:63 三处遗漏，第四轮独立普查确认 21/21 收敛），代码盲审 WARN 零阻塞（dev 由 Main Agent 通道执行的降级有记录理由成立、证据链重放属实、23 文件范围零越权），其三项措辞级建议已收尾吸收。返工 3 次（两轮计划盲审 BLOCK 退回 + 1 次 --check-scope 可写清单反引号格式试错）。技术债：SKILL.md 仍 100 行零余量（本任务四处为行内改写不减行数，T-019 拆分约束继续有效）。


## [1.7.0] ✨ Feature 吸收 该真实项目反哺四项改进：命令口径声明、bootstrap 补复制 references、adapter 踩坑沉淀位、主入口现场复核规则 (T-019) - 2026-08-31 03:40:18
- 缺陷暴露（动机）：该真实项目仓库执行「同步 SAGE 工作流 1.5.2」任务（T-119）时产出四项已在其项目实证有效、且上游缺失的实践反哺（工作区输入 `外部反馈记录`，核实基线 v1.5.2 @ `3b601d8`）；对照 v1.6.0 逐项复核四项全部仍然成立。①入口文档全部命令示例假设宿主装有 `uv`，该真实项目型环境（Windows、有 .venv 与系统 python、无全局 uv）下入口给出的命令不可直接执行——脚本层 `.githooks/commit-msg` 探测链已解决，文档层没有；②SKILL.md「内置核心」列出 `references/dispatch-protocol.md` 与 `path-registry.md`，但 `bootstrap_sage.py` 的 `build_plan` 复制清单不含 references/，bootstrap 项目装上派发可执行层（sage_dispatch.py + adapters）却没有协议全文；③四个 adapter md 均无宿主特定陷阱沉淀位，该真实项目已验证的三条实战结论无处跨项目复用；④「失败恢复前现场复核」仅存在于 override 规则 5 / execution-channels / TASK-TEMPLATE X.0 且都绑定 fallback 场景，主入口 AGENTS.md 任务入口规则 1~7 无此条——盲目重试多发生在尚未决定 fallback 的阶段。
- 四项落地：①命令口径**声明式**方案（用户裁决，计划放行轮三轮定稿）——既有 40 处 `uv run python` 命令示例零改动，仅在 SKILL.md 常用命令块后与 README 快速开始各加一行声明，明确三层执行优先级：默认 `uv run python`（uv 自动优先项目虚拟环境）→ 无 uv 时优先项目虚拟环境中的 python（例如 `.venv`）→ 再退系统 python，与 `.githooks` 探测链同构；Main Agent 首轮误读为「改写命令为 python」，被用户在计划放行门纠正，误读与纠正过程在 TASK 1.2 决策 3 如实存证。②`build_plan` 追加 references 整目录复制（`SKILL_ROOT/references/` → `<repo>/docs/guides/references/`，`is_dir()` 守卫 + `_is_build_artifact` 过滤与既有循环口径一致；references/*.md 零相对链接无需 transform，T-019 实测）；SKILL.md Bootstrap 规则清单补落点行，保持「内置核心 = 可分发资产」口径一致。③四份 `adapters/<id>/<id>.md` 统一增设「已知踩坑」节（官方沉淀位，新踩坑随任务收尾沉淀，纳入内容卫生范围）：claude-code 吸收 `--add-dir` 可变参数吞 prompt（prompt 须放参数序列最前或经 stdin）；cli 吸收 Qwen 用户级 `~/.qwen/skills/using-superpowers` 残留、Qwen Windows `'printf' is not recognized` stderr 噪声（成功判定回到「TASK/Git 产出为准」，不得仅因附带 stderr 判失败）；codex/generic-tool 置「暂无记录」。④根/entry `AGENTS.md` 任务入口规则追加第 8 条「失败恢复前现场复核」（该真实项目原表述：复核 Git/TASK/进程/已有产出，禁止未复核盲目重试或切换通道），根/entry `AGENTS.override.md` 规则 5 与 `execution-channels.md` 核心原则及 fallback 条款泛化为「任何重试、修复或切换通道之前必须先完成现场复核」，降级链「人类明确处理或授权后」语义原样保留。
- 验证：临时空目录真实 bootstrap 实证复制 46 文件、references 两文件与源 diff 零差异（T-015 先例）；AC-1~4 全部 grep/diff 可证伪验证通过并由代码盲审独立重跑确认；双盲审均 WARN 零阻塞（计划盲审四条建议两条采纳两条被用户裁决取代，代码盲审四条建议三条收尾吸收一条登记后续任务）。返工 1 次（init 期覆写丢失模板骨架被 SAGE-01/02 拦截）；收尾修正 sed 全局替换误伤 2.1/4.1 冻结盲审文本的操作（已恢复原文，教训记 5.2）。技术债：`build_plan` 复制清单无持久化单测（AC-2 实证替代，5.1 登记）；path-registry.md 派发协议行未反映 references 新落点（登记后续任务）；SKILL.md 达 100 行零余量，后续增补必须先拆分。


## [1.6.0] ✨ Feature 计划放行门：L1/L2 任务进入 dev 前强制用户放行（人类掌舵点）(T-018) - 2026-08-31 01:51:04

- 缺陷暴露（动机）：L2 及以下任务除初始交互式需求确定外全程自动完成，人类在流程内没有掌舵点——L0/L1 无人工确认、L2 双盲审均为独立代理审查，人类唯一实际权力是最终合并，与"约束代码化但方向权归人类"的初衷不符；T-017 实证自决项（范围捆绑/分支策略）直到收尾汇报才被用户看见。新门落在 planner 主线程契约（planner.md 第 8 节）：L1 于 1.1~1.5 冻结后、L2 于计划盲审报告回写 2.1 后，Main Agent 必须提交**固定五要素放行请求**（目标与验收概览 / 可写文件清单——用户未提及项标注「范围增量」+ 理由 / 自决项清单——每条标注「已确认」或「自决」+ 理由 / 风险与缓解概览 / L2 附盲审结论），用户三处置：**放行**（元数据「计划放行」置已放行+时间戳）/ **修正**（回改 1.x 重提）/ **停止**（挂起记录）；未获明确「放行」禁止将阶段置 dev、禁止派发 coder、禁止代填放行记录。L0 豁免（纯机械）；L3 豁免（每阶段人工确认已覆盖，不设双重门）。本任务自身为首次真实演练（五要素经交互组件批量上桌，计划放行与注入式盲审派发授权同轮获取）。
- 门禁固化（rule ID SAGE-18）：`sage_linter.py` 新增检查器 `check_plan_clearance`（清单编号 18），阶段感知判定矩阵——dev/code-review/close 且 L1/L2 到期强制；init/plan-review 未到期跳过；L0/L3 豁免；当前阶段为模板默认行时跳过（「计划放行: 待放行」是该字段**合法初始值**，与「当前阶段」默认行语义不同，且模板默认态会被既有三阶段感知检查器阻断，无逃逸路径）；字段缺失或风险等级缺失按 fail-safe 阻断。解析经新增 `_parse_plan_clearance` 整行捕获（T-016 同款模式，不经 `_parse_current_stage`）；fail 消息自述判定依据与修复指引（AP-009）。双注册面：`--all` 场景标签 `[17/17]` 经 `ResultCollector.add` 新增的显式 rule_id 覆盖参数映射 **SAGE-18**（SAGE-17 为提交信息单项检查器保留段，T-014 刻意保留）；`--check-task` 场景标 "18." 自然派生。`--all` 输出序号 [17/17] 位于 [16/17] 单元测试之前属注册序错位（CODE_WIKI 备案）。编号口径全量同步：`/16]` → `/17]` 9 处标签、「16 个检查器」文字 3 处。信任边界备案（DECISION_LOG）：静态门禁强制"记录存在"而非"询问真实发生"，代填在最终 diff 中对人类可见，与 task-document-standards「改码前先登记」同一信任模型。
- 注入式派发授权口径修订（用户裁决，dev 期发现即修）：execution-channels.md 二·补规则 1"注入式通道要求逐次人工授权"（T-008 引入）与 T-011~T-016 实践存在规则-实践落差，本任务首次字面执行即暴露；按"发现于本任务即修于本任务"原则四表述面同改（execution-channels.md 规则 1 与 5.4 节、generic-tool.json 信封 notes、dispatch-protocol.md 字段说明）——注入式盲审/coder/closer 派发**不要求逐次人工授权**，人工确认点收敛为计划放行门（planner.md 第 8 节）、L3 每阶段人工确认与 merge/push/deploy 授权；隔离等级写回 TASK 证据链的可审计要求保留，降级链级别 4 人工授权降级审查（熔断紧急通道）不受影响。
- 口径同步 6 文件：`TASK-TEMPLATE.md` 元数据新增 `- **计划放行**: 待放行` 行（bootstrap render_template 纯文本透传，无路径转换）；`planner.md`（0.1 矩阵 L1/L2 流转规则补放行时点、新增第 8 节协议、第 7 节自检补放行请求备齐项、输出规范补 L1/L2 门禁声明）；`orchestrator.md`（等级表 L1/L2 门禁列、五阶段任务链图插入放行门、输出流水线格式同步）；`task-document-standards.md`（阶段写入边界约束新增放行规则与待放行合法初始值语义）；根 `AGENTS.md` / `core/entry/AGENTS.md` / `AGENTS.override.md` 三份分级判定表门禁列与子代理派发门禁条款（"1.1~1.5 冻结且计划放行后"）。coder/closer/doc-gardener 契约零改动——coder 既有"当前阶段不是 dev 即暂停"与门天然衔接。
- 测试与文档同步：`test_sage_linter.py` 新增 11 例（CheckPlanClearanceTests 8 例判定矩阵：dev 待放行阻断披露指引 / 已放行通过 / init·plan-review 跳过 / L0·L3 豁免 / close 阻断 / 字段缺失 fail-safe / 等级缺失 fail-safe / 阶段模板默认行跳过；PlanClearanceRuleIdContractTests 3 例：显式覆盖生效 / 场景 A 标签派生 / 全场景 rule ID 唯一且 SAGE-17 不出现），全量 66 → 77 例全绿；`CODE_WIKI.md` 检查器清单补第 18 项、数量表述 17、`_rule_id_from_label` 显式覆盖注记。

## [1.5.4] 📚 Docs 修正 planner.md `/grill-me` 工具绑定死引用 (L0) - 2026-08-31 00:38:32
- T-010（SAGE 1.0 发布前内容卫生）AC-1 清理了编程方法论中的工具绑定词并验证 grep 为 0，但 `core/prompts/planner.md` L41 漏网——保留"通过 `/grill-me` 触发深度需求探询"，而该命令实体在本仓库与任何 adapter 中均不存在，属死引用。本条改为工具中性表述"通过结构化多轮探询触发深度需求探询（slash command、内置交互或人工多轮对话均可）"，与方法论"宿主能力要求"表（苏格拉底式探询行）既有口径一致；探询行为约束（追问边界/挑战假设/不清晰即暂停报告/禁止猜测）零变化。
- 验证：`grep -rn "grill" skills/sage-workflow/core/` 零命中；`sage_linter.py --all` 通过（含 66 例单测）。

## [1.5.3] 📚 Docs coder/reviewer 契约增补根因诊断纪律：堵住闭环驱动的症状修补防线 (T-017) - 2026-08-30 14:34:38
- 缺陷暴露（本次增补动机）：核心信念 1"闭环驱动"（测试失败→修复→重试，最多 3 次）存在未被任何契约覆盖的症状修补路径——智能体可通过修改测试断言迁就实现、静默吞异常或加特判挡住症状让重试循环"收敛通过"，而代码盲审对照 TASK 契约验收，症状修补只要满足验收标准即可过审。检索证实 coder.md/reviewer.md/TASK-TEMPLATE.md 中"根因/症状/复现"零命中；知识沉淀不能替代该纪律——KNOWN_PATTERNS 在收尾阶段写入，沉淀质量是诊断质量的下游，无根因诊断的沉淀只是症状级条目。
- coder.md Green Phase 重试闭环升级："分析 → 修复 → 重试"改为"先复现并定位根因，再针对根因修复——禁止通过修改测试断言迁就实现、静默吞异常或加特判挡住症状让用例变绿"，重试上限 3 次语义不变。
- reviewer.md 流程 B 新增第 11 维度"根因性（仅 Bug 修复类任务）"：检查修复是否针对根因而非症状、是否存在改断言/吞异常/加特判的症状修补，非 Bug 修复任务记 ✅（不适用）；伴生修正流程 B 增量维度编号与流程 A 重号的既有缺陷（6/7/8 → 8/9/10）并将维度计数 10 → 11（7+4）——若不修正，新增维度会使文档自相矛盾。
- 形态取舍存证：以两行提示词纪律落地，不加 TASK 模板必填节、不新增 sage_linter 检查器——对占多数的琐碎修复（空指针/拼写/路径错）强制根因分析构成流程税，违反最小情境原则（用户决策否决门禁形态）；思想来源为 mattpocock/skills 的 diagnosing-bugs 纪律评估，同仓库"四大失败模式"框架经核实为 README 自创修辞分类（书籍引文为佐证非分类来源、维度重叠），评估后不引入。

## [1.5.2] 🐛 BugFix 修复 TD-9：阶段元数据模板默认值被误判为 init 的三检查器共享暴露 (T-016) - 2026-08-29 23:45:41
- TD-9 修复（对管道默认值报错）：`sage_linter.py` 新增模块级 `_parse_current_stage(content)`（三阶段感知检查器共享单一实现，整行捕获元数据值——含 `|` 判定为模板默认行未更新、否则提取首个 `[a-z-]+` token）。`check_evidence_complete`/`check_review_complete`/`check_execution_channel_records` 三处解析点统一替换：元数据仍为模板默认行 `- **当前阶段**: init | plan-review | ...` 时不再被 `([a-z-]+)` 误捕获为 "init"，改为显式阻断并披露「模板默认值（未更新）」与更新指引——此前任务推进后未更新元数据会被误判 init 而跳过阶段感知校验（证据链/盲审报告/执行通道记录三面误放行暴露，T-015 代码盲审建议 2 备案）。
- 语义保持与漂移消除：已填阶段值的既有行为零变化（init 跳过、plan-review/dev 仅 2.1 到期、code-review/close 双节到期、缺失 fail-safe、未知值报错）；执行通道检查器原对元数据缺失默认 "close"（最严）的行为保留。三处独立正则实现收敛为单一 helper（T-013 `_is_build_artifact` 集中式教训同款）。新模板未填元数据的场景 `check_model_metadata` 本就因占位符阻断，本修复不扩大新任务 init 期行为面。
- 测试与文档同步：`test_sage_linter.py` 新增 4 例（三检查器模板默认值阻断 + `_parse_current_stage` 直测：管道默认行/无 token 非 ASCII 占位/正常值三分支），全量单测 62 → 66 例全绿；CODE_WIKI.md 检查器清单 12/13/15 三行补 TD-9 阻断语义注记。

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


