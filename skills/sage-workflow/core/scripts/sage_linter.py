#!/usr/bin/env python3
"""SAGE 工作流检查器 (SAGE Linter)

此脚本集成了方法论中要求的所有 19 个检查器，不依赖任何第三方 Python 库，
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
    python scripts/sage_linter.py --all --no-log          # 禁用运行日志写入

退出码:
    0 = 全部通过
    1 = 有警告（但无阻断）
    2 = 有阻断性问题

规则 ID 与运行日志:
    fail/warn 结果携带稳定规则 ID（SAGE-01~17，由检查器标签编号派生），text/json/artifact
    三种格式统一输出；消息内同时披露启发式判定的命中依据（命中的占位词/缺失的格式）。
    默认每次运行向 <sage_root>/.sage/linter-runs.jsonl 追加单行 JSON
    （ts/mode/exit_code/fail/warn），供统计各检查器拦截频率；--no-log 关闭；
    ANTIGRAVITY_HOOK=1 高频调用仅记录存在 fail/warn 的运行。
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
# .sage/ 为 linter 自身运行日志目录，避免门禁产物被误判为项目源码
_META_PREFIXES = (".sage/", "docs/", "templates/", "archive/", "scripts/", "prompts/")

# L0 分支命名模式：SAGE-04 allowed_patterns 与 SAGE-08 L0 豁免共用同一模式源，防漂移
# （T-022 盲审建议 1：两检查器共享「l0 分支形态」契约，避免各自维护正则）
_L0_BRANCH_PATTERNS = [
    r"^fix/l0-[a-z0-9][a-z0-9-]*$",
    r"^docs/l0-[a-z0-9][a-z0-9-]*$",
    r"^chore/l0-[a-z0-9][a-z0-9-]*$",
    r"^style/l0-[a-z0-9][a-z0-9-]*$",
]
_META_EXACT = {
    "AGENTS.md", "ARCHITECTURE.md", "CHANGELOG.md",
    ".gitignore", ".env", ".editorconfig",
}

# 文档扫描排除项（T2 体积 / 新鲜度 / 交叉引用三检查器共享）：
# 基础标记 + 各检查器按需追加；只读第三方参考目录以跨项目通用后缀识别
# （-ref / -reference / -vendor），禁止写入具体项目名，避免工具链与业务仓库耦合
_SCAN_EXCLUDE_MARKERS = ("node_modules",)
_SCAN_EXCLUDE_SUFFIXES = ("-ref", "-reference", "-vendor")

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


def _is_scan_excluded(fp_posix, extra_markers=()):
    """判断路径是否排除在文档扫描之外（依赖 / 归档 / 只读第三方参考目录）。

    只读参考目录按目录名后缀（-ref / -reference / -vendor）识别，
    不写具体项目名——业务仓库代号不得硬编码进通用工具链。
    """
    for marker in tuple(_SCAN_EXCLUDE_MARKERS) + tuple(extra_markers):
        if marker in fp_posix:
            return True
    return any(part.endswith(_SCAN_EXCLUDE_SUFFIXES) for part in fp_posix.split("/"))


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

def _rule_id_from_label(label):
    """从检查器显示标签提取稳定规则 ID（SAGE-XX）

    兼容两种标签形态：全量模式 "[10/17] 范围锁定校验" 与单项模式 "10. 范围锁定校验"。
    无法解析编号时返回 None，输出侧降级为不标注规则 ID，不影响判定结果。
    """
    match = re.match(r"^(?:\[(\d+)/\d+\]|(\d+)[.、])", label.strip())
    if not match:
        return None
    return f"SAGE-{int(match.group(1) or match.group(2)):02d}"


class CheckResult:
    """单个检查器的结果"""
    __slots__ = ("checker", "status", "message", "rule_id")

    def __init__(self, checker, status, message, rule_id=None):
        self.checker = checker      # 检查器名称
        self.status = status        # "pass" | "warn" | "fail"
        self.message = message      # 详细信息
        self.rule_id = rule_id      # 稳定规则 ID（SAGE-XX），无法派生时为 None

    def to_dict(self):
        return {
            "checker": self.checker,
            "status": self.status,
            "message": self.message,
            "rule_id": self.rule_id,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ResultCollector:
    """收集所有检查结果并按指定格式输出"""

    def __init__(self, fmt="text"):
        self.fmt = fmt              # "text" | "json" | "artifact"
        self.results = []

    def add(self, checker_name, ok, message, rule_id=None):
        """添加一个检查结果。ok=True 且含 ⚠️ 时视为 warn，否则 pass/fail

        rule_id 显式指定时优先于标签派生：用于标签编号与保留段冲突的检查器
        （如计划放行 [17/17] 显式映射 SAGE-18——SAGE-17 为提交信息单项检查器
        保留段，T-014 刻意保留；契约见 T-018 1.2 决策）。
        """
        if ok and "⚠️" in message:
            status = "warn"
        elif ok:
            status = "pass"
        else:
            status = "fail"
        self.results.append(CheckResult(
            checker_name, status, message,
            rule_id if rule_id is not None else _rule_id_from_label(checker_name),
        ))

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
        warn_results = []
        for r in self.results:
            icon = {"pass": "🟢", "warn": "🟡", "fail": "🔴"}[r.status]
            tag = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}[r.status]
            rule_tag = f"[{r.rule_id}] " if r.rule_id else ""
            if r.status == "warn":
                warn_results.append(r)
                print(f"  {icon} {r.checker}: {tag}")
            elif r.status == "pass":
                print(f"  {icon} {r.checker}: {r.message}")
            else:
                print(f"  {icon} {r.checker}: {tag}\n    👉 {rule_tag}{r.message}")
        if warn_results:
            print("\n💡 警告细节:")
            for r in warn_results:
                rule_tag = f"[{r.rule_id}] " if r.rule_id else ""
                print(f"{rule_tag}{r.message}")

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
            rule_tag = f"[{r.rule_id}] " if r.rule_id else ""
            # 在 Markdown 表格中转义管道符和换行
            msg = (rule_tag + r.message).replace("|", "\\|").replace("\n", " ")
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
                lines.append(f"### {r.checker}（{r.rule_id}）" if r.rule_id else f"### {r.checker}")
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
# 19 个检查器核心实现
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
        cell_names = ("验收标准", "验证方式", "证据位置")
        for ac_id, ac_type, criterion, verify, evidence in ac_rows:
            if ac_type not in ["[auto]", "[manual]"]:
                invalid_ac.append(f"{ac_id}: 类型列当前值 \"{ac_type}\"，必须为 [auto] 或 [manual]")
            if ac_type == "[auto]":
                auto_count += 1
            if ac_type == "[manual]":
                manual_count += 1
            # 逐单元格披露判定依据：空列与占位命中分别报告，并附完整判定词表
            for cell_name, value in zip(cell_names, (criterion, verify, evidence)):
                if not value:
                    invalid_ac.append(f"{ac_id}: {cell_name} 列为空")
                    continue
                hit_marker = next((m for m in placeholder_markers_ac if m in value), None)
                if hit_marker:
                    invalid_ac.append(
                        f"{ac_id}: {cell_name} 列 \"{value}\" 命中占位符标记 \"{hit_marker}\""
                        f"（判定词表: {'、'.join(placeholder_markers_ac)}）"
                    )

        if not ac_rows:
            return False, (
                f"风险等级为 {risk_level}，但 ### 1.3a 验收标准 未使用 AC-ID 验收映射。"
                "请为每条验收标准填写 AC-ID、[auto]/[manual]、验证方式和证据位置。"
            )
        if invalid_ac:
            return False, "验收标准映射不完整（判定依据见各项）：\n  - " + "\n  - ".join(invalid_ac)

        acceptance_warning = ""
        if manual_count > 0 and auto_count == 0:
            acceptance_warning = " ⚠️ 验收标准全部为 [manual]，请确认不存在可自动化验证的关键约束。"

        # [FIX BUG-3] 检查 1.3b 风险矩阵：用多个占位符标记综合判定
        idx_13b = content.find("### 1.3b 风险矩阵")
        section_content_b = content[idx_13b:idx_14] if idx_14 != -1 else content[idx_13b:]
        table_lines = [l.strip() for l in section_content_b.splitlines() if "|" in l]
        # 表格应该有表头、分割线、以及至少一行非占位符的真实数据
        placeholder_markers = ["风险描述", "低/中/高", "缓解方案", "待填", "缓解措施"]
        if len(table_lines) < 3:
            return False, (
                f"风险等级为 {risk_level}，但 ### 1.3b 风险矩阵 缺少完整表格"
                f"（需表头行 + 分隔行 + 至少一行数据，当前仅 {len(table_lines)} 行）。"
            )
        data_rows = table_lines[2:]
        rows_with_hit = [row for row in data_rows if any(m in row for m in placeholder_markers)]
        if len(rows_with_hit) == len(data_rows):
            hit_markers = sorted({m for row in data_rows for m in placeholder_markers if m in row})
            return False, (
                f"风险等级为 {risk_level}，但 ### 1.3b 风险矩阵 未填写具体内容："
                f"全部 {len(data_rows)} 行数据均命中占位符标记（命中: {'、'.join(hit_markers)}；"
                f"判定词表: {'、'.join(placeholder_markers)}）。请替换为真实的风险条目。"
            )

    return True, f"风险分级扩展项校验通过 (风险等级: {risk_level})" + (acceptance_warning if risk_level in ["L2", "L3"] else "")

def check_git_branch_isolation(cwd=None, allow_protected=False, task_file=None):
    """4. 分支隔离校验: 校验当前是否处于受保护的主干分支上开发

    上下文三态感知（T-022）：受保护分支命中时按上下文判定，而非无脑阻断——
    ①有活跃任务 → 阻断（开发应走功能分支）；②无活跃任务+工作区有变更 → 阻断
    （直改保护分支即违规开发）；③无活跃任务+工作区干净 → True+💡 终态/闲置跳过
    说明（合并后终态或任务间闲置，非开发场景）。两条阻断消息均补 AP-009 披露
    （自述判定依据 + --allow-protected-branch 豁免参数与适用条件）。非受保护分支
    命名校验路径零改动。task_file=None（向后兼容）时退化为「无活跃任务」上下文。
    """
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

        # 上下文三态判定：活跃任务存在性（task_file 非空且文件存在）
        # 与工作区干净度（get_git_diff_files 复用既有实现）为判定信号
        has_active_task = task_file is not None and Path(task_file).exists()

        if has_active_task:
            # 态①有活跃任务 → 阻断（开发应走功能分支）
            return False, (
                f"🛑 隔离红线违规：当前处于受保护的分支 '{curr_branch}' 且存在活跃任务"
                f"（{Path(task_file).name}），开发必须在独立功能分支上进行！"
                f"如为已授权的合并/推送阶段，可使用 --allow-protected-branch 参数豁免本项校验。"
            )

        # 无活跃任务：检查工作区是否干净
        changed_files = get_git_diff_files(cwd)
        if changed_files:
            # 态②无活跃任务+工作区非干净 → 阻断（直改保护分支即违规开发）
            return False, (
                f"🛑 隔离红线违规：当前处于受保护的分支 '{curr_branch}'，无活跃任务"
                f"但工作区非干净（{len(changed_files)} 个未提交变更文件）。"
                f"如为已授权的合并/推送阶段，可使用 --allow-protected-branch 参数豁免本项校验。"
            )

        # 态③无活跃任务+工作区干净 → True+💡 终态/闲置跳过说明
        return True, (
            f"💡 受保护分支 '{curr_branch}' 无活跃任务且工作区干净，"
            f"判定为合并后终态或任务间闲置，跳过分支隔离阻断。"
        )

    allowed_patterns = [
        * _L0_BRANCH_PATTERNS,
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
        if _is_scan_excluded(fp_posix):
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
        if _is_scan_excluded(fp_posix, extra_markers=("architecture/tasks", "archive")):
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
        # AP-009 披露：报错须自述出路——披露豁免参数与适用条件，
        # 避免模板升级类任务的执行者误回滚合法交付物（T-018 计划盲审实证的返工诱因，T-015 先例）
        msg += (
            "若交付物本身即模板变更的任务，可在开发期使用 --allow-template-changes 参数"
            "豁免本项校验，并须在任务文档中记录豁免理由。"
        )
        return False, msg

    return True, "模板完整性校验通过 (模板文件未被篡改)"

def check_changelog_update(changelog_file, cwd=None, task_file=None):
    """8. CHANGELOG 更新校验: 检查发生代码变更时，CHANGELOG.md 是否有对应修改

    阶段感知（T-021）：CHANGELOG 回填是收尾期（close）动作（closer 契约将「更新 CHANGELOG」
    划归阶段 5 归档职责），init/plan-review/dev/code-review 期该产出本不应存在，此时强制属
    「拦截位置写错」的阶段预期拦截；close 期维持既有强制判定。task_file=None（向后兼容）或
    TASK 文件不存在、元数据缺失/未知阶段值/模板默认行时，按 fail-safe 退回既有强制行为（最严侧），
    与 check_evidence_complete 的阶段感知设计同构（复用 _parse_current_stage 单一解析点）。

    L0 流程感知（T-022）：无活跃任务上下文（task_file=None 或文件不存在）时，l0 命名分支
    豁免 CHANGELOG 强制（changelog-standards §一「L0 纯机械修正可不新增版本」）；非 l0 分支
    维持既有强制（fail-safe 最严侧）。l0 判定模式与 SAGE-04 allowed_patterns 共用
    _L0_BRANCH_PATTERNS 同一模式源，防漂移。有活跃任务时的阶段感知判定（T-021）零改动。
    """
    changelog_path = Path(changelog_file)
    if not changelog_path.exists():
        return True, "CHANGELOG.md 不存在，跳过更新校验。"

    changed_files = get_git_diff_files(cwd)
    if not changed_files:
        return True, "无任何文件变更，无需校验 CHANGELOG 更新。"

    # 阶段感知判定：置于「无文件变更早退」之后、既有强制判定之前，
    # 使 close 期真实变更路径完整保留（close 落入下方原有逻辑）。
    if task_file is not None:
        task_path = Path(task_file)
        if task_path.exists():
            content = "".join(get_file_lines(task_path))
            current_stage, stage_is_default = _parse_current_stage(content)
            if stage_is_default:
                # 模板默认行（未随任务推进更新）：无法判定阶段，fail-safe 强制并披露判定依据（AP-009）
                return False, (
                    "🛑 当前阶段元数据仍为模板默认值（未更新），无法判定任务所处阶段，"
                    "按 fail-safe 强制校验 CHANGELOG 更新；请更新任务元数据「当前阶段」"
                    "（取值：init/plan-review/dev/code-review/close）。"
                )
            if current_stage in ("init", "plan-review", "dev", "code-review"):
                # CHANGELOG 回填未到期：绿色通过 + 一行状态说明（非阻断、非警告、无动作要求）
                return True, (
                    f"💡 提示：当前阶段为 {current_stage}，CHANGELOG 更新回填属收尾期"
                    f"（close）动作，尚未到期，跳过校验。"
                )
            if current_stage != "close":
                # 元数据缺失（空值）或未知阶段值：无法判定阶段，fail-safe 强制并回显实际值（AP-009）
                return False, (
                    f"🛑 当前阶段元数据无法识别（当前阶段: {current_stage or '<缺失>'}），"
                    "无法判定任务所处阶段，按 fail-safe 强制校验 CHANGELOG 更新；"
                    "请更新任务元数据「当前阶段」（取值：init/plan-review/dev/code-review/close）。"
                )
        # task_file 指向的文件不存在：落入下方 L0 判定（无活跃任务上下文，fail-safe 最严侧）

    # L0 流程感知（T-022）：无活跃任务上下文（task_file=None 或文件不存在）时，
    # l0 命名分支豁免 CHANGELOG 强制——changelog-standards §一明文「L0 纯机械修正可不新增版本」；
    # l0 分支前缀是 SAGE-04 allowed_patterns 已固化的既有契约，是「本变更属 L0 流程」唯一
    # 机器可读声明。命中 → 💡 跳过（含规范出处 + 若改变规则仍需记录的提示）；未命中
    # （如 t-XXX 分支却无 TASK 文档）维持既有强制（fail-safe 最严侧）。有活跃任务时
    # （task_file 指向文件存在）上方阶段感知判定已先行 return，不进入本块。
    has_active_task_ctx = task_file is not None and Path(task_file).exists()
    if not has_active_task_ctx:
        curr_branch = run_git_cmd(["branch", "--show-current"], cwd)
        if curr_branch and any(re.match(pat, curr_branch) for pat in _L0_BRANCH_PATTERNS):
            return True, (
                f"💡 当前分支 '{curr_branch}' 符合 L0 流程命名规范且无活跃任务，"
                f"按 changelog-standards §一「L0 纯机械修正可不新增版本」跳过 CHANGELOG 强制。"
                f"若改变规则、目录口径或历史归档，仍需记录变更。"
            )

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
        if _is_scan_excluded(fp_posix, extra_markers=("archive", "references")):
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

def _parse_current_stage(content: str) -> tuple[str, bool]:
    """解析任务元数据「当前阶段」（TD-9，三阶段感知检查器共享单一实现）。

    返回 (stage, is_template_default)：
    - stage: 元数据声明的阶段值（首个小写 token）；标签行缺失或无法提取 token 时为 ""
    - is_template_default: 元数据仍为模板管道默认行（未更新）时为 True

    模板默认行 `- **当前阶段**: init | plan-review | ...` 曾被 ([a-z-]+) 捕获为 "init"，
    任务推进后未更新元数据会被误判为 init 而跳过阶段感知校验（误放行暴露，T-016 修复）；
    调用方对默认值按各自 fail-safe 语义显式报错并披露更新指引。
    """
    match = re.search(r'-\s*\*\*当前阶段\*\*:\s*(.*)', content)
    if not match:
        return "", False
    value = match.group(1).strip()
    if "|" in value:
        return "", True
    token = re.match(r"[a-z-]+", value)
    return (token.group(0) if token else ""), False

def check_evidence_complete(task_file):
    """12. 证据链完整性: 校验开发完成后，任务文档中的测试结果和 lint 结果是否已填写勾选"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    # 阶段感知：证据链在开发完成（code-review/close）后才强制校验。
    # init/plan-review/dev 期 3.2 复选框本应留空，提前勾选反而属于伪造证据；
    # 元数据缺失或未知阶段时维持强制（fail-safe），与 check_execution_channel_records 的阶段感知设计一致。
    current_stage, stage_is_default = _parse_current_stage(content)
    if stage_is_default:
        return False, (
            "🛑 当前阶段元数据仍为模板默认值（未更新），无法判定任务所处阶段，"
            "按 fail-safe 强制校验 3.2 证据链；请更新任务元数据「当前阶段」"
            "（取值：init/plan-review/dev/code-review/close）。"
        )
    if current_stage in ("init", "plan-review", "dev"):
        return True, f"💡 提示：当前阶段为 {current_stage}，3.2 证据链尚未到期，跳过校验。"

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

