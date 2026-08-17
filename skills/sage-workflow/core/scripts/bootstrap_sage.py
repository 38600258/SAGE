#!/usr/bin/env python3
"""将 SAGE skill 默认发行版 bootstrap 到项目仓库。"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from shutil import copy2


CORE_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = CORE_ROOT.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap SAGE 默认发行版")
    parser.add_argument("--repo-root", required=True, type=Path, help="目标仓库根目录")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 SAGE 文件")
    parser.add_argument("--dry-run", action="store_true", help="只显示将要复制的文件")
    parser.add_argument("--skip-hooks", action="store_true", help="跳过 core.hooksPath 配置")
    return parser.parse_args()


def render_entry(content: str) -> str:
    replacements = (
        ("../methodology/", ""),
        ("../guides/", "docs/guides/"),
        ("../templates/", "templates/"),
        ("../prompts/", "prompts/"),
        ("../scaffold/", ""),
        ("../scripts/dispatch_phase.py", "scripts/sage_dispatch.py"),
    )
    for old, new in replacements:
        content = content.replace(old, new)
    return content


def render_project_guide(content: str) -> str:
    return content.replace("../entry/AGENTS.md", "../../AGENTS.md")


def build_plan(repo_root: Path) -> list[tuple[Path, Path, str | None]]:
    plan: list[tuple[Path, Path, str | None]] = []
    for source, target in (
        (CORE_ROOT / "prompts", repo_root / "prompts"),
        (CORE_ROOT / "templates", repo_root / "templates"),
        (CORE_ROOT / "guides", repo_root / "docs" / "guides"),
        (CORE_ROOT / "methodology", repo_root),
        (CORE_ROOT / "scaffold", repo_root),
        (CORE_ROOT / "githooks", repo_root / ".githooks"),
    ):
        for source_file in source.rglob("*"):
            if source_file.is_file():
                relative = source_file.relative_to(source)
                target_file = target / relative
                transform = None
                if source == CORE_ROOT / "guides":
                    transform = "guide"
                plan.append((source_file, target_file, transform))

    for source_file in (SKILL_ROOT / "adapters").glob("*.json"):
        plan.append(
            (
                source_file,
                repo_root / "docs" / "guides" / "execution-adapters" / source_file.name,
                None,
            )
        )

    for script_name, target_name in (
        ("sage_linter.py", "sage_linter.py"),
        ("dispatch_phase.py", "sage_dispatch.py"),
    ):
        plan.append((CORE_ROOT / "scripts" / script_name, repo_root / "scripts" / target_name, None))
    for name in ("AGENTS.md", "AGENTS.override.md", "GEMINI.md"):
        plan.append((CORE_ROOT / "entry" / name, repo_root / name, "entry"))
    return plan


def configure_hooks(repo_root: Path, dry_run: bool) -> None:
    try:
        git_root = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        print("未检测到 Git 仓库，跳过 core.hooksPath 配置。")
        return

    configured = subprocess.run(
        ["git", "-C", str(repo_root), "config", "--show-origin", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
        check=False,
    )
    if configured.returncode == 0 and configured.stdout.strip():
        record = configured.stdout.strip().splitlines()[-1]
        origin, value = record.split("\t", 1) if "\t" in record else ("未知来源", record)
        configured_path = Path(value)
        if not configured_path.is_absolute():
            configured_path = Path(git_root) / configured_path
        desired_path = Path(git_root) / ".githooks"
        if configured_path.resolve() == desired_path.resolve():
            print(f"Git hooks 已启用：{value}（来源：{origin}）")
        else:
            print(f"发现已有 core.hooksPath 配置：{value}（来源：{origin}），不覆盖。")
        return

    if dry_run:
        print("将设置 Git hooks：core.hooksPath=.githooks")
        return

    subprocess.run(
        ["git", "-C", str(repo_root), "config", "--local", "core.hooksPath", ".githooks"],
        check=True,
    )
    print("已自动设置 Git hooks：core.hooksPath=.githooks")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if not repo_root.is_dir():
        raise SystemExit(f"目标仓库不存在：{repo_root}")

    copied = 0
    skipped = 0
    for source, target, transform in build_plan(repo_root):
        if target.exists() and not args.force:
            skipped += 1
            print(f"跳过已存在文件：{target.relative_to(repo_root)}")
            continue
        if args.dry_run:
            print(f"将复制：{source.relative_to(CORE_ROOT)} -> {target.relative_to(repo_root)}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if transform == "entry":
            target.write_text(render_entry(source.read_text(encoding="utf-8")), encoding="utf-8", newline="")
        elif transform == "guide":
            target.write_text(render_project_guide(source.read_text(encoding="utf-8")), encoding="utf-8", newline="")
        else:
            copy2(source, target)
        copied += 1
        print(f"已复制：{target.relative_to(repo_root)}")

    print(f"Bootstrap 完成：复制 {copied} 个文件，跳过 {skipped} 个文件。")
    if args.skip_hooks:
        print("已跳过 Git hooks 配置（--skip-hooks）。")
    else:
        configure_hooks(repo_root, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
