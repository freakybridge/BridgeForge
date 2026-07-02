---
name: feedback-hook-input-channel-bugclass
description: 修一个 hook 的 stdin/env-var 输入通道 bug 后要主动排查所有结构同胞，不能只信任单点 CHANGELOG 记录已解决
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 75ba2145-0b1a-452f-bdbb-f4c88670577c
---

**事故**：`requirements_check.py` 曾因只读 legacy 环境变量 `CLAUDE_TOOL_INPUT`（当前 Claude Code 仅走 stdin 时永不触发）被修复为 stdin-first + env fallback 双通道，CHANGELOG 记了这条修复。但 v0.40.0 全仓库审计发现同一 bug 原样存在于 4 个结构同胞：`find_doc_reminder.py`/`memory_lint.py` 完全没有 stdin 分支（100% 死），`rule_index_check.py`/`rule_size_check.py` 的 PostToolUse 软提醒路径同病（有 pre-commit 硬闸兜底才没酿成大祸）。这些 hook 挂在 settings.json 里、pre-commit 也跑得通，表面看不出任何异常——**静默失效不产生任何错误信号**，只有系统性审计才能揪出来。

**根因**：单点修复只解决了「这一个 hook 的这一次故障」，没有触发"同类结构的其他文件是否也这样写"的横向排查。CHANGELOG 记了"已修"，容易让人误以为这类 bug 已经根除。

**How to apply**：
1. 发现一个 hook 有输入解析类 bug（stdin/env-var、路径解析、编码等"样板代码"层面的问题）时，**同时 grep 全部同类 hook 找同一段样板代码**，别只改报错的那一个。
2. CHANGELOG 记"已修复 X"时，若该 bug 是样板代码层面的（不是业务逻辑特有），额外记一句"已排查同类 N 个文件"或明确留一条 TODO 排查——不要让"已修复"的措辞掩盖"只修了举报的那个"的事实。
3. 静默失效类 hook bug 无法靠正常使用发现（不报错、不崩溃，只是不触发），常规做法是定期做一次全量审计（本例：4 agent 并行分维度扫描）。

[[project-v040-state]]
