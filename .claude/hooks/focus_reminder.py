"""任务防漂移 focus 提醒 — UserPromptSubmit hook

机制(与 clarify_reminder 同族: hook 提醒 + 模型判断):
1. 读 stdin JSON 的 prompt + transcript_path。
2. 维护一个「任务锚 anchor」(.runtime/focus/anchor.json):
   - 新 session(transcript 变) → 清旧锚, 重新开始
   - 本 session 第一条「实质」prompt → 记为 anchor, 不提醒(这条就是原任务, 还没漂)
   - 之后每条实质 prompt → turns+1; 攒够 FOCUS_MIN_TURN 轮后, 每 FOCUS_EVERY 轮
     注入一次 [focus] 提醒
3. [focus] 把原始任务重新贴到模型眼前, 问"还在推进它吗"。
   是否真漂、漂成哪类、怎么响应, 由模型语义判断(hook 不替它决定)。

「实质」prompt = 非 slash / 非续接确认词 / 非极短(同 clarify gate)。
gate 掉的轮不计数、不提醒。

为什么前几轮不提醒: 漂移需要时间发酵, 头几轮还在原任务上, 提醒纯噪声。
为什么周期(非每轮)提醒: 漂移是慢发展状态, 周期脉冲足够; 每轮贴会和 clarify
叠成噪声。FOCUS_MIN_TURN 之后每 FOCUS_EVERY 轮一次, 命中注意力衰减区。

为什么单文件 last-write-wins(非 per-session 文件): 让 hook 和 /focus·/spinoff
skill 都能用同一固定路径读写。代价: 真·并发多 session 会互相覆盖锚 —
并发场景用 /focus <本会话任务> 手动把锚重设回来。

详见 CLAUDE.md "focus 信号约定"(§9.6)。

【模板使用提示】
- FOCUS_MIN_TURN / FOCUS_EVERY / CONTINUATION_TOKENS 按需调。
- 想更勤 → 降 FOCUS_MIN_TURN 或 FOCUS_EVERY; 想更安静 → 升它们。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, Exception):
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ANCHOR_FILE = REPO_ROOT / ".runtime" / "focus" / "anchor.json"

# 攒够这么多「实质」轮后才开始贴 [focus](漂移需时间发酵, 头几轮免打扰)
FOCUS_MIN_TURN = 4
# 之后每隔几轮提醒一次(周期脉冲, 避免每轮叠 clarify 成噪声)
FOCUS_EVERY = 3
# 锚文本截断长度(原任务 prompt 可能很长, 只留开头当提示)
ANCHOR_MAX_CHARS = 240
# 极短输入跳过阈值(同 clarify)
MIN_CHARS = 2

CONTINUATION_TOKENS = {
    "next", "yes", "y", "ok", "okay", "k", "go", "yep", "yup", "sure",
    "continue", "done", "next one",
    "继续", "对", "嗯", "好", "好的", "好滴", "是", "是的", "行", "可以",
    "确认", "没问题", "下一个", "下一步", "继续吧", "接着",
}


def _is_substantive(prompt: str) -> bool:
    if prompt.startswith("/"):
        return False
    if len(prompt) < MIN_CHARS:
        return False
    normalized = prompt.lower().rstrip("。.!！~～、，, ")
    return normalized not in CONTINUATION_TOKENS


def _load() -> dict:
    try:
        return json.loads(ANCHOR_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(state: dict) -> None:
    try:
        ANCHOR_FILE.parent.mkdir(parents=True, exist_ok=True)
        ANCHOR_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    prompt = (data.get("prompt", "") or "").strip()
    session = Path(data.get("transcript_path", "") or "").stem or "default"

    if not _is_substantive(prompt):
        return  # gate 掉: 不计数不提醒

    state = _load()

    # 新 session → 重置锚, 第一条实质 prompt = 原任务本身, 不提醒
    if state.get("session") != session:
        _save({"session": session, "anchor": prompt[:ANCHOR_MAX_CHARS], "turns": 1})
        return

    # 同 session, 累加轮次
    state["turns"] = int(state.get("turns", 1)) + 1
    _save(state)

    # 头几轮免打扰 + 之后周期脉冲
    if state["turns"] < FOCUS_MIN_TURN:
        return
    if (state["turns"] - FOCUS_MIN_TURN) % FOCUS_EVERY != 0:
        return

    anchor = (state.get("anchor") or "").strip()
    if not anchor:
        return

    print(
        f"[focus] 本会话原始任务:「{anchor}」。这轮是否仍在推进它?\n"
        f"[focus] 若在做偏离原任务的子问题, 别闷头做 — 按 CLAUDE.md §9.6 分类响应: "
        f"前置阻塞→大用 /spinoff 交接+开新对话·小做完即回 | 附加→/todo | "
        f"无关→/todo 或新对话 | 仍是原任务正当子步→忽略本提示"
    )


if __name__ == "__main__":
    main()
