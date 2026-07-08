#!/usr/bin/env python3
"""
allow_memory_write.py — PreToolUse hook

目的：放行对 memory 目录的 Write/Edit，免去权限弹窗。

背景：`.codex/` 是 Codex 的"受保护目录"，写入时无视 acceptEdits
和 permissions.allow 规则一律强制弹窗（安全设计，防恶意篡改 settings/hooks）。
memory 在 `.codex/memory/` 下被连带保护，导致每次保存记忆都弹窗。

本 hook 在权限弹窗之前介入，识别"写 memory 目录的 .md 文件"并直接 allow，
其它 `.codex/` 文件（settings/hooks 本体）不放行，安全边界不破。

匹配三种路径形态（兼容 junction + 可移植）：
- 项目真身    : <proj>/.codex/memory/xxx.md
- 系统 junction: ~/.codex/projects/<hash>/memory/xxx.md
- 相对路径    : .codex/memory/xxx.md

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
    if "/.codex/memory/" in norm or norm.startswith(".codex/memory/"):
        return True
    # 形态 2：系统 junction（~/.codex/projects/<hash>/memory/）
    if "/.codex/projects/" in norm and "/memory/" in norm:
        return True
    return False


def main():
    # 输入双兜底：官方 Codex hook 走 stdin JSON；环境变量只作兼容兜底。
    # 若存在 env fallback，优先读 CODEX_TOOL_*；CLAUDE_TOOL_* 只保留给旧导入配置。
    data = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}

    tool_name = (
        data.get("tool_name")
        or os.environ.get("CODEX_TOOL_NAME")
        or os.environ.get("CLAUDE_TOOL_NAME", "")
    )
    tool_input = data.get("tool_input")
    if not tool_input:
        try:
            env_raw = os.environ.get("CODEX_TOOL_INPUT") or os.environ.get("CLAUDE_TOOL_INPUT", "{}")
            tool_input = json.loads(env_raw)
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
