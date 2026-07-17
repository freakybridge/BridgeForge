---
name: spinoff
description: 当主任务被一个足够大的前置问题阻塞时，存档主任务、生成新对话种子提示并保留回程链；用户调用 /spinoff、$spinoff，或推进 A 必须先独立解决 B 时使用。
user_invocable: true
argument: 前置阻塞问题描述
model: sonnet
---

# spinoff — 派生前置任务

## 定位与边界

把“大且阻塞主任务”的前置问题拆到新对话，并确保解决后能通过 `resume` 回到主任务。不阻塞的支线用 `todo`；几行可解决的小前置直接内联；同一问题反复失败用 `escalate`。

## 输入

- 主任务 A 的目标、已完成部分和下一步。
- 前置问题 B 的已知事实、已排除项及其阻塞原因。
- `$ARGUMENTS`：前置问题描述。

## 核心流程

### 1. 分类确认硬闸

只问一题：是否把 A 存档并将 B 派生到新对话，还是把 B 当小前置内联完成，或当不阻塞支线交给 `todo`。当前回合在该题结束；用户未选 spinoff 前禁止存档或生成种子。

### 2. 存档主任务

运行当前 agent 的 snapshot 脚本：

```text
Claude: .venv/Scripts/python.exe .claude/hooks/session_snapshot.py manual
Codex:  .venv/Scripts/python.exe .codex/hooks/session_snapshot.py manual
```

读回新建的 `.runtime/session_state/<ts>.md`，在末尾追加：

- 主任务 A 在做什么、被什么阻塞、已完成部分、解决 B 后从哪步继续。
- 前置 B 是什么、为何阻塞 A、派生到新对话的事实。

### 3. 生成新对话种子

输出可直接粘贴的提示词，必须包含：

- B 的清晰描述、已知上下文和已排除项。
- A 的一句话背景及 snapshot 路径。
- 完成 B 后使用 `/resume` 或 `$resume` 读取同一存档并接续 A 的回程指引。

### 4. 交付操作指引

列出 snapshot 路径、新对话动作和完成 B 后的 resume 命令。

## 输出与收据

- `.runtime/session_state/<ts>.md` 的实际路径。
- 追加的 A / B 状态摘要。
- 可复制的新对话种子提示词和双向回链。

## 停止条件

- 用户未确认 spinoff 时停止，不产生 snapshot 或种子提示。
- snapshot 创建或读回失败时停止，不输出虚假路径。
- 无法说明 B 如何阻塞 A 时，退回分类确认。

## 禁止事项

- 禁止对不阻塞支线或小前置使用 spinoff。
- 禁止漏掉 snapshot 路径、`resume` 指引或解完 B 后继续 A 的步骤。
- 禁止未确认就自动派生。
- 禁止把主观交接上下文写到 `.runtime/session_state/` 以外的位置。

$ARGUMENTS
