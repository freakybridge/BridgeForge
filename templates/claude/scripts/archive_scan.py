#!/usr/bin/env python3
"""扫描已完成的 delivery topic 与已解决 Bug，输出人工复核候选。"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DELIVERY_DIR = REPO_ROOT / "doc" / "1_delivery"
BUG_DIR = REPO_ROOT / "doc" / "2_bugs"
ARCHIVE_DIR = REPO_ROOT / "doc" / "4_archive"
DONE = re.compile(r"(?:状态|status)\s*[:：]\s*(?:已完成|已验收|已解决|done|accepted|resolved)", re.I)
STALE_DAYS = 30


def _days_by_path(paths: list[Path]) -> dict[Path, int | None]:
    if not paths:
        return {}
    relative = {
        path.relative_to(REPO_ROOT).as_posix(): path
        for path in paths
    }
    timestamps: dict[Path, int] = {}
    marker = "@@bridgeforge-commit-time:"
    try:
        result = subprocess.run(
            [
                "git", "-c", "core.quotepath=false", "log", "--no-renames",
                f"--format=%x00{marker}%at%x00", "--name-only", "-z", "--",
                *relative,
            ],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {path: None for path in paths}
        commit_time: int | None = None
        for raw_token in result.stdout.split("\0"):
            token = raw_token.strip("\r\n")
            if token.startswith(marker):
                commit_time = int(token.removeprefix(marker))
                continue
            normalized = token.replace("\\", "/")
            path = relative.get(normalized)
            if path is not None and commit_time is not None and path not in timestamps:
                timestamps[path] = commit_time
    except Exception:
        return {path: None for path in paths}
    now = int(time.time())
    return {
        path: (now - timestamps[path]) // 86400 if path in timestamps else None
        for path in paths
    }


def _done(path: Path) -> bool:
    try:
        return bool(DONE.search("\n".join(path.read_text(encoding="utf-8").splitlines()[:30])))
    except Exception:
        return False


def scan() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pending: list[tuple[Path, dict[str, Any]]] = []
    if DELIVERY_DIR.exists():
        for acceptance in DELIVERY_DIR.rglob("acceptance.md"):
            if not _done(acceptance):
                continue
            topic = acceptance.parent
            rel = topic.relative_to(DELIVERY_DIR)
            pending.append((acceptance, {
                "source": str(topic.relative_to(REPO_ROOT)),
                "target": str((ARCHIVE_DIR / "delivery" / rel).relative_to(REPO_ROOT)),
                "kind": "delivery",
                "reasons": ["acceptance.md 标记为已完成 / 已验收"],
            }))
    if BUG_DIR.exists():
        for bug in BUG_DIR.rglob("BUG-*.md"):
            if not _done(bug):
                continue
            pending.append((bug, {
                "source": str(bug.relative_to(REPO_ROOT)),
                "target": str((ARCHIVE_DIR / "bugs" / bug.name).relative_to(REPO_ROOT)),
                "kind": "bug",
                "reasons": ["Bug 记录标记为已解决"],
            }))
    days_by_path = _days_by_path([path for path, _ in pending])
    for path, item in pending:
        days = days_by_path[path]
        reasons = item["reasons"]
        if days is not None and days > STALE_DAYS:
            reasons.append(f"git log 最后修改 {days} 天前")
        item.update({
            "score": 3 + int(days is not None and days > STALE_DAYS),
            "last_modified_days": days,
        })
        candidates.append(item)
    return sorted(candidates, key=lambda item: (-item["score"], item["source"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    candidates = scan()
    if args.count:
        print(len(candidates))
    elif args.json:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
    elif not candidates:
        print("delivery / bugs 无归档候选")
    else:
        print(f"发现 {len(candidates)} 个归档候选：")
        for item in candidates:
            print(f"  {item['kind']}: {item['source']} -> {item['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
