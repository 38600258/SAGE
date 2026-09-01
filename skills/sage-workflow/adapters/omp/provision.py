#!/usr/bin/env python3
"""OMP（Oh My Pi）适配器角色路由配置生成器：生成 .omp/ 目录三件套。

OMP 的模型路由机制（以官方源码 docs/task-agent-discovery.md 为准）：
- `task` 工具派发只设置 `agent`，不设置 worker model；模型由 agent frontmatter 的
  `model` 字段决定（支持 `@角色别名`），优先级：
  `task.agentModelOverrides[agentName]` > agent frontmatter `model` > parent's active model。
- 自定义 agent 放在项目 `.omp/agents/*.md` 或用户 `~/.omp/agent/agents/*.md`，
  frontmatter `model: "@role"` 通过 `modelRoles.<role>` 解析到具体模型。
- `modelRoles` 配置在 `~/.omp/agent/config.yml`（全局）或 `<cwd>/.omp/config.yml`（项目）。

本脚本生成（--target-dir 指向 .omp/ 根目录）：
1. `config.yml` —— modelRoles 段；模型值从 omp.json `models.<phase>.id` 读取（用户在 omp.json 填实际模型标识符，如 `anthropic/claude-sonnet-4-5`），未填写时写占位符并告警
2. `agents/sage-reviewer.md` —— plan-review/code-review 用（model: "@sage-slow"）
3. `agents/sage-coder.md` —— dev 用（model: "@sage-task"）
4. `agents/sage-closer.md` —— close 用（model: "@sage-task"）

双入口设计：
- 独立运行：`python adapters/omp/provision.py --target-dir <repo>/.omp`
- 委托运行：`core/scripts/dispatch_phase.py provision --adapter omp ...`
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

# 角色 → modelRoles 角色别名（与 omp.json models.<phase>.id 互证）
AGENT_MODEL_ROLE = {
    "reviewer": "sage-slow",
    "coder": "sage-task",
    "closer": "sage-task",
}

AGENT_TOOLS = {
    "reviewer": "read, grep, glob, bash, web_search, lsp",
    "coder": "read, write, edit, grep, glob, bash",
    "closer": "read, write, edit, grep, glob, bash",
}

AGENT_DESCRIPTIONS = {
    "reviewer": "SAGE reviewer 子代理（plan-review / code-review 阶段盲审）",
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
        required=True,
        type=Path,
        help="OMP 项目配置根目录（应为 <repo>/.omp；config.yml 写入该根，agent 定义写入 agents/ 子目录）",
    )
    parser.add_argument(
        "--role",
        choices=PROVISION_ROLES,
        help="只生成指定角色；缺省生成全部",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的配置文件",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    return parser.parse_args()


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


def build_config_yml(phases: list[str], models: dict[str, Any]) -> tuple[str, list[str]]:
    """生成 config.yml 的 modelRoles 段；按角色别名去重。

    模型值从 omp.json models.<phase>.id 读取（用户填实际模型标识符，如 anthropic/claude-sonnet-4-5）。
    同一别名下多个阶段的模型值必须一致，否则告警。未填写时写占位符并告警。
    """
    warnings: list[str] = []
    # role_alias -> SAGE 阶段列表（保留声明顺序）
    alias_to_phases: dict[str, list[str]] = {}
    # phase -> alias 反查表：ROLE_PHASES[role] 列出该角色的阶段，AGENT_MODEL_ROLE[role] 是其别名
    phase_to_alias: dict[str, str] = {}
    for role, role_phases in ROLE_PHASES.items():
        for p in role_phases:
            phase_to_alias[p] = AGENT_MODEL_ROLE[role]
    # alias -> 用户在 omp.json 填写的模型标识符（同别名多阶段须一致）
    alias_to_model: dict[str, str] = {}
    for phase in phases:
        alias = phase_to_alias[phase]
        json_id = models.get(phase, {}).get("id") or ""
        if json_id:
            if alias in alias_to_model and alias_to_model[alias] != json_id:
                warnings.append(
                    f"角色别名 '{alias}' 下模型值不一致：{alias_to_model[alias]} vs {json_id}（来自 {phase}）"
                )
            else:
                alias_to_model[alias] = json_id
        else:
            if alias not in alias_to_model:
                alias_to_model[alias] = ""  # 占位符
        alias_to_phases.setdefault(alias, []).append(phase)

    lines = [
        "# OMP modelRoles 配置（SAGE 适配器生成）",
        "# 模型值来自 omp.json models.<phase>.id；将本段合并到 OMP config.yml。",
        "# 跨模型异构盲审：将 sage-slow 配置为与 default（主会话模型）不同厂商的模型。",
        "",
        "modelRoles:",
    ]
    for alias, phase_list in alias_to_phases.items():
        model_val = alias_to_model.get(alias, "")
        if model_val:
            lines.append(f"  {alias}: {model_val}    # SAGE 阶段：{', '.join(phase_list)}")
        else:
            lines.append(f"  {alias}: <{alias}-provider/model>    # ⚠️ 未配置：请在 omp.json models 对应阶段填入模型标识符")
            warnings.append(f"角色别名 '{alias}'（阶段 {', '.join(phase_list)}）未在 omp.json 配置模型标识符，已写占位符")
    advisor_desc = "可选第二遍审查角色；在 sage-*.md frontmatter 加 advisor: true 后生效；配置为第三厂商可实现三重异构审查"
    lines.append(f"  advisor: <advisor-provider/model>  # {advisor_desc}")

    lines.extend(
        [
            "",
            "# 注意：default 角色由 OMP 运行时设置，本脚本不写入；",
            "#       如需修改 default 模型，请在 config.yml 中单独设置。",
        ]
    )
    if not alias_to_phases:
        warnings.append("未生成任何角色映射")
    return "\n".join(lines) + "\n", warnings


def build_agent_md(role: str) -> str:
    """生成单个角色的 agent 定义 Markdown（frontmatter + SAGE 角色契约正文）。"""
    phases = ", ".join(ROLE_PHASES[role])
    name = f"sage-{role}"
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {AGENT_DESCRIPTIONS[role]}\n"
        f"tools: {AGENT_TOOLS[role]}\n"
        'spawns: "*"\n'
        f'model: "@{AGENT_MODEL_ROLE[role]}"\n'
        "---\n"
        "\n"
        f"{ROLE_BODY[role]}\n"
    )


def provision(args: argparse.Namespace) -> dict[str, Any]:
    """按角色生成 agents/sage-<role>.md + config.yml；已存在且未 --force 时跳过，保证幂等可重入。"""
    models, models_source = load_omp_json()
    roles = [args.role] if args.role else list(PROVISION_ROLES)

    target_dir = args.target_dir.resolve()
    agents_dir = target_dir / "agents"
    target_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for role in roles:
        content = build_agent_md(role)
        target_path = agents_dir / f"sage-{role}.md"
        if target_path.exists() and not args.force:
            results.append({"role": f"agent:{role}", "path": str(target_path), "status": "skipped", "note": "已存在；使用 --force 覆盖"})
            continue
        target_path.write_text(content, encoding="utf-8")
        results.append({"role": f"agent:{role}", "path": str(target_path), "status": "written", "note": None})

    # config.yml（modelRoles 段）：按被生成角色的阶段收集
    generated_roles = list(PROVISION_ROLES) if not args.role else [args.role]
    generated_phases: list[str] = []
    for role in generated_roles:
        generated_phases.extend(ROLE_PHASES[role])
    config_content, warnings = build_config_yml(generated_phases, models)

    config_path = target_dir / "config.yml"
    if config_path.exists() and not args.force:
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "skipped", "note": "已存在；使用 --force 覆盖"})
    else:
        # ⚠️-3：覆盖前检测已有 config.yml 是否含非 modelRoles 段，提示合并风险
        extra = detect_non_modelroles_sections(config_path) if config_path.exists() else None
        config_path.write_text(config_content, encoding="utf-8")
        note = f"警告: 已覆盖现有 config.yml，丢失非 modelRoles 段: {extra}" if extra else None
        results.append({"role": "config:modelroles", "path": str(config_path), "status": "written", "note": note})

    if warnings:
        warn_text = "; ".join(warnings)
        for item in results:
            if item["status"] == "written":
                item["note"] = f"警告: {warn_text}" if item["note"] is None else f"{item['note']}; 警告: {warn_text}"

    post_steps = [
        "将 config.yml 的 modelRoles 段合并到 OMP 实际配置（全局 ~/.omp/agent/config.yml 或项目 <repo>/.omp/config.yml）。",
        "如 omp.json 中某阶段 models.id 为 null，config.yml 对应角色为占位符 <provider/model>；请在 omp.json 填入实际模型标识符后重新 provision，或直接编辑 config.yml 替换占位符。",
        "确认 agents/sage-*.md 位于 <repo>/.omp/agents/ 下；OMP 从该目录发现自定义 agent（项目优先于用户级与内置）。",
        "重启或刷新 OMP；在 /agents 面板确认 sage-reviewer/sage-coder/sage-closer 可见，在 /model 的 Roles 视图确认 sage-slow/sage-task 角色。",
        "跨模型异构盲审：将 omp.json 中 plan-review/code-review 阶段的 models.id 配置为与 default（主会话模型）不同厂商的模型。",
        "本脚本不修改 OMP 实际配置；所有变更由用户手动合并放置。",
    ]

    return {
        "adapter": "omp",
        "target_dir": str(target_dir),
        "models_source": models_source,
        "results": results,
        "post_steps": post_steps,
    }


def detect_non_modelroles_sections(config_path: Path) -> str | None:
    """检测已存在 config.yml 中 modelRoles 段之外的顶层段（如 task/settings 等），返回逗号分隔名称；无额外段返回 None。"""
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return None
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