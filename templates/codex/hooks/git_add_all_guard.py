#!/usr/bin/env python3
"""PreToolUse hook: block unsafe bulk `git add` commands.

This hook intercepts broad staging commands such as `git add -A`, `git add
--all`, and `git add .`. It blocks only when `git status --porcelain` shows
credential-like files or `.runtime/` artifacts that would be easy to stage by
accident. Exact-path `git add <file>` remains allowed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

SENSITIVE_GLOBS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.pfx",
    "*.p12",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    ".git-credentials",
    ".npmrc",
    ".pypirc",
]
ALLOW_SUFFIXES = (".example", ".sample", ".template", ".dist")


def get_command() -> str:
    """Read Bash command from stdin JSON, then Codex env, then legacy env."""
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if raw and raw.strip():
        try:
            payload = json.loads(raw)
            tool_input = payload.get("tool_input") or {}
            if isinstance(tool_input, dict) and tool_input.get("command"):
                return str(tool_input["command"])
        except Exception:
            pass

    env_raw = os.environ.get("CODEX_TOOL_INPUT") or os.environ.get("CLAUDE_TOOL_INPUT", "")
    if env_raw:
        try:
            tool_input = json.loads(env_raw) or {}
            if isinstance(tool_input, dict):
                return str(tool_input.get("command") or "")
        except Exception:
            pass
    return ""


def _git_add_args(cmd: str) -> list[str]:
    matches = re.finditer(
        r"\bgit\b(?:\s+(?:-C\s+\S+|-c\s+\S+|--?[\w-]+(?:=\S+)?))*\s+add\b(?P<args>[^&|;]*)",
        cmd,
    )
    args: list[str] = []
    for match in matches:
        args.extend(part.strip("\"'") for part in re.split(r"\s+", match.group("args").strip()) if part)
    return args


def is_bulk_git_add(cmd: str) -> bool:
    args = _git_add_args(cmd)
    if not args:
        return False
    if any(arg in ("-A", "--all") for arg in args):
        return True
    return any(arg.replace("\\", "/") in (".", "./") for arg in args)


def parse_porcelain_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return path.strip('"')


def flag(path: str) -> str | None:
    norm = path.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    if base.endswith(ALLOW_SUFFIXES):
        return None
    if any(fnmatch(base, pattern) for pattern in SENSITIVE_GLOBS):
        return "credential or sensitive file"
    if "/.runtime/" in ("/" + norm):
        return "runtime artifact (.runtime/)"
    return None


def main() -> int:
    cmd = get_command()
    if not cmd or not is_bulk_git_add(cmd):
        return 0

    repo_root = Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        ).stdout
    except Exception:
        return 0

    flagged: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = parse_porcelain_path(line)
        reason = flag(path)
        if reason:
            flagged.append(f"  - {path}  ({reason})")

    if not flagged:
        return 0

    print(
        "[git-add-guard] Blocked bulk add: the following files look unsafe to stage:\n"
        + "\n".join(flagged)
        + "\n   Use `git add <exact-path>` for reviewed files, or add true generated/secret files "
        "to .gitignore before retrying the bulk add.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
