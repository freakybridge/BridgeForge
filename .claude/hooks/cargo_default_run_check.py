#!/usr/bin/env python3
"""PostToolUse hook: warn when a multi-bin Cargo.toml lacks default-run.

If a Cargo.toml contains two or more `[[bin]]` sections but no `default-run`, a
plain `cargo run` cannot know which binary to launch and fails with "could not
determine which binary to run". This hook prints a non-blocking warning after
Cargo.toml edits so projects can set an explicit default binary when needed.
"""
from __future__ import annotations

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


def get_tool_input() -> dict:
    try:
        raw = sys.stdin.read()
        if raw and raw.strip():
            tool_input = json.loads(raw).get("tool_input")
            if isinstance(tool_input, dict):
                return tool_input
    except Exception:
        pass
    try:
        fallback = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}")) or {}
        return fallback if isinstance(fallback, dict) else {}
    except Exception:
        return {}


def main() -> int:
    raw_path = (get_tool_input().get("file_path") or "").replace("\\", "/")
    if not raw_path.endswith("Cargo.toml"):
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent
    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / raw_path
    if not path.exists():
        return 0

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0

    bin_count = len(re.findall(r"(?m)^\s*\[\[bin\]\]", text))
    if bin_count < 2:
        return 0
    if re.search(r"(?m)^\s*default-run\s*=", text):
        return 0

    rel = path
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        pass
    print(
        f"[cargo-default-run] {rel} contains {bin_count} [[bin]] sections but no default-run.\n"
        "   Plain `cargo run` will fail with: could not determine which binary to run.\n"
        "   Fix: add `default-run = \"<main-bin-name>\"` under [package], or make launch "
        "scripts call `cargo run --bin <name>` explicitly.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
