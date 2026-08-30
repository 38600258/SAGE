#!/usr/bin/env python3
"""为 SAGE 阶段生成跨宿主派发信封，并验证 TASK/Git 真实产出。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
PHASES = {
    "plan-review": {
        "role": "reviewer",
        "section": "2",
        "instruction": "按 reviewer 角色契约执行计划盲审，将报告写回 TASK 2.x，必须包含 OK/WARN/BLOCK。",
    },
    "dev": {
        "role": "coder",
        "section": "3",
        "instruction": "只执行 TASK 1.1~1.5 冻结范围，将进度和验证证据写回 TASK 3.x；不得还原或覆盖他人修改。",
    },
    "code-review": {
        "role": "reviewer",
        "section": "4",
        "instruction": "按 reviewer 角色契约执行代码盲审，将报告写回 TASK 4.x，必须包含 OK/WARN/BLOCK。",
    },
    "close": {
        "role": "closer",
        "section": "5",
        "instruction": "只做收尾归档、质量门禁和中文提交；严禁新增功能，严禁 merge、push、deploy。",
    },
}
ALLOWED_CONTEXT_FIELDS = ("REPO_ROOT", "TASK_PATH", "ROLE_PROMPT", "PHASE", "DIFF_CMD")
SUBAGENT_MODEL_BINDINGS = {"none", "request", "agent-registration"}
CLI_MODEL_BINDINGS = {"none", "command-argument"}
CHANNEL_PRIORITY = {"subagent": 3, "injected": 2, "cli": 1}
PROVISION_ROLES = ("reviewer", "coder", "closer")


class DispatchError(RuntimeError):
    """表示派发配置、上下文或产出验证不满足契约。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SAGE 跨宿主阶段派发器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capabilities = subparsers.add_parser("capabilities", help="查看 adapter 能力")
    add_adapter_args(capabilities, require_repo=False)
    capabilities.add_argument("--format", choices=("text", "json"), default="text")

    prepare = subparsers.add_parser("prepare", help="生成派发信封与派发前回执")
    add_adapter_args(prepare, require_repo=True)
    prepare.add_argument("--task-path", required=True, type=Path, help="TASK 文档路径")
    prepare.add_argument("--phase", required=True, choices=tuple(PHASES), help="目标阶段")
    prepare.add_argument("--channel", choices=("auto", "subagent", "injected", "cli"), default="auto")
    prepare.add_argument("--diff-cmd", help="代码审查阶段使用的 diff 命令")
    prepare.add_argument("--model", help="指定当前阶段执行模型；是否可覆盖由 adapter 绑定方式决定")
    prepare.add_argument("--fallback-reason", help="从原生 subagent 切换 CLI 的失败记录")
    prepare.add_argument("--fallback-authorized", action="store_true", help="确认 CLI fallback 已获授权")
    prepare.add_argument("--allow-phase-mismatch", action="store_true", help="允许 TASK 当前阶段与目标阶段不同")
    prepare.add_argument("--state-dir", type=Path, help="回执目录，默认位于系统临时目录")
    prepare.add_argument("--format", choices=("text", "json"), default="text")

    verify = subparsers.add_parser("verify", help="验证 TASK/Git 是否出现有效产出")
    verify.add_argument("--receipt", required=True, type=Path, help="prepare 生成的回执")
    verify.add_argument("--skip-close-commit-check", action="store_true", help="跳过 close 阶段提交检查")
    verify.add_argument("--format", choices=("text", "json"), default="text")

    status = subparsers.add_parser("status", help="查看派发回执状态")
    status.add_argument("--receipt", required=True, type=Path)
    status.add_argument("--format", choices=("text", "json"), default="text")

    cancel = subparsers.add_parser("cancel", help="标记派发取消")
    cancel.add_argument("--receipt", required=True, type=Path)
    cancel.add_argument("--reason", required=True, help="取消原因")
    cancel.add_argument("--format", choices=("text", "json"), default="text")

    run_cli = subparsers.add_parser("run-cli", help="执行 CLI 派发并立即验证")
    run_cli.add_argument("--receipt", required=True, type=Path)
    run_cli.add_argument("--command-json", help="无 shell 命令数组 JSON；优先于 adapter/env")
    run_cli.add_argument("--timeout", type=int, default=3600, help="CLI 超时秒数")
    run_cli.add_argument("--skip-close-commit-check", action="store_true")
    run_cli.add_argument("--format", choices=("text", "json"), default="text")

    doctor = subparsers.add_parser("doctor", help="探测各执行通道的运行时可用性")
    add_adapter_args(doctor, require_repo=False)
    doctor.add_argument("--format", choices=("text", "json"), default="text")

    provision = subparsers.add_parser("provision", help="生成宿主 agent 注册文件（委托适配器 provision.py 执行）")
    provision.add_argument("--adapter", required=True, help="adapter 名称（如 codex、claude-code）")
    provision.add_argument("--repo-root", type=Path, help="项目根目录；提供时优先使用项目本地 execution-adapters 下的 provision.py")
    provision.add_argument("--target-dir", required=True, type=Path, help="宿主注册目录（如 ~/.codex/agents 或项目 .claude/agents）")
    provision.add_argument("--model-provider", help="TOML 模板的 model_provider（仅 codex 适配器消费），默认 codex_shim")
    provision.add_argument("--role", choices=PROVISION_ROLES, help="只生成指定角色；缺省生成全部")
    provision.add_argument("--force", action="store_true", help="覆盖已存在的注册文件")
    provision.add_argument("--format", choices=("text", "json"), default="text")

    return parser.parse_args()


