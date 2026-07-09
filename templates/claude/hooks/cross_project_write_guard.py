#!/usr/bin/env python3
"""PreToolUse hook: block silent writes outside the current project root."""
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

REPO_ROOT = Path(__file__).resolve().parents[2]

DANGEROUS_GIT = {
    "add",
    "commit",
    "restore",
    "reset",
    "push",
    "checkout",
    "merge",
    "cherry-pick",
    "clean",
    "branch",
    "tag",
    "update-ref",
    "stash",
}

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
GIT_C_RE = re.compile(
    r"\bgit\b(?P<opts>(?:\s+(?:-C\s+(?:\"[^\"]+\"|'[^']+'|\S+)|-\w+(?:\s+\S+)?|--[\w-]+(?:=\S+)?))*)"
    r"\s+(?P<sub>[A-Za-z][\w-]*)\b",
    re.IGNORECASE,
)
GIT_C_PATH_RE = re.compile(r"-C\s+(?P<path>\"[^\"]+\"|'[^']+'|\S+)", re.IGNORECASE)


def _payload_from_env() -> dict:
    for name in ("CODEX_TOOL_INPUT", "CLAUDE_TOOL_INPUT"):
        raw = os.environ.get(name, "")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            return {"tool_input": data}
    return {}


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if raw and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return _payload_from_env()


def tool_name(payload: dict) -> str:
    for key in ("tool_name", "name"):
        value = payload.get(key)
        if value:
            return str(value)
    return os.environ.get("CODEX_TOOL_NAME") or os.environ.get("CLAUDE_TOOL_NAME", "")


def tool_input(payload: dict) -> dict:
    data = payload.get("tool_input")
    return data if isinstance(data, dict) else {}


def norm_path(raw: str) -> Path:
    stripped = raw.strip().strip("\"'")
    path = Path(stripped)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve(strict=False)


def is_inside_repo(path: Path) -> bool:
    root = REPO_ROOT.resolve(strict=False)
    left = os.path.normcase(str(path))
    right = os.path.normcase(str(root))
    return left == right or left.startswith(right + os.sep)


def outside(path: str) -> Path | None:
    try:
        resolved = norm_path(path)
    except Exception:
        return None
    return None if is_inside_repo(resolved) else resolved


def file_target(tool_input_data: dict) -> str:
    for key in ("file_path", "path"):
        value = tool_input_data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def find_abs_paths(command: str) -> list[str]:
    paths: list[str] = []
    for match in ABS_PATH_RE.finditer(command):
        raw = match.group("quoted") or match.group("bare") or ""
        if raw and raw not in paths:
            paths.append(raw)
    return paths


def command_has_write_verb(command: str) -> bool:
    lower = command.lower()
    return any(re.search(rf"(^|[\s|;&]){re.escape(verb)}(\.exe)?\b", lower) for verb in WRITE_VERBS)


def redirection_targets(command: str) -> list[str]:
    return [match.group("path").strip("\"'") for match in REDIRECT_RE.finditer(command)]


def dangerous_external_git(command: str) -> tuple[str, Path] | None:
    for match in GIT_C_RE.finditer(command):
        subcommand = match.group("sub").lower()
        if subcommand not in DANGEROUS_GIT:
            continue
        opts = match.group("opts") or ""
        path_match = GIT_C_PATH_RE.search(opts)
        if not path_match:
            continue
        target = outside(path_match.group("path"))
        if target:
            return (f"external git {subcommand}", target)
    return None


def risky_shell_target(command: str) -> tuple[str, Path] | None:
    git_risk = dangerous_external_git(command)
    if git_risk:
        return git_risk

    for raw in redirection_targets(command):
        target = outside(raw)
        if target:
            return ("external shell redirection", target)

    if command_has_write_verb(command):
        for raw in find_abs_paths(command):
            target = outside(raw)
            if target:
                return ("external shell write/delete/move", target)
    return None


def block(reason: str, target: Path) -> int:
    print(
        "[cross-project-write-guard] Blocked cross-project write boundary.",
        file=sys.stderr,
    )
    print(f"[cross-project-write-guard]   current project: {REPO_ROOT}", file=sys.stderr)
    print(f"[cross-project-write-guard]   target path: {target}", file=sys.stderr)
    print(f"[cross-project-write-guard]   operation: {reason}", file=sys.stderr)
    print(
        "[cross-project-write-guard] This conversation belongs to the current project, "
        "but the tool would modify another project/path. Ask the user to confirm the "
        "target project explicitly, then retry with that confirmation in context.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    payload = read_payload()
    name = tool_name(payload)
    data = tool_input(payload)

    if name in {"Write", "Edit", "MultiEdit"}:
        target_raw = file_target(data)
        target = outside(target_raw) if target_raw else None
        if target:
            return block(f"{name} outside project root", target)
        return 0

    if name in {"Bash", "PowerShell"}:
        command = str(data.get("command") or "")
        risk = risky_shell_target(command)
        if risk:
            return block(*risk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
