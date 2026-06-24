#!/usr/bin/env python3
"""Hook C: 校验 CLAUDE.md §2 规则索引 ↔ `.claude/rules/*.md` 一致性。

触发：PostToolUse(Edit|Write) 且 file_path 命中 `.claude/rules/` 或 `CLAUDE.md`。
非阻塞：索引死链接 / 未索引的 rule 打印到 stderr。
"""
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def main() -> int:
    raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    f = d.get("file_path", "").replace("\\", "/")
    if not (".claude/rules" in f or f.endswith("CLAUDE.md")):
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent
    claude_md = repo_root / "CLAUDE.md"
    rules_dir = repo_root / ".claude" / "rules"
    if not (claude_md.exists() and rules_dir.exists()):
        return 0

    text = claude_md.read_text(encoding="utf-8")
    # 捕获 `rules/xxx.md` 形式的路径引用
    listed = set(re.findall(r"rules/([a-z_]+\.md)", text))
    actual = {p.name for p in rules_dir.glob("*.md")}

    missing = sorted(listed - actual)  # CLAUDE.md 列了但文件不存在
    unlisted = sorted(actual - listed)  # 文件存在但 CLAUDE.md 没列

    issues: list[str] = []
    if missing:
        issues.append(f"CLAUDE.md 死链接（{len(missing)}）: {', '.join(missing)}")
    if unlisted:
        issues.append(f"rule 文件未加索引（{len(unlisted)}）: {', '.join(unlisted)}")

    if issues:
        print("[rule_index_check 发现问题]", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
