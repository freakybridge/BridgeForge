#!/usr/bin/env python3
"""Emit the rebuilt hot project-memory index as bounded hook context."""
from __future__ import annotations

import json
from pathlib import Path

MAX_CONTEXT = 6000


def build_context(memory_dir: Path, limit: int = MAX_CONTEXT) -> str:
    index = memory_dir / "MEMORY.md"
    if not index.is_file() or index.is_symlink():
        return ""
    text = index.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= limit:
        return text
    suffix = "\n\n[project-memory] truncated; use $find-memory for deep search."
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def main() -> int:
    memory_dir = Path(__file__).resolve().parent.parent / "memory"
    context = build_context(memory_dir)
    if context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "[project-memory index]\n" + context}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
