#!/usr/bin/env python3
"""Codex 适配器子代理生成器：生成 Codex 宿主的 TOML agent 注册文件。

双入口设计：
- 独立运行：`python adapters/codex/provision.py`（默认项目目录 <脚本所在项目根>/.codex/agents）或 `--user`（用户目录 ~/.codex/agents）
- 委托运行：`core/scripts/dispatch_phase.py provision --adapter codex ...`（主入口以 subprocess 调用本脚本，显式传 --target-dir）
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROVISION_ROLES = ("reviewer", "coder", "closer")
ROLE_PHASES = {
    "reviewer": ("plan-review", "code-review"),
    "coder": ("dev",),
    "closer": ("close",),
}


def role_model_id(role: str, models: dict[str, Any]) -> tuple[str | None, str | None]:
    """返回角色的期望模型标识符与告警：审查角色取 plan-review 首个非空，与 code-review 不一致时告警。"""
    phases = ROLE_PHASES[role]
    ids = [models.get(phase, {}).get("id") or None for phase in phases]
    model_id = next((item for item in ids if item), None)
    distinct = {item for item in ids if item}
    warning = None
    if len(distinct) > 1:
        warning = f"{role} 各阶段默认模型不一致：{sorted(distinct)}；已采用 {model_id}"
    if not model_id:
        warning = f"未解析到 {role} 默认模型；请替换 model 字段后再注册"
    return model_id, warning


# 写入注册文件的角色级指令：与派发信封的角色契约互补，只约束执行载体层行为
ROLE_INSTRUCTIONS = {
    "reviewer": (
        "只执行计划或代码盲审。审查报告必须写回角色契约要求的 TASK 章节，"
        "且必须包含 OK/WARN/BLOCK。不得修改其他文件。"
    ),
    "coder": (
        "只实现 TASK 1.1~1.5 冻结范围。你不是代码库中唯一的修改者："
        "不得还原或覆盖他人的修改。"
    ),
    "closer": (
        "只收尾已完成范围：TASK 收尾章节、CHANGELOG、归档。"
        "不新增功能；永不 merge、push、deploy。"
    ),
}


def detect_repo_root() -> Path | None:
    """bootstrap 布局下从脚本自身位置推导项目根目录。

    bootstrap 后脚本位于 `<repo>/docs/guides/execution-adapters/codex/provision.py`，项目根即
    其 parents[4]。只在路径形态精确命中该布局时返回；skill 目录布局
    （`<skill-root>/adapters/codex/provision.py`）返回 None，由调用方回退到当前工作目录，
    避免把 SAGE 仓库自身误判成目标项目（skill 仓库根同样有 AGENTS.md，不能靠它定位）。
    """
    script = Path(__file__).resolve()
    expected_tail = ("docs", "guides", "execution-adapters", "codex", "provision.py")
    if script.parts[-5:] != expected_tail:
        return None
    return script.parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Codex 宿主 TOML agent 注册文件")
    parser.add_argument("--target-dir", type=Path, default=None, help="宿主注册目录（项目 .codex/agents 或用户 ~/.codex/agents）；不指定时，bootstrap 布局下默认 <脚本所在项目根>/.codex/agents，否则 <当前目录>/.codex/agents")
    parser.add_argument("--user", action="store_true", help="部署到宿主用户注册目录（~/.codex/agents），而非项目目录；与 --target-dir 互斥")
    parser.add_argument("--model-provider", help="TOML 模板的 model_provider，默认 codex_shim")
    parser.add_argument("--role", choices=PROVISION_ROLES, help="只生成指定角色；缺省生成全部")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的注册文件")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if args.user and args.target_dir is not None:
        parser.error("--user 与 --target-dir 互斥，不能同时指定")
    if args.user:
        args.target_dir = Path.home() / ".codex" / "agents"
    elif args.target_dir is None:
        repo_root = detect_repo_root()
        args.target_dir = (repo_root if repo_root is not None else Path.cwd()) / ".codex" / "agents"
    return args


def load_models() -> tuple[dict[str, Any], str]:
    """从脚本同目录 codex.json 读取 models 声明；缺失或无效时回退为空并提示人工填写。"""
    candidate = Path(__file__).resolve().parent / "codex.json"
    if not candidate.is_file():
        return {}, f"无（未找到 {candidate}，模型字段需人工填写）"
    try:
        profile = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, f"{candidate}（JSON 无效，模型字段需人工填写）"
    models = profile.get("models", {})
    return (models if isinstance(models, dict) else {}), str(candidate)


def build_toml_agent(role: str, models: dict[str, Any], provider: str) -> tuple[str, str | None]:
    """生成单个角色的 TOML 注册内容；各阶段模型不一致或缺失时返回人工处理警示。"""
    phases = ROLE_PHASES[role]
    model_id, warning = role_model_id(role, models)
    if not model_id:
        model_id = "REPLACE_WITH_MODEL_ID"
    sandbox = "workspace-write"
    sandbox_note = None
    if role == "reviewer":
        sandbox_note = (
            "sandbox_mode=workspace-write：reviewer 必须能写回 TASK 2.x/4.x 审查章节；"
            "写权限已由 developer_instructions 限定为仅 TASK 文档。"
        )
    content = (
        f'name = "sage_{role}"\n'
        f'description = "SAGE {role} subagent for SAGE workflow phases: {", ".join(phases)}."\n'
        "\n"
        f'model = "{model_id}"\n'
        f'model_provider = "{provider}"\n'
        f'sandbox_mode = "{sandbox}"\n'
        "\n"
        'developer_instructions = """\n'
        f"你是 SAGE {role} 子代理。提供了 ROLE_PROMPT 路径时，遵循仓库的 {role} 角色契约。\n"
        "从派发 prompt 中读取 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE；TASK 元数据是调度事实的唯一来源。\n"
        f"{ROLE_INSTRUCTIONS[role]}\n"
        + ("只允许写 TASK 文档（含 2.x/4.x 审查章节），不得改代码、改计划或触碰其他文件。\n" if role == "reviewer" else "")
        + "默认用中文回复，附证据与变更文件清单。\n"
        '"""\n'
    )
    return content, sandbox_note


