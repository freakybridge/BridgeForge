---
paths:
  - ".codex/hooks/**"
  - ".codex/settings.json"
---

# 反漂移 hook 低频细节（clarify / focus / ctx-budget）

> 本文件是 AGENTS.md §9.5 / §9.6 / §10 反漂移 hook 契约的**低频细节承接**——「为什么这么分工 / 主动+被动入口 / hook 路径 / 注册 / 调参 / 豁免」。
> **红线本身（分支动作、漂移分类表、各级信号行为表、所有"禁止"条款）在 AGENTS.md 正文，不在这里。** 本文件只放论述与配置参数。

---

## 1. `[clarify]` 信号 — 较大需求主动澄清（AGENTS.md §9.5）

**机制**：`UserPromptSubmit` hook（`.codex/hooks/clarify_reminder.py`）每次用户提交 prompt 时做「便宜负向 gate」，候选轮（非 slash 命令 / 非纯续接词 / 非极短输入）输出 `[clarify]` system reminder。

**混合判定分工**（hook 粗筛 + 模型精判）：

| 谁 | 干什么 | 为什么归它 |
|----|--------|-----------|
| **hook** | 每轮粗筛掉 slash / `next`·`继续` 等续接词 / 极短输入，其余贴 `[clarify]` 便利贴 | 可靠、不随长会话衰减；但它没 LLM，判断不了"大不大"也不会提问 |
| **模型** | 读到 `[clarify]` 后**语义精判**这轮够不够大，再决定问不问、问什么 | 只有 LLM 干得了 |

**配置**：

- Hook 入口：`.codex/hooks/clarify_reminder.py`（项目内）
- 注册位置：`.codex/settings.json` → `hooks.UserPromptSubmit`
- 调参：hook 文件开头改 `MIN_CHARS`（极短阈值）和 `CONTINUATION_TOKENS`（续接/确认词集合，按团队语言习惯增删）

---

## 2. `[focus]` 信号 — 任务防漂移（AGENTS.md §9.6）

**机制**：`UserPromptSubmit` hook（`.codex/hooks/focus_reminder.py`）自动把本会话第一条实质 prompt 记为「任务锚 anchor」，攒够几轮后**周期性**注入 `[focus]` system reminder，把原始任务重新贴到眼前。锚存 `.runtime/focus/anchor.json`，可用 `$focus` 查看 / 改 / 清。

**主动 + 被动两条入口**：

| 入口 | 谁发起 | 机制 |
|------|--------|------|
| **主动** | hook 自动 | 周期贴 `[focus]`，读到后自检是否跑偏 |
| **被动** | 用户 `$focus` | 当场对照锚核一次；`$focus <文本>` 纠正锚 |
| **被动** | 用户 `$spinoff` | 确认是前置阻塞后，一键交接派生到新对话 |

**配置**：

- Hook 入口：`.codex/hooks/focus_reminder.py`（项目内）
- 锚文件：`.runtime/focus/anchor.json`（per-session，换 session 自动重置；并发多 session 会 last-write-wins 互相覆盖锚 — 用 `$focus <本会话任务>` 手动重设回来）
- 调参：hook 开头改 `FOCUS_MIN_TURN`（攒几轮才开始提醒）/ `FOCUS_EVERY`（每几轮提醒一次）
- 配套 skill：`$spinoff`（前置派生交接）、`$focus`（锚控制 + 手动自检）

---

## 3. `[ctx-budget]` 信号 — 上下文预算（AGENTS.md §10）

**机制**：`UserPromptSubmit` hook（`.codex/hooks/context_warning.py`）优先读取当前 Codex `event_msg.token_count`，兼容旧 `assistant.usage`；两者都不存在时才 fallback 到 char/4。成本档位为 ECONOMY / HANDOFF / CRITICAL，缓存命中偏低时叠加 CACHE_MISS。

**Codex 窗口口径**：优先使用 token_count 中的 `model_context_window`；`BRIDGEFORGE_CODEX_CTX_WINDOW` 可显式覆盖；日志缺值时才退回默认 `353_000`。当前 Codex 的 `input_tokens` 已包含 cached 部分，禁止再次累加 `cached_input_tokens`。

**交接命令豁免**：仅 `$snapshot` / `$resume` / `/compact` 静默放行，避免交接动作被重复提示；其他 skill（含 `$git-sync`）仍可执行，但不会隐藏高成本信号。

**配置**：

- Hook 入口：`.codex/hooks/context_warning.py`（项目内）
- 注册位置：`.codex/settings.json` → `hooks.UserPromptSubmit`
- 调参：窗口用 `BRIDGEFORGE_CODEX_CTX_WINDOW`；成本档位用 `BRIDGEFORGE_CTX_ECONOMY_TOKENS` / `BRIDGEFORGE_CTX_HANDOFF_TOKENS` / `BRIDGEFORGE_CTX_CRITICAL_TOKENS`（默认 80k / 140k / 200k）
