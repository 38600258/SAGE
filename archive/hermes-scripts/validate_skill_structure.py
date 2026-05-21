#!/usr/bin/env python3
"""验证所有技能包的结构完整性。

扫描 skills/ 目录，检查每个技能包是否符合规范：
1. 必须包含 SKILL.md
2. SKILL.md 必须包含 frontmatter（name, description）
3. name 必须与目录名一致
4. 必须引用关键 kanban 工具

Usage:
    python scripts/validate_skill_structure.py [skills_dir]

退出码:
    0 = 全部通过
    1 = 存在校验失败
"""

import re
import sys
import io
from pathlib import Path

# 修复 Windows GBK 编码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def parse_frontmatter(content: str) -> dict:
    """从 SKILL.md 中解析 YAML frontmatter。"""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    result = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def validate_skill(skill_dir: Path) -> list[str]:
    """验证单个技能包，返回错误列表。"""
    errors = []
    skill_file = skill_dir / "SKILL.md"

    # 检查 1: SKILL.md 必须存在
    if not skill_file.exists():
        errors.append(f"缺少 SKILL.md")
        return errors

    content = skill_file.read_text(encoding="utf-8")

    # 检查 2: frontmatter 必须存在
    fm = parse_frontmatter(content)
    if not fm:
        errors.append("缺少 YAML frontmatter (--- ... ---)")
        return errors

    # 检查 3: name 字段必须存在且与目录名一致
    if "name" not in fm:
        errors.append("frontmatter 缺少 'name' 字段")
    elif fm["name"] != skill_dir.name:
        errors.append(
            f"name '{fm['name']}' 与目录名 '{skill_dir.name}' 不一致"
        )

    # 检查 4: description 字段必须存在
    if "description" not in fm:
        errors.append("frontmatter 缺少 'description' 字段")

    # 检查 5: 必须引用关键 kanban 工具（按角色区分）
    if "gardener" in skill_dir.name:
        # doc-gardener 可能只用 kanban_create
        pass
    elif "orchestrator" in skill_dir.name:
        # orchestrator 用 kanban_create，不用 kanban_show/kanban_complete
        if "kanban_create" not in content:
            errors.append("未引用关键工具: kanban_create")
    else:
        required_tools = ["kanban_show", "kanban_complete"]
        for tool in required_tools:
            if tool not in content:
                errors.append(f"未引用关键工具: {tool}")

    # 检查 6: 文件不能太短（至少 20 行）
    lines = content.splitlines()
    if len(lines) < 20:
        errors.append(f"SKILL.md 仅 {len(lines)} 行，疑似内容不完整（最少 20 行）")

    return errors


def main(skills_dir: str = None) -> bool:
    """扫描并验证所有技能包。"""
    if skills_dir:
        root = Path(skills_dir)
    else:
        # 默认从脚本所在位置推断
        root = Path(__file__).parent.parent / "skills"

    if not root.exists():
        print(f"🛑 技能目录不存在: {root}", file=sys.stderr)
        return False

    skill_dirs = sorted(
        d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    if not skill_dirs:
        print(f"⚠️ 未找到任何技能包目录", file=sys.stderr)
        return False

    all_passed = True
    for skill_dir in skill_dirs:
        errors = validate_skill(skill_dir)
        if errors:
            all_passed = False
            print(f"🛑 {skill_dir.name}:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"✅ {skill_dir.name}")

    if all_passed:
        print(f"\n✅ 全部 {len(skill_dirs)} 个技能包校验通过")
    else:
        print(f"\n🛑 存在校验失败", file=sys.stderr)

    return all_passed


if __name__ == "__main__":
    skills_path = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(0 if main(skills_path) else 1)
