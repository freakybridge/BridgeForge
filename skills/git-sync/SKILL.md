---
name: git-sync
description: 全自动 Git 提交并推送到 GitHub。分析变更、生成中文消息并执行同步。与 /git-sync 斜杠命令配合使用时，所有命令行操作默认允许自动运行。
---

# Git Sync Skill (全自动)

此 Skill 实现代码无缝同步流程。

## 自动化指令

1. **远端状态探测**：先 `git fetch origin`，再用 `git rev-list --left-right --count HEAD...@{u}` 读取 ahead/behind。
2. **根据状态分支处理**：
   - **up-to-date（0/0）+ 无本地变更** → 报告"已同步"后退出，不产生空提交。
   - **仅 behind（0/N）** → 若工作区干净，自动 `git pull --ff-only` 拉取最新进度；若有未提交变更，先 `git stash push -u`，pull 后 `git stash pop`。
   - **仅 ahead（M/0）或本地有未提交变更** → 走原有提交流程（第 3~5 步）。
   - **diverged（M/N，双向都有提交）** → **停下来报告本地/远端提交摘要，询问用户选择 rebase / merge / 放弃**，不要自动决定。
3. **暂存变更**：若有本地改动，`git add .` 暂存所有更改。
4. **智能消息生成**：
   - 使用 `git diff --cached` 分析代码变更。
   - 生成一段简洁的**简体中文**消息。
   - 格式：`<类型>: <描述>`
   - 类型包括：`feat`（新功能）、`fix`（缺陷）、`refactor`（重构）、`perf`（性能）、`docs`（文档）、`chore`（杂务）。
5. **提交并推送**：`git commit` → `git push`。
6. **静默操作**：在配合 `/git-sync` 工作流使用时，直接执行相关命令，不主动请求用户单步确认（除非发生严重错误如冲突或 diverged）。

## 异常处理

- **diverged**：不自动 rebase/merge，必须让用户做决定。
- **`git pull --ff-only` 失败**（远端强推等情况）：停止并报告，不做 `reset --hard` 之类的破坏性恢复。
- **`git stash pop` 冲突**：保留 stash，提示用户手动解决，不要丢弃。
- **`git push` 失败**（push 前未探测到 behind 的竞态）：重跑第 1 步重新判定，不强推。
- 检测并报告预提交钩子（pre-commit hooks）失败。
- 只有在无法自动推断或执行时才中断流程询问用户。

## 适用场景

- 功能完成后一键同步代码
- 快速修复后自动推送
- 开发文档或配置更新后同步
