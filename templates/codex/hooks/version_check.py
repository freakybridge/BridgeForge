#!/usr/bin/env python3
"""Compatibility shim for the retired downstream version gate.

Business versions and BridgeForge skeleton versions are independent. New
templates do not register this hook; keeping it as a no-op prevents old
downstream settings from blocking commits during incremental upgrades.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

VERSION_FILE = "VERSION"


def get_command() -> str:
    """取本次 Bash 命令文本。优先 stdin JSON；环境变量只作兼容兜底。"""
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if raw and raw.strip():
        try:
            d = json.loads(raw)
            ti = d.get("tool_input", {}) or {}
            if ti.get("command"):
                return ti["command"]
        except Exception:
            pass
    env_raw = os.environ.get("CODEX_TOOL_INPUT") or os.environ.get("CLAUDE_TOOL_INPUT", "")
    if env_raw:
        try:
            return (json.loads(env_raw) or {}).get("command", "") or ""
        except Exception:
            pass
    return ""


def is_git_commit(cmd: str) -> bool:
    # 匹配 `git commit`，容忍前置 `git -C <path>` / 全局 flag
    return bool(re.search(r"\bgit\b(?:\s+-C\s+\S+|\s+--?[\w-]+)*\s+commit\b", cmd))


def main() -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
