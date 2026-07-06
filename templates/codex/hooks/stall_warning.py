#!/usr/bin/env python3
"""stall_warning.py — UserPromptSubmit hook：空转弱事后提醒（D4-M4）。

**定位（诚实标注，务必先读）**：
- 这是**弱事后代理提醒，不是实时刹车**。空转发生在单个 assistant 轮内（thinking 期
  LLM 被 SUSPENDED，任何 hook 都插不进去），本 hook 只在**下一轮** UserPromptSubmit 触发，
  作用是让下一轮尽快收口。见 memory `feedback-llm-suspended-during-tool-exec`。
- **对合法长思考轮无区分力**：本 repo「连续多轮写 rule/doc 而少 tool_use」是最常见的合法
  长思考；去抖救不了主力误报（设计批评⑧）。故判据用**多特征合取 + 降级为只在明显场景弱提醒**，
  达不到全部可得特征就**不 fire**（宁漏不烦）。Opus 4.8 无硬开关、概率遵守、**不保证根治**。

**判据（多特征合取，全部满足才 fire）**：
- (a) 最近 >=2 轮 assistant **output_tokens 偏高 且 零 tool_use**（写了/想了很多但没动工具）；
- (b) 这几轮由**用户续接式 nudge**（/ 短语 / "继续 next" 类）驱动、**非新实质指令**
      （排除「用户连发几条让它连写几轮」的合法场景），且当前这条 prompt 也是续接式；
- (c) **thinking 占比偏高的代理**：这些轮 output_tokens 远大于可见正文量（大部分 token 花在
      thinking 而非产出）。CC usage 不单列 thinking token，故用 output_tokens vs 正文字符数
      的差值估算；估不出则跳过 (c)、只用 a+b（设计允许优雅降级）。

非阻塞：始终只 print [stall] 到 stdout，exit 0。复用 context_warning 的 tail-read 骨架，
新增**多轮遍历 + message.content[] 的 tool_use/text block 扫描**（这是新逻辑，非「仅换判据」）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 倒查 transcript 末尾字节数：需覆盖最近几轮（比 context_warning 的 256KB 大）
TAIL_BYTES = 512 * 1024
# "output 偏高" 阈值（单轮 assistant output_tokens 合计）
STALL_OUTPUT_MIN = 2000
# 需连续满足的最近轮数
MIN_TURNS = 2
# thinking 占比代理阈值（thinking_est / output_tokens）
THINK_RATIO = 0.5
# 续接式 nudge：<= 这么多字符视为短 nudge
CONT_MAX_CHARS = 15
CONTINUATION = {
    "next", "继续", "go", "go on", "go ahead", "continue", "proceed", "keep going",
    "ok", "okay", "好", "好的", "嗯", "嗯嗯", "行", "接着", "下一个", "y", "yes",
}

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _read_tail(path: Path) -> bytes:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
                f.readline()  # 丢弃可能被切断的半行
            return f.read()
    except Exception:
        return b""


def _is_continuation(prompt: str) -> bool:
    p = (prompt or "").strip()
    if not p:
        return True
    low = p.lower()
    if low in CONTINUATION:
        return True
    return len(p) <= CONT_MAX_CHARS  # 短 nudge 视为续接


def _blocks(content) -> list:
    if isinstance(content, list):
        return content
    return []


def _parse_events(chunk: bytes) -> list:
    """把 JSONL 逐行解析成有序事件:
      ('user', text, is_real_prompt)  —— is_real=False 表示只是 tool_result 载体
      ('asst', output_tokens, has_tool_use, text_chars)
    """
    events: list = []
    for raw in chunk.splitlines():
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        msg = d.get("message") or {}
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            if isinstance(content, str):
                events.append(("user", content, bool(content.strip())))
            else:
                text = "".join(
                    b.get("text", "") for b in _blocks(content)
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                has_tool_result = any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in _blocks(content)
                )
                # 真实 prompt = 有正文文本且不是纯 tool_result 载体
                is_real = bool(text.strip()) and not (has_tool_result and not text.strip())
                events.append(("user", text, is_real))
        elif role == "assistant":
            usage = msg.get("usage") or {}
            try:
                out = int(usage.get("output_tokens", 0))
            except Exception:
                out = 0
            has_tool = any(
                isinstance(b, dict) and b.get("type") == "tool_use"
                for b in _blocks(content)
            )
            text_chars = sum(
                len(b.get("text", "")) for b in _blocks(content)
                if isinstance(b, dict) and b.get("type") == "text"
            )
            events.append(("asst", out, has_tool, text_chars))
    return events


def _turns(events: list) -> list:
    """把事件按「真实 user prompt」切成轮。每轮聚合其 assistant 步。
    返回 [{prompt, out, has_tool, text}]，按时间顺序。tool_result user 消息不切轮。
    """
    turns: list = []
    cur = None
    for e in events:
        if e[0] == "user" and e[2]:  # 真实 prompt → 开新轮
            cur = {"prompt": e[1], "out": 0, "has_tool": False, "text": 0}
            turns.append(cur)
        elif e[0] == "asst" and cur is not None:
            cur["out"] += e[1]
            cur["has_tool"] = cur["has_tool"] or e[2]
            cur["text"] += e[3]
    return turns


def _stall_turn(t: dict) -> bool:
    """单轮是否 stall-ish：高 output + 零 tool_use + (可算时) thinking 占比高。"""
    if t["has_tool"]:
        return False
    if t["out"] < STALL_OUTPUT_MIN:
        return False
    # (c) thinking 占比代理：可见正文 tokens ~= text_chars/4；剩下的算 thinking
    if t["out"] > 0:
        think_est = t["out"] - (t["text"] / 4.0)
        if (think_est / t["out"]) < THINK_RATIO:
            return False  # 正文产出多 → 是真产出不是空转
    return True


def main() -> int:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return 0

    cur_prompt = data.get("prompt", "") or ""
    if cur_prompt.lstrip().startswith("/"):
        return 0  # slash 命令豁免（同 context_warning）
    # (b) 当前这条也必须是续接式 nudge，否则用户在给新指令 → 不算空转
    if not _is_continuation(cur_prompt):
        return 0

    tp = data.get("transcript_path", "")
    if not tp:
        return 0
    p = Path(tp)
    if not p.exists():
        return 0

    turns = _turns(_parse_events(_read_tail(p)))
    if len(turns) < MIN_TURNS:
        return 0

    recent = turns[-MIN_TURNS:]
    # (a)+(c) 每轮 stall-ish
    if not all(_stall_turn(t) for t in recent):
        return 0
    # (b) 每轮由续接式 nudge 驱动（非新实质指令）
    if not all(_is_continuation(t["prompt"]) for t in recent):
        return 0

    print(
        f"[stall] 最近 {MIN_TURNS} 轮均高 output_tokens 且零 tool_use、由续接式 nudge 驱动 —— "
        "疑似空转（长 thinking 无产出）。这是**弱事后提醒**：空转发生在上一轮内、已无法当轮止损，"
        "本轮请尽快收口给结论或落一个具体动作（工具调用/文件改），别继续纯 thinking 空耗。"
    )
    print(
        "[stall] （已知对合法长思考轮无区分力；若你确在做正当分析，忽略本提醒即可。"
        "Opus 4.8 无硬开关，此为概率软提醒、不保证根治。）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
