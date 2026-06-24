"""较大需求澄清提醒 — UserPromptSubmit hook

机制:
1. 读 stdin JSON 的 prompt 字段。
2. 「便宜负向 gate」(纯字符串判断, hook 不判断需求大小):
   - slash 命令 (/ 开头)         → 跳过 (不干扰 /resume /snapshot 等)
   - 极短输入 (< MIN_CHARS)       → 跳过 (嗯 / 哦 / ? 之类噪声)
   - 纯续接/确认词 (next/继续...) → 跳过 (避免在续接轮反问背景)
3. 其余「候选」轮: print [clarify] 中性提醒到 stdout,
   Claude Code 包成 system-reminder 注入本轮上下文。
4. 这轮到底大不大、该问什么, 由模型(读到提醒后)语义判断 — hook 不替模型决定。

为什么 hook 只「提醒」不「强制」: hook 是 shell 脚本, 没有 LLM, 既判断不了
"这轮够不够大", 也生成不了那几个背景问题。它的全部价值 = 每轮把"较大需求先
问背景"这条规矩重新贴到模型眼前, 对抗长会话里 CLAUDE.md 规矩的注意力衰减
(meta_rule §1: CLAUDE.md 越长越被忽略)。真正的判断与提问留给模型(混合判定:
hook 粗筛 + 贴便利贴, 模型精判 + 真提问)。

详见 CLAUDE.md "clarify 信号约定"。

【模板使用提示】
- MIN_CHARS / CONTINUATION_TOKENS 按团队语言习惯增删。
- 想更激进(每轮都提醒)→ 清空 CONTINUATION_TOKENS 并把 MIN_CHARS 设 0。
- 想更保守(只在明确需求词时提醒)→ 反过来加一个关键词白名单 gate(不推荐:
  口语化大需求"加个 / 搞个 X"没硬关键词, 易漏)。
"""
from __future__ import annotations

import json
import sys

# Windows 终端默认非 UTF-8, 中文会乱码 → 强制 stdout 用 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# 极短输入跳过: 只杀 1 字符噪声(嗯 / 哦 / ?), 不会误伤真需求
# (最短的真需求如"加个导出"=4 字符也保留)。len < MIN_CHARS 即跳过。
MIN_CHARS = 2

# 纯续接/确认词: 去空白 + 去尾部标点 + 小写后【完全相等】才跳过 —
# 只杀"整条就是确认"的轮, 不误伤含这些词的真需求
# (如"继续做就得先重构 X"不会被当成续接)。
CONTINUATION_TOKENS = {
    "next", "yes", "y", "ok", "okay", "k", "go", "yep", "yup", "sure",
    "continue", "done", "next one",
    "继续", "对", "嗯", "好", "好的", "好滴", "是", "是的", "行", "可以",
    "确认", "没问题", "下一个", "下一步", "继续吧", "接着",
}

REMINDER = (
    "[clarify] 若本轮是较大需求 / 设计问题 / 模糊目标，**先用 AskUserQuestion "
    "问用户 2-4 个背景问题**（帮 ta 理清思路、对齐范围）再动手；"
    "若是琐碎改动 / 续接确认 / 用户已说全细节，忽略本提示直接执行。"
)


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    prompt = (data.get("prompt", "") or "").strip()

    # gate 1: slash 命令跳过 (放行 /resume /snapshot 等关键操作)
    if prompt.startswith("/"):
        return

    # gate 2: 极短输入跳过
    if len(prompt) < MIN_CHARS:
        return

    # gate 3: 纯续接/确认词跳过
    normalized = prompt.lower().rstrip("。.!！~～、，, ")
    if normalized in CONTINUATION_TOKENS:
        return

    # 候选 → 贴便利贴, 真假留给模型语义判断
    print(REMINDER)


if __name__ == "__main__":
    main()