def _strip_html_comments(content: str) -> str:
    """剥离 Markdown 中的 HTML 注释（含跨行，TD-8）：模板 2.1/4.1 节内置的门禁注释含
    OK/WARN/BLOCK 字样，不剥离会被 check_review_complete 误计为审查结论标记与实质内容，
    空章节恒放行。剥离仅用于判定输入，不改变原文件。"""
    return re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

def check_review_complete(task_file):
    """13. 盲审结果完整性: L2/L3 任务必须写入计划评审与代码评审报告"""
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))
    # TD-8：HTML 门禁注释不参与结论标记与实质内容判定，剥离后再做章节定位与三态诊断
    content = _strip_html_comments(content)

    risk_match = re.search(r'-\s*\*\*风险等级\*\*:\s*(L1|L2|L3)', content)
    if not risk_match:
        risk_match = re.search(r'风险等级\s*[:：]\s*(L1|L2|L3)', content)
    risk_level = risk_match.group(1) if risk_match else "L2"

    if risk_level == "L1":
        return True, "L1 任务可跳过阶段二/四盲审，跳过盲审完整性校验。"

    # 阶段感知（T-015）：计划评审报告到 plan-review 才到期，代码评审报告到 code-review 才到期；
    # 早期阶段模板空节未填属预期，提前强制会误报阻断。元数据缺失或未知阶段维持强制（fail-safe），
    # 与 check_evidence_complete 的阶段感知设计一致。
    current_stage, stage_is_default = _parse_current_stage(content)
    if stage_is_default:
        return False, (
            "🛑 当前阶段元数据仍为模板默认值（未更新），无法判定任务所处阶段，"
            "按 fail-safe 强制校验（2.1/4.1 均须写入有效审查报告）；请更新任务元数据「当前阶段」"
            "（取值：init/plan-review/dev/code-review/close）。"
        )
    if current_stage == "init":
        return True, "💡 提示：当前阶段为 init，2.1/4.1 盲审报告均未到期，跳过校验。"
    code_due = current_stage not in ("plan-review", "dev")

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

    placeholders = ["由 reviewer 填写", "如有修改", "评审反馈", "待填", "(由", "(如有"]
    substantive_markers = ["审查结果", "OK", "WARN", "BLOCK", "✅", "⚠️", "🛑"]

    def diagnose_review_section(section):
        """三态诊断：章节缺失 / 无审查结论标记 / 有标记但仅占位文本。

        判定语义与词表内容保持不变，仅把判定理由返回给调用方用于消息披露。
        返回 None 表示章节有效。
        """
        if not section:
            return "章节不存在（要求标题: ### 2.1 评审意见 / ### 4.1 代码评审）"
        if not any(m in section for m in substantive_markers):
            return (
                "章节存在但未找到审查结论标记（判定词表: "
                + "/".join(substantive_markers)
                + "）；请写明审查结果 OK/WARN/BLOCK 或对应符号"
            )
        has_content = any(
            line.strip()
            and not line.strip().startswith("###")
            and not line.strip().startswith("- [ ]")
            and not line.startswith("- [ ]")
            and not any(p in line for p in placeholders)
            for line in section.splitlines()
        )
        if not has_content:
            return (
                "存在审查标记但无实质内容（除标题、空复选框与占位行外无有效文本；"
                "占位词表: " + "/".join(placeholders) + "）"
            )
        return None

    problems = []
    plan_reason = diagnose_review_section(plan_section)
    if plan_reason:
        problems.append(f"2.1 计划评审报告：{plan_reason}")
    if code_due:
        code_reason = diagnose_review_section(code_section)
        if code_reason:
            problems.append(f"4.1 代码评审报告：{code_reason}")

    if problems:
        return False, (
            f"🛑 盲审结果缺失：风险等级为 {risk_level}，以下章节未写入有效审查报告：\n  - "
            + "\n  - ".join(problems)
            + "\n调用 agy 后必须确认 TASK 文档对应章节已写入 OK/WARN/BLOCK 等 Markdown 审查结果，"
            + "否则不得继续流转。"
        )

    if not code_due:
        return True, (
            f"盲审结果完整性校验通过 (风险等级: {risk_level}；当前阶段 {current_stage}，"
            f"4.1 代码评审报告未到期跳过)"
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

    # 检测空值或占位符文本（正则与类别标签配对，命中时向消息披露判定依据）
    placeholder_patterns = [
        (r'^\s*$', "空值"),
        (r'^\[.*\]$', "方括号占位符"),
        (r'待填', "占位词\"待填\""),
        (r'TBD', "占位词 TBD"),
        (r'N/?A', "占位词 N/A"),
        (r'^[-—]+$', "破折号占位"),
        (r'^\(.*\)$', "括号占位符"),
        (r'填写', "占位词\"填写\""),
    ]

    for pat, label in placeholder_patterns:
        if re.search(pat, model_value, re.IGNORECASE):
            return False, (
                f"⚠️ 任务文档元数据中的\"使用模型\"字段仍为占位符文本: \"{model_value}\"（命中判定: {label}）。"
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

    current_stage, stage_is_default = _parse_current_stage(content)
    if stage_is_default:
        return False, (
            "🛑 当前阶段元数据仍为模板默认值（未更新），无法判定已到达阶段；"
            "请更新任务元数据「当前阶段」（取值：init/plan-review/dev/code-review/close）后重跑。"
        )
    if not current_stage:
        current_stage = "close"

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
            missing.append(f"{section_id} {section_name}（要求标题: ### {section_id} 执行通道记录）")
            continue
        section = match.group(0)
        for label in required_labels:
            label_match = re.search(rf'-\s*\[\s*([xX\s])\s*\]\s*\*\*{label}\*\*:\s*(.+)', section)
            if not label_match:
                incomplete.append(
                    f"{section_id} {section_name}: 缺少 {label}（要求行格式: - [x] **{label}**: 实际内容）"
                )
                continue
            checked, value = label_match.groups()
            value = value.strip()
            if checked.strip() == "":
                incomplete.append(f"{section_id} {section_name}: {label} 复选框未勾选（[ ] 需改为 [x]）")
            elif not value:
                incomplete.append(f"{section_id} {section_name}: {label} 值为空，需填写实际内容")
            elif "待填" in value or "(填写" in value:
                incomplete.append(
                    f"{section_id} {section_name}: {label} 值 \"{value}\" 为占位文本（判定词: 待填、(填写）"
                )

    if missing or incomplete:
        msg = "🛑 阶段执行通道记录不完整：\n"
        for item in missing:
            msg += f"  - 缺少章节: {item}\n"
        for item in incomplete:
            msg += f"  - {item}\n"
        msg += "L1+ 已到达阶段必须记录角色契约加载、执行通道和偏离/阻塞处理；不得主观绕过规范通道。"
        return False, msg

    return True, f"阶段执行通道记录校验通过 (当前阶段: {current_stage}, 风险等级: {risk_level})"


def _parse_plan_clearance(content: str) -> tuple[str, bool]:
    """解析任务元数据「计划放行」（T-018 人类掌舵点，check_plan_clearance 专用）。

    返回 (value, present)：value 为整行捕获的元数据值（strip 后），present 为标签行是否存在。
    与 _parse_current_stage 不同：模板默认值「待放行」是该字段的合法初始值（新任务 init 期
    尚未到放行时点），因此不设模板默认值标记；到期判定由调用方结合阶段与风险等级完成。
    """
    match = re.search(r'-\s*\*\*计划放行\*\*:\s*(.*)', content)
    if not match:
        return "", False
    return match.group(1).strip(), True

def check_plan_clearance(task_file):
    """18. 计划放行校验: L1/L2 任务进入 dev 前必须已获用户明确放行（人类掌舵点，T-018）

    编号口径：清单编号与 --check-task 场景 A 标签为 18.；--all 场景 B 标签为 [17/17]
    （任务级注册序），经 ResultCollector.add 显式 rule_id 映射 SAGE-18。

    判定矩阵（T-018 1.2 决策 4/5）：
    - 到期：当前阶段 ∈ {dev, code-review, close}（或未知值 fail-safe）且风险等级 ∈ {L1, L2}
      （或等级缺失 fail-safe 强制）
    - 未到期：init / plan-review——放行请求按 planner.md 第 8 节时点尚未发生属预期
    - 跳过：L0（不适用）；L3（每阶段人工确认已覆盖）；当前阶段为模板默认行——任务尚处
      init 模板态，「计划放行: 待放行」是合法初始值，此时不存在进 dev 暴露（且模板默认
      阶段会被 T-016 三个阶段感知检查器阻断，无逃逸路径）
    - 放行记录判定：整行捕获（T-016 同款模式，不经 _parse_current_stage），以「已放行」
      开头即通过；行缺失或其余值一律阻断，披露当前值与修复指引（AP-009：自述判定依据）。
    """
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    risk_match = re.search(r'-\s*\*\*风险等级\*\*:\s*(L0|L1|L2|L3)', content)
    if not risk_match:
        risk_match = re.search(r'风险等级\s*[:：]\s*(L0|L1|L2|L3)', content)
    risk_level = risk_match.group(1) if risk_match else "L2"

    if risk_level == "L0":
        return True, "L0 任务不适用计划放行门，跳过校验。"
    if risk_level == "L3":
        return True, "L3 任务由每阶段人工确认覆盖，跳过计划放行校验。"

    current_stage, stage_is_default = _parse_current_stage(content)
    if stage_is_default:
        return True, (
            "💡 提示：当前阶段元数据仍为模板默认值（任务尚处 init 模板态），"
            "「计划放行: 待放行」为合法初始值，跳过校验；进入 dev 前必须完成计划放行"
            "（planner.md 第 8 节五要素请求 + 用户三处置）。"
        )
    if current_stage in ("init", "plan-review"):
        return True, f"💡 提示：当前阶段为 {current_stage}，计划放行尚未到期，跳过校验。"

    # 到期（dev/code-review/close，未知阶段值按 fail-safe 强制）
    value, present = _parse_plan_clearance(content)
    if present and value.startswith("已放行"):
        return True, "计划放行校验通过（元数据记录已放行）"
    if not present:
        return False, (
            "🛑 任务已进入 dev 及之后阶段，但元数据缺失「计划放行」字段，按 fail-safe "
            "强制要求放行记录；请按 planner.md 第 8 节向用户提交计划放行请求（五要素："
            "目标概览/可写清单【范围增量标注】/自决清单/风险概览/盲审结论），获用户明确"
            "「放行」后将元数据置为「已放行（用户确认，时间戳）」。代理不得代填放行记录。"
        )
    return False, (
        f"🛑 任务已进入 dev 及之后阶段，但计划放行未完成（当前值：{value or '空'}）。"
        "未获用户明确「放行」不得进入 dev 或派发 coder；请按 planner.md 第 8 节向用户"
        "提交计划放行请求（五要素：目标概览/可写清单【范围增量标注】/自决清单/风险概览/"
        "盲审结论），获用户明确「放行」后将元数据置为「已放行（用户确认，时间戳）」。"
        "代理不得代填放行记录。"
    )


_CLEARANCE_REQUEST_HEADING = "计划放行请求"
# 放行请求五要素关键词（T-024 判定矩阵，与 planner.md 第 8 节固定五要素对齐）：
# 目标/可写清单/自决清单/风险概览/盲审结论。用正则做容错匹配（允许「可写文件清单」
# 「自决项清单」「风险与缓解概览」等既有措辞），避免对同义词误报也避免漏报。
# 每个键为关键词展示名，值为命中正则；缺失时以展示名披露缺失项。
_CLEARANCE_REQUEST_KEYWORDS = {
    "目标": r"目标",
    "可写清单": r"可写.{0,4}清单",
    "自决清单": r"自决.{0,4}清单",
    "风险概览": r"风险.{0,8}概览",
    "盲审结论": r"盲审结论",
}


def _extract_clearance_request_record(content: str, risk_level: str) -> str | None:
    """从 TASK 文档提取放行请求落盘小节正文。

    落盘位置（T-024，与 planner.md 第 8 节「落盘要求」一致）：
    - L2 → 2.x 节固定小节「计划放行请求」（如 `### 2.2 计划放行请求`）
    - L1 → 1.5 后固定小节同名（如 `### 1.6 计划放行请求`）
    按小节标题精确定位（标题行即「计划放行请求」），提取到下一个 `###` 标题为止，
    避免把 2.x/1.5 节其他内容误纳入关键词检测范围造成误判。
    返回小节正文；未找到小节返回 None（由调用方按 fail-safe 阻断）。
    """
    pattern = r"^###\s*2\.\d+\s*" + _CLEARANCE_REQUEST_HEADING if risk_level == "L2" else \
        r"^###\s*1\.(?:[6-9]|\d{2,})\s*" + _CLEARANCE_REQUEST_HEADING
    section_start = re.search(pattern, content, flags=re.MULTILINE)
    if not section_start:
        return None
    next_heading = re.search(r"^###\s", content[section_start.end():], flags=re.MULTILINE)
    if next_heading:
        return content[section_start.end():section_start.end() + next_heading.start()]
    return content[section_start.end():]


def check_clearance_request_record(task_file):
    """19. 放行请求落盘校验: L1/L2 任务 dev 及之后，放行请求五要素原文必须落盘 TASK 文档

    （T-024 人类掌舵点可追溯性：ask 弹窗瞬逝无法追溯「当时放了什么行」，五要素原文
    必须写入 TASK 文档持久化，不依赖弹窗；与 SAGE-18 check_plan_clearance 互补——
    SAGE-18 校验「已放行」状态，本检查器校验「放行请求原文已落盘」）

    编号口径：清单编号与 --check-task 场景 A 标签为 19.；--all 场景 B 标签为 [19/19]
    （任务级注册序），经 ResultCollector.add 显式 rule_id 映射 SAGE-19。

    判定矩阵：
    - 到期：当前阶段 ∈ {dev, code-review, close} 且风险等级 ∈ {L1, L2}（或等级缺失
      fail-safe 强制）→ 检查落盘位置存在放行请求五要素关键词
    - 未到期：init / plan-review → 跳过（放行请求时点尚未发生，属预期）
    - 跳过：L0（不适用）；L3（每阶段人工确认已覆盖）；当前阶段为模板默认行
      （任务尚处 init 模板态，「待放行」为合法初始值，无进 dev 暴露）
    - fail-safe：当前阶段字段缺失或未知阶段值 → 阻断（维持既有最严侧强制语义，
      与 check_plan_clearance 同构）
    - 落盘位置：L2 → 2.x 节固定小节「计划放行请求」；L1 → 1.5 后固定小节同名；
      关键词检测用包含关系（目标/可写清单/自决清单/风险概览/盲审结论），避免误报
    """
    task_path = Path(task_file)
    if not task_path.exists():
        return False, f"任务文档不存在: {task_file}"

    content = "".join(get_file_lines(task_path))

    risk_match = re.search(r'-\s*\*\*风险等级\*\*:\s*(L0|L1|L2|L3)', content)
    if not risk_match:
        risk_match = re.search(r'风险等级\s*[:：]\s*(L0|L1|L2|L3)', content)
    risk_level = risk_match.group(1) if risk_match else "L2"

    if risk_level == "L0":
        return True, "L0 任务不适用放行请求落盘校验，跳过校验。"
    if risk_level == "L3":
        return True, "L3 任务由每阶段人工确认覆盖，跳过放行请求落盘校验。"

    current_stage, stage_is_default = _parse_current_stage(content)
    if stage_is_default:
        return True, (
            "💡 提示：当前阶段元数据仍为模板默认值（任务尚处 init 模板态），"
            "放行请求落盘校验未到期，跳过校验。"
        )
    if current_stage in ("init", "plan-review"):
        return True, f"💡 提示：当前阶段为 {current_stage}，放行请求落盘校验未到期，跳过校验。"

    # 到期（dev/code-review/close，未知阶段值按 fail-safe 强制）——提取落盘小节并核对五要素关键词
    record = _extract_clearance_request_record(content, risk_level)
    if record is None:
        return False, (
            "🛑 任务已进入 dev 及之后阶段，但 TASK 文档缺失放行请求落盘小节"
            f"「{_CLEARANCE_REQUEST_HEADING}」（L2 应写入 2.x 节、L1 应写入 1.5 后固定小节同名）。"
            "请按 planner.md 第 8 节将放行请求五要素原文落盘 TASK 文档，不依赖 ask 弹窗；"
            "代理不得代填放行记录。"
        )
    missing = [name for name, pattern in _CLEARANCE_REQUEST_KEYWORDS.items()
               if not re.search(pattern, record)]
    if missing:
        return False, (
            "🛑 任务已进入 dev 及之后阶段，但放行请求落盘小节"
            f"「{_CLEARANCE_REQUEST_HEADING}」缺少五要素关键词：{('、'.join(missing))}。"
            "请补齐（目标概览/可写清单/自决清单/风险概览/盲审结论）后重新落盘。"
        )
    return True, (
        f"放行请求落盘校验通过（{risk_level} 任务，{current_stage} 阶段，"
        f"「{_CLEARANCE_REQUEST_HEADING}」小节五要素齐全）"
    )


def check_unit_tests(tests_dir=None, timeout=600):
    """16. 单元测试执行: 以子进程真实执行 linter 同级 tests 目录的单测套件

    [TD-3 修复] --all 此前仅做静态扫描不执行测试，测试断言失配可在门禁
    绿灯下长期潜伏主干（HEAD 提交 4fac1b7 的 4 处断言失配实锤）。本检查器
    让 --all 升级为「静态扫描 + 真实执行」双保险：
    - 目录缺失或无 test_*.py → 跳过提示（bootstrap 项目可能不含测试，不强制）；
    - 存在测试 → 以 sys.executable -m unittest discover 子进程执行；
    - 测试失败或执行超时 → 按阻断处理（--all 退出码 2）。

    tests_dir / timeout 均可注入：单测在临时目录上验证三态行为，
    避免用例内递归触发本套件所在的 --all 全量路径。
    """
    # 以 linter 脚本自身位置定位测试目录：Skill 内置布局（core/scripts/tests）
    # 与 bootstrap 后布局（项目 scripts/tests）均适用
    tests_path = Path(tests_dir) if tests_dir is not None else Path(__file__).parent / "tests"

    # 跳过语义：目录缺失或无测试文件属合法布局（如 bootstrap 项目），非阻断
    if not tests_path.is_dir():
        return True, f"💡 提示：测试目录不存在，跳过单测执行: {tests_path}"
    if not list(tests_path.glob("test_*.py")):
        return True, f"💡 提示：测试目录无 test_*.py 用例，跳过单测执行: {tests_path}"

    # 用当前解释器真实执行测试套件；强制子进程 UTF-8 输出，避免结果解码乱码
    cmd = [sys.executable, "-m", "unittest", "discover",
           "-s", str(tests_path), "-p", "test_*.py"]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"单元测试执行超时（>{timeout} 秒），按失败处理。"
            f"可单独运行 `{' '.join(cmd)}` 定位慢用例。"
        )

    if result.returncode != 0:
        # unittest 结果写入 stderr，截取尾部核心失败信息便于定位
        detail_lines = (result.stderr or "").strip().splitlines()
        detail = "\n".join(detail_lines[-12:]) if detail_lines else "(无输出)"
        return False, f"单元测试存在失败（退出码 {result.returncode}）：\n{detail}"

    # 从 stderr 提取 "Ran N tests in Xs" 摘要行
    ran_line = ""
    for line in (result.stderr or "").splitlines():
        if line.strip().startswith("Ran "):
            ran_line = line.strip()
    return True, f"单元测试执行通过（{ran_line}）" if ran_line else "单元测试执行通过"


# ==============================================================================
# 活跃任务定位辅助
# ==============================================================================

def resolve_workflow_path(sage_root, local_relative, core_relative=None):
    """优先使用项目本地文件；缺失时回退到 skill 默认发行版。"""
    local_path = sage_root / local_relative
    if local_path.exists():
        return local_path
    skill_path = sage_root / "skills" / "sage-workflow" / "core" / (core_relative or local_relative)
    if skill_path.exists():
        return skill_path
    return local_path

def find_active_task(sage_root):
    """在项目中寻找当前活跃任务文档，返回 Path 或 None"""
    # 活跃任务只允许放在 docs/project/；完成后归档到 docs/project/tasks/T-XXX.md
    active_tasks = list((sage_root / "docs" / "project").glob("ACTIVE_TASK_T-*.md"))
    return active_tasks[0] if active_tasks else None


def write_run_log(sage_root, mode, collector, hook_mode=None):
    """将本次门禁运行结果以单行 JSON 追加到 .sage/linter-runs.jsonl

    用于统计各检查器（规则 ID）的实际拦截频率。best-effort 写入：
    任何失败静默忽略，绝不影响门禁退出码与判定结果。
    hook_mode 缺省取模块常量 _IS_HOOK；hook 高频调用下仅记录存在 fail/warn 的运行。
    单测可通过 hook_mode 参数注入验证降频分支，不依赖 import 期环境变量。
    """
    if hook_mode is None:
        hook_mode = _IS_HOOK
    try:
        fails = [r.rule_id for r in collector.results if r.status == "fail" and r.rule_id]
        warns = [r.rule_id for r in collector.results if r.status == "warn" and r.rule_id]
        if hook_mode and not fails and not warns:
            return
        log_dir = Path(sage_root) / ".sage"
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode": mode,
            "exit_code": collector.exit_code(),
            "fail": fails,
            "warn": warns,
        }
        with open(log_dir / "linter-runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


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
    parser.add_argument("--no-log", action="store_true",
                        help="禁用运行日志写入（默认记录到 .sage/linter-runs.jsonl 统计拦截频率）")

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
    template_file = resolve_workflow_path(sage_root, Path("templates") / "TASK-TEMPLATE.md")
    docs_dir = sage_root / "docs"
    templates_dir = resolve_workflow_path(sage_root, Path("templates"))
    changelog_file = sage_root / "CHANGELOG.md"
    decision_log_file = sage_root / "docs" / "project" / "DECISION_LOG.md"

    # 创建结果收集器
    collector = ResultCollector(fmt=args.format)

    # 运行模式标识（写入运行日志，区分全量/任务级/单项检查）
    if args.check_branch:
        run_mode = "branch"
    elif args.check_scope:
        run_mode = "scope"
    elif args.check_commit_msg:
        run_mode = "commit-msg"
    elif args.check_freshness:
        run_mode = "freshness"
    elif args.check_links:
        run_mode = "links"
    elif args.check_task:
        run_mode = "task"
    else:
        run_mode = "all"

    # ======================================================================
    # 单项快速检查模式（供 hooks / cron 高频调用）
    # ======================================================================
    if is_single_check:
        if args.check_branch:
            task_file = find_active_task(sage_root)
            ok, msg = check_git_branch_isolation(sage_root, args.allow_protected_branch, task_file=task_file)
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
            collector.add("17. 提交信息中文校验", ok, msg)

        if args.check_freshness:
            ok, msg = check_document_freshness(docs_dir, args.stale_days)
            collector.add("6. 文档新鲜度扫描", ok, msg)

        if args.check_links:
            ok, msg = check_cross_links(sage_root)
            collector.add("11. 交叉引用校验", ok, msg)

        collector.flush()
        if not args.no_log:
            write_run_log(sage_root, run_mode, collector)
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
            (lambda: check_plan_clearance(task_file), "18. 计划放行校验"),
            (lambda: check_clearance_request_record(task_file), "19. 放行请求落盘校验"),
        ]

        for func, name in checkers:
            ok, msg = func()
            collector.add(name, ok, msg)

        if args.format == "text":
            collector.flush()
            print()

    # ======================================================================
    # 场景 B: 一键全量校验 (一键运行全部 19 个检查器)
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
        ok, msg = check_git_branch_isolation(sage_root, args.allow_protected_branch, task_file=task_file)
        collector.add("[4/17] 分支隔离校验", ok, msg)

        # 2. 模板守护校验
        if args.allow_template_changes:
            ok, msg = True, "模板变更已由 --allow-template-changes 显式允许"
        else:
            ok, msg = check_templates_pristine(templates_dir, sage_root)
        collector.add("[7/17] 模板完整校验", ok, msg)

        # 3. 只增不改日志校验
        ok, msg = check_append_only(decision_log_file, sage_root)
        collector.add("[9/17] 日志增改限制", ok, msg)

        # 4. CHANGELOG 联动更新校验（T-021：透传活跃任务文档启用阶段感知——
        #    init/plan-review/dev/code-review 未到期跳过，close 维持强制；无活跃任务时
        #    task_file=None 退化为既有强制行为）
        ok, msg = check_changelog_update(changelog_file, sage_root, task_file=task_file)
        collector.add("[8/17] 日志更新联动", ok, msg)

        # 5. T2 规范体积校验
        ok, msg = check_t2_document_lines(docs_dir)
        collector.add("[5/17] 规范文档体积", ok, msg)

        # 6. 本地交叉引用验证 — 扫描整个项目根目录
        ok, msg = check_cross_links(sage_root)
        collector.add("[11/17] 交叉引用校验", ok, msg)

        # 7. 文档新鲜度扫描 (警告级)
        ok, msg = check_document_freshness(docs_dir, args.stale_days)
        collector.add("[6/17] 文档新鲜扫描", ok, msg)

        # [FIX DESIGN-3] 如果已通过 --check-task 单独校验过，不再重复执行任务级校验
        if task_file and not args.check_task:
            if args.format == "text":
                print("\n--- 任务级细节深度扫描 ---")
            task_checkers = [
                (lambda: check_template_copy(task_file, template_file), "[1/17] 模板复制校验", None),
                (lambda: check_task_structure(task_file), "[2/17] 任务大纲校验", None),
                (lambda: check_task_risk_sections(task_file), "[3/17] 风险扩展校验", None),
                (lambda: check_scope_lock(task_file, sage_root), "[10/17] 范围锁定校验", None),
                (lambda: check_evidence_complete(task_file), "[12/17] 证据链校验", None),
                (lambda: check_review_complete(task_file), "[13/17] 盲审结果校验", None),
                (lambda: check_model_metadata(task_file), "[14/17] 模型元数据校验", None),
                (lambda: check_execution_channel_records(task_file), "[15/17] 执行通道记录校验", None),
                # 标签 [17/17] 显式映射 SAGE-18（SAGE-17 为提交信息单项检查器保留段，T-014）；
                # 输出序号 [17/17] 先于 [16/17] 单元测试出现（task_checkers 块在单测之前执行）属注册序错位，CODE_WIKI 有备案
                (lambda: check_plan_clearance(task_file), "[17/17] 计划放行校验", "SAGE-18"),
                # 标签 [19/19] 显式映射 SAGE-19（T-024：放行请求五要素原文必须落盘 TASK 文档，弹窗瞬逝后可追溯）
                (lambda: check_clearance_request_record(task_file), "[19/19] 放行请求落盘校验", "SAGE-19"),
            ]
            for func, name, rule_id in task_checkers:
                ok, msg = func()
                collector.add(name, ok, msg, rule_id=rule_id)

        # 8. 单元测试执行（TD-3：门禁从纯静态扫描升级为真实执行测试套件）
        # 无条件执行（不依赖活跃任务存在）；失败/超时 → 阻断（退出码 2）
        ok, msg = check_unit_tests(timeout=600)
        collector.add("[16/17] 单元测试执行", ok, msg)

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

    if not args.no_log:
        write_run_log(sage_root, run_mode, collector)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
