#!/usr/bin/env python3
"""OMP（Oh My Pi）适配器角色路由配置生成器：生成 .omp/ 目录（config.yml + agents/sage_*.md）。

OMP 的模型路由机制（以官方源码 docs/task-agent-discovery.md 为准）：
- `task` 工具派发只设置 `agent`，不设置 worker model；模型由 agent frontmatter 的
  `model` 字段决定（支持 `@角色别名`），优先级：
  `task.agentModelOverrides[agentName]` > agent frontmatter `model` > parent's active model。
- 自定义 agent 放在项目 `.omp/agents/*.md` 或用户 `~/.omp/agent/agents/*.md`，
  frontmatter `model: "@role"` 通过 `modelRoles.<role>` 解析到具体模型。
- `modelRoles` 配置在 `~/.omp/agent/config.yml`（全局）或 `<cwd>/.omp/config.yml`（项目）。

四阶段各自独立 agent + 独立 modelRoles 键：`sage_plan_reviewer`（plan-review）、`sage_coder`（dev）、
`sage_code_reviewer`（code-review）、`sage_closer`（close）。用户可在 omp.json `models.<phase>.id`
为每阶段配置实际模型标识符——两个审查阶段因此可以使用不同模型；想要同一模型时，在
plan-review 与 code-review 两处填同一个 id 即可（脚本不做一致性约束，也不再取「首个非空」）。

本脚本生成（bootstrap 布局下默认写入 <脚本所在项目根>/.omp；--user 写入 ~/.omp/agent 用户目录）：
1. `config.yml` —— modelRoles 段（四个阶段键 + advisor 固定键）
2. `agents/sage_plan_reviewer.md` —— plan-review 用
3. `agents/sage_coder.md` —— dev 用
4. `agents/sage_code_reviewer.md` —— code-review 用
5. `agents/sage_closer.md` —— close 用

双入口设计：
- 独立运行：`python adapters/omp/provision.py`（默认项目目录）或 `--user`（用户目录）
- 委托运行：`core/scripts/dispatch_phase.py provision --adapter omp ...`（主入口以 subprocess 调用本脚本，显式传 --target-dir）
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROVISION_ROLES = ("reviewer", "coder", "closer")

# 阶段 → 角色（--role 过滤与角色正文复用）
PHASE_ROLE: dict[str, str] = {
    "plan-review": "reviewer",
    "dev": "coder",
    "code-review": "reviewer",
    "close": "closer",
}

# 阶段 → modelRoles 角色键 / agent 名（与 omp.json agent_types 值一致；每阶段独立键，可配不同模型）
PHASE_MODEL_ROLE: dict[str, str] = {
    "plan-review": "sage_plan_reviewer",
    "dev": "sage_coder",
    "code-review": "sage_code_reviewer",
    "close": "sage_closer",
}
PHASE_AGENT_NAME: dict[str, str] = PHASE_MODEL_ROLE

# 宿主用户注册目录（--user 部署目标；OMP 用户级结构为 ~/.omp/agent/config.yml + ~/.omp/agent/agents/*.md）
USER_AGENT_DIR: Path = Path.home() / ".omp" / "agent"

AGENT_TOOLS = {
    "reviewer": "read, write, edit, grep, glob, bash, web_search, lsp",
    "coder": "read, write, edit, grep, glob, bash",
    "closer": "read, write, edit, grep, glob, bash",
}

AGENT_DESCRIPTIONS: dict[str, str] = {
    "plan-review": "SAGE reviewer 子代理（plan-review 计划盲审）",
    "dev": "SAGE coder 子代理（dev 阶段实现）",
    "code-review": "SAGE reviewer 子代理（code-review 代码盲审）",
    "close": "SAGE closer 子代理（close 阶段收尾）",
}

ROLE_BODY = {
    "reviewer": (
        "你是 SAGE reviewer 子代理。派发 prompt 会提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE。\n"
        "先定位到 REPO_ROOT，读取 ROLE_PROMPT 与 TASK_PATH，任务调度事实以 TASK 元数据为准；\n"
        "角色职责以 ROLE_PROMPT 指向的当前权威角色契约为唯一来源，本文件不复制角色规则。\n"
        "按 reviewer 角色契约执行计划/代码盲审，报告必须包含 OK/WARN/BLOCK，并写回 TASK 对应阶段章节；\n"
        "只允许写 TASK 文档（含 2.x/4.x 审查章节），不得改代码、改计划或触碰其他文件；\n"
        "stdout、退出码或口头完成不能单独作为成功证据。"
    ),
    "coder": (
        "你是 SAGE coder 子代理。派发 prompt 会提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE。\n"
        "先定位到 REPO_ROOT，读取 ROLE_PROMPT 与 TASK_PATH，任务调度事实以 TASK 元数据为准；\n"
        "角色职责以 ROLE_PROMPT 指向的当前权威角色契约为唯一来源，本文件不复制角色规则。\n"
        "只执行 TASK 1.1~1.5 冻结范围；不得还原或覆盖他人修改；进度和证据写回 TASK 对应阶段章节；\n"
        "完成后必须写回 TASK 对应章节，stdout、退出码或口头完成不能单独作为成功证据。"
    ),
    "closer": (
        "你是 SAGE closer 子代理。派发 prompt 会提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE。\n"
        "先定位到 REPO_ROOT，读取 ROLE_PROMPT 与 TASK_PATH，任务调度事实以 TASK 元数据为准；\n"
        "角色职责以 ROLE_PROMPT 指向的当前权威角色契约为唯一来源，本文件不复制角色规则。\n"
        "只收尾已完成范围：TASK 收尾章节、CHANGELOG、归档；不新增功能；永不 merge、push、deploy；\n"
        "完成后必须写回 TASK 对应章节，stdout、退出码或口头完成不能单独作为成功证据。"
    ),
}


# build_modelroles_block 生成的注释头。merge_config_yml 用它从保留段剥离上一次生成的
# 注释，避免增量合并逐次重复堆积（2026-10-25 实测：裸跑一次 +4 行）。
_GENERATED_HEADER_LINES = (
    "# OMP modelRoles 配置（SAGE 适配器生成）",
    "# 四阶段独立键；模型值来自 omp.json models.<phase>.id，两个审查阶段可分别配置不同模型。",
    "# 跨模型异构盲审：将 plan-review/code-review 阶段的模型配为与 default（主会话模型）不同厂商的模型。",
)


def detect_repo_root() -> Path | None:
    """bootstrap 布局下从脚本自身位置推导项目根目录。

    bootstrap 后脚本位于 `<repo>/docs/guides/execution-adapters/omp/provision.py`，项目根即
    其 parents[4]。只在路径形态精确命中该布局时返回；skill 目录布局
    （`<skill-root>/adapters/omp/provision.py`）返回 None，由调用方回退到当前工作目录，
    避免把 SAGE 仓库自身误判成目标项目（skill 仓库根同样有 AGENTS.md，不能靠它定位）。
    """
    script = Path(__file__).resolve()
    expected_tail = ("docs", "guides", "execution-adapters", "omp", "provision.py")
    if script.parts[-5:] != expected_tail:
        return None
    return script.parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 OMP .omp/ 配置：config.yml（modelRoles）+ agents/sage_*.md（自定义 agent 定义）"
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="OMP 项目配置根目录（应为 <repo>/.omp）；不指定时，bootstrap 布局下默认 <脚本所在项目根>/.omp（与 omp.json 同项目），否则 <当前目录>/.omp；config.yml 写入该根，agent 定义写入 agents/ 子目录",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        help="部署到宿主用户注册目录（~/.omp/agent），而非项目目录；与 --target-dir 互斥",
    )
    parser.add_argument(
        "--role",
        choices=PROVISION_ROLES,
        help="只生成指定角色（reviewer 生成 plan-review + code-review 两个 agent）；缺省生成全部",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的配置文件；不带 --force 时 config.yml 为增量合并（保留非 modelRoles 段，注释头不重复），agent 文件存在时覆盖（内容完全由角色决定，无用户手改价值）",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    args = parser.parse_args()
    if args.user and args.target_dir is not None:
        parser.error("--user 与 --target-dir 互斥，不能同时指定")
    if args.user:
        args.target_dir = USER_AGENT_DIR
    elif args.target_dir is None:
        repo_root = detect_repo_root()
        args.target_dir = (repo_root if repo_root is not None else Path.cwd()) / ".omp"
    return args


def load_omp_json() -> tuple[dict[str, Any], str]:
    """从脚本同目录 omp.json 读取 models 声明（models.<phase>.id 是用户填写的实际模型标识符，如 anthropic/claude-sonnet-4-5）；缺失或无效时回退为空并提示。"""
    candidate = Path(__file__).resolve().parent / "omp.json"
    if not candidate.is_file():
        return {}, f"无（未找到 {candidate}）"
    try:
        profile = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, f"{candidate}（JSON 无效）"
    models = profile.get("models", {}) if isinstance(profile, dict) else {}
    return (models if isinstance(models, dict) else {}), str(candidate)


def phase_model_id(phase: str, models: dict[str, Any]) -> tuple[str | None, str | None]:
    """返回该阶段的模型标识符与告警：只读本阶段 models.<phase>.id，不做跨阶段一致性约束。

    两个审查阶段各有独立 modelRoles 键，因此可以配不同模型；需要同一模型时在
    plan-review 与 code-review 两处填相同 id 即可。
    """
    model_id = models.get(phase, {}).get("id") or None
    if not model_id:
        return None, f"未解析到 {phase} 阶段模型；请在 omp.json models.{phase}.id 填入模型标识符"
    return model_id, None


ADVISOR_LINE = (
    "advisor: <advisor-provider/model>  # 可选第二遍审查角色；在 sage_*.md frontmatter 加 advisor: true 后生效；"
    "配置为第三厂商可实现三重异构审查"
)
_GENERATED_TRAILER_LINES = (
    "# 注意：default 角色由 OMP 运行时设置，本脚本不写入；",
    "#       如需修改 default 模型，请在 config.yml 中单独设置。",
)
# agent frontmatter 中由脚本管理的键；其余键（如用户按文档加的 advisor: true）原样保留
_MANAGED_FRONTMATTER_KEYS = ("name", "description", "tools", "spawns", "model")


def build_modelrole_entries(phases: list[str], models: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """返回「受管键 → 该行内容」映射与告警；只包含本次 phases 对应的键。

    模型值从 omp.json models.<phase>.id 读取（用户填实际模型标识符），逐阶段独立，
    不做跨阶段一致性约束；未填写时写占位符并告警。
    """
    warnings: list[str] = []
    entries: dict[str, str] = {}
    for phase in phases:
        alias = PHASE_MODEL_ROLE[phase]
        model_id, phase_warning = phase_model_id(phase, models)
        if phase_warning:
            warnings.append(phase_warning)
        if model_id:
            entries[alias] = f"{alias}: {model_id}    # SAGE 角色：{PHASE_ROLE[phase]}（阶段：{phase}）"
        else:
            entries[alias] = f"{alias}: <{alias}-provider/model>    # ⚠️ 未配置：请在 omp.json models.{phase}.id 填入模型标识符"
    if not phases:
        warnings.append("未生成任何角色映射")
    return entries, warnings


def render_modelroles_section(entries: dict[str, str]) -> list[str]:
    """渲染全新的 modelRoles 段（含注释头与尾部说明）；仅用于 config.yml 不存在时新建。"""
    lines = [*_GENERATED_HEADER_LINES, "", "modelRoles:"]
    lines.extend(f"  {value}" for value in entries.values())
    lines.append(f"  {ADVISOR_LINE}")
    lines.extend(["", *_GENERATED_TRAILER_LINES])
    return lines


def _section_key(line: str) -> str | None:
    """返回 modelRoles 子键名；注释、空行与非缩进行返回 None。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or line[:1] not in (" ", "\t"):
        return None
    return stripped.split(":", 1)[0].strip() or None


