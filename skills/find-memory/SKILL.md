---
name: find-memory
description: 按关键词搜索 .claude/memory/ 下所有文件，按需召回热区未覆盖的 memory。当 MEMORY.md 找不到所需知识时使用。
user-invocable: true
model: sonnet
---

# /find-memory — 按需搜索 memory 冷区

## 触发时机

- MEMORY.md 热区没有相关条目，但感觉历史上有过决策/踩坑记录
- 用户问"有没有关于 X 的记录"
- 需要在开始实现前先确认是否有历史经验

## 执行步骤

### Step 1：提取关键词
从用户查询或当前上下文提取 2-4 个核心关键词（英文技术词优先）。

### Step 2：搜索
```bash
python .claude/scripts/memory_search.py <关键词>
```

### Step 3：展示结果
列出前5个匹配文件名 + description 摘要。

### Step 4：按需读取
用 Read 工具读最相关的 1-2 个文件。

> 读取后 `memory_access_tracker.py`（PostToolUse hook）自动记录本次访问。
> 下次 Stop 时 `memory_rebuild_index.py` 重建 MEMORY.md，该文件可能升回热区。

## 注意

- 搜索覆盖 `.claude/memory/` 下所有 `.md`（含热区和冷区），不只是 MEMORY_COLD.md
- 结果全无相关 → 换关键词再试，或确认该知识尚未记录过
- 禁止自己反复 grep `.claude/memory/` 逐文件翻找——直接调本 skill，省 5-10× token

$ARGUMENTS