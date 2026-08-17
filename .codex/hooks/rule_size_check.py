#!/usr/bin/env python3
"""Compatibility entry for the retired Markdown rule gates.

bridgeforge-codex validates Codex-native instruction sources through
``instruction_source_check.py``.  This filename remains only so older direct
callers fail closed against the current contract during migration.
"""
from __future__ import annotations

import sys

from instruction_source_check import main as instruction_source_main


def main() -> int:
    if not any(
        arg in {"--pre-commit", "--audit-all", "--post-edit"}
        for arg in sys.argv[1:]
    ):
        sys.argv.append("--post-edit")
    return instruction_source_main()


if __name__ == "__main__":
    raise SystemExit(main())
