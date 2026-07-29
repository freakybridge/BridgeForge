#!/usr/bin/env python3
"""Hook: git commit 前强制版本号 bump 检查（PreToolUse / Bash matcher）。

落实 rules/workflow.md §9 红线「每次 commit 前必须提升一次版本号」——从机制上防忘，
不再依赖 agent 自觉（历史上靠软规则反复忘记 bump / 漏打 tag）。

机制：
1. 拦截所有 Bash 调用，只对 `git commit` 命令做检查（其余立即放行，开销 = 一次 python 冷启动）。
2. 检查本次 staged 改动是否包含根目录 `VERSION`：这是 BridgeForge 管理的唯一骨架版本源。
3. 没包含 → exit 2 + stderr 提示 → Codex 阻断该 commit，把 stderr 反馈给 Codex，
   Codex 先 bump 版本号 + 同步 CHANGELOG 再重试 commit。

跳过（任一即放行，避免误伤）：
- 不是 git commit 命令
- commit message 含 [skip-version]（人工豁免：纯 merge / 紧急 hotfix）
- git commit --amend（修补上一条，不强制再 bump）
- 正在 merge（存在 .git/MERGE_HEAD）
- 项目找不到版本号文件（还没建版本号机制，不拦）
- git 不可用 / 异常（宁可放行，不阻断正常工作）

【模板使用提示】
- 本 hook 只对 Python 项目自动注册（依赖 .venv/Scripts/python.exe，见 settings.json）。
- 非 Python 项目跳过本 hook → 退化为只靠 workflow.md §9 软规则。
- 不想要硬拦、只想提醒：把下方 `return 2` 改成 `return 0`（stderr 仍打印，但不阻断）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

VERSION_FILE = "VERSION"


def get_command() -> str:
    """取本次 Bash 命令文本。优先 stdin JSON；环境变量只作兼容兜底。"""
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    if raw and raw.strip():
        try:
            d = json.loads(raw)
            ti = d.get("tool_input", {}) or {}
            if ti.get("command"):
                return ti["command"]
        except Exception:
            pass
    env_raw = os.environ.get("CODEX_TOOL_INPUT") or os.environ.get("CLAUDE_TOOL_INPUT", "")
    if env_raw:
        try:
            return (json.loads(env_raw) or {}).get("command", "") or ""
        except Exception:
            pass
    return ""


def is_git_commit(cmd: str) -> bool:
    # 匹配 `git commit`，容忍前置 `git -C <path>` / 全局 flag
    return bool(re.search(r"\bgit\b(?:\s+-C\s+\S+|\s+--?[\w-]+)*\s+commit\b", cmd))


def main() -> int:
    cmd = get_command()
    if not cmd or not is_git_commit(cmd):
        return 0  # 放行非 commit

    # 人工豁免：[skip-version] 标记 / --amend
    if "[skip-version]" in cmd or re.search(r"\bcommit\b[^\n]*--amend\b", cmd):
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent

    # 正在 merge → 放行
    if (repo_root / ".git" / "MERGE_HEAD").exists():
        return 0

    if not (repo_root / VERSION_FILE).is_file():
        return 0  # 尚未接入 BridgeForge 根 VERSION，不拦

    # 读 staged 文件列表
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except Exception:
        return 0  # git 不可用 → 不拦（避免误伤正常工作）

    staged = {line.strip() for line in out.splitlines() if line.strip()}
    if VERSION_FILE in staged:
        return 0  # 版本号文件已在本次 commit → 放行

    # 拦下
    print(
        f"[version-check] 阻断 commit：本次 staged 改动未包含骨架版本源 `{VERSION_FILE}`。\n"
        f"[version-check] 按 rules/workflow.md §9 红线，每次 commit 前必须提升版本号。\n"
        f"[version-check] 请先编辑 `{VERSION_FILE}` bump 骨架版本 + 同步 CHANGELOG.md，"
        f"再 git add 后重试 commit。\n"
        f"[version-check] 确需跳过（纯 merge / 紧急 hotfix）：commit message 里加 [skip-version]。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
