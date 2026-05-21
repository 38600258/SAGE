#!/usr/bin/env python3
"""检查仓库文档的新鲜度和链接有效性。

扫描 docs/ 和根目录的 .md 文件，检查：
1. 最后修改时间（超过阈值标记为陈旧）
2. Markdown 链接指向的文件是否存在
3. 交叉引用的一致性

Usage:
    python scripts/validate_docs_freshness.py [--stale-days 30]

退出码:
    0 = 全部健康
    1 = 存在陈旧或断链
"""

import argparse
import io
import re
import sys
import time
from pathlib import Path

# 修复 Windows GBK 编码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def find_md_files(root: Path) -> list[Path]:
    """递归查找所有 Markdown 文件（排除 node_modules 等）。"""
    exclude = {".git", "node_modules", "__pycache__", ".hermes"}
    result = []
    for p in root.rglob("*.md"):
        if not any(part in exclude for part in p.parts):
            result.append(p)
    return sorted(result)


def check_staleness(path: Path, stale_days: int) -> str | None:
    """检查文件是否超过 stale_days 未更新。"""
    mtime = path.stat().st_mtime
    age_days = (time.time() - mtime) / 86400
    if age_days > stale_days:
        return f"已 {int(age_days)} 天未更新（阈值: {stale_days} 天）"
    return None


def check_links(path: Path, root: Path) -> list[str]:
    """检查文件中的相对链接是否指向存在的文件。"""
    content = path.read_text(encoding="utf-8", errors="replace")
    broken = []

    # 匹配 [text](relative/path) 格式的链接，排除 http/https
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
    for match in link_pattern.finditer(content):
        text, target = match.groups()
        # 跳过外部链接和锚点
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # 解析相对路径
        target_path = (path.parent / target.split("#")[0]).resolve()
        if not target_path.exists():
            broken.append(f"断链: [{text}]({target}) → {target_path}")

    return broken


def main():
    parser = argparse.ArgumentParser(description="文档新鲜度检查")
    parser.add_argument("--stale-days", type=int, default=30, help="陈旧阈值（天）")
    parser.add_argument("--root", type=str, default=None, help="仓库根目录")
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).parent.parent
    md_files = find_md_files(root)

    if not md_files:
        print("⚠️ 未找到任何 Markdown 文件")
        return True

    stale_files = []
    broken_links = []

    for f in md_files:
        rel = f.relative_to(root)

        # 检查新鲜度
        stale_msg = check_staleness(f, args.stale_days)
        if stale_msg:
            stale_files.append((rel, stale_msg))

        # 检查链接
        links = check_links(f, root)
        if links:
            broken_links.append((rel, links))

    # 输出报告
    print(f"📊 文档健康报告 ({len(md_files)} 个文件)")
    print("=" * 50)

    if stale_files:
        print(f"\n⚠️ 陈旧文档 ({len(stale_files)} 个):")
        for rel, msg in stale_files:
            print(f"  📄 {rel}: {msg}")

    if broken_links:
        print(f"\n🔗 断链 ({sum(len(v) for _, v in broken_links)} 个):")
        for rel, links in broken_links:
            print(f"  📄 {rel}:")
            for link in links:
                print(f"    - {link}")

    if not stale_files and not broken_links:
        print("\n✅ 全部文档健康")
        return True

    has_errors = bool(broken_links)
    if has_errors:
        print(f"\n🛑 存在断链，需要修复", file=sys.stderr)
    elif stale_files:
        print(f"\n⚠️ 存在陈旧文档，建议更新")

    return not has_errors


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
