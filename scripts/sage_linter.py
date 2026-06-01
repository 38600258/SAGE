#!/usr/bin/env python3
"""SAGE 工作流检查器 (SAGE Linter)

此脚本集成了方法论中要求的所有 13 个检查器，不依赖任何第三方 Python 库，
仅使用标准库及本地 git 命令。可以在任何智能体或人类开发流程中独立运行。

SAGE = Steer, Agent Goes Execute (人类掌舵，智能体执行)

用法:
    python scripts/sage_linter.py --all
    python scripts/sage_linter.py --check-task docs/project/ACTIVE_TASK_T-XXX.md
    python scripts/sage_linter.py --check-branch         # 分支隔离与命名校验
    python scripts/sage_linter.py --check-scope          # hooks 高频调用
    python scripts/sage_linter.py --check-commit-msg .git/COMMIT_EDITMSG
    python scripts/sage_linter.py --check-freshness      # /schedule cron 定期调用
    python scripts/sage_linter.py --check-links          # 交叉引用单独校验
    python scripts/sage_linter.py --all --format json    # JSON 结构化输出
    python scripts/sage_linter.py --all --artifact        # Markdown 报告

退出码:
    0 = 全部通过
    1 = 有警告（但无阻断）
    2 = 有阻断性问题
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ==============================================================================
# 全局常量
# ==============================================================================

# 元文件前缀与文件名（范围锁定和 CHANGELOG 校验中需排除的非项目源文件）
_META_PREFIXES = ("docs/", "templates/", "archive/", "scripts/", "prompts/")
_META_EXACT = {
    "AGENTS.md", "AGENTS.override.md", "ARCHITECTURE.md", "CHANGELOG.md", "GEMINI.md",
    ".gitignore", ".env", ".editorconfig",
}

# 是否从 hooks 调用（环境变量 ANTIGRAVITY_HOOK=1 时自动精简输出）
_IS_HOOK = os.environ.get("ANTIGRAVITY_HOOK") == "1"


def _is_meta_file(filepath):
    """判断文件路径是否属于工作流元文件（非项目源代码），应被范围锁定排除"""
    fp = filepath.replace("\\", "/")
    if any(fp.startswith(p) for p in _META_PREFIXES):
        return True
    if fp in _META_EXACT:
        return True
    # 根目录下的 .md 文件视为方法论/流程文档，不是项目源码
    if fp.endswith(".md") and "/" not in fp:
        return True
    return False


# ==============================================================================
# 通用工具函数
# ==============================================================================

def run_git_cmd(args, cwd=None):
    """运行 git 命令并返回输出，失败时返回空字符串"""
    try:
        git_args = ["git"]
        if cwd:
            git_args.extend(["-c", f"safe.directory={Path(cwd).as_posix()}"])
        res = subprocess.run(
            git_args + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            errors="ignore"
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""

def get_git_diff_files(cwd=None):
    """获取当前有变更的文件列表（已暂存 + 未暂存 + 未跟踪）"""
    out = run_git_cmd(["diff", "--name-only"], cwd)
    out_cached = run_git_cmd(["diff", "--cached", "--name-only"], cwd)
    out_porcelain = run_git_cmd(["status", "--porcelain"], cwd)

    files = set()
    for line in (out + "\n" + out_cached).splitlines():
        if line.strip():
            files.add(line.strip())

    # [FIX DESIGN-5] 解析 porcelain 全部状态码（??, A, M, AM, R 等），不只看 ??
    for line in out_porcelain.splitlines():
        if len(line) >= 3 and line[0:2].strip():
            if line.startswith("?? ") or (len(line) > 2 and line[2] == " "):
                filepath = line[3:].strip().strip('"')
            else:
                # 兼容部分 Windows/Git 输出中的紧凑短状态（如 "M path"）
                filepath = line[2:].strip().strip('"')
            if filepath:
                files.add(filepath)

    return files

def get_file_lines(path):
    """读取文件行，忽略编码错误"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()
    except Exception as e:
        if not _IS_HOOK:
            print(f"🛑 无法读取文件 {path}: {e}")
        return []

# ==============================================================================
# 结果收集器（支持多格式输出）
# ==============================================================================