def add_adapter_args(parser: argparse.ArgumentParser, require_repo: bool) -> None:
    parser.add_argument("--adapter", default="codex", help="adapter 名称")
    parser.add_argument("--adapter-file", type=Path, help="显式 adapter JSON 路径")
    parser.add_argument("--repo-root", required=require_repo, type=Path, help="仓库根目录")


def discover_skill_root() -> Path | None:
    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if (parent / "SKILL.md").is_file() and (parent / "adapters").is_dir():
            return parent
    return None


def ensure_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise DispatchError(f"{label} 必须位于仓库内：{resolved}") from exc
    return resolved


def profile_candidates(adapter: str, repo_root: Path | None) -> list[Path]:
    """按"项目本地优先、Skill 内置兜底"返回 adapter JSON 候选路径（子目录结构 <id>/<id>.json）。"""
    candidates: list[Path] = []
    if repo_root:
        candidates.append(repo_root / "docs" / "guides" / "execution-adapters" / adapter / f"{adapter}.json")
    skill_root = discover_skill_root()
    if skill_root:
        candidates.append(skill_root / "adapters" / adapter / f"{adapter}.json")
    return candidates


def load_profile(adapter: str, repo_root: Path | None, adapter_file: Path | None) -> tuple[dict[str, Any], Path]:
    candidates = [adapter_file.resolve()] if adapter_file else profile_candidates(adapter, repo_root)
    for candidate in candidates:
        if candidate and candidate.is_file():
            try:
                profile = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise DispatchError(f"adapter JSON 无效：{candidate}: {exc}") from exc
            validate_profile(profile, candidate)
            return profile, candidate
    searched = "、".join(str(path) for path in candidates) or "未发现候选路径"
    raise DispatchError(f"找不到 adapter '{adapter}'：{searched}")


def validate_profile(profile: dict[str, Any], path: Path) -> None:
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise DispatchError(f"adapter schema_version 必须为 {SCHEMA_VERSION}：{path}")
    if not isinstance(profile.get("id"), str) or not profile["id"]:
        raise DispatchError(f"adapter 缺少 id：{path}")
    native = profile.get("native_subagent")
    cli = profile.get("cli")
    if not isinstance(native, dict) or not isinstance(native.get("supported"), bool):
        raise DispatchError(f"adapter 缺少 native_subagent.supported：{path}")
    if not isinstance(cli, dict) or not isinstance(cli.get("supported"), bool):
        raise DispatchError(f"adapter 缺少 cli.supported：{path}")
    agent_types = native.get("agent_types", {})
    if native["supported"]:
        missing = [phase for phase in PHASES if not agent_types.get(phase)]
        if missing:
            raise DispatchError(f"adapter 缺少阶段 agent_type：{', '.join(missing)}")

    injected = profile.get("injected_subagent")
    if injected is not None:
        if not isinstance(injected, dict) or not isinstance(injected.get("supported"), bool):
            raise DispatchError(f"adapter injected_subagent.supported 必须是布尔值：{path}")
        if injected["supported"]:
            injected_types = injected.get("agent_types", {})
            missing = [phase for phase in PHASES if not (isinstance(injected_types, dict) and injected_types.get(phase))]
            if missing:
                raise DispatchError(f"adapter 缺少注入式阶段 agent_type：{', '.join(missing)}")

    models = profile.get("models", {})
    if not isinstance(models, dict):
        raise DispatchError(f"adapter models 必须是对象：{path}")
    unknown_phases = sorted(set(models) - set(PHASES))
    if unknown_phases:
        raise DispatchError(f"adapter models 包含未知阶段：{', '.join(unknown_phases)}")
    for phase, model_config in models.items():
        if not isinstance(model_config, dict):
            raise DispatchError(f"adapter models.{phase} 必须是对象：{path}")
        model_id = model_config.get("id")
        if model_id is not None and (not isinstance(model_id, str) or not model_id.strip()):
            raise DispatchError(f"adapter models.{phase}.id 必须是非空字符串或 null：{path}")
        subagent_binding = model_config.get("subagent_binding", "none")
        cli_binding = model_config.get("cli_binding", "none")
        if subagent_binding not in SUBAGENT_MODEL_BINDINGS:
            raise DispatchError(
                f"adapter models.{phase}.subagent_binding 无效：{subagent_binding}"
            )
        if cli_binding not in CLI_MODEL_BINDINGS:
            raise DispatchError(f"adapter models.{phase}.cli_binding 无效：{cli_binding}")
        if subagent_binding == "agent-registration" and not model_id:
            raise DispatchError(
                f"adapter models.{phase} 使用 agent-registration 时必须声明 id：{path}"
            )


