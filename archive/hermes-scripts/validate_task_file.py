#!/usr/bin/env python3
"""验证任务文档是否从模板正确复制，防止 AI 覆盖模板结构。

Usage:
    python scripts/validate_task_file.py <任务文档路径>

退出码:
    0 = 校验通过
    1 = 校验失败（模板可能被覆盖或不完整）
"""

import sys
from pathlib import Path


def validate(filepath: str) -> bool:
    """验证任务文档的结构完整性。"""
    path = Path(filepath)

    if not path.exists():
        print(f"🛑 文件不存在: {filepath}", file=sys.stderr)
        return False

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    errors = []

    # 检查 1：行数（模板应 ≥ 80 行，含所有阶段骨架）
    if len(lines) < 80:
        errors.append(f"文件仅 {len(lines)} 行，模板应 ≥80 行，疑似被覆盖或截断")

    # 检查 2：必须包含阶段标题
    required_sections = [
        ("阶段 1", "初始化"),
        ("阶段 3", "开发"),
        ("阶段 5", "收尾"),
    ]
    for keyword, stage_name in required_sections:
        if keyword not in content:
            errors.append(f"缺少「{keyword}」({stage_name})标题，模板结构不完整")

    # 检查 3：必须包含自检清单
    if "自检清单" not in content:
        errors.append("缺少自检清单节，模板结构不完整")

    if errors:
        print("🛑 模板校验失败：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(
            "\n修复方法：重新执行 cp 复制模板文件，不要用 write_to_file 从零生成。",
            file=sys.stderr,
        )
        return False

    print(f"✅ 模板校验通过（{len(lines)} 行）")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_task_file.py <任务文档路径>", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if validate(sys.argv[1]) else 1)
