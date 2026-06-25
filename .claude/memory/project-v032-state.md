---
name: project-v032-state
description: v0.32.0 反漂移红线补强：4条文本红线进 templates/CLAUDE.md，16-agent debate 定案，focus 结构盲点指针进 design-rationale
metadata: 
  node_type: memory
  type: project
  originSessionId: 5c24cf4c-21d5-4ad4-8692-9e7b9b3e767d
---

## v0.32.0（2026-06-25）

### 背景：会话 e1a00860 跑偏调查

调查 live 会话"现在仓库可以公开了吗？" 如何从评估问题漂移成全量脱敏执行。

**跑偏双因机制**（两个独立问题，互为放大器）：
- **根因 A — scope drift**：A4 轮（ctx≈45k）agent 答完评估后立即发 AskUserQuestion 执行菜单，用户点击 = 授权执行。clarify hook 是共谋（鼓励 agent 询问），focus hook v0.28.2 起中立化（设计上不干预新任务）。
- **根因 B — 工具传结果线腐蚀**：shell for+pipe 批处理大输出 + AskUserQuestion 大段中文参数 → `\u` 转义爆炸 → `__unparsedToolInput`，把脏数据注入判断层。

**重要验证**：交接文件称"脱敏成功 13 文件 81 处"——bash 验证为 **FALSE**。git status 干净，StratusAgent 全部存在。所有操作是 dry-run；任何以该数据为依据的判断均无效。

### 16-agent Debate 定案（三问一致）

三个问题（工具腐蚀防护 / 评估推送约束 / focus 结构盲点）全部一致结论：**零新 hook，只改文本**。理由：medium baseline 已处理 high-effort 冲动 → hook 加固边际 ROI 为负（产品层传播+dogfood 成本 > 收益）。

### 改动一览

| 文件 | 改动 | 层 |
|---|---|---|
| `templates/CLAUDE.md` §2.5 | +2 bullet：禁止自拼 shell 批处理 + 脏数据上不拍板红线 | product |
| `templates/CLAUDE.md` §9.5 | 收窄第1分支 + 新增评估类问收口约束 + AskUserQuestion 文案约束 | product |
| `docs/design-rationale.md` §7 | focus 结构盲点指针（为何不改 focus）| meta |

**focus 不改的三层理由**：UserPromptSubmit 只读 stdin；范围升级发生在"点选项"那轮，不在"打字"那轮；纯字符串 anchor_kind 门控会误分类"公开"；重新加固 = 重蹈 v0.28.2 错误。三层兜底：medium baseline + §9.5 红线 + /focus 被动入口。

### 版本

- `VERSION`：0.30.0（+ effort 批 0.31.0）→ **0.32.0**
- `templates/VERSION`：0.3.0（+ effort 批 0.4.0）→ **0.5.0**
- 提交：`e3a7628`（两批被另一对话框合并为单 commit，已推送，内容正确）

### 遗留

- `.runtime/spinoff/` 未跟踪（CHANGELOG 指针悬空，仅本地存档），无 git 风险
- 分批提交未完成（另一对话框先 push，force-rewrite 代价 > 收益，用户未要求）
- [[ghost-wall-threshold-conflict]] 阈值冲突仍未解决

关联 [[utf8-garble-rootcause]]（不同机制：hook 编码 vs 工具传结果线腐蚀）[[project-v031-state]]（同批推送）
