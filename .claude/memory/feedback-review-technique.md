---
name: feedback-review-technique
description: setup_agent review 时的两条操作红线（并行编辑 + hook 删除安全检查）
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0e54f5a5-13d9-45e9-bdcf-67d584475678
---

## 做 code review 时用户可能同时在编辑文件

review 期间用户往往**并行改文件**。会话开始时的 git status 快照≠review 结束时的真实状态。

**How to apply:** review 收尾前**必须重拉一次 `git status`**，把新冒出来的改动也纳入检查，不能只靠对话开始时的快照。本次 review 中途就冒出了 `VERSION` / `docs/memory-scoring-design.md` / `memory_guard.py` 删除等改动。

## 删除 hook 时：grep 当前文件状态，不能只看 git diff

删 hook 后用 `git diff` 查悬空引用有盲区：
- `settings.json` 可能只有 CRLF/LF 变化 → `git diff` 显示空 → 实际内容可能还在
- diff 只显示"变了什么"，不显示"现在长什么样"

**How to apply:** 删 hook 后一律 `grep -rn "hook_name" settings.json` 查**当前文件实际内容**，不依赖 diff 为空就判断"已摘除"。本次 memory_guard 删除就是先 grep 才确认了 settings 已清干净。

**Why:** [[project-v024-state]]