class CheckResult:
    """单个检查器的结果"""
    __slots__ = ("checker", "status", "message")

    def __init__(self, checker, status, message):
        self.checker = checker      # 检查器名称
        self.status = status        # "pass" | "warn" | "fail"
        self.message = message      # 详细信息

    def to_dict(self):
        return {"checker": self.checker, "status": self.status, "message": self.message}

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ResultCollector:
    """收集所有检查结果并按指定格式输出"""

    def __init__(self, fmt="text"):
        self.fmt = fmt              # "text" | "json" | "artifact"
        self.results = []

    def add(self, checker_name, ok, message):
        """添加一个检查结果。ok=True 且含 ⚠️ 时视为 warn，否则 pass/fail"""
        if ok and "⚠️" in message:
            status = "warn"
        elif ok:
            status = "pass"
        else:
            status = "fail"
        self.results.append(CheckResult(checker_name, status, message))

    @property
    def has_fail(self):
        return any(r.status == "fail" for r in self.results)

    @property
    def has_warn(self):
        return any(r.status == "warn" for r in self.results)

    def exit_code(self):
        """退出码语义：0=全部通过, 1=有警告, 2=有阻断"""
        if self.has_fail:
            return 2
        if self.has_warn:
            return 1
        return 0

    def flush_text(self):
        """以纯文本格式输出所有结果"""
        warns = []
        for r in self.results:
            icon = {"pass": "🟢", "warn": "🟡", "fail": "🔴"}[r.status]
            tag = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}[r.status]
            if r.status == "warn":
                warns.append(r.message)
                print(f"  {icon} {r.checker}: {tag}")
            elif r.status == "pass":
                print(f"  {icon} {r.checker}: {r.message}")
            else:
                print(f"  {icon} {r.checker}: {tag}\n    👉 {r.message}")
        if warns:
            print("\n💡 警告细节:")
            for w in warns:
                print(w)

    def flush_json(self):
        """以 JSON 格式输出所有结果"""
        output = {
            "summary": {
                "total": len(self.results),
                "pass": sum(1 for r in self.results if r.status == "pass"),
                "warn": sum(1 for r in self.results if r.status == "warn"),
                "fail": sum(1 for r in self.results if r.status == "fail"),
                "exit_code": self.exit_code(),
            },
            "results": [r.to_dict() for r in self.results]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    def flush_artifact(self):
        """以 Markdown artifact 格式输出完整报告"""
        total = len(self.results)
        passes = sum(1 for r in self.results if r.status == "pass")
        warns = sum(1 for r in self.results if r.status == "warn")
        fails = sum(1 for r in self.results if r.status == "fail")

        lines = [
            "# 🔍 SAGE Linter 扫描报告",
            "",
            f"> 扫描时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 摘要",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 检查器总数 | {total} |",
            f"| ✅ 通过 | {passes} |",
            f"| ⚠️ 警告 | {warns} |",
            f"| ❌ 阻断 | {fails} |",
            f"| 退出码 | {self.exit_code()} |",
            "",
            "## 详细结果",
            "",
            "| # | 检查器 | 状态 | 详情 |",
            "|---|--------|------|------|",
        ]
        for i, r in enumerate(self.results, 1):
            icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[r.status]
            # 在 Markdown 表格中转义管道符和换行
            msg = r.message.replace("|", "\\|").replace("\n", " ")
            if len(msg) > 120:
                msg = msg[:117] + "..."
            lines.append(f"| {i} | {r.checker} | {icon} | {msg} |")

        # 失败项详情展开
        fail_results = [r for r in self.results if r.status == "fail"]
        if fail_results:
            lines.append("")
            lines.append("## ❌ 阻断项详情")
            for r in fail_results:
                lines.append("")
                lines.append(f"### {r.checker}")
                lines.append("")
                lines.append(r.message)

        # 警告项详情展开
        warn_results = [r for r in self.results if r.status == "warn"]
        if warn_results:
            lines.append("")
            lines.append("## ⚠️ 警告项详情")
            for r in warn_results:
                lines.append("")
                lines.append(f"### {r.checker}")
                lines.append("")
                lines.append(r.message)

        print("\n".join(lines))

    def flush(self):
        """按配置的格式输出"""
        if self.fmt == "json":
            self.flush_json()
        elif self.fmt == "artifact":
            self.flush_artifact()
        else:
            self.flush_text()


# ==============================================================================
# 13 个检查器核心实现
# ==============================================================================

def check_template_copy(task_file, template_file):
    """1. 模板复制校验: 确保任务文档是从模板复制的，且行数和关键标题未被恶意删减"""
    task_path = Path(task_file)
    tpl_path = Path(template_file)

    if not task_path.exists():
        return False, f"任务文件不存在: {task_file}"
    if not tpl_path.exists():
        return False, f"模板文件不存在: {template_file}"

    task_lines = get_file_lines(task_path)
    tpl_lines = get_file_lines(tpl_path)

    # 检查行数
    if len(task_lines) < len(tpl_lines) * 0.8:  # 容忍 20% 的微调，但不能过少
        return False, f"任务文档行数 ({len(task_lines)}) 显著少于模板行数 ({len(tpl_lines)})，疑似未完整复制模板。"

    # 提取模板中的关键二级标题
    tpl_headers = [line.strip() for line in tpl_lines if line.startswith("## ")]
    task_content = "".join(task_lines)

    missing_headers = []
    for h in tpl_headers:
        # 提取标题核心字，如 "任务元数据" 或 "阶段 1"
        h_core = re.sub(r"\s+—\s+.*$", "", h)
        h_core = re.sub(r"\s+`[^`]+`", "", h_core)
        h_core = re.sub(r"\s*\([^)]*\)", "", h_core).strip()
        if h_core not in task_content:
            missing_headers.append(h)

    if missing_headers:
        return False, f"任务文档中缺失模板中定义的关键小节:\n  - " + "\n  - ".join(missing_headers)

    return True, f"模板复制校验通过 ({task_path.name} 结构完整)"

def check_task_structure(task_file):
    """2. 任务文档结构校验: 校验任务控制面的关键节是否存在且顺序正确"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    # [FIX DESIGN-1] 使用正则匹配核心文字，忽略前导 Emoji
    # 避免跨平台 Unicode 编码差异（如 U+1F6E0 vs U+1F6E0+U+FE0F）导致匹配失败
    required_patterns = [
        (r"##\s+\S*\s*任务元数据", "任务元数据"),
        (r"##\s+\S*\s*阶段\s*1[：:]", "阶段 1：初始化"),
        (r"##\s+\S*\s*阶段\s*2[：:]", "阶段 2：计划评审"),
        (r"##\s+\S*\s*阶段\s*3[：:]", "阶段 3：开发与验证"),
        (r"##\s+\S*\s*阶段\s*4[：:]", "阶段 4：代码审查"),
        (r"##\s+\S*\s*阶段\s*5[：:]", "阶段 5：收尾与归档"),
    ]

    missing = []
    for pattern, label in required_patterns:
        if not re.search(pattern, content):
            missing.append(label)

    if missing:
        return False, f"任务控制面结构破损，缺失以下必要大节:\n  - " + "\n  - ".join(missing)

    return True, f"任务文档大纲结构完整 ({task_path.name})"

def check_task_risk_sections(task_file):
    """3. L2/L3 扩展章节校验: 如果风险等级为 L2/L3，确保 1.3a 和 1.3b 存在且不为空"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    lines = get_file_lines(task_path)
    content = "".join(lines)

    # 提取风险等级
    risk_match = re.search(r'-\s*\*\*风险等级\*\*:\s*(L1|L2|L3)', content)
    if not risk_match:
        # 兼容性匹配
        risk_match = re.search(r'风险等级\s*[:：]\s*(L1|L2|L3)', content)

    risk_level = risk_match.group(1) if risk_match else "L2"  # 默认 L2

    if risk_level in ["L2", "L3"]:
        # 检查 1.3a 验收标准
        has_13a = "### 1.3a 验收标准" in content
        # 检查 1.3b 风险矩阵
        has_13b = "### 1.3b 风险矩阵" in content

        if not has_13a or not has_13b:
            return False, f"风险等级为 {risk_level} 时，必须包含 ### 1.3a 验收标准 和 ### 1.3b 风险矩阵 章节。"

        # 提取 1.3a 验收标准内容
        idx_13a = content.find("### 1.3a 验收标准")
        idx_14 = content.find("### 1.4", idx_13a)
        if idx_14 == -1:
            idx_14 = content.find("## ", idx_13a + 20)  # 搜索下一个 ## 标题

        section_content = content[idx_13a:idx_14] if idx_14 != -1 else content[idx_13a:]

        # 新版验收标准必须是可证伪契约：AC-ID + [auto]/[manual] + 验证方式 + 证据位置。
        # 兼容旧版 checkbox 的存在性检查，但 L2/L3 会要求至少一条新版 AC 映射。
        ac_rows = []
        for line in section_content.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 5 and re.fullmatch(r"AC-\d+", cells[0]):
                ac_rows.append(cells[:5])

        invalid_ac = []
        auto_count = 0
        manual_count = 0
        placeholder_markers_ac = ["(如", "（如", "待填", "...", "可证伪验收标准", "验证方式", "证据位置"]
        for ac_id, ac_type, criterion, verify, evidence in ac_rows:
            if ac_type not in ["[auto]", "[manual]"]:
                invalid_ac.append(f"{ac_id}: 类型必须为 [auto] 或 [manual]")
            if ac_type == "[auto]":
                auto_count += 1
            if ac_type == "[manual]":
                manual_count += 1
            values = [criterion, verify, evidence]
            if any(not value for value in values) or any(
                any(marker in value for marker in placeholder_markers_ac) for value in values
            ):
                invalid_ac.append(f"{ac_id}: 验收标准、验证方式或证据位置仍为空或占位")

        if not ac_rows:
            return False, (
                f"风险等级为 {risk_level}，但 ### 1.3a 验收标准 未使用 AC-ID 验收映射。"
                "请为每条验收标准填写 AC-ID、[auto]/[manual]、验证方式和证据位置。"
            )
        if invalid_ac:
            return False, "验收标准映射不完整：\n  - " + "\n  - ".join(invalid_ac)

        acceptance_warning = ""
        if manual_count > 0 and auto_count == 0:
            acceptance_warning = " ⚠️ 验收标准全部为 [manual]，请确认不存在可自动化验证的关键约束。"

        # [FIX BUG-3] 检查 1.3b 风险矩阵：用多个占位符标记综合判定
        idx_13b = content.find("### 1.3b 风险矩阵")
        section_content_b = content[idx_13b:idx_14] if idx_14 != -1 else content[idx_13b:]
        table_lines = [l.strip() for l in section_content_b.splitlines() if "|" in l]
        # 表格应该有表头、分割线、以及至少一行非占位符的真实数据
        placeholder_markers = ["风险描述", "低/中/高", "缓解方案", "待填", "缓解措施"]
        data_rows = table_lines[2:] if len(table_lines) >= 3 else []
        if len(table_lines) < 3 or all(
            any(m in row for m in placeholder_markers) for row in data_rows
        ):
            return False, f"风险等级为 {risk_level}，但 ### 1.3b 风险矩阵 未填写具体的风险防范矩阵。"

    return True, f"风险分级扩展项校验通过 (风险等级: {risk_level})" + (acceptance_warning if risk_level in ["L2", "L3"] else "")

def check_git_branch_isolation(cwd=None, allow_protected=False):
    """4. 分支隔离校验: 校验当前是否处于受保护的主干分支上开发"""
    curr_branch = run_git_cmd(["branch", "--show-current"], cwd)
    if not curr_branch:
        # 尝试通过 git status 解析
        status = run_git_cmd(["status"], cwd)
        match = re.search(r'On branch\s+(\S+)', status)
        if match:
            curr_branch = match.group(1)

    if not curr_branch:
        return True, "无法确定当前 Git 分支，跳过分支隔离校验（可能不在 Git 仓库中）。"

    protected_branches = ["main", "master", "dev", "develop", "release"]
    if curr_branch in protected_branches:
        if allow_protected:
            return True, f"受保护分支 '{curr_branch}' 已由显式授权参数放行。"
        return False, f"🛑 隔离红线违规：当前处于受保护的分支 '{curr_branch}'。所有开发必须在独立功能分支上进行！"

    allowed_patterns = [
        r"^fix/l0-[a-z0-9][a-z0-9-]*$",
        r"^docs/l0-[a-z0-9][a-z0-9-]*$",
        r"^chore/l0-[a-z0-9][a-z0-9-]*$",
        r"^style/l0-[a-z0-9][a-z0-9-]*$",
        r"^feat/t-\d{3,}-[a-z0-9][a-z0-9-]*$",
        r"^feature/[Tt]-\d{3,}-[a-z0-9][a-z0-9-]*$",
        r"^fix/t-\d{3,}-[a-z0-9][a-z0-9-]*$",
        r"^docs/t-\d{3,}-[a-z0-9][a-z0-9-]*$",
        r"^chore/t-\d{3,}-[a-z0-9][a-z0-9-]*$",
        r"^refactor/t-\d{3,}-[a-z0-9][a-z0-9-]*$",
    ]
    if not any(re.match(pat, curr_branch) for pat in allowed_patterns):
        return False, (
            f"🛑 分支命名违规：当前分支 '{curr_branch}' 不符合 SAGE 通用分支规范。\n"
            "允许格式: L1+ 使用 feat/t-XXX-name, fix/t-XXX-name, docs/t-XXX-name, "
            "chore/t-XXX-name, refactor/t-XXX-name；兼容旧功能分支 feature/T-XXX-name；"
            "L0 使用 fix/l0-name, docs/l0-name, "
            "chore/l0-name, style/l0-name。"
        )

    return True, f"分支隔离与命名校验通过 (当前分支: {curr_branch})"


def check_commit_message(message_file):
    """提交信息校验: Conventional Commit 标题描述必须包含中文字符"""
    msg_path = Path(message_file)
    if not msg_path.exists():
        return False, f"提交信息文件不存在: {message_file}"

    lines = get_file_lines(msg_path)
    subject = ""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            subject = stripped
            break

    if not subject:
        return False, "提交信息为空，请填写提交标题。"

    exempt_patterns = [
        r"^Merge\b",
        r"^Revert\b",
        r"^fixup!",
        r"^squash!",
    ]
    if any(re.match(pattern, subject, re.IGNORECASE) for pattern in exempt_patterns):
        return True, f"系统/整理类提交豁免中文标题检查: {subject}"

    conventional_re = re.compile(
        r"^(feat|fix|docs|refactor|test|chore|style|perf|build|ci|revert)"
        r"(\([^)]+\))?:\s+.+"
    )
    if not conventional_re.match(subject):
        return False, (
            "提交标题不符合 Conventional Commit 格式。\n"
            "允许格式: type(scope): 中文描述，例如 docs(project): 审查 PRD 看板任务拆分"
        )

    if not re.search(r"[\u4e00-\u9fff]", subject):
        return False, (
            "提交标题描述必须包含中文字符。\n"
            "示例: docs(project): 审查 PRD 看板任务拆分"
        )

    return True, f"提交信息校验通过: {subject}"


def check_t2_document_lines(docs_dir):
    """5. T2 文档体积校验: 检查 docs/ guides 下的文件行数是否超过 500 行"""
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        return True, f"文档目录不存在，跳过体积校验: {docs_dir}"

    over_limit_files = []
    # 递归查找 guides 目录下的 md 文件
    for md_file in docs_path.glob("**/guides/**/*.md"):
        # 排除只读/第三方参考目录
        fp_posix = md_file.as_posix()
        if "cj-claw-ref" in fp_posix or "node_modules" in fp_posix:
            continue
        lines = get_file_lines(md_file)
        if len(lines) > 500:
            over_limit_files.append((md_file, len(lines)))

    if over_limit_files:
        msg = "发现 T2 规范文档体积超标（超过 500 行，应当拆分子文档以维护可读性）：\n"
        for f, l in over_limit_files:
            msg += f"  - {f.relative_to(docs_path.parent)} ({l} 行)\n"
        return False, msg

    return True, "T2 文档体积校验通过 (所有规范文档均控制在 500 行以内)"

def check_document_freshness(docs_dir, stale_days=30):
    """6. 文档新鲜度扫描: 检查 docs 下是否存在超过 N 天未更新的陈旧文档"""
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        return True, f"文档目录不存在，跳过新鲜度扫描: {docs_dir}"

    now = time.time()
    stale_secs = stale_days * 24 * 3600
    stale_files = []

    for md_file in docs_path.glob("**/*.md"):
        # 排除已归档的任务和第三方参考目录
        fp_posix = md_file.as_posix()
        if "architecture/tasks" in fp_posix or "archive" in fp_posix or "cj-claw-ref" in fp_posix or "node_modules" in fp_posix:
            continue

        # 优先使用 git log 获取最后修改时间
        git_time_str = run_git_cmd(["log", "-1", "--format=%ct", str(md_file)], cwd=docs_path.parent)
        if git_time_str.isdigit():
            mtime = float(git_time_str)
        else:
            # 降级使用文件系统修改时间
            mtime = md_file.stat().st_mtime

        age_days = (now - mtime) / (24 * 3600)
        if (now - mtime) > stale_secs:
            stale_files.append((md_file, int(age_days)))

    if stale_files:
        msg = f"发现以下文档已超过 {stale_days} 天未更新，请评估是否已过时并进行修剪或更新：\n"
        for f, d in sorted(stale_files, key=lambda x: x[1], reverse=True):
            msg += f"  - {f.relative_to(docs_path.parent)} ({d} 天未更新)\n"
        return True, f"⚠️ 新鲜度警告：\n{msg}"  # 警告级别，不阻塞流程

    return True, "文档新鲜度校验通过 (所有活跃文档均保持新鲜)"


def check_templates_pristine(templates_dir, cwd=None):
    """7. 模板完整性守护: 检测 templates/ 目录下的模板是否被意外篡改"""
    tpl_path = Path(templates_dir)
    if not tpl_path.exists():
        return True, f"模板目录不存在，跳过完整性校验: {templates_dir}"

    # [FIX DESIGN-4] 使用相对路径传给 git diff，避免跨平台绝对路径兼容性问题
    try:
        rel_tpl = str(tpl_path.relative_to(Path(cwd) if cwd else Path.cwd())).replace("\\", "/")
    except ValueError:
        rel_tpl = str(tpl_path)
    diff = run_git_cmd(["diff", "--name-only", "--", rel_tpl], cwd)
    diff_cached = run_git_cmd(["diff", "--cached", "--name-only", "--", rel_tpl], cwd)

    changed = set(diff.splitlines() + diff_cached.splitlines())
    changed = {c for c in changed if c.strip()}

    if changed:
        msg = "🛑 警告：检测到模板文件被非法修改！模板是神圣不可侵犯的，请撤销更改：\n"
        for f in changed:
            msg += f"  - {f}\n"
        return False, msg

    return True, "模板完整性校验通过 (模板文件未被篡改)"

def check_changelog_update(changelog_file, cwd=None):
    """8. CHANGELOG 更新校验: 检查发生代码变更时，CHANGELOG.md 是否有对应修改"""
    changelog_path = Path(changelog_file)
    if not changelog_path.exists():
        return True, "CHANGELOG.md 不存在，跳过更新校验。"

    changed_files = get_git_diff_files(cwd)
    if not changed_files:
        return True, "无任何文件变更，无需校验 CHANGELOG 更新。"

    # [FIX BUG-5] 使用统一的 _is_meta_file 判定，而非硬编码不完整的排除列表
    has_code_change = False
    for f in changed_files:
        if not _is_meta_file(f):
            has_code_change = True
            break

    if has_code_change:
        # 检查 CHANGELOG.md 是否在变更列表中
        changelog_rel = str(changelog_path.relative_to(Path(cwd) if cwd else Path.cwd())).replace("\\", "/")
        if changelog_rel not in changed_files:
            return False, f"检测到项目代码有变更，但 {changelog_rel} 未进行同步更新。请在发布前记录变更！"

    return True, "CHANGELOG 更新校验通过"

def check_append_only(file_path, cwd=None):
    """9. 只增不改校验: 确保决策日志 (DECISION_LOG.md) 或变更日志没有历史删除"""
    path = Path(file_path)
    if not path.exists():
        return True, f"文件不存在，跳过只增不改校验: {file_path}"

    # [FIX BUG-6] 区分「真正的历史内容删除」与「仅换行符变化的误报」
    rel_path = str(path.relative_to(Path(cwd) if cwd else Path.cwd())).replace("\\", "/")
    diff_output = run_git_cmd(["diff", "-U0", rel_path], cwd)
    if not diff_output:
        return True, f"只增不改校验通过 ({path.name})"

    diff_lines = diff_output.splitlines()
    deleted_contents = []
    added_contents = []
    for line in diff_lines:
        # 忽略 git 注释行（如 "\ No newline at end of file"）
        if line.startswith("\\"):
            continue
        if line.startswith("-") and not line.startswith("---"):
            deleted_contents.append(line[1:].rstrip())
        elif line.startswith("+") and not line.startswith("+++"):
            added_contents.append(line[1:].rstrip())

    # 核心修复：如果被删除行的内容在新增行中也出现了，说明只是换行符/空白变化，
    # 不算真正的历史删除。只标记那些内容确实消失了的行。
    added_set = set(added_contents)
    truly_deleted = [d for d in deleted_contents if d.strip() and d not in added_set]

    if truly_deleted:
        msg = f"🛑 只增不改红线违规：检测到对 {rel_path} 历史记录的删除或修改：\n"
        for s in truly_deleted[:5]:
            msg += f'  - 删除内容: "{s.strip()}"\n'
        if len(truly_deleted) > 5:
            msg += "  - ... (更多删除项已省略)\n"
        msg += "此文件仅允许在末尾追加记录，严禁修改或删除历史存证！"
        return False, msg

    return True, f"只增不改校验通过 ({path.name})"

def check_scope_lock(task_file, cwd=None):
    """10. 范围锁定校验: 检查实际修改的文件是否在任务文档声明的 Writable 可写范围内"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    # 提取可写文件列表
    # 支持 1.4 🛡️ 范围锁定 格式：
    # - **可写文件 (Writable)**: (文件1, 文件2) 或列表形式
    writable_match = re.search(r'-\s*\*\*可写文件\s*\(Writable\)\*\*:\s*(.*)', content)
    if not writable_match:
        writable_match = re.search(r'可写文件\s*[:：]\s*(.*)', content)

    if not writable_match:
        return True, "未在任务文档中找到明确的可写文件锁定声明，跳过范围校验。"

    writable_text = writable_match.group(1).strip()

    # [FIX BUG-4] 优先提取反引号包裹的路径（最严格、最不易误匹配）
    writable_files = set(re.findall(r'`([^`]+)`', writable_text))
    # 降级：提取包含 / 或文件扩展名的路径模式
    if not writable_files:
        writable_files = set(re.findall(r'[\w\-./\\]+\.[\w]+', writable_text))
        writable_files |= set(re.findall(r'[\w\-]+/[\w\-./\\]*', writable_text))
    # 移除空值或占位符
    writable_files = {f.strip("`'\" ") for f in writable_files
                      if f.strip("`'\" ") and "列出" not in f and "待填" not in f}

    if not writable_files:
        # 尝试向下寻找列表行
        idx = content.find("**可写文件")
        if idx != -1:
            sub_content = content[idx:idx + 500]
            # 匹配列表项中的反引号路径或类路径字符串
            items = re.findall(r'`([^`]+)`', sub_content)
            if not items:
                items = re.findall(r'[\w\-./\\]+\.[\w]+', sub_content)
            writable_files = {i.strip() for i in items
                              if i.strip() and "Writable" not in i and "可写" not in i}

    if not writable_files:
        return True, "💡 提示：任务文档未定义具体的可写文件白名单，跳过范围锁定校验。"

    # 获取实际修改的文件
    actual_changed = get_git_diff_files(cwd)
    # [FIX BUG-5] 使用统一的 _is_meta_file 过滤工作流元文件
    actual_changed = {f for f in actual_changed if not _is_meta_file(f)}

    # 统一路径分隔符进行比对
    def norm(p):
        return Path(p).as_posix().strip("./")

    norm_writable = {norm(f) for f in writable_files}
    violating_files = []

    for f in actual_changed:
        normalized_f = norm(f)
        # 允许前缀匹配或精确匹配
        matched = False
        for w in norm_writable:
            if normalized_f == w or normalized_f.startswith(w + "/"):
                matched = True
                break
        if not matched:
            violating_files.append(f)

    if violating_files:
        msg = "🛑 范围锁定违规：修改了超出可写文件锁定清单的文件！\n"
        msg += "  已声明的可写文件: " + ", ".join(writable_files) + "\n"
        msg += "  未授权的修改文件:\n"
        for f in violating_files:
            msg += f"    - {f}\n"
        msg += "请更新任务文档 1.4 节将上述文件加入白名单，或撤销对这些文件的修改。"
        return False, msg

    return True, "范围锁定校验通过 (无越权修改文件)"

def check_cross_links(scan_dir):
    """11. 交叉引用验证: 扫描 md 文档，验证其中的本地相对链接是否有效"""
    scan_path = Path(scan_dir)
    if not scan_path.exists():
        return True, f"扫描目录不存在: {scan_dir}"

    broken_links = []
    for md_file in scan_path.glob("**/*.md"):
        # 忽略归档、只读参考及依赖目录
        fp_posix = md_file.as_posix()
        if "archive" in fp_posix or "cj-claw-ref" in fp_posix or "node_modules" in fp_posix or "references" in fp_posix:
            continue

        content = "".join(get_file_lines(md_file))
        # 寻找 markdown 链接 [text](link)
        links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', content)

        for link in links:
            # 排除普通网络链接和锚点链接，但保留本地 file:// 链接
            if (link.startswith("http://") or link.startswith("https://") or
                link.startswith("mailto:") or link.startswith("#")):
                continue

            # 处理本地绝对文件协议：file://
            if link.startswith("file://"):
                link_clean = link[7:]
                # Windows 环境：如果开头是 /D:/... 或者是 D:/...
                if link_clean.startswith("/") and len(link_clean) > 2 and link_clean[2] == ":":
                    link_clean = link_clean[1:]
                # 移除可能存在的锚点/参数
                link_clean = link_clean.split("#")[0].split("?")[0].strip()
                if not link_clean:
                    continue
                # 直接检查绝对路径在文件系统中是否存在
                target_path = Path(link_clean)
                if not target_path.exists():
                    broken_links.append((md_file, link, link_clean))
                continue

            # 正常本地相对路径处理
            # 去掉参数和锚点后缀，如 path/to/file.md#L12
            link_clean = link.split("#")[0].split("?")[0].strip()
            if not link_clean:
                continue

            # 判定目标路径是否存在
            target_path = (md_file.parent / link_clean).resolve()
            if not target_path.exists():
                # 尝试从项目根目录解析 (支持绝对路径写法)
                root_target = (scan_path / link_clean).resolve()
                if not root_target.exists():
                    broken_links.append((md_file, link, link_clean))

    if broken_links:
        msg = "发现失效的本地文档链接：\n"
        for src, raw_link, clean_link in broken_links:
            try:
                rel = src.relative_to(scan_path)
            except ValueError:
                rel = src
            msg += f'  - 文件 {rel} 中链接 "{raw_link}" 指向的路径不存在。\n'
        return False, msg

    return True, "交叉引用验证通过 (所有本地链接均有效)"

def check_evidence_complete(task_file):
    """12. 证据链完整性: 校验开发完成后，任务文档中的测试结果和 lint 结果是否已填写勾选"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    # 提取 3.2 🧪 证据链 小节（兼容有/无 Emoji 的写法）
    idx_ev = content.find("### 3.2 🧪 证据链")
    if idx_ev == -1:
        idx_ev = content.find("### 3.2 证据链")

    if idx_ev == -1:
        return True, "💡 提示：未在任务文档中找到 3.2 证据链章节，跳过校验。"

    idx_next = content.find("## ", idx_ev + 10)  # 搜索下一个 ## 标题
    evidence_section = content[idx_ev:idx_next] if idx_next != -1 else content[idx_ev:]

    # 提取所有的复选框状态
    checkboxes = re.findall(r'-\s*\[\s*([xX\s])\s*\]\s*(.+)', evidence_section)
    if not checkboxes:
        return True, "💡 提示：3.2 证据链中无校验项，跳过。"

    unchecked = []
    for status, desc in checkboxes:
        if status.strip() == "":  # 未勾选
            # 排除非开发人员必勾项，只校验自动化测试和 Lint 结果
            if "测试" in desc or "Lint" in desc or "检查" in desc:
                unchecked.append(desc.strip())

    if unchecked:
        msg = "⚠️ 证据链不完整：阶段三（开发与验证）已进入收尾，但未勾选确认以下验证证据：\n"
        for item in unchecked:
            msg += f"  - [ ] {item}\n"
        msg += "请先执行测试/Lint 检查，并在任务文档 3.2 节勾选对应的证据项。"
        return False, msg

    return True, "证据链完整性校验通过 (自动化测试与 Lint 证据已勾选确认)"

def check_review_complete(task_file):
    """13. 盲审结果完整性: L2/L3 任务必须写入计划评审与代码评审报告"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    risk_match = re.search(r'-\s*\*\*风险等级\*\*:\s*(L1|L2|L3)', content)
    if not risk_match:
        risk_match = re.search(r'风险等级\s*[:：]\s*(L1|L2|L3)', content)
    risk_level = risk_match.group(1) if risk_match else "L2"

    if risk_level == "L1":
        return True, "L1 任务可跳过阶段二/四盲审，跳过盲审完整性校验。"

    def section_between(start_markers, end_markers):
        start = -1
        for marker in start_markers:
            start = content.find(marker)
            if start != -1:
                break
        if start == -1:
            return None
        end_positions = [
            match.start()
            for marker in end_markers
            for match in re.finditer(r"(?m)^" + re.escape(marker), content[start + 1:])
        ]
        end_positions = [start + 1 + p for p in end_positions]
        end = min(end_positions) if end_positions else len(content)
        return content[start:end]

    plan_section = section_between(
        ["### 2.1 评审意见", "### 2.1 Review Feedback"],
        ["## 💻 阶段 3", "## 阶段 3"],
    )
    code_section = section_between(
        ["### 4.1 代码评审", "### 4.1 Code Review Feedback"],
        ["## 🧠 阶段 5", "## 阶段 5"],
    )

    def is_review_filled(section):
        if not section:
            return False
        placeholders = ["由 reviewer 填写", "如有修改", "评审反馈", "待填", "(由", "(如有"]
        substantive_markers = ["审查结果", "OK", "WARN", "BLOCK", "✅", "⚠️", "🛑"]
        has_marker = any(m in section for m in substantive_markers)
        has_content = any(
            line.strip()
            and not line.strip().startswith("###")
            and not line.strip().startswith("- [ ]")
            and not line.startswith("- [ ]")
            and not any(p in line for p in placeholders)
            for line in section.splitlines()
        )
        return has_marker and has_content

    missing = []
    if not is_review_filled(plan_section):
        missing.append("2.1 计划评审报告")
    if not is_review_filled(code_section):
        missing.append("4.1 代码评审报告")

    if missing:
        return False, (
            f"🛑 盲审结果缺失：风险等级为 {risk_level}，但以下章节未写入有效审查报告："
            + "、".join(missing)
            + "。调用 agy 后必须确认 TASK 文档对应章节已写入 OK/WARN/BLOCK 等 Markdown 审查结果，"
            + "否则不得继续流转。"
        )

    return True, f"盲审结果完整性校验通过 (风险等级: {risk_level})"

def check_model_metadata(task_file):
    """14. 模型元数据校验: 验证活跃 TASK 文档元数据中是否已记录"使用模型"字段"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    # 提取"使用模型"字段
    model_match = re.search(r'-\s*\*\*使用模型\*\*\s*[:：]\s*(.*)', content)
    if not model_match:
        # 兼容不加粗的写法
        model_match = re.search(r'使用模型\s*[:：]\s*(.*)', content)

    if not model_match:
        return False, "任务文档元数据中未找到\"使用模型\"字段。请在任务元数据中记录实际使用的模型。"

    model_value = model_match.group(1).strip()

    # 检测空值或占位符文本
    placeholder_patterns = [
        r'^\s*$',                           # 空值
        r'^\[.*\]$',                        # 方括号占位符 [填写实际使用的模型]
        r'待填',                            # 待填
        r'TBD',                             # TBD
        r'N/?A',                            # N/A
        r'^[-—]+$',                         # 破折号占位
        r'^\(.*\)$',                        # 括号占位符
        r'填写',                            # 包含"填写"
    ]

    for pat in placeholder_patterns:
        if re.search(pat, model_value, re.IGNORECASE):
            return False, (
                f"⚠️ 任务文档元数据中的\"使用模型\"字段仍为占位符文本: \"{model_value}\"。"
                f"\n请填写实际使用的模型名称（如强推理模型、快速编码模型、agy CLI reviewer 等）。"
            )

    return True, f"模型元数据校验通过 (使用模型: {model_value})"

def check_execution_channel_records(task_file):
    """15. 阶段执行通道记录: L1+ 已到达阶段必须记录角色契约与执行通道证据"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))
    if "执行通道记录" not in content:
        return True, "💡 提示：旧版任务文档未包含执行通道记录章节，跳过校验。"

    risk_match = re.search(r'-\s*\*\*风险等级\*\*:\s*(L1|L2|L3)', content)
    if not risk_match:
        risk_match = re.search(r'风险等级\s*[:：]\s*(L1|L2|L3)', content)
    risk_level = risk_match.group(1) if risk_match else "L2"

    stage_match = re.search(r'-\s*\*\*当前阶段\*\*:\s*([a-z-]+)', content)
    current_stage = stage_match.group(1).strip() if stage_match else "close"

    stage_order = ["init", "plan-review", "dev", "code-review", "close"]
    if current_stage not in stage_order:
        return False, f"未知当前阶段: {current_stage}。请使用 init/plan-review/dev/code-review/close。"

    reached = set(stage_order[: stage_order.index(current_stage) + 1])
    required = [("1.0", "初始化")]
    if risk_level in ("L2", "L3") and "plan-review" in reached:
        required.append(("2.0", "计划评审"))
    if "dev" in reached:
        required.append(("3.0", "开发与验证"))
    if risk_level in ("L2", "L3") and "code-review" in reached:
        required.append(("4.0", "代码审查"))
    if "close" in reached:
        required.append(("5.0", "收尾归档"))

    missing = []
    incomplete = []
    required_labels = ["角色契约", "执行通道", "偏离处理"]

    for section_id, section_name in required:
        pattern = rf"###\s+{re.escape(section_id)}\s+执行通道记录.*?(?=\n###\s+|\n##\s+|\Z)"
        match = re.search(pattern, content, re.S)
        if not match:
            missing.append(f"{section_id} {section_name}")
            continue
        section = match.group(0)
        for label in required_labels:
            label_match = re.search(rf'-\s*\[\s*([xX\s])\s*\]\s*\*\*{label}\*\*:\s*(.+)', section)
            if not label_match:
                incomplete.append(f"{section_id} {section_name}: 缺少 {label}")
                continue
            checked, value = label_match.groups()
            value = value.strip()
            if checked.strip() == "":
                incomplete.append(f"{section_id} {section_name}: {label} 未勾选")
            elif not value or "待填" in value or "(填写" in value:
                incomplete.append(f"{section_id} {section_name}: {label} 仍为占位")

    if missing or incomplete:
        msg = "🛑 阶段执行通道记录不完整：\n"
        for item in missing:
            msg += f"  - 缺少章节: {item}\n"
        for item in incomplete:
            msg += f"  - {item}\n"
        msg += "L1+ 已到达阶段必须记录角色契约加载、执行通道和偏离/阻塞处理；不得主观绕过规范通道。"
        return False, msg

    return True, f"阶段执行通道记录校验通过 (当前阶段: {current_stage}, 风险等级: {risk_level})"


# ==============================================================================
# 活跃任务定位辅助
# ==============================================================================

def find_active_task(sage_root):
    """在项目中寻找当前活跃任务文档，返回 Path 或 None"""
    # 活跃任务只允许放在 docs/project/；完成后归档到 docs/project/tasks/T-XXX.md
    active_tasks = list((sage_root / "docs" / "project").glob("ACTIVE_TASK_T-*.md"))
    return active_tasks[0] if active_tasks else None


# ==============================================================================
# CLI 入口与多功能调度
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="SAGE 工作流检查器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/sage_linter.py --all                  # 全量扫描\n"
            "  python scripts/sage_linter.py --check-branch         # 分支隔离与命名\n"
            "  python scripts/sage_linter.py --check-scope          # 范围锁定 (hooks 高频)\n"
            "  python scripts/sage_linter.py --check-commit-msg .git/COMMIT_EDITMSG\n"
            "  python scripts/sage_linter.py --check-freshness      # 新鲜度 (cron 定期)\n"
            "  python scripts/sage_linter.py --check-links          # 交叉引用\n"
            "  python scripts/sage_linter.py --all --allow-template-changes  # 规范任务允许模板变更\n"
            "  python scripts/sage_linter.py --all --format json    # JSON 输出\n"
            "  python scripts/sage_linter.py --all --artifact        # Markdown 报告\n"
            "\n退出码: 0=通过, 1=警告, 2=阻断"
        )
    )
    parser.add_argument("--check-task", help="验证指定的活跃任务文档结构与规范")
    parser.add_argument("--all", action="store_true", help="在当前目录下运行一键全量工作流校验")
    parser.add_argument("--allow-template-changes", action="store_true",
                        help="允许模板文件变更（仅限模板/流程规范任务使用）")
    parser.add_argument("--allow-protected-branch", action="store_true",
                        help="允许在已授权的合并/推送阶段对受保护分支运行全量门禁")
    parser.add_argument("--stale-days", type=int, default=30, help="文档新鲜度天数门限 (默认 30 天)")
    # Hooks / CI 单项参数
    parser.add_argument("--check-branch", action="store_true",
                        help="仅执行检查器 #4（分支隔离与 SAGE 通用分支命名）")
    parser.add_argument("--check-scope", action="store_true",
                        help="仅执行检查器 #10（范围锁定），供 hooks 高频调用")
    parser.add_argument("--check-commit-msg",
                        help="检查提交信息文件，要求 Conventional Commit 标题描述包含中文")
    parser.add_argument("--check-freshness", action="store_true",
                        help="仅执行检查器 #6（新鲜度扫描），供 /schedule cron 定期调用")
    parser.add_argument("--check-links", action="store_true",
                        help="仅执行检查器 #11（交叉引用验证）")
    parser.add_argument("--format", choices=["text", "json", "artifact"], default="text",
                        help="输出格式选项 (默认 text)")
    parser.add_argument("--artifact", action="store_true",
                        help="等价于 --format artifact，生成 Markdown 报告到 stdout")
    parser.add_argument("--antigravity", action="store_true",
                        help="兼容旧参数：等价于 --artifact")

    args = parser.parse_args()

    # --artifact / --antigravity 等价于 --format artifact
    if args.artifact or args.antigravity:
        args.format = "artifact"

    # Hooks 感知：SAGE_HOOK=1 或 ANTIGRAVITY_HOOK=1 时自动使用 json 格式（除非显式指定）
    if _IS_HOOK and args.format == "text":
        args.format = "json"

    # 判断是否为单项快速检查模式
    is_single_check = (
        args.check_branch
        or args.check_scope
        or bool(args.check_commit_msg)
        or args.check_freshness
        or args.check_links
    )

    # 自动定位项目路径
    cwd = Path.cwd()

    # 寻找包含 AGENTS.md 的目录作为 SAGE 项目根目录
    sage_root = None
    for p in [cwd] + list(cwd.parents):
        if (p / "AGENTS.md").exists():
            sage_root = p
            break

    if not sage_root:
        if args.format == "json":
            print(json.dumps({"error": "无法定位 SAGE 项目根目录（未找到 AGENTS.md）"}, ensure_ascii=False))
        else:
            print("🛑 错误：无法定位 SAGE 项目根目录（未找到 AGENTS.md）。请在项目根目录下运行此脚本。")
        sys.exit(2)

    # 获取常用的路径引用
    template_file = sage_root / "templates" / "TASK-TEMPLATE.md"
    docs_dir = sage_root / "docs"
    templates_dir = sage_root / "templates"
    changelog_file = sage_root / "CHANGELOG.md"
    decision_log_file = sage_root / "docs" / "project" / "DECISION_LOG.md"

    # 创建结果收集器
    collector = ResultCollector(fmt=args.format)

    # ======================================================================
    # 单项快速检查模式（供 hooks / cron 高频调用）
    # ======================================================================
    if is_single_check:
        if args.check_branch:
            ok, msg = check_git_branch_isolation(sage_root, args.allow_protected_branch)
            collector.add("4. 分支隔离与命名校验", ok, msg)

        if args.check_scope:
            task_file = find_active_task(sage_root)
            if task_file:
                ok, msg = check_scope_lock(task_file, sage_root)
                collector.add("10. 范围锁定校验", ok, msg)
            else:
                collector.add("10. 范围锁定校验", True, "未发现活跃任务文档，跳过范围锁定校验。")

        if args.check_commit_msg:
            ok, msg = check_commit_message(args.check_commit_msg)
            collector.add("15. 提交信息中文校验", ok, msg)

        if args.check_freshness:
            ok, msg = check_document_freshness(docs_dir, args.stale_days)
            collector.add("6. 文档新鲜度扫描", ok, msg)

        if args.check_links:
            ok, msg = check_cross_links(sage_root)
            collector.add("11. 交叉引用校验", ok, msg)

        collector.flush()
        sys.exit(collector.exit_code())

    # ======================================================================
    # 非单项模式：打印 banner（仅 text 格式）
    # ======================================================================
    if args.format == "text":
        print(f"🔍 正在初始化 SAGE Linter，工作根目录: {sage_root}\n")

    # ======================================================================
    # 场景 A: 验证特定的活跃任务
    # ======================================================================
    if args.check_task:
        task_file = Path(args.check_task)
        if not task_file.is_absolute():
            task_file = (sage_root / task_file).resolve()

        if args.format == "text":
            print(f"--- 💡 验证活跃任务文档: {task_file.name} ---")

        # 运行任务特有关联校验
        checkers = [
            (lambda: check_template_copy(task_file, template_file), "1. 模板复制校验"),
            (lambda: check_task_structure(task_file), "2. 任务结构校验"),
            (lambda: check_task_risk_sections(task_file), "3. 风险扩展校验"),
            (lambda: check_scope_lock(task_file, sage_root), "10. 范围锁定校验"),
            (lambda: check_evidence_complete(task_file), "12. 证据链完整校验"),
            (lambda: check_review_complete(task_file), "13. 盲审结果校验"),
            (lambda: check_model_metadata(task_file), "14. 模型元数据校验"),
            (lambda: check_execution_channel_records(task_file), "15. 执行通道记录校验"),
        ]

        for func, name in checkers:
            ok, msg = func()
            collector.add(name, ok, msg)

        if args.format == "text":
            collector.flush()
            print()

    # ======================================================================
    # 场景 B: 一键全量校验 (一键运行全部 13 个检查器)
    # ======================================================================
    if args.all or not args.check_task:
        # 如果 check_task 已运行，需要一个新的收集器用于全量（或合并）
        # 这里我们沿用同一个收集器，让所有结果汇总
        if not args.all and not args.check_task:
            if args.format == "text":
                print("💡 提示：未指定特定参数，默认执行全量一键静态扫描 (--all)\n")

        if args.format == "text":
            print("===================== 🚀 开始工作流静态扫描 =====================")

        # 寻找当前活跃任务文档
        task_file = find_active_task(sage_root)
        if task_file:
            if args.format == "text":
                print(f"发现活跃任务文档: {task_file.name}")
        else:
            if args.format == "text":
                print("ℹ️ 未发现当前活跃任务文档 (docs/project/ACTIVE_TASK_T-*.md)，跳过任务级细节校验。")

        # 1. 物理分支隔离校验
        ok, msg = check_git_branch_isolation(sage_root, args.allow_protected_branch)
        collector.add("[4/13] 分支隔离校验", ok, msg)

        # 2. 模板守护校验
        if args.allow_template_changes:
            ok, msg = True, "模板变更已由 --allow-template-changes 显式允许"
        else:
            ok, msg = check_templates_pristine(templates_dir, sage_root)
        collector.add("[7/13] 模板完整校验", ok, msg)

        # 3. 只增不改日志校验
        ok, msg = check_append_only(decision_log_file, sage_root)
        collector.add("[9/13] 日志增改限制", ok, msg)

        # 4. CHANGELOG 联动更新校验
        ok, msg = check_changelog_update(changelog_file, sage_root)
        collector.add("[8/13] 日志更新联动", ok, msg)

        # 5. T2 规范体积校验
        ok, msg = check_t2_document_lines(docs_dir)
        collector.add("[5/13] 规范文档体积", ok, msg)

        # 6. 本地交叉引用验证 — 扫描整个项目根目录
        ok, msg = check_cross_links(sage_root)
        collector.add("[11/13] 交叉引用校验", ok, msg)

        # 7. 文档新鲜度扫描 (警告级)
        ok, msg = check_document_freshness(docs_dir, args.stale_days)
        collector.add("[6/13] 文档新鲜扫描", ok, msg)

        # [FIX DESIGN-3] 如果已通过 --check-task 单独校验过，不再重复执行任务级校验
        if task_file and not args.check_task:
            if args.format == "text":
                print("\n--- 任务级细节深度扫描 ---")
            task_checkers = [
                (lambda: check_template_copy(task_file, template_file), "[1/13] 模板复制校验"),
                (lambda: check_task_structure(task_file), "[2/13] 任务大纲校验"),
                (lambda: check_task_risk_sections(task_file), "[3/13] 风险扩展校验"),
                (lambda: check_scope_lock(task_file, sage_root), "[10/13] 范围锁定校验"),
                (lambda: check_evidence_complete(task_file), "[12/13] 证据链校验"),
                (lambda: check_review_complete(task_file), "[13/14] 盲审结果校验"),
                (lambda: check_model_metadata(task_file), "[14/14] 模型元数据校验"),
                (lambda: check_execution_channel_records(task_file), "[15/15] 执行通道记录校验"),
            ]
            for func, name in task_checkers:
                ok, msg = func()
                collector.add(name, ok, msg)

        if args.format == "text":
            print("\n================================================================")

    # ======================================================================
    # 输出结果
    # ======================================================================
    collector.flush()

    # 最终状态出口（text 格式额外打印总结行）
    exit_code = collector.exit_code()
    if args.format == "text":
        if exit_code == 0:
            print("\n🎉 恭喜！工作流静态扫描全部通过。可以安全进入下一阶段。")
        elif exit_code == 1:
            print("\n⚠️ 扫描发现警告项（非阻断）。建议关注上述标黄(🟡)项目。")
        else:
            print("\n❌ 扫描发现阻断级错误。请修正上述标红(🔴)项目后重试。")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
