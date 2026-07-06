---
paths:
  - ".claude/hooks/**"
  - ".claude/settings.json"
---

# 反漂移 hook 低频细节（clarify / focus / ctx-budget）

> 本文件是 CLAUDE.md §9.5 / §9.6 / §10 反漂移 hook 契约的**低频细节承接**——「为什么这么分工 / 主动+被动入口 / hook 路径 / 注册 / 调参 / 豁免」。
> **红线本身（分支动作、漂移分类表、各级信号行为表、所有"禁止"条款）在 CLAUDE.md 正文，不在这里。** 本文件只放论述与配置参数。

---

## 1. `[clarify]` 信号 — 较大需求主动澄清（CLAUDE.md §9.5）

**机制**：`UserPromptSubmit` hook（`.claude/hooks/clarify_reminder.py`）每次用户提交 prompt 时做「便宜负向 gate」，候选轮（非 slash 命令 / 非纯续接词 / 非极短输入）输出 `[clarify]` system reminder。

**混合判定分工**（hook 粗筛 + 模型精判）：

| 谁 | 干什么 | 为什么归它 |
|----|--------|-----------|
| **hook** | 每轮粗筛掉 slash / `next`·`继续` 等续接词 / 极短输入，其余贴 `[clarify]` 便利贴 | 可靠、不随长会话衰减；但它没 LLM，判断不了"大不大"也不会提问 |
| **模型** | 读到 `[clarify]` 后**语义精判**这轮够不够大，再决定问不问、问什么 | 只有 LLM 干得了 |

**配置**：

- Hook 入口：`.claude/hooks/clarify_reminder.py`（项目内）
- 注册位置：`.claude/settings.json` → `hooks.UserPromptSubmit`
- 调参：hook 文件开头改 `MIN_CHARS`（极短阈值）和 `CONTINUATION_TOKENS`（续接/确认词集合，按团队语言习惯增删）

---

## 2. `[focus]` 信号 — 任务防漂移（CLAUDE.md §9.6）

**机制**：`UserPromptSubmit` hook（`.claude/hooks/focus_reminder.py`）自动把本会话第一条实质 prompt 记为「任务锚 anchor」，攒够几轮后**周期性**注入 `[focus]` system reminder，把原始任务重新贴到眼前。锚存 `.runtime/focus/anchor.json`，可用 `/focus` 查看 / 改 / 清。

**主动 + 被动两条入口**：

| 入口 | 谁发起 | 机制 |
|------|--------|------|
| **主动** | hook 自动 | 周期贴 `[focus]`，读到后自检是否跑偏 |
| **被动** | 用户 `/focus` | 当场对照锚核一次；`/focus <文本>` 纠正锚 |
| **被动** | 用户 `/spinoff` | 确认是前置阻塞后，一键交接派生到新对话 |

**配置**：

- Hook 入口：`.claude/hooks/focus_reminder.py`（项目内）
- 锚文件：`.runtime/focus/anchor.json`（per-session，换 session 自动重置；并发多 session 会 last-write-wins 互相覆盖锚 — 用 `/focus <本会话任务>` 手动重设回来）
- 调参：hook 开头改 `FOCUS_MIN_TURN`（攒几轮才开始提醒）/ `FOCUS_EVERY`（每几轮提醒一次）
- 配套 skill：`/spinoff`（前置派生交接）、`/focus`（锚控制 + 手动自检）

---

## 3. `[ctx-budget]` 信号 — 上下文预算（CLAUDE.md §10）

**机制**：`UserPromptSubmit` hook（`.claude/hooks/context_warning.py`）在每次用户提交 prompt 时估算上下文用量，超阈值时输出 `[ctx-budget]` system reminder（MEDIUM / HIGH / CRITICAL 三级）。判定基于 char/4 启发式，精度 ±10%；边界附近以信号为准。

**slash command 豁免**：`/snapshot` / `/resume` / `/git-sync` 等以 `/` 开头的 prompt 不触发预警 — 否则用户连保命操作都被拦，死锁。所以响应 CRITICAL 时建议用户做的 `/snapshot` 不会自相矛盾。

**配置**：

- Hook 入口：`.claude/hooks/context_warning.py`（项目内）
- 注册位置：`.claude/settings.json` → `hooks.UserPromptSubmit`
- 调参：在 hook 文件开头改 `WINDOW`（窗口大小，按模型选 1M / 200k）和 `THR_MEDIUM/HIGH/CRITICAL`（三个阶梯阈值，默认 75/85/95）
