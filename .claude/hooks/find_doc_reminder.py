#!/usr/bin/env python3
"""PreToolUse Hook: 提醒 agent 搜 doc/ 时优先用 /find-doc skill。

来源：2026-04-29 debate（doc 索引体系审视）—— D1+D4 决议：
- 用 hook 而非 rule 强制 agent 调用 find-doc（rule 是文字 cargo cult）
- 同时记录调用统计（替代 D4 的独立监控 hook）

工作机制：
- 每次 Grep / Glob / Read 工具调用前触发
- 检查 path/glob/file_path 参数是否指向 doc/ 目录
- 是 → 1) 记录到 .runtime/find-doc-stats.log；2) stdout 输出提醒（Claude 会看到）
- 不阻止工具调用（exit 0），只提醒
- 跳过 doc/README.md 单文件 Read（Read 主索引是合理操作）

输出统计文件：`.runtime/find-doc-stats.log`（记录 grep doc/ 调用频次）。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOG = REPO_ROOT / ".runtime" / "find-doc-stats.log"

# 强制 stdout UTF-8 (Windows 默认 GBK 会乱码)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _is_doc_search(tool_name: str, data: dict) -> tuple[bool, str]:
    """判定该次工具调用是否针对 doc/ 目录。返回 (是否, 原因描述)。"""
    if tool_name not in ("Grep", "Glob", "Read"):
        return False, ""

    # 收集所有可能的路径字段
    candidate_fields = ("path", "file_path", "glob")
    paths: list[str] = []
    for k in candidate_fields:
        v = data.get(k, "")
        if isinstance(v, str) and v:
            paths.append(f"{k}={v}")

    if not paths:
        return False, ""

    # 任一字段含 "doc/" 或 "doc\\" 视为 doc 搜索
    for p in paths:
        v = p.split("=", 1)[1] if "=" in p else p
        if "doc/" in v or "doc\\" in v or v.endswith("/doc") or v == "doc":
            # 跳过单文件 Read 主索引（Read doc/README.md 等是合理）
            if tool_name == "Read" and v.endswith(("README.md", "TODO-INDEX.md")):
                return False, ""
            return True, " ".join(paths)

    return False, ""


def _log_call(tool_name: str, paths_desc: str) -> None:
    """记录调用到 .runtime/find-doc-stats.log。"""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    line = f"{ts}\t{tool_name}\t{paths_desc}\n"
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # 静默失败，不阻塞工具调用
        pass


def main() -> int:
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
    tool_input_raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")

    try:
        data = json.loads(tool_input_raw)
    except Exception:
        return 0

    is_doc, paths_desc = _is_doc_search(tool_name, data)
    if not is_doc:
        return 0

    # 记录统计
    _log_call(tool_name, paths_desc)

    # 输出提醒到 stdout（Claude Code PreToolUse hook stdout 注入到 agent 上下文）
    print(
        f"[find-doc reminder] 检测到 {tool_name} 直接搜 doc/（{paths_desc}）。"
        f"如果是定位文档请优先调用 `/find-doc <topic>` skill：单次聚合 + 省 50-70% token。"
        f" **跳过场景**：已知精确路径 / 同 session 已查过 / 代码搜索（用 Grep path: <source-dir>/）。"
        f" 触发词速查：'帮我找 X' / 'X 还有什么没解决' / 'X 进展如何' / 'X 的设计在哪' 等。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
