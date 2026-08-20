#!/usr/bin/env python3
"""Codex lifecycle hook dispatcher.

Codex may start command hooks from the same event concurrently.  bridgeforge-codex
therefore registers one dispatcher per event and expresses every dependency in
this file instead of relying on JSON array order.
"""
from __future__ import annotations

import json
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

HOST_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HOST_DIR.parent
HOOK_DIR = HOST_DIR / "hooks"
SCRIPT_DIR = HOST_DIR / "scripts"
PATCH_FILE_RE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$")
PATCH_MOVE_RE = re.compile(r"^\*\*\* Move to: (.+)$")
MIN_PYTHON = (3, 11)

RUNTIME_ROUTES = {
    "pre-shell": (
        "hooks/git_add_all_guard.py", "hooks/non_ascii_shell_guard.py",
        "hooks/cross_project_write_guard.py", "hooks/user_config_write_guard.py",
    ),
    "pre-edit": (
        "hooks/cross_project_write_guard.py", "hooks/user_config_write_guard.py",
        "hooks/memory_dup_check.py",
    ),
    "pre-allow": ("hooks/allow_memory_write.py",),
    "post-encoding": ("hooks/encoding_check.py",),
    "post-memory": ("scripts/memory_rebuild_index.py", "hooks/memory_lint.py"),
    "post-edit": (
        "hooks/instruction_source_check.py", "hooks/requirements_check.py",
        "hooks/cargo_default_run_check.py", "hooks/fallback_smell_check.py",
    ),
    "post-shell": ("hooks/test_receipt.py",),
    "post-read": ("scripts/memory_router.py",),
    "user-prompt": (
        "scripts/memory_router.py",
        "hooks/show_state.py", "hooks/clarify_reminder.py", "hooks/focus_reminder.py",
    ),
    "post-compact": ("hooks/session_snapshot.py",),
    "stop": ("hooks/session_snapshot.py",),
    "session-before": (
        "hooks/config_health_check.py",
        "hooks/enforce_no_effortlevel.py", "hooks/githooks_path_check.py",
        "scripts/memory_rebuild_index.py", "scripts/memory_context.py",
    ),
    "session-after": (
        "hooks/show_state.py", "hooks/skill_sync_check.py",
    ),
}

def runtime_route_errors(routes: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    active_routes = routes if routes is not None else RUNTIME_ROUTES
    errors: list[str] = []
    for route, targets in active_routes.items():
        if not route or not targets:
            errors.append(f"runtime route is empty: {route!r}")
            continue
        for target in targets:
            relative = PurePosixPath(target)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or len(relative.parts) != 2
                or relative.parts[0] not in {"hooks", "scripts"}
                or relative.suffix != ".py"
            ):
                errors.append(f"{route} has unsafe runtime target: {target!r}")
                continue
            if not (HOST_DIR / Path(*relative.parts)).is_file():
                errors.append(f"{route} runtime target is missing: {target}")
    return errors


def _python_version_error(version_info: object = sys.version_info) -> str | None:
    major = int(getattr(version_info, "major", version_info[0]))  # type: ignore[index]
    minor = int(getattr(version_info, "minor", version_info[1]))  # type: ignore[index]
    if (major, minor) >= MIN_PYTHON:
        return None
    return (
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; "
        f"running {major}.{minor}"
    )


def _project_runtime_error() -> str | None:
    contract_path = SCRIPT_DIR / "project_runtime.py"
    if not contract_path.is_file():
        return f"project runtime validator is missing: {contract_path}"
    module_name = "_bridgeforge_codex_hook_project_runtime"
    try:
        spec = importlib.util.spec_from_file_location(module_name, contract_path)
        if spec is None or spec.loader is None:
            return f"project runtime validator cannot be loaded: {contract_path}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        module.validate_project_runtime(REPO_ROOT, executable=sys.executable)
        return None
    except Exception as exc:
        return f"project runtime contract rejected: {type(exc).__name__}: {exc}"
    finally:
        sys.modules.pop(module_name, None)


def _read_payload() -> tuple[dict, bytes]:
    raw = sys.stdin.buffer.read()
    if raw.strip():
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value, raw
        except Exception:
            pass
    return {}, b"{}"


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("name") or "")


def _tool_input(payload: dict) -> dict:
    value = payload.get("tool_input")
    return value if isinstance(value, dict) else {}


