---
name: feedback-bash-cwd-persistence
description: Bash 工具的 cwd 在会话内持久——cd 进子目录后所有后续调用都从那里执行，导致相对路径 hook 全部失效
metadata:
  node_type: memory
  type: feedback
  originSessionId: b229b107-36d0-4ca6-8979-9ef64f2d7699
---

**事故（2026-06-27）**：操作 `.claude/memory/` 目录时，一条 `cd .claude/memory` Bash 命令把 cwd 锁进了子目录。后续所有 Bash 调用（包括 `pwd`）都从那里执行，PreToolUse hook 用相对路径 `.claude/hooks/xxx.py` 全部解析失败，报 "can't open file ... memory/.claude/hooks/..."。连 `cd d:/Quant/BridgeForge` 也被 hook 拦截，无法自救。

**根因**：Bash 工具的工作目录**在同一 shell session 内持久**，`cd` 一旦执行就改变后续所有调用的 cwd。Hook 用相对路径 → cwd 偏就炸。

**解法**：PowerShell 工具有独立 cwd（不与 Bash 共享），通过 PowerShell 的 `Set-Location <项目根>` 把共享 cwd 拉回来，Bash 随之恢复。

**How to apply（预防）**：
- 操作子目录时**永远用绝对路径**，禁止 `cd` 进去。例：`ls .claude/memory/` 而非 `cd .claude/memory && ls`。
- 必须 `cd` 时（极少数情况）紧接着再 `cd <项目根>` 归位，别隔命令。
- 发现 Bash 突然全部被 hook 拦截且报路径错乱 → 第一反应是 cwd 跑偏，用 PowerShell `Set-Location` 归位。

[[feedback-glob-search-gotchas]]