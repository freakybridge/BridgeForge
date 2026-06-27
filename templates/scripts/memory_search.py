#!/usr/bin/env python3
"""
关键词搜索 .claude/memory/*.md 文件。

用法：python .claude/scripts/memory_search.py <关键词>
输出：按匹配频率排名的前10个文件（含 description 和摘录）

由 /find-memory skill 调用，用于召回 MEMORY.md 主索引之外
（已自动滚入冷区 MEMORY_COLD.md）的 memory。纯关键词频率搜索，不依赖热度。
"""
import re
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: memory_search.py <关键词>")
        sys.exit(1)

    query = " ".join(sys.argv[1:]).lower()
    terms = [t for t in query.split() if len(t) > 1]
    if not terms:
        print("请提供搜索关键词")
        sys.exit(0)

    script_dir = Path(__file__).resolve().parent
    claude_dir = script_dir.parent
    memory_dir = claude_dir / "memory"
    skip_names = {"MEMORY.md", "MEMORY_COLD.md"}

    results: list[tuple[int, str, str, list[str]]] = []
    for f in sorted(memory_dir.glob("*.md")):
        if f.name.startswith("_") or f.name in skip_names:
            continue
        try:
            raw = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        text = raw.lower()
        score = sum(text.count(t) for t in terms)
        if score == 0:
            continue

        # 从 frontmatter 提取 description
        m = re.search(r"^description:\s*(.+)", raw, re.MULTILINE)
        desc = m.group(1).strip() if m else ""

        # 提取2个命中摘录
        excerpts: list[str] = []
        for term in terms:
            idx = text.find(term)
            if idx >= 0:
                s = max(0, idx - 30)
                e = min(len(raw), idx + 70)
                excerpt = raw[s:e].replace("\n", " ").strip()
                excerpts.append(f"…{excerpt}…")
            if len(excerpts) >= 2:
                break

        results.append((score, f.name, desc, excerpts))

    results.sort(key=lambda x: x[0], reverse=True)

    if not results:
        print(f"未找到匹配：{query}")
        sys.exit(0)

    print(f"找到 {len(results)} 个匹配，搜索词：{query}\n")
    for score, name, desc, excerpts in results[:10]:
        desc_str = f"\n   {desc}" if desc else ""
        print(f"[{score:3d}] {name}{desc_str}")
        for ex in excerpts:
            print(f"      {ex}")
        print()


if __name__ == "__main__":
    main()
