---
name: spinoff
description: 任务漂移到「前置阻塞问题」时的交接原语 — 存档当前主任务状态 + 生成解决前置问题的种子提示词 + 双向回链，引导去新对话解前置后再用 /resume（Claude）或 $resume（Codex）回来。当发现"要解决 A 得先解决 B 且 B 阻塞 A 又够大"时主动调用。
model: sonnet
---

# /spinoff / $spinoff — 前置问题派生交接

**定位**：推进主任务 A 时发现必须先解决前置问题 B（B 阻塞 A），用本 skill 把「当前进度 + 前置任务 + 回程路径」一键打包，干净地把 B 甩到一个**新对话**去解——避免在当前对话里就地展开 B 引起漂移。

## 与相邻机制的区别

| 机制 | 干什么 | 何时用 |
|------|--------|--------|
| **`/spinoff`（Claude）/ `$spinoff`（Codex，本 skill）** | 前置 B 阻塞 A → 派生 B 到新对话 + 留回程 | B 是**阻塞性前置**且**够大**（值得独立对话）|
| `/todo`（Claude）/ `$todo`（Codex） | 把新问题归档，不打断主线 | B/C **不阻塞** A（附加 / 无关支线），先做完 A 再说 |
| `/snapshot`（Claude）/ `$snapshot`（Codex） | 纯存当前状态 | 只想存档，不派生 |
| `/escalate`（Claude）/ `$escalate`（Codex） | 同一 bug 鬼打墙求外援 | 卡死，不是前置依赖 |

> **先判再用**（与 CLAUDE.md / AGENTS.md 漂移分类一致）：不是所有"还得先做 X"都该 spinoff。**小前置**（几行就能搞定）→ 直接内联做完即回，别为它开新对话。**不阻塞的附加 / 支线** → `/todo`（Claude）/ `$todo`（Codex）。只有"**B 阻塞 A 且 B 本身够一坨**"才 spinoff。

## 执行步骤

### 1. 确认这是「够大的阻塞性前置」（⛔ 硬闸）

> ⛔ **硬契约**：把「要解决 A 得先解决 B，我把 A 存档 + 派生 B 去新对话？」作为 **AskUserQuestion**（选项：spinoff / 小前置内联做完 / 不阻塞先 `/todo` 或 `$todo`）**结束当前回合**；用户未选前**禁止**执行存档或生成种子提示词。判错了（其实是小前置 / 不阻塞）就别 spinoff。

### 2. 存档主任务 A 的状态（复用 snapshot）

```bash
# Claude
.venv/Scripts/python.exe .claude/hooks/session_snapshot.py manual
# Codex
.venv/Scripts/python.exe .codex/hooks/session_snapshot.py manual
```

读回刚写的 `.runtime/session_state/<ts>.md`，**追加**主任务上下文到文件末尾：

```markdown
## 主任务 A（spinoff 暂挂）
- 在做什么：...
- 卡在哪：被前置 B 阻塞
- A 已完成的部分：...
- 解完 B 后从哪一步继续：...

## 派生的前置 B
- B 是什么：...
- 为什么阻塞 A：...
- 派生去向：新对话（见下方种子提示词）
```

### 3. 生成「解 B」的种子提示词（给用户复制到新对话）

输出一段**可直接粘贴**的提示词，**必须含回程双向链**：

```
我需要先解决一个前置问题：<B 的清晰描述 + 已知上下文 / 已排除项>。

【背景】这是主任务「<A 一句话>」的前置阻塞项。A 的状态已存档在
.runtime/session_state/<ts>.md。

【完成后】解决后请提醒我：回到主任务用 /resume（Claude）或 $resume（Codex）读上面那份存档接续 A。
```

### 4. 回复用户操作指引

```
✓ 已 spinoff
  • 主任务 A 存档 → .runtime/session_state/<ts>.md
  • 下一步：开新对话，粘贴上面的种子提示词解 B
  • 解完 B：回来（或新对话）跑 /resume（Claude）或 $resume（Codex）接续 A
```

## 何时主动建议

- `[focus]` 信号触发后，你判定当前是「前置阻塞型」漂移且 B 够大
- 用户聊着 A 突然深入一个"得先搞定"的 B/C/D
- 任何"这事得先解决另一件事"且那件事值得独立对话的场景

## 禁止

- ❌ 对**不阻塞**的附加 / 支线用 spinoff（应 `/todo` / `$todo`）
- ❌ 对**几行就能解**的小前置用 spinoff（直接内联做完即回）
- ❌ 种子提示词漏掉**回程链**（存档路径 + /resume / $resume 指引）——否则解完 B 找不回 A
- ❌ 不确认就自动派生（必须用户点头）
- ❌ 把主观上下文写到 `.runtime/session_state/` 以外的地方
