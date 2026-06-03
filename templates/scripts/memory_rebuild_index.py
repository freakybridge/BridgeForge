#!/usr/bin/env python3
"""
根据 _stats.json 重建 MEMORY.md（热区）和 MEMORY_COLD.md（冷区）。

由 session_snapshot.py Stop hook 末尾调用，每轮对话结束后自动跑。

算法（艾宾浩斯衰减）：
  S     = min(7 + session_count * 10, 90)   # 稳定性，天
  score = exp(-days_since_last / S)          # 保留率 [0, 1]
  热区  = pinned(≤5) + top-40 by score

设计详见 docs/memory-scoring-design.md
"""
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

HOT_N = 40
MAX_PINNED = 5
HEADER_MARKER_START = "<!-- AUTO-HOT-START -->"
HEADER_MARKER_END = "<!-- AUTO-HOT-END -->"


def compute_score(session_dates: list[str], today: date) -> float:
    if not session_dates:
        return 0.0
    session_count = len(session_dates)
    last = date.fromisoformat(max(session_dates))
    days = (today - last).days
    S = min(7 + session_count * 10, 90)
    return math.exp(-days / S)


def get_description(memory_dir: Path, filename: str) -> str:
    f = memory_dir / filename
    if not f.exists():
        return ""
    try:
        m = re.search(r"^description:\s*(.+)", f.read_text(encoding="utf-8", errors="ignore"), re.MULTILINE)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


def main() -> None:
    # 推导项目根：.claude/scripts/ -> .claude/ -> project/
    script_dir = Path(__file__).resolve().parent
    claude_dir = script_dir.parent
    memory_dir = claude_dir / "memory"
    stats_file = memory_dir / "_stats.json"

    if not stats_file.exists():
        sys.exit(0)

    try:
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
    except Exception:
        sys.exit(0)

    files_stats: dict = stats.get("files", {})
    config: dict = stats.get("config", {})
    pinned: list[str] = config.get("pinned", [])[:MAX_PINNED]
    hot_n: int = config.get("hot_n", HOT_N)
    today = date.today()

    # 扫描 memory/ 中所有未追踪的 .md 文件（新写入的）
    skip_names = {"MEMORY.md", "MEMORY_COLD.md"}
    for f in memory_dir.glob("*.md"):
        if f.name.startswith("_") or f.name in skip_names:
            continue
        if f.name not in files_stats:
            files_stats[f.name] = {
                "session_dates": [],
                "created_at": today.isoformat(),
            }

    # 计算得分
    scored: list[tuple[float, str, str]] = []
    for filename, fstats in files_stats.items():
        if not (memory_dir / filename).exists():
            continue
        if filename in pinned:
            continue
        session_dates = fstats.get("session_dates", [])
        if not session_dates:
            # 新文件：按创建日期算，当天创建得 score=1，之后自然衰减
            created_at = fstats.get("created_at", today.isoformat())
            days_old = (today - date.fromisoformat(created_at)).days
            score = math.exp(-days_old / 7)   # 初始 S=7 天
        else:
            score = compute_score(session_dates, today)
        desc = get_description(memory_dir, filename)
        scored.append((score, filename, desc))

    scored.sort(key=lambda x: x[0], reverse=True)
    warm = scored[:hot_n]
    cold = scored[hot_n:]

    today_str = today.isoformat()

    # ── 生成热区内容块 ────────────────────────────────────────
    hot_lines: list[str] = [HEADER_MARKER_START, ""]

    if pinned:
        hot_lines.append("## 📌 Pinned")
        for p in pinned:
            desc = get_description(memory_dir, p)
            suffix = f" — {desc}" if desc else ""
            hot_lines.append(f"- [{p}]({p}){suffix}")
        hot_lines.append("")

    hot_lines.append(f"## 🔥 Hot（Top-{hot_n}，按访问时效自动维护）")
    for _score, filename, desc in warm:
        suffix = f" — {desc}" if desc else ""
        hot_lines.append(f"- [{filename}]({filename}){suffix}")

    if cold:
        hot_lines.append("")
        hot_lines.append(f"## 🔍 Cold（{len(cold)} 条，用 /find-memory 搜索）")
        hot_lines.append("详见 MEMORY_COLD.md")

    hot_lines += ["", HEADER_MARKER_END]

    # ── 写入 MEMORY.md ────────────────────────────────────────
    memory_md = memory_dir / "MEMORY.md"
    if memory_md.exists():
        original = memory_md.read_text(encoding="utf-8")
        if HEADER_MARKER_START in original and HEADER_MARKER_END in original:
            before = original[: original.index(HEADER_MARKER_START)]
            after = original[original.index(HEADER_MARKER_END) + len(HEADER_MARKER_END):]
            new_content = before + "\n".join(hot_lines) + after
        else:
            # 首次运行：在文件末尾追加热区块
            new_content = original.rstrip("\n") + "\n\n" + "\n".join(hot_lines) + "\n"
    else:
        new_content = f"# 开发备忘\n\n<!-- auto-managed | {today_str} -->\n\n" + "\n".join(hot_lines) + "\n"

    memory_md.write_text(new_content, encoding="utf-8")

    # ── 写入 MEMORY_COLD.md ───────────────────────────────────
    cold_md = memory_dir / "MEMORY_COLD.md"
    cold_lines = [
        f"<!-- MEMORY_COLD.md — 冷区索引 | rebuilt {today_str} | 用 /find-memory <关键词> 搜索 -->",
        "",
    ]
    for _score, filename, desc in cold:
        suffix = f" — {desc}" if desc else ""
        cold_lines.append(f"- [{filename}]({filename}){suffix}")
    cold_md.write_text("\n".join(cold_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()