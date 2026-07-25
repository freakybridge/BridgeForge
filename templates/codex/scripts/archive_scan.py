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


def _days(path: Path) -> int | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%at", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        return (int(time.time()) - int(result.stdout.strip())) // 86400 if result.stdout.strip() else None
    except Exception:
        return None


def _done(path: Path) -> bool:
    try:
        return bool(DONE.search("\n".join(path.read_text(encoding="utf-8").splitlines()[:30])))
    except Exception:
        return False


def scan() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if DELIVERY_DIR.exists():
        for acceptance in DELIVERY_DIR.rglob("acceptance.md"):
            if not _done(acceptance):
                continue
            topic = acceptance.parent
            rel = topic.relative_to(DELIVERY_DIR)
            days = _days(acceptance)
            reasons = ["acceptance.md 标记为已完成 / 已验收"]
            if days is not None and days > STALE_DAYS:
                reasons.append(f"git log 最后修改 {days} 天前")
            candidates.append({"source": str(topic.relative_to(REPO_ROOT)), "target": str((ARCHIVE_DIR / "delivery" / rel).relative_to(REPO_ROOT)), "kind": "delivery", "score": 3 + int(days is not None and days > STALE_DAYS), "reasons": reasons, "last_modified_days": days})
    if BUG_DIR.exists():
        for bug in BUG_DIR.rglob("BUG-*.md"):
            if not _done(bug):
                continue
            days = _days(bug)
            reasons = ["Bug 记录标记为已解决"]
            if days is not None and days > STALE_DAYS:
                reasons.append(f"git log 最后修改 {days} 天前")
            candidates.append({"source": str(bug.relative_to(REPO_ROOT)), "target": str((ARCHIVE_DIR / "bugs" / bug.name).relative_to(REPO_ROOT)), "kind": "bug", "score": 3 + int(days is not None and days > STALE_DAYS), "reasons": reasons, "last_modified_days": days})
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