def merge_config_yml(existing_text: str, entries: dict[str, str]) -> tuple[str, list[str]]:
    """按配置键增量合并 config.yml，返回新文本与被保留的用户键名。

    只改写本次生成涉及的 modelRoles 子键（`entries` 的键），其余一律保留：
    - 其他顶层段（settings/task 等）原样保留；
    - modelRoles 下的自定义键原样保留；
    - 用户已填的 `advisor` 原样保留（缺失时才补占位符）；
    - 段内用户注释保留，仅剥离上次生成的注释头/尾部说明，避免逐次堆积。
    这样 `--role` 局部刷新不会再删掉其他阶段的键。
    """
    lines = existing_text.splitlines()
    start = next(
        (i for i, line in enumerate(lines)
         if line[:1] not in (" ", "\t") and line.strip().startswith("modelRoles:")),
        None,
    )
    if start is None:
        preserved = [line for line in lines if line.strip() not in _generated_noise()]
        while preserved and preserved[-1].strip() == "":
            preserved.pop()
        section = render_modelroles_section(entries)
        text = "\n".join(preserved + ([""] if preserved else []) + section) + "\n"
        return text, []

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line and line[:1] not in (" ", "\t") and not line.strip().startswith("#"):
            end = i
            break

    noise = _generated_noise()
    existing_managed: dict[str, str] = {}
    user_lines: list[str] = []
    user_keys: list[str] = []
    for line in lines[start + 1 : end]:
        key = _section_key(line)
        if key is None:
            if line.strip() in noise:
                continue
            user_lines.append(line)
            continue
        if key in _all_managed_aliases():
            # 脚本管理的键：旧行丢弃，稍后按阶段顺序统一重排
            existing_managed.setdefault(key, line)
            continue
        user_keys.append(key)
        user_lines.append(line)
    # 受管键按阶段顺序输出：本次生成的值优先，未涉及的阶段保留原值（--role 局部刷新不丢键）
    kept: list[str] = []
    for alias in _all_managed_aliases():
        if alias in entries:
            kept.append(f"  {entries[alias]}")
        elif alias in existing_managed:
            kept.append(existing_managed[alias])
    if "advisor" not in user_keys:
        kept.append(f"  {ADVISOR_LINE}")
    kept.extend(user_lines)
    while kept and kept[-1].strip() == "":
        kept.pop()

    before = lines[:start]
    # 剥离上一次生成的注释头（可能隔着空行），避免逐次重复堆积
    while before and (before[-1].strip() == "" or before[-1].strip() in noise):
        before.pop()
    rebuilt = [
        *before,
        *([""] if before else []),
        *_GENERATED_HEADER_LINES,
        "",
        "modelRoles:",
        *kept,
        "",
        *_GENERATED_TRAILER_LINES,
    ]
    after = lines[end:]
    if after:
        rebuilt.extend([""] + after)
    return "\n".join(rebuilt) + "\n", user_keys


