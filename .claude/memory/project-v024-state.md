---
name: project-v024-state
description: setup_agent v0.24.0 主要变更摘要（2026-06-09）
metadata: 
  node_type: memory
  type: project
  originSessionId: 0e54f5a5-13d9-45e9-bdcf-67d584475678
---

## v0.24.0 发版内容（2026-06-09）

### 产品层改动（[product]）
1. **`context_warning.py` 升级**：弃用 char/4 文件大小估算，改从 transcript JSONL 末尾倒查最近一条 assistant 消息的 `usage` 字段（input + cache_creation + cache_read + output），与 `/context` 一致，精确到个位 token。缺 usage 字段时 fallback char/4。两份（templates/ + dogfood .claude/）字节一致。
2. **`WINDOW` 默认值 200k → 1_000_000**（反转 v0.23.2）：Claude Code 无法在 hook 里探测 `[1m]` 后缀，默认 1M 让主力 Opus-1M 用户开局即准。标准 200k 模型**必须手动改回** `200_000`，否则分母过大永不预警。
3. **find-doc / sync-docs 字典外置**：`topic→rule` 字典和源码→文档映射从 skill 本体 placeholder 改为读项目本地 `.claude/find-doc.map.md` / `.claude/sync-docs.map.md`。
4. **`SKILL.md` Step 0.5（新增）**：清理项目 `.claude/skills/` 里的通用 skill 重复副本（单一源在用户级 `~/.claude/skills/`）。DUP-IDENTICAL → 直接删；含项目专属数据 → 先迁 `.map.md` 再删；含用户定制 → 问用户。
5. **`memory_guard.py` + `prune-memory` 废弃**：memory_rebuild Stop hook 自动评分（封顶活跃 40 条 + >45 天冷区化）已把 MEMORY.md 自动控制在 ~45 条，手动治理成冗余，整套退役。
6. **`templates/rules/portability.md §2`**：补记"通用 skill 本体不进项目 git，靠 `/setup_agent` 装用户级；`.map.md` 进项目 git"的单一源拆分约定。

### repo 改动（[repo]）
- `.gitignore` 补 `__pycache__/` `*.pyc`（之前缺失，Python hook dogfood 时会自动生成字节码）

### 本次 review 发现的小修补（meta）
- `SKILL.md:334`：WINDOW 指引"Opus 4.7 / Sonnet 4.6 1M context → 1M"过时且误导，已对齐 hook 头部注释（标准 200k 模型必须手动下调）
- `SKILL.md:170`：Step 0.5 交叉引用"格式见各自 skill Step 2/4"笔误，已改为"find-doc Step 4 / sync-docs Step 7"

**Why:** 跨会话能快速知道这批改动的动因和已完成状态，避免重复 review 或回滚。
**How to apply:** 下次遇到 WINDOW 或 map 外置相关问题时，先查本条定位上下文。
