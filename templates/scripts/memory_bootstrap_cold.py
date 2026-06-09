#!/usr/bin/env python3
"""
一次性冷启动引导：把从未被 recall 过的 memory 沉入 Cold 区。

何时运行（日常不需要）：
  - 首次铺设完一批历史 memory 之后
  - 手动重置过 _stats.json 之后
  想跳过 1-2 周的自愈期、让 MEMORY.md 的 Hot 区立刻收敛成"近期 recall 过的"，运行一次。

原理：
  _stats.json 的 created_at 记的是"追踪系统首次登记该文件的日期"，不是真实创建日。
  铺设/重置后所有 never-recalled 文件 created_at 约等于同一天 → 初始 score 全部 = 1.0，
  与刚被 recall 的文件并列 → Hot 区 top-N 选取靠排序巧合，而非真实热度。
  把 never-recalled 文件的 created_at 拨到数周前 → 它们立即沉入 Cold 区；
  recall 命中某 Cold 文件后会自动升回 Hot。

安全不变量：
  created_at 只在 session_dates 为空时被评分用到（见 memory_rebuild_index.py 的 never-recalled 分支），
  对有 recall 记录的文件是死字段 —— 只动空 session_dates 的文件绝不扰动已成型的 Hot 区。

详见 docs/memory-scoring-design.md「冷启动 / 首次激活」。
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

BACKDATE_DAYS = 60   # 拨到几天前（需大于任何合理的 Hot 衰减窗口）


def main() -> None:
    # 推导项目根：.claude/scripts/ -> .claude/ -> memory/_stats.json
    stats_file = Path(__file__).resolve().parent.parent / "memory" / "_stats.json"
    if not stats_file.exists():
        print(f"_stats.json not found: {stats_file}", file=sys.stderr)
        sys.exit(1)

    stats = json.loads(stats_file.read_text(encoding="utf-8"))
    files = stats.get("files", {})
    old = (date.today() - timedelta(days=BACKDATE_DAYS)).isoformat()

    moved, kept = 0, 0
    for fstats in files.values():
        if not fstats.get("session_dates"):   # 空 = 从没 recall 过
            fstats["created_at"] = old
            moved += 1
        else:
            kept += 1

    stats_file.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[memory-bootstrap] backdated(->cold): {moved} | kept(warm): {kept}")
    print("下次 Stop 重建后 Hot 区将只保留近期 recall 过的 memory；冷区用 /find-memory 搜索。")


if __name__ == "__main__":
    main()