def _generated_noise() -> set[str]:
    """本脚本生成过、合并时应剥离而不应重复堆积的行（去空白后比较）。"""
    return {line.strip() for line in (*_GENERATED_HEADER_LINES, *_GENERATED_TRAILER_LINES)}


def _all_managed_aliases() -> tuple[str, ...]:
    """脚本管理的全部 modelRoles 键（固定阶段顺序），用于合并时稳定排序与保留未刷新阶段。"""
    return tuple(PHASE_MODEL_ROLE[phase] for phase in PHASE_MODEL_ROLE)


def build_agent_md(phase: str, existing_text: str | None = None) -> str:
    """生成单个阶段的 agent 定义 Markdown（frontmatter + SAGE 角色契约正文）。

    已存在文件时保留用户添加的 frontmatter 键（如按文档加的 `advisor: true`），
    只改写脚本管理的键与正文。
    """
    name = PHASE_AGENT_NAME[phase]
    role = PHASE_ROLE[phase]
    managed = {
        "name": name,
        "description": AGENT_DESCRIPTIONS[phase],
        "tools": AGENT_TOOLS[role],
        "spawns": '"*"',
        "model": f'"@{PHASE_MODEL_ROLE[phase]}"',
    }
    frontmatter: list[str] = []
    if existing_text:
        fm_lines = _frontmatter_lines(existing_text)
        for line in fm_lines:
            key = line.split(":", 1)[0].strip() if ":" in line else None
            if key in _MANAGED_FRONTMATTER_KEYS:
                continue
            frontmatter.append(line)
    for key in _MANAGED_FRONTMATTER_KEYS:
        frontmatter.append(f"{key}: {managed[key]}")
    return (
        "---\n"
        + "\n".join(frontmatter)
        + "\n---\n\n"
        + f"{ROLE_BODY[role]}\n"
    )


