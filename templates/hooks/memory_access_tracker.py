#!/usr/bin/env python3
"""
PostToolUse hook — memory 访问追踪器。

检测 Claude 读取 .claude/memory/*.md 时，把今天的日期写入
_stats.json 对应文件的 session_dates（唯一日期列表，同日去重）。

触发：PostToolUse / Read
设计：见 .claude/skills/setup_agent/docs/memory-scoring-design.md
"""
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def main() -> None:
    try:
        raw = sys.stdin.read()
    except Exception:
        sys.exit(0)

    # 快速预过滤：避免对非 memory 读取做 JSON 解析
    if ".claude/memory/" not in raw:
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except Exception:
        sys.exit(0)

    if hook_input.get("tool_name") != "Read":
        sys.exit(0)

    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    # 定位 memory 目录（从 hook 文件所在路径推导项目根）
    hook_dir = Path(__file__).resolve().parent          # .claude/hooks/
    claude_dir = hook_dir.parent                         # .claude/
    memory_dir = claude_dir / "memory"
    stats_file = memory_dir / "_stats.json"

    # 检查是否是 memory 文件
    try:
        read_path = Path(file_path).resolve()
        mem_resolved = memory_dir.resolve()
        if not str(read_path).startswith(str(mem_resolved)):
            sys.exit(0)
        if read_path.suffix != ".md":
            sys.exit(0)
        # 跳过索引文件和内部文件
        if read_path.name in ("MEMORY.md", "MEMORY_COLD.md") or read_path.name.startswith("_"):
            sys.exit(0)
    except Exception:
        sys.exit(0)

    filename = read_path.name
    today = date.today().isoformat()

    # 加载 stats
    stats: dict = {}
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text(encoding="utf-8"))
        except Exception:
            stats = {}

    files = stats.setdefault("files", {})
    entry = files.setdefault(filename, {"session_dates": [], "created_at": today})
    session_dates: list = entry.setdefault("session_dates", [])

    # 同日去重 — 一天内无论读多少次只算一个 session
    if today not in session_dates:
        session_dates.append(today)
        entry["session_dates"] = session_dates[-30:]   # 只保留最近 30 个日期

        stats_file.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
