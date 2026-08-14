#!/usr/bin/env python3
"""Atomic, project-local runtime receipts for memory discovery and use."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def append_event(repo_root: Path, event: dict[str, object]) -> None:
    runtime = repo_root / ".runtime"
    if runtime.exists() and (runtime.is_symlink() or not runtime.is_dir()):
        raise RuntimeError(".runtime must be a real directory")
    runtime.mkdir(exist_ok=True)
    target = runtime / "memory_usage.jsonl"
    if target.exists() and target.is_symlink():
        raise RuntimeError("memory usage log must not be a link")
    lock = runtime / ".memory_usage.lock"
    deadline = time.monotonic() + 2.0
    descriptor = -1
    while descriptor < 0:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 30:
                    lock.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("memory usage log is busy")
            time.sleep(0.02)
    try:
        payload = dict(event)
        payload.setdefault("utc", datetime.now(timezone.utc).isoformat())
        with target.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def used_count_since_last_search(
    repo_root: Path,
    *,
    session_id: str = "",
    turn_id: str = "",
) -> int:
    target = repo_root / ".runtime" / "memory_usage.jsonl"
    if not target.is_file() or target.is_symlink():
        return 0
    used: set[str] = set()
    for raw in reversed(target.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if str(event.get("session_id") or "") != session_id or str(event.get("turn_id") or "") != turn_id:
            continue
        if event.get("event") == "search":
            break
        if event.get("event") == "used" and isinstance(event.get("path"), str):
            used.add(event["path"])
    return len(used)
