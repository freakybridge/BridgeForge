#!/usr/bin/env python3
"""扫描 doc/2_pending/ 找出可归档的候选文档。

判断逻辑（宽松）：
- +3：含关键词 "已完成" / "已部署" / "已归档" / "DONE" / "SHIPPED"
- +3：首部（前 10 行）有 "> 状态：已完成" / "**状态**：已完成"
- +2：TODO-INDEX.md 未引用该文档
- +1：git log 最后修改 > 30 天
- -2：TODO-INDEX.md 仍被引用（惩罚活跃文档，防误归档）

**阈值 score ≥ 3** → 候选。

用法：
  python archive_scan.py           # 打印人类可读候选列表
  python archive_scan.py --count   # 只打印数量（给 SessionStart hook 用）
  python archive_scan.py --json    # JSON 输出（给 skill 用）
"""
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
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURRENT_DIR = REPO_ROOT / "doc" / "2_pending"
TODO_INDEX = REPO_ROOT / "doc" / "0_architecture" / "TODO-INDEX.md"

KEYWORDS_STRONG = ["已完成", "已部署", "已归档", "DONE", "COMPLETED", "SHIPPED"]
STATUS_MARKERS = [
    r">\s*状态[:：]\s*已完成",
    r"\*\*状态\*\*[:：]\s*已完成",
    r">\s*Status[:：]\s*DONE",
]
STALE_DAYS = 30
CANDIDATE_THRESHOLD = 3


def _keyword_hit(text: str) -> bool:
    return any(k in text for k in KEYWORDS_STRONG)


def _status_marker_hit(text: str) -> bool:
    head = "\n".join(text.splitlines()[:10])
    return any(re.search(p, head) for p in STATUS_MARKERS)


def _todo_ref_count(file_name: str, todo_text: str) -> int:
    """统计 TODO-INDEX 里引用该文件名的次数。"""
    stem = file_name[:-3] if file_name.endswith(".md") else file_name
    count = 0
    for ln in todo_text.splitlines():
        # 只看表格行（以 | 开头）
        if not ln.strip().startswith("|"):
            continue
        if file_name in ln or stem in ln:
            count += 1
    return count


def _git_last_modified_days(file_path: Path) -> int | None:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%at", str(file_path.relative_to(REPO_ROOT))],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        last_ts = int(r.stdout.strip())
        return (int(time.time()) - last_ts) // 86400
    except Exception:
        return None


def scan() -> list[dict[str, Any]]:
    if not CURRENT_DIR.exists() or not TODO_INDEX.exists():
        return []
    todo_text = TODO_INDEX.read_text(encoding="utf-8")

    candidates = []
    for f in sorted(CURRENT_DIR.glob("*.md")):
        if f.name == "TODO-INDEX.md":
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue

        score = 0
        reasons = []

        if _keyword_hit(text):
            score += 3
            reasons.append("含 '已完成'/'已部署' 等强关键词")
        if _status_marker_hit(text):
            score += 3
            reasons.append("首部有状态标记 '> 状态：已完成'")

        ref_count = _todo_ref_count(f.name, todo_text)
        if ref_count == 0:
            score += 2
            reasons.append("TODO-INDEX 未引用")
        else:
            score -= 2
            reasons.append(f"TODO-INDEX 有 {ref_count} 处引用（活跃，扣分）")

        days = _git_last_modified_days(f)
        if days is not None and days > STALE_DAYS:
            score += 1
            reasons.append(f"git log 最后修改 {days} 天前")

        if score >= CANDIDATE_THRESHOLD:
            candidates.append({
                "file": f.name,
                "score": score,
                "reasons": reasons,
                "refs_in_todo": ref_count,
                "last_modified_days": days,
            })

    # 按 score 降序
    candidates.sort(key=lambda c: -c["score"])
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", action="store_true", help="只输出候选数量")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    candidates = scan()

    if args.count:
        print(len(candidates))
        return 0

    if args.json:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
        return 0

    if not candidates:
        print(f"doc/2_pending/ 无归档候选（阈值 score ≥ {CANDIDATE_THRESHOLD}）")
        return 0

    print(f"发现 {len(candidates)} 个归档候选（阈值 score ≥ {CANDIDATE_THRESHOLD}）：\n")
    for c in candidates:
        print(f"  📄 {c['file']}  [score={c['score']}]")
        for r in c['reasons']:
            print(f"      - {r}")
        print()

    print("建议操作（/archive-scan skill 会代跑）：")
    print("  1. 人工 review 每个候选")
    print("  2. 确认后 git mv doc/2_pending/<file> doc/4_archive/")
    print("  3. 更新 doc/README.md 的 current/ 和 archive/ 表格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