def _frontmatter_lines(text: str) -> list[str]:
    """提取 YAML frontmatter 行；没有 frontmatter 时返回空列表。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return [line for line in lines[1:index] if line.strip()]
    return []


def _has_unmanaged_frontmatter(text: str) -> bool:
    """判断已有 agent 文件是否含脚本管理范围外的 frontmatter 键（用户手加）。"""
    return any(
        (line.split(":", 1)[0].strip() if ":" in line else None) not in _MANAGED_FRONTMATTER_KEYS
        for line in _frontmatter_lines(text)
    )


def provision(args: argparse.Namespace) -> dict[str, Any]:
    """按阶段生成 agents/sage_*.md + config.yml。

    写入语义：
    - agent 文件：一律覆盖脚本管理的 frontmatter 键与正文；用户添加的其他 frontmatter 键
      （如按文档加的 `advisor: true`）原样保留。
    - config.yml：不存在→新建；存在+不带 --force→按配置键增量合并（只更新本次生成涉及的
      modelRoles 子键，其他顶层段、自定义 modelRoles 键、用户已填的 advisor 一律保留）；
      存在+--force→整文件覆盖（会丢自定义段，显式告警）
    - 目标目录：bootstrap 布局默认 <脚本所在项目根>/.omp（与 omp.json 同项目）；否则 <当前目录>/.omp；
      --user → ~/.omp/agent（宿主用户注册目录）
    """
    models, models_source = load_omp_json()
    if args.role:
        phases = [phase for phase, role in PHASE_ROLE.items() if role == args.role]
    else:
        phases = list(PHASE_MODEL_ROLE)

    target_dir = args.target_dir.resolve()
    agents_dir = target_dir / "agents"
    target_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for phase in phases:
        target_path = agents_dir / f"{PHASE_AGENT_NAME[phase]}.md"
        existing_agent = target_path.read_text(encoding="utf-8") if target_path.is_file() else None
        target_path.write_text(build_agent_md(phase, existing_agent), encoding="utf-8")
        note = "保留用户添加的 frontmatter 键" if existing_agent and _has_unmanaged_frontmatter(existing_agent) else None
        results.append({"role": f"agent:{phase}", "path": str(target_path), "status": "written", "note": note})

    # config.yml（modelRoles 段）
    entries, warnings = build_modelrole_entries(phases, models)

    config_path = target_dir / "config.yml"
    if config_path.exists() and not args.force:
        existing = config_path.read_text(encoding="utf-8")
        merged, user_keys = merge_config_yml(existing, entries)
        config_path.write_text(merged, encoding="utf-8")
        extra = detect_non_modelroles_sections(existing)
        details = [f"非 modelRoles 段（{extra}）"] if extra else []
        if user_keys:
            details.append(f"modelRoles 用户键（{', '.join(user_keys)}）")
        note = f"增量合并：保留{'、'.join(details)}" if details else "增量合并"
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": note})
    elif config_path.exists() and args.force:
        extra = detect_non_modelroles_sections(config_path.read_text(encoding="utf-8"))
        config_path.write_text("\n".join(render_modelroles_section(entries)) + "\n", encoding="utf-8")
        note = f"警告: --force 整文件覆盖，丢失非 modelRoles 段: {extra}" if extra else None
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": note})
    else:
        config_path.write_text("\n".join(render_modelroles_section(entries)) + "\n", encoding="utf-8")
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": None})

    if warnings:
        warn_text = "; ".join(warnings)
        for item in results:
            if item["role"].startswith("config:") and item["status"] == "written":
                item["note"] = f"警告: {warn_text}" if item["note"] is None else f"{item['note']}; 警告: {warn_text}"

    is_user_dir = target_dir == USER_AGENT_DIR.resolve()
    post_steps = [
        "如 omp.json 中某阶段 models.id 为 null，config.yml 对应阶段角色为占位符 <provider/model>；请在 omp.json 填入实际模型标识符后重新 provision，或直接编辑 config.yml 替换占位符。",
        f"确认 agents/sage_*.md 位于 {'~/.omp/agent/agents/' if is_user_dir else '<repo>/.omp/agents/'} 下；OMP 从该目录发现自定义 agent（项目优先于用户级与内置）。",
        "重启或刷新 OMP；在 /agents 面板确认 sage_plan_reviewer/sage_coder/sage_code_reviewer/sage_closer 可见，在 /model 的 Roles 视图确认同名角色。",
        "跨模型异构盲审：plan-review 与 code-review 各有独立 modelRoles 键，可分别配不同厂商模型；想用同一模型时在两处填相同 id。",
        "config.yml：不带 --force 时增量合并（保留自定义段，只替换 modelRoles 段）；带 --force 时整文件覆盖（会丢失自定义段）。agent 文件一律覆盖，不含手改内容。",
    ]

    return {
        "adapter": "omp",
        "target_dir": str(target_dir),
        "models_source": models_source,
        "results": results,
        "post_steps": post_steps,
    }


def detect_non_modelroles_sections(text: str) -> str | None:
    """检测 config.yml 文本中 modelRoles 段之外的顶层段（如 task/settings 等），返回逗号分隔名称；无额外段返回 None。"""
    extra: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 顶层键判定：无缩进且含冒号
        if not line.startswith((" ", "\t")) and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            if key and key != "modelRoles":
                extra.append(key)
    return ", ".join(sorted(set(extra))) if extra else None


def format_provision(payload: dict[str, Any], output_format: str) -> str:
    """将 provision 结果渲染为 text 或 json；委托执行时由主入口透传 stdout。"""
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = [
        f"adapter: {payload['adapter']}",
        f"target_dir: {payload['target_dir']}",
        f"models_source: {payload['models_source']}",
        "results:",
    ]
    for item in payload["results"]:
        suffix = f"（{item['note']}）" if item.get("note") else ""
        lines.append(f"  {item['role']}: {item['status']} -> {item['path']}{suffix}")
    lines.append("后续步骤:")
    lines.extend(f"  - {step}" for step in payload["post_steps"])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = provision(args)
    print(format_provision(payload, args.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
