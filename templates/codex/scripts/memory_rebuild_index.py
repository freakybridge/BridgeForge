#!/usr/bin/env python3
"""
确定性重建 MEMORY.md（主索引）+ MEMORY_COLD.md（冷区索引）。

设计（2026-06-27 改版，见 docs/memory-scoring-design.md）：
  - 纯确定性：索引内容 = f(memory 文件集, created_at, pinned)，**不含当天日期 / 访问热度**。
    → 不碰 memory 时，重建产出逐字不变；git 只比对内容，故工作区永不"自发变脏"。
  - 事件驱动：由 PostToolUse(Write/Edit memory 文件) 触发（--from-hook），不再每轮 Stop 跑。
  - 排序：pinned 置顶 + 其余按 created_at 倒序（新增的在前），并列按文件名升序。
  - 容量滚动：主索引保留 ACTIVE_N 条，超出的自动滚入冷区（MEMORY_COLD.md）。
    → "冷热维护"全自动、不需人工决定；只在真增删 memory 时才变（那本就该提交）。
  - 无日期戳、无艾宾浩斯衰减。

调用方式：
  python memory_rebuild_index.py              # 无条件重建（SessionStart 兜底 / 手动）
  python memory_rebuild_index.py --from-hook  # 读 stdin，仅当写入的是 memory 文件时才重建
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ACTIVE_N = 40
MAX_PINNED = 5
SKIP_NAMES = {"MEMORY.md", "MEMORY_COLD.md"}
DEFAULT_TITLE = "Memory Index"


def is_memory_file(name: str) -> bool:
    return name.endswith(".md") and name not in SKIP_NAMES and not name.startswith("_")


def hook_should_run() -> str:
    """--from-hook 模式：读 stdin 的 PostToolUse 负载，返回被写入的 memory 文件名（触发重建）；
    非 memory 写入返回 ""（falsy）。返回文件名供 D5-M3「memory 当场报」提醒引用。

    非 --from-hook 模式不调用本函数（无条件重建，避免在无 stdin 时阻塞）。
    """
    try:
        raw = sys.stdin.read()
    except Exception:
        return ""
    if not raw.strip() or ".codex/memory/" not in raw.replace("\\", "/"):
        return ""
    try:
        hi = json.loads(raw)
    except Exception:
        return ""
    fp = hi.get("tool_input", {}).get("file_path", "") or ""
    norm = fp.replace("\\", "/")
    if ".codex/memory/" in norm and is_memory_file(Path(fp).name):
        return Path(fp).name
    return ""


def get_description(memory_dir: Path, filename: str) -> str:
    f = memory_dir / filename
    if not f.exists():
        return ""
    try:
        m = re.search(
            r"^description:\s*(.+)",
            f.read_text(encoding="utf-8", errors="ignore"),
            re.MULTILINE,
        )
        return m.group(1).strip().strip('"').strip("'") if m else ""
    except Exception:
        return ""


def main() -> None:
    written = ""
    if "--from-hook" in sys.argv:
        written = hook_should_run()
        if not written:
            sys.exit(0)

    # 推导路径：.codex/scripts/ -> .codex/ -> memory/
    memory_dir = Path(__file__).resolve().parent.parent / "memory"
    stats_file = memory_dir / "_stats.json"
    if not memory_dir.exists():
        sys.exit(0)

    today = date.today().isoformat()

    # 加载 stats（仅 created_at + config，无访问热度）
    stats: dict = {}
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text(encoding="utf-8"))
        except Exception:
            stats = {}
    files_stats: dict = stats.setdefault("files", {})
    config: dict = stats.get("config", {})
    title: str = config.get("title", DEFAULT_TITLE)
    pinned: list = [p for p in config.get("pinned", [])[:MAX_PINNED]]

    # 扫描所有 memory 文件，新文件登记 created_at（一次性，固定不变）
    stats_dirty = False
    present = []
    for f in sorted(memory_dir.glob("*.md")):
        if not is_memory_file(f.name):
            continue
        present.append(f.name)
        if f.name not in files_stats:
            files_stats[f.name] = {"created_at": today}
            stats_dirty = True

    # 清理 stats 里已不存在的文件记录（保持单一事实源）
    for gone in [n for n in files_stats if n not in present]:
        del files_stats[gone]
        stats_dirty = True

    if stats_dirty:
        stats_file.write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # 排序：非 pinned 按 created_at 降序（新增的在前），并列按文件名升序。
    # 利用 Python 稳定排序：先排次级键（文件名升序），再排主键（created_at 降序）。
    non_pinned = [n for n in present if n not in pinned]
    non_pinned.sort()  # 次级：文件名升序
    non_pinned.sort(
        key=lambda n: files_stats.get(n, {}).get("created_at", today), reverse=True
    )  # 主：created_at 降序

    active = non_pinned[:ACTIVE_N]
    cold = non_pinned[ACTIVE_N:]

    pinned_present = [p for p in pinned if p in present]

    # ── 生成 MEMORY.md（整文件，确定性）──────────────────────
    lines = [
        f"# {title}",
        "",
        "<!-- 自动生成索引，勿手改（改动会被下次重建覆盖）。新增 memory：在 .codex/memory/ 下新建 .md 文件，"
        "本索引会自动收录；写法见 ~/.codex/AGENTS.md「auto memory」段。满 40 条自动滚入冷区，用 $find-memory 搜。 -->",
        "",
        f"> Active: {len(pinned_present) + len(active)} | Cold: {len(cold)}",
        "",
    ]

    if pinned_present:
        lines.append("## 📌 Pinned")
        for p in pinned_present:
            d = get_description(memory_dir, p)
            lines.append(f"- [{p[:-3]}]({p}){f' — {d}' if d else ''}")
        lines.append("")

    lines.append(f"## Active（按新增时间，新在前；满 {ACTIVE_N} 自动滚入 Cold）")
    for n in active:
        d = get_description(memory_dir, n)
        lines.append(f"- [{n[:-3]}]({n}){f' — {d}' if d else ''}")

    if cold:
        lines.append("")
        lines.append(f"## 🔍 Cold（{len(cold)} 条，用 $find-memory 搜索）")
        lines.append("详见 MEMORY_COLD.md")

    (memory_dir / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── 生成 MEMORY_COLD.md（无日期戳，确定性）────────────────
    cold_lines = ["<!-- MEMORY_COLD.md — 冷区索引 | 用 $find-memory <关键词> 搜索 -->", ""]
    for n in cold:
        d = get_description(memory_dir, n)
        cold_lines.append(f"- [{n[:-3]}]({n}){f' — {d}' if d else ''}")
    (memory_dir / "MEMORY_COLD.md").write_text("\n".join(cold_lines) + "\n", encoding="utf-8")

    # D5-M3「memory 当场报」：--from-hook 写入 memory 后，当轮可见地报一行提醒。
    # 只挂 PostToolUse --from-hook（写入后触发、LLM 恢复时注回本轮 context）——绝不接
    # allow_memory_write.py（PreToolUse 放行闸，只吐 permissionDecision，回注不进 context）。
    # 纯 ASCII（文件名一并 ASCII 化）防 GBK Windows 上 utf8-garble 糊成 U+FFFD。
    if written:
        safe = written.encode("ascii", "replace").decode("ascii")
        sys.stdout.write(f"[memory-write] wrote {safe}; revert via git\n")


if __name__ == "__main__":
    main()
