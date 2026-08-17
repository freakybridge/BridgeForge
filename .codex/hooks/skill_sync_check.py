#!/usr/bin/env python3
"""只读检查当前平台的 bridgeforge-codex 托管 skill 是否与本地账本一致。

本 hook 不访问 GitHub、本地 bridgeforge-codex clone、~/.bridgeforge 或 ~/.agents。
发现托管账本缺失、损坏、skill 缺失或内容漂移时，只提示运行无参
`$bridgeforge-codex`；SessionStart 期间绝不自动修复。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

_SKIP_DIRS = {"__pycache__", ".git"}


def _platform() -> str | None:
    config_name = Path(__file__).resolve().parent.parent.name.casefold()
    if config_name == ".codex":
        return "codex"
    return None


def _normalize_hash(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    if normalized.startswith("sha256:"):
        normalized = normalized[7:]
    if len(normalized) != 64:
        return None
    try:
        int(normalized, 16)
    except ValueError:
        return None
    return normalized


def _tree_hash(root: Path) -> str:
    records: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in _SKIP_DIRS
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            rel = path.relative_to(root).as_posix()
            records.append((rel, hashlib.sha256(path.read_bytes()).hexdigest()))
    payload = "".join(
        f"{rel}\n{file_hash}\n" for rel, file_hash in sorted(records)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _valid_name(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    name = value.strip()
    if name in {".", ".."} or "/" in name or "\\" in name:
        return None
    return name


def _warn(detail: str) -> None:
    print(f"[skill-sync] {detail}。请运行无参 $bridgeforge-codex 重新同步。")


def main() -> None:
    platform = _platform()
    if platform is None:
        return
    platform_root = Path.home() / f".{platform}"
    shelf = platform_root / "skills"
    entry = shelf / "bridgeforge-codex" / "SKILL.md"
    ledger_path = platform_root / "bridgeforge-codex-managed.json"

    if not entry.is_file() and not ledger_path.exists():
        return
    if not ledger_path.is_file():
        _warn("bridgeforge-codex 托管账本缺失")
        return
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        _warn("bridgeforge-codex 托管账本无法读取")
        return
    if not isinstance(ledger, dict):
        _warn("bridgeforge-codex 托管账本格式无效")
        return
    if ledger.get("schema_version") != 1 or ledger.get("platform") != platform:
        _warn("bridgeforge-codex 托管账本版本或平台不匹配")
        return
    records = ledger.get("records")
    if not isinstance(records, dict) or not records:
        _warn("bridgeforge-codex 托管账本没有有效记录")
        return

    stale: list[str] = []
    invalid = False
    for raw_name, record in records.items():
        name = _valid_name(raw_name)
        if name is None or not isinstance(record, dict):
            invalid = True
            continue
        expected = _normalize_hash(record.get("content_hash"))
        skill_root = shelf / name
        if expected is None:
            invalid = True
            continue
        try:
            current = skill_root.is_dir() and _tree_hash(skill_root) == expected
        except OSError:
            current = False
        if not current:
            stale.append(name)
    if invalid:
        _warn("bridgeforge-codex 托管账本包含无效 skill 记录")
    elif stale:
        _warn(f"{len(stale)} 个托管 skill 缺失或内容漂移（{', '.join(stale)}）")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
