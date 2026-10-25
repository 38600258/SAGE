#!/usr/bin/env python3
"""Claude Code 适配器子代理生成器：生成项目内 agents 目录的 Markdown 注册文件。

双入口设计：
- 独立运行：`python adapters/claude-code/provision.py`（默认项目目录 <脚本所在项目根>/.claude/agents）或 `--user`（用户目录 ~/.claude/agents）
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

    bootstrap 后脚本位于 `<repo>/docs/guides/execution-adapters/claude-code/provision.py`，项目根即
    其 parents[4]。只在路径形态精确命中该布局时返回；skill 目录布局
    （`<skill-root>/adapters/claude-code/provision.py`）返回 None，由调用方回退到当前工作目录，
    避免把 SAGE 仓库自身误判成目标项目（skill 仓库根同样有 AGENTS.md，不能靠它定位）。
    """
    script = Path(__file__).resolve()
    expected_tail = ("docs", "guides", "execution-adapters", "claude-code", "provision.py")
    if script.parts[-5:] != expected_tail:
        return None
    return script.parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Claude Code Markdown agent 注册文件")
    parser.add_argument("--target-dir", type=Path, default=None, help="宿主注册目录（项目 .claude/agents 或用户 ~/.claude/agents）；不指定时，bootstrap 布局下默认 <脚本所在项目根>/.claude/agents，否则 <当前目录>/.claude/agents")
    parser.add_argument("--user", action="store_true", help="部署到宿主用户注册目录（~/.claude/agents），而非项目目录；与 --target-dir 互斥")
    parser.add_argument("--role", choices=PROVISION_ROLES, help="只生成指定角色；缺省生成全部")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的注册文件")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if args.user and args.target_dir is not None:
        parser.error("--user 与 --target-dir 互斥，不能同时指定")
    if args.user:
        args.target_dir = Path.home() / ".claude" / "agents"
    elif args.target_dir is None:
        repo_root = detect_repo_root()
        args.target_dir = (repo_root if repo_root is not None else Path.cwd()) / ".claude" / "agents"
    return args


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
    """按角色循环生成 sage-<role>.md。

    一律覆盖：Markdown 注册不绑定模型（模型由宿主默认值决定），内容完全由 role 决定，
    不含用户手改价值，故不设跳过保护；`--force` 不再影响它。
    """
    target_dir = args.target_dir.resolve()
    roles = [args.role] if args.role else list(PROVISION_ROLES)
    models_source = load_models_source()

    target_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for role in roles:
        filename = f"sage-{role}.md"
        content = build_markdown_agent(role)
        target_path = target_dir / filename
        target_path.write_text(content, encoding="utf-8")
        results.append({"role": role, "path": str(target_path), "status": "written", "note": None})
    post_steps = [
        "重启或刷新宿主以加载新的 agent 注册；注册是否生效以宿主实际派发结果为准。",
        f"目标目录为 {'~/.claude/agents（宿主用户注册目录，--user）' if args.user else '项目 .claude/agents（默认；随仓库版本管理）'}；用户目录为全局配置，请人工确认放置位置。",
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