def resolve_role_prompt(repo_root: Path, role: str) -> Path:
    project_prompt = repo_root / "prompts" / f"{role}.md"
    if project_prompt.is_file():
        return project_prompt.resolve()
    skill_root = discover_skill_root()
    if skill_root:
        core_prompt = skill_root / "core" / "prompts" / f"{role}.md"
        if core_prompt.is_file():
            return core_prompt.resolve()
    raise DispatchError(f"找不到 {role} 角色契约；请先 bootstrap SAGE 或提供项目本地 prompts/{role}.md")


def parse_task_metadata(content: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    patterns = {
        "task_level": r"(?m)^-\s*\*\*(?:风险等级|TASK_LEVEL|Task Level).*?\*\*:\s*(L[0-3])\s*$",
        "current_phase": r"(?m)^-\s*\*\*(?:当前阶段|Current Phase).*?\*\*:\s*([a-z-]+)\s*$",
        "repo_root": r"(?m)^-\s*\*\*(?:项目根目录|Repository Root).*?\*\*:\s*(.+?)\s*$",
        "branch": r"(?m)^-\s*\*\*(?:功能分支|Feature Branch).*?\*\*:\s*(.+?)\s*$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()
    metadata.setdefault("task_level", "L2")
    return metadata


def require_task_gate(content: str, phase: str) -> None:
    if parse_task_metadata(content)["task_level"] == "L0":
        raise DispatchError("L0 不允许调用 CLI/subagent，应由 Main Agent 直接执行")
    missing = []
    for section in ("1.1", "1.2", "1.3", "1.4", "1.5"):
        if not re.search(rf"(?m)^###\s+{re.escape(section)}(?:\s|\b)", content):
            missing.append(section)
    if missing:
        raise DispatchError(f"TASK 1.1~1.5 尚未冻结，缺少章节：{', '.join(missing)}")
    if phase == "code-review" and not re.search(r"(?m)^###\s+3\.2(?:\s|\b)", content):
        raise DispatchError("代码审查前 TASK 3.2 必须存在验证证据")


def resolve_injected_agent_types(profile: dict[str, Any]) -> dict[str, str]:
    injected = profile.get("injected_subagent", {})
    agent_types = injected.get("agent_types", {})
    if not isinstance(agent_types, dict):
        raise DispatchError("adapter injected_subagent.agent_types 必须是对象")
    resolved: dict[str, str] = {}
    for phase in PHASES:
        agent_type = agent_types.get(phase)
        if not isinstance(agent_type, str) or not agent_type.strip():
            raise DispatchError(f"adapter 缺少 injected_subagent.agent_types.{phase}")
        resolved[phase] = agent_type
    return resolved


def choose_channel(
    profile: dict[str, Any],
    requested: str,
    fallback_reason: str | None,
    fallback_authorized: bool,
) -> str:
    native_supported = profile["native_subagent"]["supported"]
    injected_supported = bool(profile.get("injected_subagent", {}).get("supported"))
    cli_supported = profile["cli"]["supported"]
    if requested == "auto":
        supported = [
            channel
            for channel, ok in (
                ("subagent", native_supported),
                ("injected", injected_supported),
                ("cli", cli_supported),
            )
            if ok
        ]
        if not supported:
            raise DispatchError("adapter 未声明可用的 subagent、注入式 subagent 或 CLI 通道")
        return max(supported, key=lambda channel: CHANNEL_PRIORITY[channel])
    if requested == "subagent":
        if not native_supported:
            raise DispatchError("adapter 不支持原生 subagent；请使用注入式 subagent、CLI 或提供项目 adapter 覆盖")
        return "subagent"
    if requested == "injected":
        if not injected_supported:
            raise DispatchError("adapter 未声明注入式 subagent 支持；请在项目 adapter 中配置 injected_subagent")
        resolve_injected_agent_types(profile)
        return "injected"
    if not cli_supported:
        raise DispatchError("adapter 不支持 CLI 通道")
    higher = [
        channel
        for channel, ok in (("subagent", native_supported), ("injected", injected_supported))
        if ok and CHANNEL_PRIORITY[channel] > CHANNEL_PRIORITY["cli"]
    ]
    if higher and (not fallback_reason or not fallback_authorized):
        raise DispatchError(
            "从更高优先级通道（原生/注入式 subagent）切换 CLI 必须同时提供 --fallback-reason 和 --fallback-authorized"
        )
    return "cli"


def resolve_model(
    profile: dict[str, Any],
    phase: str,
    channel: str,
    requested_model: str | None,
) -> dict[str, str | None]:
    model_config = profile.get("models", {}).get(phase, {})
    default_model = model_config.get("id")
    binding_key = "subagent_binding" if channel == "subagent" else "cli_binding"
    binding = model_config.get(binding_key, "none")

    if requested_model and binding == "none":
        raise DispatchError(f"adapter 未声明 {phase} 阶段 {channel} 通道支持指定模型")
    if channel == "subagent" and binding == "agent-registration" and requested_model:
        if requested_model != default_model:
            raise DispatchError(
                "当前 subagent 模型由宿主 Agent 注册固定；请同步修改 adapter JSON 与宿主 Agent 注册配置，"
                "不能通过单次 --model 覆盖"
            )

    selected_model = requested_model or default_model
    source = "argument" if requested_model else "adapter" if default_model else "unspecified"
    return {
        "requested": selected_model,
        "binding": binding,
        "source": source,
    }


def build_context(
    repo_root: Path,
    task_path: Path,
    role_prompt: Path,
    phase: str,
    diff_cmd: str | None,
) -> dict[str, str]:
    context = {
        "REPO_ROOT": str(repo_root),
        "TASK_PATH": str(task_path),
        "ROLE_PROMPT": str(role_prompt),
        "PHASE": phase,
    }
    if diff_cmd:
        context["DIFF_CMD"] = diff_cmd
    return context


def build_prompt(context: dict[str, str], phase: str) -> str:
    lines = [f"{key}={context[key]}" for key in ALLOWED_CONTEXT_FIELDS if key in context]
    lines.extend(
        (
            "",
            "请先定位到 REPO_ROOT，读取 ROLE_PROMPT 和 TASK_PATH，从 TASK 元数据获取其他调度信息。",
            PHASES[phase]["instruction"],
            "完成后必须写回 TASK 对应章节；stdout、退出码或口头完成不能单独作为成功证据。",
        )
    )
    return "\n".join(lines)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo_root: Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def git_head(repo_root: Path) -> str | None:
    result = run_git(repo_root, ["rev-parse", "HEAD"])
    return result.stdout.decode("utf-8", errors="replace").strip() if result.returncode == 0 else None


def git_branch(repo_root: Path) -> str | None:
    result = run_git(repo_root, ["branch", "--show-current"])
    return result.stdout.decode("utf-8", errors="replace").strip() if result.returncode == 0 else None


def git_fingerprint(repo_root: Path) -> str | None:
    probe = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    if probe.returncode != 0:
        return None
    digest = hashlib.sha256()
    diff_commands = (
        (["diff", "--binary", "--no-ext-diff", "HEAD", "--"], ["diff", "--binary", "--no-ext-diff", "--"]),
        (["diff", "--binary", "--cached", "--no-ext-diff", "HEAD", "--"], ["diff", "--binary", "--cached", "--no-ext-diff", "--"]),
    )
    has_head = git_head(repo_root) is not None
    for with_head, without_head in diff_commands:
        result = run_git(repo_root, with_head if has_head else without_head)
        digest.update(result.stdout)
    untracked = run_git(repo_root, ["ls-files", "--others", "--exclude-standard", "-z"])
    for raw_path in sorted(part for part in untracked.stdout.split(b"\0") if part):
        relative = raw_path.decode("utf-8", errors="surrogateescape")
        candidate = repo_root / relative
        digest.update(raw_path)
        if candidate.is_file():
            digest.update(bytes.fromhex(sha256_file(candidate) or ""))
    return digest.hexdigest()


def extract_phase_section(content: str, phase: str) -> str:
    section = PHASES[phase]["section"]
    match = re.search(rf"(?ms)^##\s+[^\n]*阶段\s*{section}[^\n]*\n(.*?)(?=^##\s+|\Z)", content)
    return match.group(1).strip() if match else ""


def snapshot(repo_root: Path, task_path: Path, phase: str) -> dict[str, Any]:
    task_content = task_path.read_text(encoding="utf-8")
    phase_section = extract_phase_section(task_content, phase)
    return {
        "captured_at": utc_now(),
        "task_sha256": sha256_bytes(task_content.encode("utf-8")),
        "phase_section_sha256": sha256_bytes(phase_section.encode("utf-8")),
        "git_head": git_head(repo_root),
        "git_branch": git_branch(repo_root),
        "git_fingerprint": git_fingerprint(repo_root),
        "review_verdicts": re.findall(
            r"审查结果\s*[：:]\s*(OK|WARN|BLOCK)\b",
            phase_section,
            re.IGNORECASE,
        ),
    }


def default_state_dir(repo_root: Path) -> Path:
    repo_key = sha256_bytes(str(repo_root).encode("utf-8"))[:12]
    return Path(tempfile.gettempdir()) / "sage-dispatch" / repo_key


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_receipt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DispatchError(f"回执不存在：{path}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DispatchError(f"回执 JSON 无效：{path}: {exc}") from exc
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise DispatchError(f"回执 schema_version 必须为 {SCHEMA_VERSION}")
    return receipt


def prepare_dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    repo_root = args.repo_root.resolve()
    if not repo_root.is_dir():
        raise DispatchError(f"仓库根目录不存在：{repo_root}")
    task_input = args.task_path if args.task_path.is_absolute() else repo_root / args.task_path
    task_path = ensure_within(task_input, repo_root, "TASK_PATH")
    if not task_path.is_file():
        raise DispatchError(f"TASK 文档不存在：{task_path}")

    task_content = task_path.read_text(encoding="utf-8")
    require_task_gate(task_content, args.phase)
    metadata = parse_task_metadata(task_content)
    current_phase = metadata.get("current_phase")
    if current_phase and current_phase != args.phase and not args.allow_phase_mismatch:
        raise DispatchError(f"TASK 当前阶段为 {current_phase}，不能派发 {args.phase}；请先完成阶段流转")

    profile, profile_path = load_profile(args.adapter, repo_root, args.adapter_file)
    channel = choose_channel(profile, args.channel, args.fallback_reason, args.fallback_authorized)
    model = resolve_model(profile, args.phase, channel, args.model)
    role = PHASES[args.phase]["role"]
    role_prompt = resolve_role_prompt(repo_root, role)
    context = build_context(repo_root, task_path, role_prompt, args.phase, args.diff_cmd)
    prompt = build_prompt(context, args.phase)
    dispatch_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{args.phase}-{uuid.uuid4().hex[:8]}"
    action = "run_cli" if channel == "cli" else "spawn_subagent"
    if channel == "subagent":
        agent_type = profile["native_subagent"].get("agent_types", {}).get(args.phase)
    elif channel == "injected":
        agent_type = resolve_injected_agent_types(profile)[args.phase]
    else:
        agent_type = None
    injection = None
    if channel == "injected":
        injected = profile.get("injected_subagent", {})
        injection = {
            "isolation": injected.get("isolation", "unknown"),
            "notes": injected.get("notes"),
            "host_model": injected.get("host_model"),
            "requires_authorization": True,
        }
    state_dir = args.state_dir.resolve() if args.state_dir else default_state_dir(repo_root)
    receipt_path = state_dir / f"{dispatch_id}.json"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "dispatch_id": dispatch_id,
        "status": "prepared",
        "created_at": utc_now(),
        "adapter": profile["id"],
        "adapter_path": str(profile_path.resolve()),
        "channel": channel,
        "action": action,
        "agent_type": agent_type,
        "injection": injection,
        "model": model,
        "context": context,
        "prompt": prompt,
        "fallback": {
            "reason": args.fallback_reason,
            "authorized": bool(args.fallback_authorized),
        },
        "before": snapshot(repo_root, task_path, args.phase),
        "receipt_path": str(receipt_path),
    }
    write_receipt(receipt_path, receipt)
    return receipt, receipt_path


def subsection_body(section: str, number: str) -> str:
    match = re.search(rf"(?ms)^###\s+{re.escape(number)}[^\n]*\n(.*?)(?=^###\s+|\Z)", section)
    return match.group(1).strip() if match else ""


def is_meaningful(body: str) -> bool:
    cleaned = re.sub(r"[`*_#>\-\s]", "", body)
    normalized = cleaned.upper()
    placeholders = {"待填写", "待执行", "TODO", "TBD", "N/A"}
    return len(cleaned) >= 8 and normalized not in placeholders


def verify_receipt(receipt_path: Path, skip_close_commit_check: bool) -> tuple[dict[str, Any], bool]:
    receipt = load_receipt(receipt_path)
    if receipt.get("status") == "cancelled":
        raise DispatchError("派发已取消，不能验证为成功")
    context = receipt["context"]
    repo_root = Path(context["REPO_ROOT"])
    task_path = Path(context["TASK_PATH"])
    phase = context["PHASE"]
    task_content = task_path.read_text(encoding="utf-8")
    current = snapshot(repo_root, task_path, phase)
    before = receipt["before"]
    phase_section = extract_phase_section(task_content, phase)
    errors: list[str] = []
    warnings: list[str] = []

    if current["task_sha256"] == before["task_sha256"]:
        errors.append("TASK 文档未发生变化")
    if current["phase_section_sha256"] == before["phase_section_sha256"]:
        errors.append(f"TASK 阶段 {PHASES[phase]['section']}.x 未发生变化")

    if phase in ("plan-review", "code-review"):
        verdicts = current["review_verdicts"]
        if not verdicts:
            errors.append("reviewer 产出缺少 OK/WARN/BLOCK 审查结果")
        elif verdicts == before.get("review_verdicts", []):
            errors.append("reviewer 未新增或修改 OK/WARN/BLOCK 审查结果")
    elif phase == "dev":
        if not is_meaningful(subsection_body(phase_section, "3.1")):
            errors.append("TASK 3.1 缺少有效进度")
        if not is_meaningful(subsection_body(phase_section, "3.2")):
            errors.append("TASK 3.2 缺少有效验证证据")
        git_changed = current["git_fingerprint"] != before["git_fingerprint"] or current["git_head"] != before["git_head"]
        if before["git_fingerprint"] is not None and not git_changed:
            errors.append("Git 内容指纹和 HEAD 均未发生变化")
        elif before["git_fingerprint"] is None:
            warnings.append("目标目录不是 Git 仓库，只验证 TASK 证据")
    elif phase == "close":
        if not is_meaningful(phase_section):
            errors.append("TASK 5.x 缺少有效收尾记录")
        if not skip_close_commit_check and before["git_head"] is not None and current["git_head"] == before["git_head"]:
            errors.append("close 阶段未产生新的 Git 提交")
        if skip_close_commit_check:
            warnings.append("已按显式参数跳过 close 阶段提交检查")

    success = not errors
    receipt["status"] = "completed" if success else "failed"
    receipt["verified_at"] = utc_now()
    receipt["after"] = current
    receipt["verification"] = {
        "success": success,
        "errors": errors,
        "warnings": warnings,
    }
    write_receipt(receipt_path, receipt)
    return receipt, success


def resolve_cli_command(receipt: dict[str, Any], command_json: str | None) -> tuple[list[str], str | None]:
    profile_path = Path(receipt["adapter_path"])
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    validate_profile(profile, profile_path)
    cli = profile["cli"]
    raw_command: Any = None
    source: str | None = None
    if command_json:
        raw_command = json.loads(command_json)
        source = "--command-json"
    else:
        command_env = cli.get("command_env")
        if command_env and os.environ.get(command_env):
            raw_command = json.loads(os.environ[command_env])
            source = command_env
        elif cli.get("command"):
            raw_command = cli["command"]
            source = str(profile_path)
    if not isinstance(raw_command, list) or not raw_command or not all(isinstance(item, str) for item in raw_command):
        raise DispatchError("CLI 命令必须是非空 JSON 字符串数组；请使用 --command-json 或 adapter 的 command_env")

    model = receipt.get("model", {})
    model_id = model.get("requested")
    model_binding = model.get("binding", "none")
    uses_model_placeholder = any("{model}" in item for item in raw_command)
    if model_id and model_binding == "command-argument" and not uses_model_placeholder:
        raise DispatchError(
            f"已指定模型 {model_id}，但 CLI 命令未消费 {{model}} 占位符；来源：{source}"
        )
    if uses_model_placeholder and not model_id:
        raise DispatchError("CLI 命令包含 {model}，但 prepare 未解析到模型；请传入 --model 或配置 adapter 默认值")

    values = {
        "prompt": receipt["prompt"],
        "repo_root": receipt["context"]["REPO_ROOT"],
        "task_path": receipt["context"]["TASK_PATH"],
        "role_prompt": receipt["context"]["ROLE_PROMPT"],
        "phase": receipt["context"]["PHASE"],
        "diff_cmd": receipt["context"].get("DIFF_CMD", ""),
        "model": model_id or "",
    }
    try:
        command = [item.format_map(values) for item in raw_command]
    except KeyError as exc:
        raise DispatchError(f"CLI 命令包含未知占位符：{exc.args[0]}") from exc
    stdin_mode = cli.get("stdin", "prompt")
    stdin_value = receipt["prompt"] if stdin_mode == "prompt" and not any("{prompt}" in item for item in raw_command) else None
    return command, stdin_value


def run_cli_dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    receipt_path = args.receipt.resolve()
    receipt = load_receipt(receipt_path)
    if receipt.get("channel") != "cli":
        raise DispatchError("该回执不是 CLI 通道")
    if receipt.get("status") not in ("prepared", "failed"):
        raise DispatchError(f"当前状态不能执行 CLI：{receipt.get('status')}")
    command, stdin_value = resolve_cli_command(receipt, args.command_json)
    for stale_key in ("cli_error", "cli_returncode", "verification"):
        receipt.pop(stale_key, None)
    receipt["status"] = "running"
    receipt["started_at"] = utc_now()
    receipt["cli_command"] = command
    log_path = receipt_path.with_suffix(".log")
    receipt["cli_log"] = str(log_path)
    write_receipt(receipt_path, receipt)
    try:
        with log_path.open("w", encoding="utf-8", newline="") as log_stream:
            completed = subprocess.run(
                command,
                cwd=receipt["context"]["REPO_ROOT"],
                input=stdin_value,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=args.timeout,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        receipt = load_receipt(receipt_path)
        receipt["status"] = "failed"
        receipt["cli_error"] = str(exc)
        receipt["finished_at"] = utc_now()
        write_receipt(receipt_path, receipt)
        raise DispatchError(f"CLI 执行失败：{exc}") from exc

    receipt = load_receipt(receipt_path)
    receipt["cli_returncode"] = completed.returncode
    receipt["finished_at"] = utc_now()
    if completed.returncode != 0:
        receipt["status"] = "failed"
        receipt["verification"] = {
            "success": False,
            "errors": [f"CLI 退出码为 {completed.returncode}"],
            "warnings": [],
        }
        write_receipt(receipt_path, receipt)
        return receipt, False
    write_receipt(receipt_path, receipt)
    return verify_receipt(receipt_path, args.skip_close_commit_check)


def format_capabilities(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    native = payload["native_subagent"]
    cli = payload["cli"]
    lines = [
        f"adapter: {payload['id']}",
        f"adapter_path: {payload['adapter_path']}",
        f"native_subagent: {'支持' if native['supported'] else '不支持'}",
        f"native_invoker: {native.get('invoker', 'none')}",
        f"cli: {'支持' if cli['supported'] else '不支持'}",
        f"cli_command_env: {cli.get('command_env', '')}",
    ]
    models = payload.get("models", {})
    if models:
        lines.append("models:")
        for phase in PHASES:
            model = models.get(phase)
            if not model:
                continue
            lines.append(
                f"  {phase}: id={model.get('id') or '未指定'}, "
                f"subagent={model.get('subagent_binding', 'none')}, "
                f"cli={model.get('cli_binding', 'none')}"
            )
    return "\n".join(lines)


def format_result(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = []
    for key in ("dispatch_id", "status", "action", "channel", "adapter", "agent_type", "receipt_path"):
        if key in payload and payload[key] is not None:
            lines.append(f"{key}: {payload[key]}")
    if payload.get("model"):
        model = payload["model"]
        lines.append(
            f"model: {model.get('requested') or '未指定'} "
            f"(binding={model.get('binding', 'none')}, source={model.get('source', 'unspecified')})"
        )
    if payload.get("context"):
        lines.append("context:")
        lines.extend(f"  {key}={value}" for key, value in payload["context"].items())
    if payload.get("prompt"):
        lines.extend(("prompt:", payload["prompt"]))
    if payload.get("verification"):
        verification = payload["verification"]
        lines.append(f"verification: {'通过' if verification['success'] else '失败'}")
        lines.extend(f"  ERROR: {item}" for item in verification.get("errors", []))
        lines.extend(f"  WARN: {item}" for item in verification.get("warnings", []))
    if payload.get("host_cancel_required"):
        lines.append("host_cancel_required: true")
    return "\n".join(lines)


def resolve_cli_probe_command(profile: dict[str, Any]) -> tuple[list[str] | None, str]:
    cli = profile.get("cli", {})
    command_env = cli.get("command_env")
    if command_env and os.environ.get(command_env):
        try:
            command = json.loads(os.environ[command_env])
        except json.JSONDecodeError as exc:
            return None, f"环境变量 {command_env} JSON 无效：{exc}"
        if isinstance(command, list) and command and all(isinstance(item, str) for item in command):
            return command, f"环境变量 {command_env}"
        return None, f"环境变量 {command_env} 不是字符串数组"
    command = cli.get("command")
    if command is None:
        return None, "未配置 CLI 命令（设置 command_env 或 adapter cli.command 后可探测）"
    if isinstance(command, list) and command and all(isinstance(item, str) for item in command):
        return command, "adapter cli.command"
    return None, "adapter cli.command 不是有效字符串数组"


def check_cli_command_available(command: list[str]) -> tuple[bool, str]:
    """仅探测 CLI 可执行文件是否可定位，不执行实际命令。"""
    executable = command[0]
    if Path(executable).is_file():
        return True, f"可执行文件存在：{executable}"
    resolved = shutil.which(executable)
    if resolved:
        return True, f"PATH 可解析：{resolved}"
    return False, f"无法定位可执行文件：{executable}"


def doctor_probe(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else None
    profile, profile_path = load_profile(args.adapter, repo_root, args.adapter_file)
    checks: list[dict[str, Any]] = []

    native = profile["native_subagent"]
    native_declared = bool(native.get("supported"))
    checks.append(
        {
            "channel": "subagent",
            "priority": CHANNEL_PRIORITY["subagent"],
            "declared": native_declared,
            "available": native_declared,
            "verification": "declared",
            "note": "声明为宿主原生注册；宿主运行时可用性需以实际派发结果为准"
            if native_declared
            else "adapter 未声明原生 subagent",
        }
    )

    injected = profile.get("injected_subagent", {})
    injected_declared = bool(injected.get("supported"))
    injected_available = False
    injected_note = "adapter 未声明注入式 subagent"
    if injected_declared:
        try:
            resolve_injected_agent_types(profile)
            injected_available = True
            injected_note = (
                f"isolation={injected.get('isolation', 'unknown')}；"
                "不要求逐次人工授权（T-018 裁决）；隔离等级须在 TASK 证据链记录"
            )
        except DispatchError as exc:
            injected_note = str(exc)
    checks.append(
        {
            "channel": "injected",
            "priority": CHANNEL_PRIORITY["injected"],
            "declared": injected_declared,
            "available": injected_available,
            "verification": "declared",
            "note": injected_note,
        }
    )

    cli = profile.get("cli", {})
    cli_declared = bool(cli.get("supported"))
    cli_available = False
    cli_note = "adapter 未声明 CLI 通道"
    cli_verification = "none"
    if cli_declared:
        cli_verification = "probe"
        command, source = resolve_cli_probe_command(profile)
        if command is None:
            cli_note = source
        else:
            cli_available, cli_note = check_cli_command_available(command)
            cli_note = f"{cli_note}（命令来源：{source}）"
    checks.append(
        {
            "channel": "cli",
            "priority": CHANNEL_PRIORITY["cli"],
            "declared": cli_declared,
            "available": cli_available,
            "verification": cli_verification,
            "note": cli_note,
        }
    )

    recommended = None
    for check in sorted(checks, key=lambda item: -item["priority"]):
        if check["available"]:
            recommended = check["channel"]
            break
    return {
        "adapter": profile["id"],
        "adapter_path": str(profile_path.resolve()),
        "checks": checks,
        "recommended_channel": recommended,
    }


def locate_provision_script(adapter: str, repo_root: Path | None) -> Path:
    """定位适配器 provision 脚本：项目本地 execution-adapters 优先，Skill 内置 adapters 兜底。

    报错语义区分三种情况（TD-2）：
    1. candidate provision.py 全缺失时，先经 profile_candidates 探测 adapter JSON：
       - 均无 JSON → 适配器不存在/未知 → "找不到 adapter"（附排查提示）
       - 有 JSON 但无 provision → 适配器声明无子代理生成能力 → "不提供子代理生成"
    2. 正常定位成功直接返回脚本路径。
    """
    if repo_root:
        local = repo_root / "docs" / "guides" / "execution-adapters" / adapter / "provision.py"
        if local.is_file():
            return local.resolve()
    skill_root = discover_skill_root()
    if skill_root:
        builtin = skill_root / "adapters" / adapter / "provision.py"
        if builtin.is_file():
            return builtin.resolve()
    # candidate provision 全缺失：先探测 adapter JSON 是否存在以区分两种语义
    has_adapter_json = any(candidate.is_file() for candidate in profile_candidates(adapter, repo_root))
    if has_adapter_json:
        raise DispatchError(
            f"adapter '{adapter}' 不提供子代理生成（未找到 adapters/{adapter}/provision.py）"
        )
    raise DispatchError(
        f"找不到 adapter '{adapter}'（请检查适配器 id 拼写；若运行在独立环境请确认 skill 已挂载或指定 --repo-root）"
    )


def provision_delegate(args: argparse.Namespace) -> int:
    """以 subprocess 委托适配器 provision.py 生成注册文件，透传参数与退出码（0/2 映射）。

    生成格式由各适配器脚本自定（codex→TOML、claude-code→Markdown），
    主入口只负责定位脚本、拼装透传参数并转发 stdout/stderr。
    """
    script = locate_provision_script(args.adapter, args.repo_root)
    command = [
        sys.executable,
        str(script),
        "--target-dir",
        str(args.target_dir),
        "--format",
        args.format,
    ]
    if args.role:
        command.extend(("--role", args.role))
    if args.force:
        command.append("--force")
    if args.model_provider:
        if args.adapter != "codex":
            raise DispatchError("--model-provider 仅 codex 适配器（TOML 注册）消费；Markdown 生成不使用该参数")
        command.extend(("--model-provider", args.model_provider))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def format_doctor(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    lines = [f"adapter: {payload['adapter']}", f"adapter_path: {payload['adapter_path']}", "checks:"]
    for check in payload["checks"]:
        lines.append(
            f"  [{check['channel']}] declared={check['declared']} available={check['available']} "
            f"priority={check['priority']} verification={check['verification']}"
        )
        lines.append(f"    {check['note']}")
    lines.append(f"recommended_channel: {payload['recommended_channel'] or '无可用通道'}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    try:
        if args.command == "capabilities":
            repo_root = args.repo_root.resolve() if args.repo_root else None
            profile, profile_path = load_profile(args.adapter, repo_root, args.adapter_file)
            payload = {**profile, "adapter_path": str(profile_path.resolve())}
            print(format_capabilities(payload, args.format))
            return 0
        if args.command == "prepare":
            receipt, _ = prepare_dispatch(args)
            print(format_result(receipt, args.format))
            return 0
        if args.command == "verify":
            receipt, success = verify_receipt(args.receipt.resolve(), args.skip_close_commit_check)
            print(format_result(receipt, args.format))
            return 0 if success else 1
        if args.command == "status":
            receipt = load_receipt(args.receipt.resolve())
            print(format_result(receipt, args.format))
            return 0
        if args.command == "cancel":
            receipt_path = args.receipt.resolve()
            receipt = load_receipt(receipt_path)
            if receipt.get("status") == "completed":
                raise DispatchError("已完成的派发不能取消")
            receipt["status"] = "cancelled"
            receipt["cancelled_at"] = utc_now()
            receipt["cancel_reason"] = args.reason
            receipt["host_cancel_required"] = receipt.get("channel") == "subagent"
            write_receipt(receipt_path, receipt)
            print(format_result(receipt, args.format))
            return 0
        if args.command == "run-cli":
            receipt, success = run_cli_dispatch(args)
            print(format_result(receipt, args.format))
            return 0 if success else 1
        if args.command == "doctor":
            payload = doctor_probe(args)
            print(format_doctor(payload, args.format))
            return 0 if payload["recommended_channel"] else 1
        if args.command == "provision":
            return provision_delegate(args)
    except (DispatchError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())