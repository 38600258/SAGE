#!/usr/bin/env python3
"""OMP（Oh My Pi）适配器角色路由配置生成器：生成 .omp/ 目录三件套。

OMP 的模型路由机制（以官方源码 docs/task-agent-discovery.md 为准）：
- `task` 工具派发只设置 `agent`，不设置 worker model；模型由 agent frontmatter 的
  `model` 字段决定（支持 `@角色别名`），优先级：
  `task.agentModelOverrides[agentName]` > agent frontmatter `model` > parent's active model。
- 自定义 agent 放在项目 `.omp/agents/*.md` 或用户 `~/.omp/agent/agents/*.md`，
  frontmatter `model: "@role"` 通过 `modelRoles.<role>` 解析到具体模型。
- `modelRoles` 配置在 `~/.omp/agent/config.yml`（全局）或 `<cwd>/.omp/config.yml`（项目）。

三角色架构：与 codex 适配器一致——`sage_reviewer` 覆盖 plan-review + code-review 两阶段，
`sage_coder` 覆盖 dev，`sage_closer` 覆盖 close。用户可在 omp.json `models.<phase>.id`
为每阶段配置实际模型标识符；审查两阶段共用 `sage_reviewer` 键，模型取 plan-review 的
首个非空值，若 code-review 与 plan-review 不一致则告警（对齐 codex build_toml_agent 语义）。

本脚本生成（默认写入 <当前目录>/.omp 项目目录，--user 写入 ~/.omp/agent 用户目录）：
1. `config.yml` —— modelRoles 段（sage_reviewer/sage_coder/sage_closer + advisor 固定键）
2. `agents/sage_reviewer.md` —— 审查（plan-review + code-review）用
3. `agents/sage_coder.md` —— dev 用
4. `agents/sage_closer.md` —— close 用

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
ROLE_PHASES: dict[str, tuple[str, ...]] = {
    "reviewer": ("plan-review", "code-review"),
    "coder": ("dev",),
    "closer": ("close",),
}

# 角色 → modelRoles 角色键（与 omp.json agent_types 值一致；审查共用 sage_reviewer 键）
ROLE_MODEL_ROLE: dict[str, str] = {
    "reviewer": "sage_reviewer",
    "coder": "sage_coder",
    "closer": "sage_closer",
}

# 宿主用户注册目录（--user 部署目标；OMP 用户级结构为 ~/.omp/agent/config.yml + ~/.omp/agent/agents/*.md）
USER_AGENT_DIR: Path = Path.home() / ".omp" / "agent"

# 角色 → agent 名（frontmatter name；与 omp.json agent_types 值一致）
ROLE_AGENT_NAME: dict[str, str] = ROLE_MODEL_ROLE

AGENT_TOOLS = {
    "reviewer": "read, grep, glob, bash, web_search, lsp",
    "coder": "read, write, edit, grep, glob, bash",
    "closer": "read, write, edit, grep, glob, bash",
}

AGENT_DESCRIPTIONS: dict[str, str] = {
    "reviewer": "SAGE reviewer 子代理（plan-review 计划盲审 + code-review 代码盲审）",
    "coder": "SAGE coder 子代理（dev 阶段实现）",
    "closer": "SAGE closer 子代理（close 阶段收尾）",
}

ROLE_BODY = {
    "reviewer": (
        "你是 SAGE reviewer 子代理。派发 prompt 会提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE。\n"
        "先定位到 REPO_ROOT，读取 ROLE_PROMPT 与 TASK_PATH，任务调度事实以 TASK 元数据为准；\n"
        "角色职责以 ROLE_PROMPT 指向的当前权威角色契约为唯一来源，本文件不复制角色规则。\n"
        "按 reviewer 角色契约执行计划/代码盲审，报告必须包含 OK/WARN/BLOCK，并写回 TASK 对应阶段章节；\n"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 OMP .omp/ 目录三件套：config.yml（modelRoles）+ agents/sage-*.md（自定义 agent 定义）"
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="OMP 项目配置根目录（应为 <repo>/.omp）；不指定时默认 <当前目录>/.omp；config.yml 写入该根，agent 定义写入 agents/ 子目录",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        help="部署到宿主用户注册目录（~/.omp/agent），而非项目目录；与 --target-dir 互斥",
    )
    parser.add_argument(
        "--role",
        choices=PROVISION_ROLES,
        help="只生成指定角色（reviewer 生成 sage_reviewer 一个 agent）；缺省生成全部",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖已存在的配置文件；不带 --force 时 config.yml 为增量合并（保留非 modelRoles 段），agent 文件存在时跳过",
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
        args.target_dir = Path.cwd() / ".omp"
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


def role_model_id(role: str, models: dict[str, Any]) -> tuple[str | None, str | None]:
    """返回角色的模型标识符与告警：审查角色取 plan-review 首个非空，与 code-review 不一致时告警。"""
    phases = ROLE_PHASES[role]
    ids = [models.get(phase, {}).get("id") or None for phase in phases]
    model_id = next((item for item in ids if item), None)
    distinct = {item for item in ids if item}
    warning = None
    if len(distinct) > 1:
        warning = f"{role} 各阶段默认模型不一致：{sorted(distinct)}；已采用 {model_id}"
    if not model_id:
        warning = f"未解析到 {role} 默认模型；请在 omp.json 对应阶段 models.id 填入模型标识符"
    return model_id, warning


def build_modelroles_block(roles: list[str], models: dict[str, Any]) -> tuple[str, list[str]]:
    """生成 config.yml 的 modelRoles 段文本（含 modelRoles: 键和子键）；三角色独立键 + advisor 固定键。

    模型值从 omp.json models.<phase>.id 读取（用户填实际模型标识符）。
    审查角色共用 sage_reviewer 键，模型取 plan-review 首个非空；未填写时写占位符并告警。
    """
    warnings: list[str] = []
    lines = [
        "# OMP modelRoles 配置（SAGE 适配器生成）",
        "# 三角色独立键；审查（sage_reviewer）覆盖 plan-review+code-review 两阶段，模型值来自 omp.json models.<phase>.id。",
        "# 跨模型异构盲审：将 plan-review/code-review 阶段的模型配为与 default（主会话模型）不同厂商的模型。",
        "",
        "modelRoles:",
    ]
    for role in roles:
        alias = ROLE_MODEL_ROLE[role]
        model_id, role_warning = role_model_id(role, models)
        if role_warning:
            warnings.append(role_warning)
        if model_id:
            lines.append(f"  {alias}: {model_id}    # SAGE 角色：{role}（阶段：{'/'.join(ROLE_PHASES[role])}）")
        else:
            lines.append(f"  {alias}: <{alias}-provider/model>    # ⚠️ 未配置：请在 omp.json 对应阶段 models.id 填入模型标识符")
    advisor_desc = "可选第二遍审查角色；在 sage-*.md frontmatter 加 advisor: true 后生效；配置为第三厂商可实现三重异构审查"
    lines.append(f"  advisor: <advisor-provider/model>  # {advisor_desc}")
    lines.extend(
        [
            "",
            "# 注意：default 角色由 OMP 运行时设置，本脚本不写入；",
            "#       如需修改 default 模型，请在 config.yml 中单独设置。",
        ]
    )
    if not roles:
        warnings.append("未生成任何角色映射")
    return "\n".join(lines) + "\n", warnings


def build_agent_md(role: str) -> str:
    """生成单个角色的 agent 定义 Markdown（frontmatter + SAGE 角色契约正文）。"""
    name = ROLE_AGENT_NAME[role]
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {AGENT_DESCRIPTIONS[role]}\n"
        f"tools: {AGENT_TOOLS[role]}\n"
        'spawns: "*"\n'
        f'model: "@{ROLE_MODEL_ROLE[role]}"\n'
        "---\n"
        "\n"
        f"{ROLE_BODY[role]}\n"
    )


def merge_config_yml(existing_text: str, new_modelroles_block: str) -> str:
    """增量合并：保留已有 config.yml 中非 modelRoles 段，替换 modelRoles 段为新生成内容。

    策略：逐行扫描，提取 modelRoles: 到下一个顶层键之间的行（即旧 modelRoles 段），
    其余行（含注释、空行、其他段）保留；最终输出 = 保留段 + 新 modelRoles 段。
    """
    preserved: list[str] = []
    in_modelroles = False
    for line in existing_text.splitlines():
        stripped = line.strip()
        # 顶层键判定：无缩进且含冒号
        if not line.startswith((" ", "\t")) and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            in_modelroles = (key == "modelRoles")
            if not in_modelroles:
                preserved.append(line)
            # modelRoles 行本身被丢弃（由 new_block 替换）
            continue
        # 非顶层行：在 modelRoles 段内则丢弃，在其他段内则保留
        if in_modelroles:
            continue
        preserved.append(line)
    # 清理末尾多余空行
    while preserved and preserved[-1].strip() == "":
        preserved.pop()
    if preserved:
        return "\n".join(preserved) + "\n\n" + new_modelroles_block
    return new_modelroles_block


def provision(args: argparse.Namespace) -> dict[str, Any]:
    """按角色生成 agents/sage-<role>.md + config.yml。

    写入语义：
    - agent 文件：不存在→写入；存在+不带 --force→skipped；存在+--force→覆盖
    - config.yml：不存在→写入（新建）；存在+不带 --force→增量合并（保留非 modelRoles 段，替换 modelRoles 段）；存在+--force→整文件覆盖
    - 目标目录：默认 <当前目录>/.omp（项目）；--user → ~/.omp/agent（宿主用户注册目录）
    """
    models, models_source = load_omp_json()
    roles = [args.role] if args.role else list(PROVISION_ROLES)

    target_dir = args.target_dir.resolve()
    agents_dir = target_dir / "agents"
    target_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for role in roles:
        content = build_agent_md(role)
        target_path = agents_dir / f"{ROLE_AGENT_NAME[role]}.md"
        if target_path.exists() and not args.force:
            results.append({"role": f"agent:{role}", "path": str(target_path), "status": "skipped", "note": "已存在；使用 --force 覆盖"})
            continue
        target_path.write_text(content, encoding="utf-8")
        results.append({"role": f"agent:{role}", "path": str(target_path), "status": "written", "note": None})

    # config.yml（modelRoles 段）
    modelroles_block, warnings = build_modelroles_block(roles, models)

    config_path = target_dir / "config.yml"
    if config_path.exists() and not args.force:
        # 增量合并：保留非 modelRoles 段，替换 modelRoles 段
        existing = config_path.read_text(encoding="utf-8")
        merged = merge_config_yml(existing, modelroles_block)
        config_path.write_text(merged, encoding="utf-8")
        extra = detect_non_modelroles_sections(existing)
        note = f"增量合并：保留非 modelRoles 段（{extra}）" if extra else "增量合并"
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": note})
    elif config_path.exists() and args.force:
        # --force：整文件覆盖（丢失非 modelRoles 段，已告警）
        extra = detect_non_modelroles_sections(config_path.read_text(encoding="utf-8"))
        config_path.write_text(modelroles_block, encoding="utf-8")
        note = f"警告: --force 整文件覆盖，丢失非 modelRoles 段: {extra}" if extra else None
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": note})
    else:
        # 不存在 → 新建
        config_path.write_text(modelroles_block, encoding="utf-8")
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": None})

    if warnings:
        warn_text = "; ".join(warnings)
        for item in results:
            if item["role"].startswith("config:") and item["status"] == "written":
                item["note"] = f"警告: {warn_text}" if item["note"] is None else f"{item['note']}; 警告: {warn_text}"

    is_user_dir = target_dir == USER_AGENT_DIR.resolve()
    post_steps = [
        "如 omp.json 中某阶段 models.id 为 null，config.yml 对应阶段角色为占位符 <provider/model>；请在 omp.json 填入实际模型标识符后重新 provision，或直接编辑 config.yml 替换占位符。",
        f"确认 agents/sage-*.md 位于 {'~/.omp/agent/agents/' if is_user_dir else '<repo>/.omp/agents/'} 下；OMP 从该目录发现自定义 agent（项目优先于用户级与内置）。",
        "重启或刷新 OMP；在 /agents 面板确认 sage_reviewer/sage_coder/sage_closer 可见，在 /model 的 Roles 视图确认同名角色。",
        "跨模型异构盲审：将 omp.json 中 plan-review/code-review 阶段的 models.id 配置为与 default（主会话模型）不同厂商的模型（两阶段共用 sage_reviewer 键，取 plan-review 值）。",
        "不带 --force 时 config.yml 为增量合并（保留非 modelRoles 段）；带 --force 时整文件覆盖。",
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
