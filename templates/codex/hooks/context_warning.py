"""上下文预算预警 — UserPromptSubmit hook

机制:
1. 读 transcript_path JSONL, 从末尾倒查最近一条 assistant 消息的 usage 字段
2. 真实 context 占用 = input_tokens + cache_creation + cache_read + output_tokens
   (与 Codex /context 一致, 精确到个位 token)
3. 跨阈值时输出 [ctx-budget] 信号到 stdout, Codex 包装成 system-reminder
4. Codex 读到信号后按 instruction 决定行为 (软化后: 建议不强拦, 决定权交用户):
   - CRITICAL (>= 95%): 强烈建议先 $snapshot 换会话, 用户坚持可继续 (提示状态可能被 compact 吞)
   - HIGH (>= 85%): 复杂多文件改动建议拆小或换会话, 用户坚持则说明风险后继续
   - MEDIUM (>= 75%): 允许执行, 完成后建议 $snapshot

command / skill 调用（以 / 或 $ 开头）跳过预警 — 否则 $snapshot 自身也被拦, 死锁。

若 transcript 缺 usage 字段 (旧 session / 损坏), fallback 到 char/4 估算。

详见 AGENTS.md "ctx-budget 信号约定"。调参(WINDOW / 阈值)见下方常量注释。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Codex Desktop 的有效 compact 窗口尚未在本骨架中实测确认。Claude 侧可硬编码
# 1_000_000；Codex 侧先用保守默认，避免真实窗口较小时被误算成低占用。
# 需要按机器/版本校准时设置 BRIDGEFORGE_CODEX_CTX_WINDOW，例如 1000000。
DEFAULT_CODEX_WINDOW = 258_000
WINDOW_ENV = "BRIDGEFORGE_CODEX_CTX_WINDOW"

# 三个阶梯阈值
THR_MEDIUM = 75
THR_HIGH = 85
THR_CRITICAL = 95

# 倒查 transcript 末尾的字节数 (单条 assistant 消息通常 < 50KB, 256KB 足够覆盖最后几轮)
TAIL_BYTES = 256 * 1024


def effective_window() -> tuple[int, str]:
    raw = os.environ.get(WINDOW_ENV, "").strip()
    if not raw:
        return DEFAULT_CODEX_WINDOW, "default"
    try:
        value = int(raw.replace("_", ""))
    except ValueError:
        return DEFAULT_CODEX_WINDOW, f"invalid-env:{WINDOW_ENV}"
    if value <= 0:
        return DEFAULT_CODEX_WINDOW, f"invalid-env:{WINDOW_ENV}"
    return value, f"env:{WINDOW_ENV}"


def read_last_usage(path: Path) -> int | None:
    """从 transcript JSONL 末尾倒查最近一条 assistant.usage, 返回真实 context token 数。

    返回 None 表示没找到 usage (旧 session 或文件损坏), 调用方走 fallback。
    """
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
                f.readline()  # 丢弃可能被切断的半行
            chunk = f.read()
    except Exception:
        return None

    lines = chunk.splitlines()
    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        msg = d.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        usage = msg.get("usage")
        if not usage:
            continue
        try:
            return (
                int(usage.get("input_tokens", 0))
                + int(usage.get("cache_creation_input_tokens", 0))
                + int(usage.get("cache_read_input_tokens", 0))
                + int(usage.get("output_tokens", 0))
            )
        except Exception:
            continue
    return None


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    # command / skill 调用跳过 (放行 $snapshot, $resume 等关键操作)
    prompt = data.get("prompt", "") or ""
    if prompt.lstrip().startswith(("/", "$")):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return
    p = Path(transcript_path)
    if not p.exists():
        return

    tokens = read_last_usage(p)
    token_source = "usage"
    if tokens is None:
        # Fallback: char/4 启发 (旧 session 缺 usage 字段时)
        try:
            tokens = p.stat().st_size // 4
            token_source = "estimate"
        except Exception:
            return

    window, window_source = effective_window()
    pct = tokens * 100 // window
    if pct < THR_MEDIUM:
        return  # 充裕, 不打扰

    if pct >= THR_CRITICAL:
        level = "CRITICAL"
        instruction = (
            "上下文几乎满。**响应开头主动告知**用户当前用量, "
            "**强烈建议**先 $snapshot 然后关闭对话框开新会话 $resume 接续。"
            "**决定权交用户**——用户坚持可继续, 但提示继续做事可能很快被自动 compact 吞掉关键状态。"
        )
    elif pct >= THR_HIGH:
        level = "HIGH"
        instruction = (
            "上下文用量偏高。**响应开头主动告知**用户当前用量百分比, "
            "建议先 $snapshot 然后开新会话再 $resume 接续。"
            "复杂多文件改动**建议先拆小或换会话**, 用户坚持则说明风险后继续。"
        )
    else:
        level = "MEDIUM"
        instruction = (
            "上下文用量已过 75%。可以继续执行当前任务, "
            "但完成后主动建议用户考虑 $snapshot 锁定状态, 为后续做准备。"
        )

    msg = (
        f"[ctx-budget] surface=codex 上下文用量 {tokens // 1000}k / {window // 1000}k = {pct}% "
        f"({level}, token_source={token_source}, window_source={window_source})\n"
        f"[ctx-budget] {instruction}"
    )
    print(msg)


if __name__ == "__main__":
    main()
