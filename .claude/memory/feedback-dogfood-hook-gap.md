---
name: feedback-dogfood-hook-gap
description: 改 templates/hooks 时漏了同步 .claude/hooks 的事故模式及已有修复
metadata:
  node_type: memory
  type: feedback
  originSessionId: f7e75bfc-a44e-46b9-b1db-f78d0947b7b9
---

**v0.19.0 暴露的事故**：新增 `allow_memory_write.py` 和 `target_cleanup.py` 进入 `templates/hooks/`，但 `.claude/hooks/` 没有同步——用户 review PR 时发现。

**根因**：「传播三问」只问"通用改进写进 templates 了吗"，没有反向一问"自己也装上了吗"。

**修复**：传播三问升级为四问（CLAUDE.md §1），第 4 问专门卡 dogfood 镜像。

**How to apply**：每次在 `templates/hooks/` 或 `templates/settings.json` 落产品层 hook 改动时，当场 cp + 注册进 `.claude/`，不能等到下次 review 才补。`.claude/settings.json` hook 命令前缀用系统 `python`（dev 仓库无 .venv），templates 版用 `.venv/Scripts/python.exe`。

[[project-target-cleanup-design]]