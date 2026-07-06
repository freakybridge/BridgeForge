#!/usr/bin/env python3
"""
allow_memory_write.py — PreToolUse hook

目的：放行对 memory 目录的 Write/Edit，免去权限弹窗。

背景：`.claude/` 是 Claude Code 的"受保护目录"，写入时无视 acceptEdits
和 permissions.allow 规则一律强制弹窗（安全设计，防恶意篡改 settings/hooks）。
memory 在 `.claude/memory/` 下被连带保护，导致每次保存记忆都弹窗。

本 hook 在权限弹窗之前介入，识别"写 memory 目录的 .md 文件"并直接 allow，
其它 `.claude/` 文件（settings/hooks 本体）不放行，安全边界不破。

匹配三种路径形态（兼容 junction + 可移植）：
- 项目真身    : <proj>/.claude/memory/xxx.md
- 系统 junction: ~/.claude/projects/<hash>/memory/xxx.md
- 相对路径    : .claude/memory/xxx.md

输出 stdout JSON: permissionDecision=allow 绕过弹窗。
只放行 .md 文件，其它扩展名不放行（防误放）。
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def is_memory_md(file_path: str) -> bool:
    if not file_path:
        return False
    norm = file_path.replace("\\", "/").lower()
    if not norm.endswith(".md"):
        return False
    # 形态 1/3：项目真身 + 相对路径
    if "/.claude/memory/" in norm or norm.startswith(".claude/memory/"):
        return True
    # 形态 2：系统 junction（~/.claude/projects/<hash>/memory/）
    if "/.claude/projects/" in norm and "/memory/" in norm:
        return True
    return False


def main():
    # 输入双兜底：官方 PreToolUse 走 stdin JSON；老 hook 走环境变量。
    data = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}

    tool_name = data.get("tool_name") or os.environ.get("CLAUDE_TOOL_NAME", "")
    tool_input = data.get("tool_input")
    if not tool_input:
        try:
            tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
        except Exception:
            tool_input = {}

    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not is_memory_md(file_path):
        sys.exit(0)  # 非 memory .md → 不干预，走默认弹窗

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "memory 目录 .md 写入已由 allow_memory_write hook 放行",
        }
    }
    print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
