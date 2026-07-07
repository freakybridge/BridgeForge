---
name: focus
description: 查看 / 设置 / 重置本会话的「任务锚 anchor」，并按需手动自检是否漂移。focus_reminder.py hook 自动维护锚 + 周期提醒（主动），本 skill 给用户手动控制权（被动入口）。
model: sonnet
---

# /focus / $focus — 任务锚控制 + 手动漂移自检

**定位**：`focus_reminder.py` hook 会自动把本会话第一条实质 prompt 记为「任务锚」，并周期性贴 `[focus]` 提醒（**主动**）。本 skill 是**被动入口**——让你手动查看 / 改 / 清锚，或当场让我对照锚自检有没有跑偏。

锚存在 `.runtime/focus/anchor.json`，结构 `{ "session": "...", "anchor": "...", "turns": N }`。

## 用法

| 输入 | 动作 |
|------|------|
| `/focus`（Claude）/ `$focus`（Codex） | 显示当前锚 + **当场自检**：对照锚判断最近在做的还属不属于原任务，跑偏了就分类提示 |
| `/focus <文本>` / `$focus <文本>` | 把锚**改成** `<文本>`（hook 自动抓错了、或任务正当演进了，用这个纠正）|
| `/focus clear` / `$focus clear` | 清掉锚（hook 会在下一条实质 prompt 重新捕获）|

## 执行步骤

1. **读** `.runtime/focus/anchor.json`。不存在 → 提示"还没有锚，hook 会在下一条实质消息自动捕获"，结束。

2. **按输入分支**：

   - **无参** → 展示 `anchor` + `turns`，然后对照锚做一次漂移自检（分类同 CLAUDE.md / AGENTS.md 漂移规则），给结论之一：
     - 「✓ 仍在原任务」
     - 「⚠ 疑似漂移 → 类型（前置阻塞 / 附加扩张 / 无关支线）→ 建议响应（Claude `/spinoff` / Codex `$spinoff` · 内联 / Claude `/todo` / Codex `$todo` / 新对话）」

   - **带文本**（`/focus 重构 OMS 事件分发` / `$focus 重构 OMS 事件分发`）→ 把 JSON 的 `anchor` 字段改为该文本，**保留** `session` 和 `turns` 字段，写回。回 `✓ 锚已更新为：<文本>`。

   - **clear** → **删除整个 anchor.json 文件**（不要只清字段——保留 `session` 会让 hook 不再重新捕获）。回 `✓ 锚已清，下一条实质消息将重新捕获`。

3. 写 JSON 用 UTF-8 + `ensure_ascii=False`（中文不转义）。

## 何时主动建议

- 你感觉聊偏了，想让我对照原任务核一下 → 建议 `/focus` / `$focus`
- hook 自动抓的锚明显不对（抓到寒暄 / 前置子问题）→ 建议 `/focus <正确任务>` / `$focus <正确任务>`
- 任务正当地演进成新目标，想把锚挪过去 → 建议 `/focus <新目标>` / `$focus <新目标>`

## 禁止

- ❌ 把锚当长期 memory（它是 session 级短期状态，换 session 自动重置；长期知识用 `/summary` / `$summary`）
- ❌ `/focus clear` / `$focus clear` 时只清 `anchor` 字段保留 `session`（会导致 hook 永不重新捕获——必须删整文件）
- ❌ 用锚存与"原任务是什么"无关的内容
