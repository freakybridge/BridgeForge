#!/usr/bin/env python3
"""PreToolUse hook: warn before creating duplicate memory shards.

When a new `.claude/memory/*.md` file is created with the Write tool, compare
its filename topic tokens with existing memory filenames. If several existing
files look like the same topic, print a soft warning recommending appending to
an existing memory file first.

This hook is intentionally non-blocking. It exits 0 and leaves the final choice
to the agent/user.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

PREFIXES = ("feedback", "project", "reference", "user", "memory")
STOPWORDS = {
    "must", "no", "not", "the", "for", "to", "of", "and", "vs", "is", "be",
    "on", "in", "by", "an", "with", "use", "used", "after", "before", "first",
    "only", "all", "via", "fix", "bug", "needs", "need", "from", "when", "if",
}


def topic_tokens(slug: str) -> set[str]:
    parts = slug.split("_")
    if parts and parts[0] in PREFIXES:
        parts = parts[1:]
    return {part for part in parts if part and part not in STOPWORDS}


def read_payload() -> tuple[str, dict]:
    data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}

    tool_name = data.get("tool_name") or os.environ.get("CLAUDE_TOOL_NAME", "")
    tool_input = data.get("tool_input")
    if not tool_input:
        try:
            tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}")) or {}
        except Exception:
            tool_input = {}
    return tool_name, tool_input if isinstance(tool_input, dict) else {}


def main() -> int:
    tool_name, tool_input = read_payload()
    if tool_name != "Write":
        return 0

    file_path = tool_input.get("file_path", "")
    normalized = file_path.replace("\\", "/").lower()
    if not normalized.endswith(".md"):
        return 0
    is_memory_path = (
        "/.claude/memory/" in normalized
        or normalized.startswith(".claude/memory/")
        or ("/.claude/projects/" in normalized and "/memory/" in normalized)
    )
    if not is_memory_path:
        return 0

    name = Path(file_path).name
    if name == "MEMORY.md":
        return 0
    if Path(file_path).exists():
        return 0

    new_tokens = topic_tokens(name[:-3])
    if len(new_tokens) < 2:
        return 0

    memory_dir = Path(__file__).resolve().parent.parent / "memory"
    if not memory_dir.is_dir():
        return 0

    hits: list[str] = []
    for path in memory_dir.glob("*.md"):
        if path.name in ("MEMORY.md", "MEMORY_COLD.md", name):
            continue
        if len(new_tokens & topic_tokens(path.name[:-3])) >= 2:
            hits.append(path.name)

    if len(hits) < 2:
        return 0

    listed = ", ".join(sorted(hits)[:6])
    suffix = f" ({len(hits)} total, first 6 listed)" if len(hits) > 6 else ""
    print(
        f"[memory-dup-check] Creating `{name}`; found {len(hits)} existing memory "
        f"files with similar topic tokens{suffix}: {listed}. "
        "Prefer appending to an existing memory file when this is the same fact; "
        "continue only if it is genuinely separate."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
