#!/usr/bin/env python3
"""Hook: 把当前工作状态快照落盘到 `.runtime/session_state/`。

触发方式（通过第 1 个 positional arg 区分事件来源）：
- `post-compact`：PostCompact 后强制存（不节流）
- `stop`：每轮 Stop 触发，**5 分钟节流**（距上次 snapshot <5min 就跳过）→ 类似 Word 自动保存
- `manual`（默认）：手动调用，不节流

落盘内容：时间戳 + 事件 + 分支 + ahead/behind + 版本号 + uncommitted + TODO P0。
**保留最近 20 份**，超出删最旧。

CLI 用法：
  session_snapshot.py manual
  session_snapshot.py post-compact
  session_snapshot.py stop
"""
import argparse
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SESSION_DIR = REPO_ROOT / ".runtime" / "session_state"
THROTTLE_SECONDS = 300  # 5 分钟节流（仅 stop 事件）
MAX_SNAPSHOTS = 20  # 保留最近 20 份


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else f"(err: {r.stderr.strip()[:80]})"
    except Exception as e:
        return f"(exc: {e})"


def _version() -> str:
    """探测项目版本号。按优先级：pyproject.toml / setup.py / package.json / Cargo.toml。"""
    candidates = [
        ("pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
        ("setup.py", r'version\s*=\s*[\'"]([^\'"]+)[\'"]'),
        ("package.json", r'"version"\s*:\s*"([^"]+)"'),
        ("Cargo.toml", r'^version\s*=\s*"([^"]+)"'),
    ]
    for fname, pattern in candidates:
        p = REPO_ROOT / fname
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
            m = re.search(pattern, text, re.MULTILINE)
            if m:
                return m.group(1)
        except Exception:
            continue
    return "?"


def _todo_active() -> str:
    p = REPO_ROOT / "doc" / "0_architecture" / "TODO-INDEX.md"
    if not p.exists():
        return "(TODO-INDEX.md 不存在)"
    try:
        text = p.read_text(encoding="utf-8")
        out = []
        for ln in text.splitlines():
            if ln.startswith("| #") or "| P0 |" in ln:
                out.append(ln.strip())
        return "\n".join(out) if out else "(无 P0 活跃条目)"
    except Exception as e:
        return f"(读取失败: {e})"


def _should_throttle() -> bool:
    """Stop 事件：距上次 snapshot <5min 跳过。"""
    snaps = sorted(SESSION_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not snaps:
        return False
    age = time.time() - snaps[0].stat().st_mtime
    return age < THROTTLE_SECONDS


def _trim_old() -> int:
    """保留最近 MAX_SNAPSHOTS 份，超出的删，返回删除数。"""
    snaps = sorted(SESSION_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(snaps) <= MAX_SNAPSHOTS:
        return 0
    to_delete = snaps[MAX_SNAPSHOTS:]
    for p in to_delete:
        try:
            p.unlink()
        except Exception:
            pass
    return len(to_delete)


def _rebuild_memory_index() -> None:
    """Stop 后重建 MEMORY.md 热区 / MEMORY_COLD.md 冷区。"""
    script = REPO_ROOT / ".claude" / "scripts" / "memory_rebuild_index.py"
    if not script.exists():
        return
    try:
        subprocess.run([sys.executable, str(script)], cwd=str(REPO_ROOT), timeout=30)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", nargs="?", default="manual",
                        choices=["manual", "post-compact", "stop"],
                        help="触发事件来源")
    args = parser.parse_args()

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # 节流（仅 stop 事件）
    if args.event == "stop" and _should_throttle():
        return 0  # silent skip

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = SESSION_DIR / f"{ts}.md"

    # 收集状态
    branch = _run(["git", "branch", "--show-current"])
    ahead_behind = _run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"])
    status = _run(["git", "status", "--short"])
    version = _version()
    todo = _todo_active()

    content = f"""# Session State Snapshot

**Timestamp**: {ts}
**Event**: {args.event}
**Branch**: {branch}
**Ahead/Behind**: {ahead_behind}
**Version**: v{version}

## Uncommitted changes

```
{status or "(clean)"}
```

## TODO-INDEX P0 条目（唤起记忆）

```
{todo}
```

---

由 `{args.event}` hook 自动生成。
下次 session 接续可用 `/resume` 读最新一份。
"""

    out.write_text(content, encoding="utf-8")

    if args.event == "stop":
        _rebuild_memory_index()

    trimmed = _trim_old()
    suffix = f" (trimmed {trimmed} old)" if trimmed else ""

    # stop 事件安静；其他事件打印
    if args.event != "stop":
        rel = out.relative_to(REPO_ROOT)
        print(f"[session snapshot {args.event}] -> {rel}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
