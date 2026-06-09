"""上下文预算预警 — UserPromptSubmit hook

机制:
1. 读 transcript_path JSONL, 从末尾倒查最近一条 assistant 消息的 usage 字段
2. 真实 context 占用 = input_tokens + cache_creation + cache_read + output_tokens
   (与 Claude Code /context 一致, 精确到个位 token)
3. 跨阈值时输出 [ctx-budget] 信号到 stdout, Claude Code 包装成 system-reminder
4. Claude 读到信号后按 instruction 决定行为:
   - CRITICAL (>= 95%): 立即拒绝任务, 强制 /snapshot
   - HIGH (>= 85%): 拒绝复杂任务, 询问是否 /snapshot 换会话
   - MEDIUM (>= 75%): 允许执行, 完成后建议 /snapshot

slash command (以 / 开头) 跳过预警 — 否则 /snapshot 自身也被拦, 死锁。

历史 (2026-05-23 改): 原版用 transcript 文件大小 // 4 估算, 受 JSONL
结构开销 (UUID/时间戳/JSON 信封) 污染显著高估, 越聊越虚报。改读真实 usage 治根。
若 transcript 缺 usage 字段 (旧 session / 损坏), fallback 到 char/4 旧法。

详见 CLAUDE.md "ctx-budget 信号约定"。

【模板使用提示】
- WINDOW 常量按实际使用模型调整 (见下方常量定义处注释)。
- 三个阶梯阈值 75/85/95 是经验值, 跑 5-10 次跨阈值场景后可校准。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 上下文窗口大小 (tokens). 按实际使用模型调整:
#   1M 专用版 Opus (model-id 含 [1m] 后缀)        → 1_000_000  (默认)
#   标准版 Opus 4.8 / Sonnet 4.6 / Haiku 4.5      → 200_000  (标准 200k 模型需手动下调)
WINDOW = 1_000_000

# 三个阶梯阈值
THR_MEDIUM = 75
THR_HIGH = 85
THR_CRITICAL = 95

# 倒查 transcript 末尾的字节数 (单条 assistant 消息通常 < 50KB, 256KB 足够覆盖最后几轮)
TAIL_BYTES = 256 * 1024


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

    # slash command 跳过 (放行 /snapshot, /resume 等关键操作)
    prompt = data.get("prompt", "") or ""
    if prompt.lstrip().startswith("/"):
        return

    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return
    p = Path(transcript_path)
    if not p.exists():
        return

    tokens = read_last_usage(p)
    source = "usage"
    if tokens is None:
        # Fallback: char/4 启发 (旧 session 缺 usage 字段时)
        try:
            tokens = p.stat().st_size // 4
            source = "estimate"
        except Exception:
            return

    pct = tokens * 100 // WINDOW
    if pct < THR_MEDIUM:
        return  # 充裕, 不打扰

    if pct >= THR_CRITICAL:
        level = "CRITICAL"
        instruction = (
            "上下文几乎满, **必须立即拒绝**用户当前任务, "
            "强制提示先 /snapshot 然后关闭对话框开新会话 /resume 接续。"
            "继续做事会很快被自动 compact 吞掉关键状态。"
        )
    elif pct >= THR_HIGH:
        level = "HIGH"
        instruction = (
            "上下文用量偏高。**响应开头主动告知**用户当前用量百分比, "
            "建议先 /snapshot 然后开新会话再 /resume 接续。"
            "**只接受小任务(单文件读 / 1-2 行改动 / 询问)**, 拒绝任何复杂多文件改动。"
        )
    else:
        level = "MEDIUM"
        instruction = (
            "上下文用量已过 75%。可以继续执行当前任务, "
            "但完成后主动建议用户考虑 /snapshot 锁定状态, 为后续做准备。"
        )

    msg = (
        f"[ctx-budget] 上下文用量 {tokens // 1000}k / {WINDOW // 1000}k = {pct}% "
        f"({level}, source={source})\n[ctx-budget] {instruction}"
    )
    print(msg)


if __name__ == "__main__":
    main()