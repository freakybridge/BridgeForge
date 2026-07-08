"""较大需求澄清提醒 — UserPromptSubmit hook

便宜负向 gate(纯字符串, hook 不判需求大小): command / skill 调用 / 极短输入(<MIN_CHARS) /
纯续接确认词(next/继续) → 跳过; 其余「候选」轮 print [clarify] 中性提醒到 stdout,
由模型读到后语义精判这轮大不大、该问什么(hook 只贴便利贴, 不替模型决定)。

分工论述 / 调参(MIN_CHARS / CONTINUATION_TOKENS)/ 豁免 → rules/anti_drift_hooks.md §1。
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

# 裸信号 + 指针: 完整响应契约常驻 AGENTS.md「主动澄清」节, 此处不重复注入
# (每轮重发完整指令 = 与常驻层双付 token)。
REMINDER = (
    "[clarify] 较大 / 模糊需求 → 按 AGENTS.md「主动澄清」红线先问再动手；"
    "琐碎 / 续接 / 已说全细节则忽略。"
)


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    prompt = (data.get("prompt", "") or "").strip()

    # gate 1: command / skill 调用跳过 (放行 $resume / $snapshot 等关键操作)
    if prompt.startswith(("/", "$")):
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
