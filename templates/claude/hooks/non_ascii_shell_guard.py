#!/usr/bin/env python3
"""PreToolUse hook: block risky non-ASCII text through shell write paths."""
from __future__ import annotations

import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

PIPE_RE = re.compile(r"(?<!\|)\|(?!\|)")
REDIRECT_RE = re.compile(r"(^|[^<>=])>{1,2}($|[^>])")
HERE_RE = re.compile(r"@['\"]|<<")
COMMAND_SUB_RE = re.compile(r"\$\(")
WRITE_COMMAND_RE = re.compile(
    r"\b(?:Set-Content|Out-File|Add-Content|Tee-Object|tee)\b",
    re.IGNORECASE,
)
DYNAMIC_EXEC_RE = re.compile(
    r"(?:^|[\s|;&])(?:python(?:3)?|py|node|deno|ruby|perl|bash|sh|pwsh|powershell)"
    r"(?:\.exe)?\s+(?:-(?=\s|$|[|;&])|-[ce]\b|-Command\b|-EncodedCommand\b)",
    re.IGNORECASE,
)
WRITE_API_RE = re.compile(
    r"\b(?:fs\.(?:writeFileSync|writeFile|appendFileSync|appendFile)|"
    r"writeFileSync|write_text|open\s*\([^)]*['\"]w|"
    r"open\s*\([^)]*['\"]a)\b",
    re.IGNORECASE,
)


def _payload_command(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict) and tool_input.get("command"):
        return str(tool_input["command"])
    if payload.get("command"):
        return str(payload["command"])
    return ""


def get_command() -> str:
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if raw and raw.strip():
        try:
            command = _payload_command(json.loads(raw))
            if command:
                return command
        except Exception:
            pass

    for name in ("CODEX_TOOL_INPUT", "CLAUDE_TOOL_INPUT"):
        env_raw = os.environ.get(name, "")
        if not env_raw:
            continue
        try:
            command = _payload_command(json.loads(env_raw))
            if command:
                return command
        except Exception:
            pass
    return ""


def has_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def risk_reasons(cmd: str) -> list[str]:
    reasons: list[str] = []
    shell_transit = any(
        pattern.search(cmd) for pattern in (PIPE_RE, REDIRECT_RE, HERE_RE, COMMAND_SUB_RE)
    )
    redirection = bool(REDIRECT_RE.search(cmd))
    write_command = bool(WRITE_COMMAND_RE.search(cmd))
    dynamic_exec = bool(DYNAMIC_EXEC_RE.search(cmd))
    write_api = bool(WRITE_API_RE.search(cmd))

    if redirection:
        reasons.append("shell redirection writes command text to a file")
    if write_command:
        reasons.append("shell file-writing command receives non-ASCII text")
    if shell_transit and dynamic_exec:
        reasons.append("non-ASCII text is routed through shell transit into dynamic execution")
    if dynamic_exec and write_api:
        reasons.append("inline dynamic script can write non-ASCII text")
    if shell_transit and write_api:
        reasons.append("shell transit carries non-ASCII text into a write API")
    return reasons


def main() -> int:
    cmd = get_command()
    if not cmd or not has_non_ascii(cmd):
        return 0

    reasons = risk_reasons(cmd)
    if not reasons:
        return 0

    print(
        "[non-ascii-shell-guard] Blocked risky shell command: non-ASCII text "
        "is crossing a shell write/dynamic-exec boundary.",
        file=sys.stderr,
    )
    for reason in reasons:
        print(f"[non-ascii-shell-guard]   - {reason}", file=sys.stderr)
    print(
        "[non-ascii-shell-guard] Use apply_patch/Edit/Write, copy an existing UTF-8 file, "
        "or keep script source ASCII and read UTF-8 input explicitly.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
