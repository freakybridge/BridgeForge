#!/usr/bin/env python3
"""UserPromptSubmit & SessionStart hook: 打印当前项目状态（分支 / uncommitted / ahead-behind / 版本）。

被两个 hook 复用：
- UserPromptSubmit：每次用户提交 prompt 前运行，输出注入到 Codex 上下文（让 Codex 实时
  感知 dirty 状态 / 远端漂移）
- SessionStart：session 开始时运行，让 Codex 一眼看到当前仓库状态 + snapshot 接续提示
  + 归档候选数

用法：`python show_state.py <prefix>`
  prefix = "prompt-state" → UserPromptSubmit 调用（只打基本状态行）
  prefix = "session-start" → SessionStart 调用（额外打 snapshot / archive 提示）
"""
import re
import subprocess
import sys
from pathlib import Path

# Windows 终端默认不是 UTF-8，中文会乱码 → 强制 stdout 用 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _version() -> str:
    """探测项目版本号。按优先级：pyproject.toml / setup.py / package.json / Cargo.toml / VERSION。

    VERSION 是无原生版本源项目的单一事实源（纯文本，整文件内容即版本号，无 key=value
    包裹），故用 None pattern 特判：不走正则，直接取 strip 后的文件内容。
    """
    candidates = [
        ("pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
        ("setup.py", r'version\s*=\s*[\'"]([^\'"]+)[\'"]'),
        ("package.json", r'"version"\s*:\s*"([^"]+)"'),
        ("Cargo.toml", r'^version\s*=\s*"([^"]+)"'),
        ("VERSION", None),
    ]
    for fname, pattern in candidates:
        p = REPO_ROOT / fname
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
            if pattern is None:
                stripped = text.strip()
                if stripped:
                    return stripped
                continue
            m = re.search(pattern, text, re.MULTILINE)
            if m:
                return m.group(1)
        except Exception:
            continue
    return "?"


def _latest_snapshot() -> str:
    """返回最新 snapshot 的提示行；无则返空串。"""
    snap_dir = REPO_ROOT / ".runtime" / "session_state"
    if not snap_dir.exists():
        return ""
    snaps = sorted(snap_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not snaps:
        return ""
    latest = snaps[0]
    return f"[snapshot] 最新存档: {latest.name} — 输入 $resume 可接续上下文"


def _archive_hint() -> str:
    """调 archive_scan.py --count 看是否有归档候选；有则提示。"""
    script = REPO_ROOT / ".codex" / "scripts" / "archive_scan.py"
    if not script.exists():
        return ""
    try:
        r = subprocess.run(
            [sys.executable, str(script), "--count"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if r.returncode != 0:
            return ""
        n = int(r.stdout.strip() or "0")
        if n > 0:
            return f"[archive] doc/2_pending/ 有 {n} 个候选可归档 — 输入 $archive-scan 查看"
    except Exception:
        pass
    return ""


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "state"
    branch = _run(["git", "branch", "--show-current"]) or "?"
    dirty_lines = _run(["git", "status", "--short"]).splitlines()
    dirty = len(dirty_lines)
    ab = _run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"])
    ab = ab.replace("\t", "/") if ab else "no-upstream"
    v = _version()
    print(f"[{prefix}] branch={branch} | dirty={dirty} | ahead/behind={ab} | v{v}")

    # SessionStart 时额外提示：snapshot 接续 + 归档候选
    if prefix == "session-start":
        snap_hint = _latest_snapshot()
        if snap_hint:
            print(snap_hint)
        arch_hint = _archive_hint()
        if arch_hint:
            print(arch_hint)
    return 0


if __name__ == "__main__":
    sys.exit(main())
