#!/usr/bin/env python3
"""Automatic project-memory candidate routing and honest Read receipts."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from memory_search import search
from memory_usage import append_event, used_count_since_last_search

HOST_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HOST_DIR.parent
MEMORY_DIR = HOST_DIR / "memory"


def _record_event(event: dict[str, object]) -> bool:
    try:
        append_event(REPO_ROOT, event)
        return True
    except (OSError, RuntimeError) as exc:
        print(f"[project-memory] WARNING: usage receipt unavailable: {exc}", file=sys.stderr)
        return False


def _payload() -> dict[str, object]:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _prompt(payload: dict[str, object]) -> str:
    for key in ("prompt", "user_prompt", "message"):
        if isinstance(payload.get(key), str):
            return str(payload[key])
    return ""


def _scope(payload: dict[str, object]) -> dict[str, str]:
    return {
        "session_id": str(payload.get("session_id") or ""),
        "turn_id": str(payload.get("turn_id") or ""),
    }


def _read_like_tool(payload: dict[str, object]) -> bool:
    name = str(payload.get("tool_name") or payload.get("name") or "").lower()
    tokens = [token for token in re.split(r"[^a-z0-9]+", name) if token]
    return any(token == "read" or token.startswith("readfile") for token in tokens)


def _response_failed(response: object) -> bool:
    if not isinstance(response, dict):
        return False
    return bool(
        response.get("isError") is True
        or response.get("is_error") is True
        or response.get("error")
    )


def route(payload: dict[str, object]) -> tuple[list[dict[str, object]], str]:
    prompt = _prompt(payload).strip()
    scope = _scope(payload)
    if not prompt:
        _record_event({"event": "search", "searched": False, "candidates": 0, **scope})
        return [], "Memory: auto searched 0; candidates 0; used 0"
    results = search(MEMORY_DIR, prompt, 5)
    candidates = [asdict(item) for item in results]
    _record_event({"event": "search", "searched": True, "query": prompt, "candidates": candidates, **scope})
    lines = [f"- .codex/memory/{item['path']} — {item['description']} [{item['reason']}]" for item in candidates]
    receipt = f"Memory: auto searched 1; candidates {len(candidates)}; used 0"
    context = receipt
    if lines:
        context += "\nCandidates (read the most relevant 1-2 bodies before relying on them):\n" + "\n".join(lines)
    return candidates, context


def record_read(payload: dict[str, object]) -> bool:
    if not _read_like_tool(payload):
        return False
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return False
    raw_path = str(tool_input.get("path") or tool_input.get("file_path") or "")
    result = payload.get("tool_response", payload.get("tool_result", payload.get("tool_output")))
    if not raw_path or result is None or _response_failed(result):
        return False
    path = Path(raw_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    try:
        relative = path.resolve().relative_to(MEMORY_DIR.resolve()).as_posix()
    except (OSError, ValueError):
        return False
    if relative in {"MEMORY.md", "MEMORY_COLD.md"} or not relative.endswith(".md"):
        return False
    scope = _scope(payload)
    if not _record_event({"event": "used", "path": relative, **scope}):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": f"Memory: body read ({relative}); usage receipt unavailable"}}, ensure_ascii=False))
        return True
    used = used_count_since_last_search(REPO_ROOT, **scope)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": f"Memory: auto searched earlier; used {used} ({relative})"}}, ensure_ascii=False))
    return True


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1 or args[0] not in {"route", "record-read"}:
        print("usage: memory_router.py route|record-read", file=sys.stderr)
        return 2
    payload = _payload()
    if args[0] == "record-read":
        record_read(payload)
        return 0
    _candidates, context = route(payload)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
