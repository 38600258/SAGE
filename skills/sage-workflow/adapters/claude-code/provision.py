#!/usr/bin/env python3
"""Claude Code 适配器子代理生成器：生成项目内 agents 目录的 Markdown 注册文件。

双入口设计：
- 独立运行：`python adapters/claude-code/provision.py --target-dir <repo>/.claude/agents`
- 委托运行：`core/scripts/dispatch_phase.py provision --adapter claude-code ...`（主入口以 subprocess 调用本脚本）

Markdown 注册不消费模型参数：子代理模型由宿主默认值或注册文件 frontmatter 决定，
角色规则一律以 ROLE_PROMPT 指向的当前权威角色契约为准，本脚本不复制角色规则。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROVISION_ROLES = ("reviewer", "coder", "closer")
ROLE_PHASES = {
    "reviewer": ("plan-review", "code-review"),
    "coder": ("dev",),
    "closer": ("close",),
}

# 写入注册文件的角色级指令：与派发信封的角色契约互补，只约束执行载体层行为
ROLE_INSTRUCTIONS = {
    "reviewer": (
        "Perform plan or code blind review only. Write the review report back to the TASK section "
        "required by the role contract; the report must contain OK/WARN/BLOCK. Do not modify other files."
    ),
    "coder": (
        "Implement only the frozen TASK scope (1.1~1.5). You are not alone in the codebase: "
        "do not revert or overwrite others' changes."
    ),
    "closer": (
        "Close out only completed scope: TASK closeout sections, changelog, archival. "
        "Do not add new features; never merge, push, or deploy."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Claude Code 项目内 Markdown agent 注册文件")
    parser.add_argument("--target-dir", required=True, type=Path, help="宿主注册目录（如 <repo>/.claude/agents）")
    parser.add_argument("--role", choices=PROVISION_ROLES, help="只生成指定角色；缺省生成全部")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的注册文件")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def load_models_source() -> str:
    """读取同目录 claude-code.json 的 models 声明来源，仅用于结果展示；Markdown 生成不消费模型。"""
    candidate = Path(__file__).resolve().parent / "claude-code.json"
    if not candidate.is_file():
        return f"无（未找到 {candidate}）"
    try:
        json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return f"{candidate}（JSON 无效）"
    return str(candidate)


def build_markdown_agent(role: str) -> str:
    """生成单个角色的 Markdown 注册内容：frontmatter 声明名称与工具，正文指向角色契约。"""
    phases = ", ".join(ROLE_PHASES[role])
    return (
        "---\n"
        f"name: sage-{role}\n"
        f"description: SAGE {role} 子代理（阶段：{phases}）。按仓库当前权威 {role} 角色契约执行，产出写回 TASK 对应章节。\n"
        "tools: Read, Write, Edit, Grep, Glob, Bash\n"
        "---\n"
        "\n"
        f"你是 SAGE {role} 子代理。派发 prompt 会提供 REPO_ROOT、TASK_PATH、ROLE_PROMPT、PHASE。\n"
        "先定位到 REPO_ROOT，读取 ROLE_PROMPT 与 TASK_PATH，任务调度事实以 TASK 元数据为准；"
        "角色职责以 ROLE_PROMPT 指向的当前权威角色契约为唯一来源，本文件不复制角色规则。\n"
        f"{ROLE_INSTRUCTIONS[role]}\n"
    )


def provision(args: argparse.Namespace) -> dict[str, Any]:
    """按角色循环生成 sage-<role>.md；已存在且未 --force 时跳过，保证幂等可重入。"""
    target_dir = args.target_dir.resolve()
    roles = [args.role] if args.role else list(PROVISION_ROLES)
    models_source = load_models_source()

    target_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for role in roles:
        filename = f"sage-{role}.md"
        content = build_markdown_agent(role)
        target_path = target_dir / filename
        if target_path.exists() and not args.force:
            results.append({"role": role, "path": str(target_path), "status": "skipped", "note": "已存在；使用 --force 覆盖"})
            continue
        target_path.write_text(content, encoding="utf-8")
        results.append({"role": role, "path": str(target_path), "status": "written", "note": None})
    post_steps = [
        "重启或刷新宿主以加载新的 agent 注册；注册是否生效以宿主实际派发结果为准。",
        "确认宿主会扫描项目 agents 目录（如 .claude/agents）；注册文件随仓库版本化分发。",
        "Markdown 注册不绑定模型；模型由宿主默认值决定，如需固定模型请在注册文件 frontmatter 中人工补充。",
    ]
    return {
        "adapter": "claude-code",
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
