#!/usr/bin/env python3
"""PreToolUse hook: block unsafe bulk `git add` commands.

Intercepts `git add -A`, `git add --all`, and `git add .` before execution.
The hook runs `git status --porcelain` and blocks only when the bulk add would
stage clearly unsafe files:

- credential-like files such as `.env`, private keys, npm/pypi credential files
- `.runtime/` transient runtime artifacts

Template/example suffixes such as `.example`, `.sample`, `.template`, and `.dist`
are allowed. The hook is intentionally narrow: it does not block large binaries
or normal project files, and it silently no-ops for non-bulk adds or when Git is
unavailable.
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
    ".env", ".env.*", "*.key", "*.pem", "*.pfx", "*.p12",
    "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*",
    ".git-credentials", ".npmrc", ".pypirc",
]
ALLOW_SUFFIXES = (".example", ".sample", ".template", ".dist")


def get_command() -> str:
    """Read the Bash command from stdin JSON first, then CLAUDE_TOOL_INPUT."""
    try:
        raw = sys.stdin.read()
        if raw and raw.strip():
            tool_input = json.loads(raw).get("tool_input") or {}
            if tool_input.get("command"):
                return tool_input["command"]
    except Exception:
        pass
    try:
        return (json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}")) or {}).get("command", "") or ""
    except Exception:
        return ""


def is_bulk_git_add(cmd: str) -> bool:
    if not re.search(r"\bgit\s+(?:-C\s+\S+\s+)?add\b", cmd):
        return False
    if re.search(r"\badd\b[^&|;]*\s(?:-A|--all)\b", cmd):
        return True
    # `git add .`, but not precise paths like `git add ./src/file.py`.
    return bool(re.search(r"\badd\b[^&|;]*\s\.(?:\s|$|&|\||;)", cmd))


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

    repo_root = Path(__file__).resolve().parent.parent.parent
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
