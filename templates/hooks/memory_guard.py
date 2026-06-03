#!/usr/bin/env python3
"""PreToolUse hook: 硬阻断 MEMORY.md 写入，防止超过行数上限。

规则：
  Write 工具  → 检查新 content 的行数，超限则阻断
  Edit 工具   → 检查写入后预计行数（当前 + 增量 > 0 时阻断）

MEMORY.md 由 memory_rebuild_index.py 自动管理，Claude 不应直接大量写入。
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, Exception):
    pass

HARD_LIMIT = 185


def main() -> int:
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
    raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    f = d.get("file_path", "").replace("\\", "/")
    if "MEMORY.md" not in f:
        return 0

    if tool_name == "Write":
        content = d.get("content", "")
        new_lines = len(content.splitlines())
        if new_lines > HARD_LIMIT:
            print(
                f"⛔ [memory_guard] 阻断写入：新内容 {new_lines} 行，超过上限 {HARD_LIMIT} 行。\n"
                f"   MEMORY.md 由 Stop hook 自动重建，请勿手动大量写入。",
                file=sys.stderr,
            )
            sys.exit(2)

    elif tool_name in ("Edit", "MultiEdit"):
        memory_md = Path(f)
        if not memory_md.exists():
            return 0
        current_text = memory_md.read_text(encoding="utf-8")
        current_lines = len(current_text.splitlines())

        if tool_name == "Edit":
            edits = [{"old_string": d.get("old_string", ""), "new_string": d.get("new_string", "")}]
        else:
            edits = d.get("edits", [])

        delta = sum(
            len(e.get("new_string", "").splitlines()) - len(e.get("old_string", "").splitlines())
            for e in edits
        )

        if delta > 0:
            predicted = current_lines + delta
            if predicted > HARD_LIMIT:
                print(
                    f"⛔ [memory_guard] 阻断写入：当前 {current_lines} 行 + 新增 {delta} 行 = {predicted} 行，"
                    f"超过上限 {HARD_LIMIT} 行。\n"
                    f"   MEMORY.md 由 Stop hook 自动重建，请勿手动大量写入。",
                    file=sys.stderr,
                )
                sys.exit(2)

    return 0


if __name__ == "__main__":
    sys.exit(main())