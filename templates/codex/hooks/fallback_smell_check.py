#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: 兜底坏味道软提醒（仅裸吞异常，D3-M1）。

只抓**一类**近零合法用途的高置信坏味道——**裸/宽异常捕获后直接 pass（静默吞掉）**：
  · Python: 裸 `except` 或 `except Exception` / `except BaseException` 后**仅**一个 pass
  · JS/TS:  空 catch 块 `catch {}` / `catch (e) {}`
这类几乎无正当用途（把真报错吞成假成功，正是根因优先的反面靶）。命中打印
`[fallback-smell]` 提醒，**exit 0 非阻塞**（软信号，交模型自己判断要不要改）。

**首版有意 NOT 命中**（避免误伤，见设计批评③）:
  - `.get(k, default)` / `or []` / `?? x` / Rust `unwrap_or` / `?` —— 合法默认值 / 惯用法
  - `except SpecificError: pass` —— 具体异常常是有意吞（如 FileNotFoundError）
  - 有真实处理的 except（`except X:` 后不是光一个 pass）
  - 只扫**代码文件**（.py/.js/.ts…），跳过 md/json 等（防文档里讨论此模式被误报）

自门控: 非 Edit/Write、非代码文件、或无命中 → 静默 no-op exit 0。
输入双兜底（stdin JSON / 环境变量）同 requirements_check.py。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

CODE_SUFFIXES = {".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

# Python: 裸 except / except Exception / except BaseException (可带 as e) 后仅一个 pass
# (同行或紧跟一行)。**不**命中具体异常类型 (那常是有意吞)。
_PY_SWALLOW = re.compile(
    r"except\s*(?:\(?\s*(?:Exception|BaseException)\s*\)?(?:\s+as\s+\w+)?)?\s*:"
    r"\s*(?:\n[ \t]*)?pass\b"
)
# JS/TS: 空 catch 块
_JS_SWALLOW = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}")


def _new_text(tool_input: dict) -> str:
    """汇集本次 Edit/Write 真正写进去的新文本（Edit.new_string / Write.content / MultiEdit.edits）。"""
    parts: list[str] = []
    ns = tool_input.get("new_string")
    if isinstance(ns, str):
        parts.append(ns)
    content = tool_input.get("content")
    if isinstance(content, str):
        parts.append(content)
    for e in tool_input.get("edits", []) or []:
        if isinstance(e, dict) and isinstance(e.get("new_string"), str):
            parts.append(e["new_string"])
    return "\n".join(parts)


def find_smells(text: str) -> list[str]:
    hits: list[str] = []
    for m in _PY_SWALLOW.finditer(text):
        hits.append("裸/宽 except 后直接 pass（静默吞异常）: " + " ".join(m.group(0).split()))
    for m in _JS_SWALLOW.finditer(text):
        hits.append("空 catch 块（静默吞异常）: " + " ".join(m.group(0).split()))
    return hits


def main() -> int:
    # 输入双兜底：官方 PostToolUse 走 stdin JSON（file_path/new_string 在 tool_input 下）；
    # 老 hook 走环境变量 CLAUDE_TOOL_INPUT（直接是 tool_input dict）。两路都试。
    data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}
    tool_input = data.get("tool_input")
    if not tool_input:
        try:
            tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
        except Exception:
            tool_input = {}
    if not isinstance(tool_input, dict):
        return 0

    fp = tool_input.get("file_path", "")
    if not fp:
        return 0
    # 只扫代码文件（防 md/json 文档里讨论此模式被误报）
    if Path(fp).suffix.lower() not in CODE_SUFFIXES:
        return 0

    text = _new_text(tool_input)
    if not text:
        return 0

    hits = find_smells(text)
    if not hits:
        return 0

    print(f"[fallback-smell] {Path(fp).name} 疑似兜底坏味道（仅裸吞异常，软提醒不阻塞）:")
    for h in hits:
        print(f"[fallback-smell]   - {h}")
    print("[fallback-smell] 静默吞异常会把真报错藏成假成功 → 先确认根因，别用 pass 掩盖（rules/debugging.md §3）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
