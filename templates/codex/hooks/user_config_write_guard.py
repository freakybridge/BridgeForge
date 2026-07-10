#!/usr/bin/env python3
"""PreToolUse hook: never let the skeleton write user-level Codex model config."""
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


USER_CONFIG = Path.home() / ".codex" / "config.toml"
WRITE_VERBS = (
    "set-content",
    "add-content",
    "out-file",
    "tee-object",
    "tee",
    "new-item",
    "copy-item",
    "move-item",
    "rename-item",
    "remove-item",
    "del",
    "erase",
    "rm",
    "mv",
    "move",
    "cp",
    "copy",
)
ABS_PATH_RE = re.compile(
    r"(?P<q>['\"])(?P<quoted>[A-Za-z]:[\\/][^'\"]+)(?P=q)"
    r"|(?P<bare>[A-Za-z]:[\\/][^\s|;&<>]+)"
)
REDIRECT_RE = re.compile(r"(?:^|[^<>=])>{1,2}\s*(?P<path>['\"]?[A-Za-z]:[\\/][^'\"\s|;&<>]+['\"]?)")
USER_CONFIG_REFERENCE_RE = re.compile(
    r"(?:~|\$HOME|\$\{HOME\}|\$env:(?:USERPROFILE|HOME)|%(?:USERPROFILE|HOME)%)[\\/]\.codex[\\/]config\.toml",
    re.IGNORECASE,
)


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if raw.strip():
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    for name in ("CODEX_TOOL_INPUT", "CLAUDE_TOOL_INPUT"):
        try:
            value = json.loads(os.environ.get(name, ""))
        except Exception:
            continue
        if isinstance(value, dict):
            return {"tool_input": value}
    return {}


def tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("name") or os.environ.get("CODEX_TOOL_NAME", ""))


def tool_input(payload: dict) -> dict:
    value = payload.get("tool_input")
    return value if isinstance(value, dict) else {}


def is_user_config(raw: str) -> bool:
    candidate = raw.strip().strip("\"'")
    if USER_CONFIG_REFERENCE_RE.fullmatch(candidate):
        return True
    try:
        return Path(candidate).resolve(strict=False) == USER_CONFIG.resolve(strict=False)
    except Exception:
        return False


def command_has_write_verb(command: str) -> bool:
    lower = command.lower()
    return any(re.search(rf"(^|[\s|;&]){re.escape(verb)}(\.exe)?\b", lower) for verb in WRITE_VERBS)


def command_targets_user_config(command: str) -> bool:
    if USER_CONFIG_REFERENCE_RE.search(command):
        return True
    paths = [match.group("quoted") or match.group("bare") or "" for match in ABS_PATH_RE.finditer(command)]
    paths.extend(match.group("path").strip("\"'") for match in REDIRECT_RE.finditer(command))
    return any(is_user_config(path) for path in paths)


def block() -> int:
    print("[user-config-write-guard] Blocked write to user-level Codex model configuration.", file=sys.stderr)
    print(f"[user-config-write-guard]   protected path: {USER_CONFIG}", file=sys.stderr)
    print("[user-config-write-guard]   BridgeForge skeletons may read but never write this file.", file=sys.stderr)
    return 2


def main() -> int:
    payload = read_payload()
    name = tool_name(payload)
    data = tool_input(payload)

    if name in {"Write", "Edit", "MultiEdit"}:
        target = str(data.get("file_path") or data.get("path") or "")
        return block() if target and is_user_config(target) else 0

    if name in {"Bash", "PowerShell"}:
        command = str(data.get("command") or "")
        if command_targets_user_config(command) and (command_has_write_verb(command) or ">" in command):
            return block()
    return 0


if __name__ == "__main__":
    sys.exit(main())
