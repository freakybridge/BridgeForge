"""上下文预算预警 — UserPromptSubmit hook

机制:
1. 读 transcript_path 文件大小, 用 char/4 估算 token 用量
2. 跨阈值时输出 [ctx-budget] 信号到 stdout
3. Claude Code 自动把 stdout 包装成 system-reminder 注入下一轮 Claude 响应上下文
4. Claude 读到 [ctx-budget] 信号后, 按 instruction 决定:
   - CRITICAL (>= 95%): 立即拒绝任务, 强制用户 /snapshot
   - HIGH (>= 85%): 拒绝复杂任务, 询问用户是否要先 /snapshot 换会话
   - MEDIUM (>= 75%): 允许执行, 但完成后主动建议 /snapshot

slash command (以 / 开头) 跳过预警 — 否则 /snapshot 自身也被拦, 死锁。

精度说明: char/4 是 OAI/Anthropic 通用启发, 中文略偏紧 / 代码略偏松,
误差 ±10%。Claude 没公开 tokenizer, 这是当前最简单方案。

详见 CLAUDE.md "ctx-budget 信号约定"。

【模板使用提示】
- WINDOW 常量按实际使用模型调整:
  * 标准版 Opus 4.8 / Sonnet 4.6 / Haiku 4.5      → 200_000  (默认)
  * 1M 专用版 (model-id 含 [1m] 后缀)              → 1_000_000
- 三个阶梯阈值 75/85/95 是经验值, 跑 5-10 次跨阈值场景后可校准
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 上下文窗口大小 (tokens). 标准模型默认 200k; 1M 版需手动改为 1_000_000
WINDOW = 200_000

# 三个阶梯阈值 (百分比)
THR_MEDIUM = 75
THR_HIGH = 85
THR_CRITICAL = 95


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

    try:
        # char/4 启发式 — Claude 没公开 tokenizer
        size_chars = p.stat().st_size
        tokens = size_chars // 4
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
        f"({level})\n[ctx-budget] {instruction}"
    )
    print(msg)


if __name__ == "__main__":
    main()
