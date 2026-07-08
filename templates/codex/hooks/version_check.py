#!/usr/bin/env python3
"""Hook: git commit 前强制版本号 bump 检查（PreToolUse / Bash matcher）。

落实 rules/workflow.md §9 红线「每次 commit 前必须提升一次版本号」——从机制上防忘，
不再依赖 agent 自觉（历史上靠软规则反复忘记 bump / 漏打 tag）。

机制：
1. 拦截所有 Bash 调用，只对 `git commit` 命令做检查（其余立即放行，开销 = 一次 python 冷启动）。
2. 检查本次 staged 改动是否包含版本号「单一事实源」文件
   （package.json / Cargo.toml / pyproject.toml / VERSION 之一，与 SKILL.md SoT 检测一致）。
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

# 版本号单一事实源候选，按优先级（与 SKILL.md Step 3 "版本号 SoT 条件复制" 一致）
VERSION_FILES = ["package.json", "Cargo.toml", "pyproject.toml", "VERSION"]


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


def declares_version(repo_root: Path, fname: str) -> bool:
    """该文件是否真的声明了版本号（避免把无 version 字段的 pyproject.toml 误判为 SoT）。"""
    p = repo_root / fname
    if not p.exists():
        return False
    if fname == "VERSION":
        return True
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if fname == "package.json":
        return '"version"' in txt
    # Cargo.toml / pyproject.toml
    return bool(re.search(r"(?m)^\s*version\s*=", txt))


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

    # 找本项目的版本号 SoT 文件
    version_file = next(
        (f for f in VERSION_FILES if declares_version(repo_root, f)), None
    )
    if version_file is None:
        return 0  # 没建版本号机制，不拦

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
    if version_file in staged:
        return 0  # 版本号文件已在本次 commit → 放行

    # 拦下
    print(
        f"[version-check] 阻断 commit：本次 staged 改动未包含版本号文件 `{version_file}`。\n"
        f"[version-check] 按 rules/workflow.md §9 红线，每次 commit 前必须提升版本号。\n"
        f"[version-check] 请先编辑 `{version_file}` bump 版本号 + 同步 CHANGELOG.md，"
        f"再 git add 后重试 commit。\n"
        f"[version-check] 确需跳过（纯 merge / 紧急 hotfix）：commit message 里加 [skip-version]。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
