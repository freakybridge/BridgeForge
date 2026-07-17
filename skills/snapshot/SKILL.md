---
name: snapshot
description: 将当前 session 的客观状态和短交接摘要保存到 .runtime/session_state/；任务暂停、即将换会话、完成重要子任务或长对话需要低 token 接续时使用。
user_invocable: true
argument: 可选——本次 snapshot 的补充说明
model: sonnet
---

# 保存短交接 snapshot

## 定位与边界

保存可在新会话中直接接续的短期状态，不写长期 memory。自动 hook 保存客观状态；本 skill 补充 agent 掌握的关键决定和下一步。

## 输入

使用当前会话状态，并把 `$ARGUMENTS` 作为补充说明。交接卡总长度目标不超过约 1,200 tokens。

## 核心流程

1. 运行当前 agent 的快照脚本：

   ```bash
   # Claude
   .venv/Scripts/python.exe .claude/hooks/session_snapshot.py manual
   # Codex
   .venv/Scripts/python.exe .codex/hooks/session_snapshot.py manual
   ```

2. 定位并读取刚生成的 `.runtime/session_state/<ts>.md`，确认路径和脚本写入的客观状态。
3. 在同一文件末尾追加以下短交接内容：

   ```markdown
   ## 交接摘要（agent 填）
   ### 已完成
   - <关键结果，最多 5 条>
   ### 关键决定 / 当前假设
   - <只写会影响后续工作的内容，并标出未验证项>
   ### 改动文件
   - <路径 + 一句话状态>
   ### 下一步
   - <按顺序列出可直接执行的动作>
   ```

4. 压缩重复背景；若接近预算，优先保留未验证风险、改动文件和下一步。
5. 重新读取文件，确认交接段已落盘且内容可独立理解。

## 输出与验证

回复：`✓ snapshot → <相对路径>`，并报告已完成项、未验证项和下一步的数量。若无法确认文件写入成功，必须标记失败。

## 停止条件

- 脚本失败或无法确定最新文件：停止追加，回报命令和错误。
- 快照中的 Git/文件状态明显异常：保留客观收据并标为未验证，不猜测修正。

## 禁止事项

- 禁止复制历史对话、完整日志、完整 diff、测试长输出或大段代码。
- 禁止调用 `summary` 代替 snapshot，或把短期状态写入长期 memory。
- 禁止删除旧 snapshot；数量上限由脚本管理。
- 禁止只在聊天中给摘要而不落盘。
