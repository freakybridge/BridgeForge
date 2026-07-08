#!/usr/bin/env python3
"""PostToolUse hook: requirements.txt 可移植性 + 编码红线检查。

仅对 `requirements*.txt` 的 Edit/Write 触发，查两条 portability 红线：
① 禁绝对路径 URL(`pkg @ file:///...`，换机即 fail)；② 内容/注释必须 ASCII(Windows pip GBK 解码)。
非阻塞（exit 0），命中打印 [requirements-check] 警告。详见 rules/portability.md §4.1/§4.2。
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

ABS_URL_RE = re.compile(r"@\s*file://", re.IGNORECASE)


def check(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        raw = path.read_bytes()
    except Exception:
        return violations
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        violations.append("文件不是合法 UTF-8 — 清理非法字节")
        text = raw.decode("utf-8", errors="replace")

    for i, line in enumerate(text.splitlines(), 1):
        if ABS_URL_RE.search(line):
            violations.append(
                f"L{i} 绝对路径 URL（`@ file://`）— 换机即 fail；"
                f"改用 libs/ + 顶部 `--find-links libs/` + `name==version`"
            )
        # 非 ASCII：pip 在 Windows 用 GBK 解码，非 ASCII 会 UnicodeDecodeError
        non_ascii = [c for c in line if ord(c) > 127]
        if non_ascii:
            violations.append(
                f"L{i} 含非 ASCII 字符 {non_ascii[:5]} — pip 在 Windows 按 GBK 解码会报错；"
                f"注释只用英文，中文挪 README"
            )
    return violations


def main() -> int:
    # 输入双兜底（与 allow_memory_write.py 一致）：官方 Codex hook 走 stdin JSON，
    # file_path 嵌在 `tool_input` 下；环境变量只作兼容兜底，优先 CODEX_TOOL_INPUT，
    # CLAUDE_TOOL_INPUT 仅保留给旧导入配置。
    data = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}
    tool_input = data.get("tool_input")
    if not tool_input:
        try:
            env_raw = os.environ.get("CODEX_TOOL_INPUT") or os.environ.get("CLAUDE_TOOL_INPUT", "{}")
            tool_input = json.loads(env_raw)
        except Exception:
            tool_input = {}
    fp = tool_input.get("file_path", "")
    if not fp:
        return 0
    p = Path(fp)
    # 只关心 requirements*.txt
    if not (p.name.startswith("requirements") and p.suffix == ".txt"):
        return 0
    if not p.exists():
        return 0

    violations = check(p)
    if not violations:
        return 0
    print(f"[requirements-check] {p.name} 违反 portability 红线（rules/portability.md §4.1/§4.2）:")
    for v in violations:
        print(f"[requirements-check]   - {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
