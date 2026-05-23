#!/usr/bin/env python3
"""Hook B: 校验 MEMORY.md 行数（≤200 硬线）+ 孤儿/死链接检测。

触发：PostToolUse(Edit|Write) 且 file_path 含 `.claude/memory`。
非阻塞：问题打印到 stderr，Claude 下一轮会看到并自主修复。
"""
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, Exception):
    pass

MEMORY_MAX_LINES = 200


def main() -> int:
    raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    f = d.get("file_path", "").replace("\\", "/")
    if ".claude/memory" not in f:
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent
    memory_dir = repo_root / ".claude" / "memory"
    memory_md = memory_dir / "MEMORY.md"
    if not memory_md.exists():
        return 0

    text = memory_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    issues: list[str] = []

    if len(lines) > MEMORY_MAX_LINES:
        issues.append(
            f"MEMORY.md 超 {MEMORY_MAX_LINES} 行: 当前 {len(lines)} 行，"
            f"超过会被 Claude 静默截断"
        )

    # 提取 MEMORY.md 中 link 的相对文件名 (仅 *.md)
    linked = set(re.findall(r"\(([a-z0-9_]+\.md)\)", text))
    # 磁盘实际 active 文件（排除 archive/ 子目录）
    actual = {p.name for p in memory_dir.glob("*.md")} - {"MEMORY.md"}

    orphans = sorted(actual - linked)
    broken = sorted(linked - actual)

    if orphans:
        issues.append(f"未索引 orphans（{len(orphans)}）: {', '.join(orphans)}")
    if broken:
        issues.append(f"索引死链接（{len(broken)}）: {', '.join(broken)}")

    if issues:
        print("[memory_lint 发现问题]", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
