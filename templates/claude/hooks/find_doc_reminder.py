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
    # 输入双兜底（与 requirements_check.py 一致）：官方 PreToolUse 走 stdin JSON
    # （tool_name / tool_input 为顶层字段）；老 hook 走环境变量 CLAUDE_TOOL_NAME/_INPUT。
    # 只读 env-var 会在「CC 仅走 stdin、不设该 env」时永不触发，故两路都试。
    tool_name = ""
    data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
            tool_name = payload.get("tool_name", "") or ""
            ti = payload.get("tool_input")
            if isinstance(ti, dict):
                data = ti
    except Exception:
        pass
    if not tool_name:
        tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
        try:
            data = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
        except Exception:
            return 0

    is_doc, paths_desc = _is_doc_search(tool_name, data)
    if not is_doc:
        return 0

    # 记录统计
    _log_call(tool_name, paths_desc)

    # 输出裸信号到 stdout（跳过场景 / 触发词速查已载于 find-doc skill description，
    # 常驻 system prompt，此处不重复注入——一轮可多次触发，重复即多倍烧 token）
    print(
        f"[find-doc] 检测到 {tool_name} 直接搜 doc/（{paths_desc}）—— "
        f"定位文档优先 `/find-doc <topic>`（省 token）；已知精确路径 / 代码搜索则忽略。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