def _virtual_edit_payloads(payload: dict) -> list[tuple[str, dict, bytes]]:
    """Expand one Codex apply_patch event into per-file edit events."""
    name = _tool_name(payload)
    data = _tool_input(payload)
    command = str(data.get("command") or "")
    files: list[tuple[str, str]] = []
    if command:
        for line in command.splitlines():
            file_match = PATCH_FILE_RE.match(line)
            if file_match:
                files.append((file_match.group(1), file_match.group(2)))
                continue
            move_match = PATCH_MOVE_RE.match(line)
            if move_match:
                files.append(("Move", move_match.group(1)))
    if files:
        result = []
        for operation, file_path in files:
            virtual_name = "Write" if operation in {"Add", "Move"} else "Edit"
            virtual = dict(payload)
            virtual["tool_name"] = virtual_name
            virtual["tool_input"] = {"file_path": file_path.strip()}
            encoded = json.dumps(virtual, ensure_ascii=False).encode("utf-8")
            result.append((virtual_name, virtual, encoded))
        return result
    if name in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        return [(name, payload, json.dumps(payload, ensure_ascii=False).encode("utf-8"))]
    return []


def _run(relative: str, payload: bytes, *args: str) -> subprocess.CompletedProcess[str]:
    path = HOST_DIR / relative
    try:
        return subprocess.run(
            [sys.executable, str(path), *args],
            input=payload.decode("utf-8", "replace"),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(
            [sys.executable, str(path), *args], 1, "", f"{type(exc).__name__}: {exc}\n"
        )


def _new_output() -> dict[str, object]:
    return {"contexts": [], "fields": {}}


def _emit(result: subprocess.CompletedProcess[str], output: dict[str, object]) -> None:
    """Collect child stdout without ever emitting multiple hook responses."""
    raw = result.stdout.strip()
    if raw:
        parsed: object = None
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        specific = parsed.get("hookSpecificOutput") if isinstance(parsed, dict) else None
        if isinstance(specific, dict):
            context = specific.get("additionalContext")
            if isinstance(context, str) and context:
                contexts = output["contexts"]
                assert isinstance(contexts, list)
                contexts.append(context)
            fields = output["fields"]
            assert isinstance(fields, dict)
            for key, value in specific.items():
                if key not in {"hookEventName", "additionalContext"}:
                    fields[key] = value
        else:
            contexts = output["contexts"]
            assert isinstance(contexts, list)
            contexts.append(raw)
    if result.stderr:
        sys.stderr.write(result.stderr)


def _finish(event: str, output: dict[str, object], returncode: int = 0) -> int:
    contexts = output["contexts"]
    fields = output["fields"]
    assert isinstance(contexts, list) and isinstance(fields, dict)
    if contexts or fields:
        specific: dict[str, object] = {"hookEventName": event}
        if contexts:
            specific["additionalContext"] = "\n".join(str(item) for item in contexts)
        specific.update(fields)
        print(json.dumps({"hookSpecificOutput": specific}, ensure_ascii=False))
    return returncode


def _run_chain(event: str, items: list[tuple[str, bytes, tuple[str, ...]]]) -> int:
    output = _new_output()
    for relative, payload, args in items:
        result = _run(relative, payload, *args)
        _emit(result, output)
        if result.returncode:
            return _finish(event, output, result.returncode)
    return _finish(event, output)


def _pre_tool(payload: dict, raw: bytes) -> int:
    name = _tool_name(payload)
    if name in {"Bash", "shell_command"}:
        return _run_chain(
            "PreToolUse",
            [(relative, raw, ()) for relative in RUNTIME_ROUTES["pre-shell"]],
        )

    edits = _virtual_edit_payloads(payload)
    if not edits:
        return 0
    output = _new_output()
    for _virtual_name, _virtual, encoded in edits:
        for relative in RUNTIME_ROUTES["pre-edit"]:
            result = _run(relative, encoded)
            _emit(result, output)
            if result.returncode:
                return _finish("PreToolUse", output, result.returncode)

    # An allow decision is safe only when the tool affects one memory Markdown
    # file.  Mixed patches keep Codex's default approval boundary.
    if len(edits) == 1:
        allow = _run(RUNTIME_ROUTES["pre-allow"][0], edits[0][2])
        _emit(allow, output)
        if allow.returncode:
            return _finish("PreToolUse", output, allow.returncode)
    return _finish("PreToolUse", output)


def _post_edit(payload: dict) -> int:
    edits = _virtual_edit_payloads(payload)
    output = _new_output()
    memory_payload: bytes | None = None
    for _name, virtual, encoded in edits:
        path = str(_tool_input(virtual).get("file_path") or "").replace("\\", "/")
        encoding = _run(RUNTIME_ROUTES["post-encoding"][0], encoded)
        _emit(encoding, output)
        if encoding.returncode:
            print(
                "[hook-dispatch] encoding_check failed; dependent memory checks skipped.",
                file=sys.stderr,
            )
            return _finish("PostToolUse", output, encoding.returncode)
        if ".codex/memory/" in "/" + path.lstrip("/") and memory_payload is None:
            memory_payload = encoded

    if memory_payload is not None:
        rebuild = _run(RUNTIME_ROUTES["post-memory"][0], memory_payload, "--from-hook")
        _emit(rebuild, output)
        if rebuild.returncode:
            print(
                f"[hook-dispatch] memory_rebuild_index failed (exit {rebuild.returncode}); "
                "memory_lint skipped to avoid checking a stale index.",
                file=sys.stderr,
            )
            return _finish("PostToolUse", output, rebuild.returncode)
        lint = _run(RUNTIME_ROUTES["post-memory"][1], memory_payload)
        _emit(lint, output)
        if lint.returncode:
            return _finish("PostToolUse", output, lint.returncode)
    for _name, _virtual, encoded in edits:
        for relative in RUNTIME_ROUTES["post-edit"]:
            extra = ("--post-edit",) if relative == "hooks/instruction_source_check.py" else ()
            result = _run(relative, encoded, *extra)
            _emit(result, output)
            if result.returncode:
                return _finish("PostToolUse", output, result.returncode)
    return _finish("PostToolUse", output)


def _session_start(raw: bytes) -> int:
    output = _new_output()
    first_failure = 0
    rebuild_failed = False
    for relative in RUNTIME_ROUTES["session-before"]:
        if relative == "scripts/memory_context.py" and rebuild_failed:
            print(
                "[hook-dispatch] memory_context skipped because index rebuild failed.",
                file=sys.stderr,
            )
            continue
        result = _run(relative, raw)
        _emit(result, output)
        if result.returncode:
            if relative == "scripts/memory_rebuild_index.py":
                rebuild_failed = True
            if not first_failure:
                first_failure = result.returncode
            print(f"[hook-dispatch] SessionStart step failed: {relative}", file=sys.stderr)
    for relative in RUNTIME_ROUTES["session-after"]:
        args = ("session-start",) if relative == "hooks/show_state.py" else ()
        result = _run(relative, raw, *args)
        _emit(result, output)
        if result.returncode:
            if not first_failure:
                first_failure = result.returncode
            print(f"[hook-dispatch] SessionStart step failed: {relative}", file=sys.stderr)
    return _finish("SessionStart", output, first_failure)


def main(version_info: object = sys.version_info) -> int:
    version_error = _python_version_error(version_info)
    if version_error:
        print(f"[hook-dispatch] BLOCKED: {version_error}", file=sys.stderr)
        return 2
    runtime_error = _project_runtime_error()
    if runtime_error:
        print(f"[hook-dispatch] BLOCKED: {runtime_error}", file=sys.stderr)
        return 2
    if len(sys.argv) != 2:
        print("usage: hook_dispatcher.py EVENT", file=sys.stderr)
        return 2
    route_errors = runtime_route_errors()
    if route_errors:
        for error in route_errors:
            print(f"[hook-dispatch] route audit failed: {error}", file=sys.stderr)
        return 2
    event = sys.argv[1]
    payload, raw = _read_payload()
    if event == "pre-tool":
        return _pre_tool(payload, raw)
    if event == "post-edit":
        return _post_edit(payload)
    route_args = {
        ("post-read", "scripts/memory_router.py"): ("record-read",),
        ("user-prompt", "scripts/memory_router.py"): ("route",),
        ("user-prompt", "hooks/show_state.py"): ("prompt-state",),
        ("post-compact", "hooks/session_snapshot.py"): ("post-compact",),
        ("stop", "hooks/session_snapshot.py"): ("stop",),
    }
    if event == "session-start":
        return _session_start(raw)
    if event not in {"post-shell", "post-read", "user-prompt", "post-compact", "stop"}:
        print(f"unknown hook event route: {event}", file=sys.stderr)
        return 2
    event_names = {
        "post-shell": "PostToolUse",
        "post-read": "PostToolUse",
        "user-prompt": "UserPromptSubmit",
        "post-compact": "PostCompact",
        "stop": "Stop",
    }
    return _run_chain(
        event_names[event],
        [
            (path, raw, route_args.get((event, path), ()))
            for path in RUNTIME_ROUTES[event]
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