def _registered_model(content: str) -> str | None:
    """从已存在的 TOML 注册内容中提取 model 字段值；解析不到返回 None。"""
    match = re.search(r'^\s*model\s*=\s*"([^"]*)"', content, flags=re.MULTILINE)
    return match.group(1) if match else None


def provision(args: argparse.Namespace) -> dict[str, Any]:
    """按角色循环生成 sage-<role>.toml；模型写进 TOML 本体，故注册文件与 adapter JSON 的
    models.<phase>.id 是两个真相源：已存在且未 --force 时**不静默跳过**，而是比对两者，
    不一致则显式告警并要求 --force，避免改了 codex.json 却以为已生效的双源漂移。
    """
    target_dir = args.target_dir.resolve()
    roles = [args.role] if args.role else list(PROVISION_ROLES)
    models, models_source = load_models()
    provider = args.model_provider or "codex_shim"

    target_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for role in roles:
        filename = f"sage_{role}.toml"
        content, sandbox_note = build_toml_agent(role, models, provider)
        target_path = target_dir / filename
        expected_model, _ = role_model_id(role, models)
        if target_path.exists() and not args.force:
            registered = _registered_model(target_path.read_text(encoding="utf-8"))
            if expected_model and registered and registered != expected_model:
                results.append({
                    "role": role,
                    "path": str(target_path),
                    "status": "drift",
                    "note": f"注册文件 model={registered}，adapter JSON 要求 {expected_model}；已跳过。加 --force 覆盖以同步",
                })
                continue
            results.append({"role": role, "path": str(target_path), "status": "skipped", "note": "已存在且与 adapter JSON 一致；加 --force 可强制覆盖"})
            continue
        target_path.write_text(content, encoding="utf-8")
        results.append({"role": role, "path": str(target_path), "status": "written", "note": sandbox_note})
    post_steps = [
        "重启或刷新宿主以加载新的 agent 注册；注册是否生效以宿主实际派发结果为准。",
        "注册型模型变更必须同步 adapter JSON（models.<phase>），避免双源漂移；检测到 drift 时加 --force 重新生成。",
        f"目标目录为 {'~/.codex/agents（宿主用户注册目录，--user）' if args.user else '项目 .codex/agents（默认；随仓库版本管理）'}；用户目录为全局配置，请人工确认放置位置。",
    ]
    return {
        "adapter": "codex",
        "target_dir": str(target_dir),
        "models_source": models_source,
        "results": results,
        "post_steps": post_steps,
    }


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
