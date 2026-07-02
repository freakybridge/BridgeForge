---
description: 扫描 doc/2_pending/ 下可归档的完成文档，列出候选让用户 review，确认后批量 git mv 到 doc/4_archive/ 并同步 doc/README.md 索引。
model: haiku
---

# /archive-scan — 扫描 doc/2_pending/ 可归档候选

**定位**：半自动归档。脚本只负责打分找候选，**移动与否由用户拍板**——防止误归档活跃文档。

> **路径说明**（2026-05-08 后）：TODO-INDEX 已迁至 `doc/0_architecture/TODO-INDEX.md`，扫描时它**不**作为归档候选（脚本已硬编码排除）。被扫描的目录仍是 `doc/2_pending/`。

## 执行步骤

### Step 1：跑扫描脚本

```bash
.venv/Scripts/python.exe .claude/scripts/archive_scan.py --json
```

脚本输出 JSON 数组，每个候选带：`file` / `score` / `reasons` / `refs_in_todo` / `last_modified_days`。

### Step 2：呈现候选清单给用户

格式化成易读表格：

```
## doc/2_pending/ 归档候选（N 个）

| 文件 | score | 理由 | TODO 引用 | 最后修改 |
|------|-------|------|----------|---------|
| xxx.md | 5 | 含'已完成' + TODO 未引用 | 0 | 12 天前 |
```

> ⛔ **硬契约**：呈现清单后必须用 **AskUserQuestion**（multiSelect 列出候选 + 「都不移」+「再看看某个」选项）**结束当前回合**；用户未选前**禁止**执行任何 `git mv`——禁止同一回合里"列完清单就动手"。用户可选：
- "全部归档" → 全移
- "只移 #1 #3" → 选择性移
- "都不移" → 退出
- "再看看 xxx.md" → 你 Read 那个文件给用户看内容，再问（再问仍走 AskUserQuestion）

### Step 3：执行归档（按用户选择）

对每个批准的文件：

```bash
git mv doc/2_pending/<file> doc/4_archive/<file>
```

### Step 4：同步 doc/README.md

1. 从 `current/` 表格删除对应行
2. 加到 `archive/` 表格（按时间倒序插入）
3. 简要说明加到末尾的"最近归档批次"注释（可选）

### Step 5：回报用户

```
✓ 归档 N 个文件：
  - xxx.md → doc/4_archive/
  - yyy.md → doc/4_archive/
✓ doc/README.md 已同步
```

## 常见判断

**推翻脚本、建议保留（keep 信号）**：① 含"已完成"但只是某子任务完成、整体还活着；② 验收清单 / 里程碑类，用户想长期留参考；③ 仍被别处引用（先 `grep doc/` 交叉确认再决定）。命中则向用户说明理由建议保留。

**主动建议归档（archive 信号，即使脚本没建议）**：① 用户明说"xxx 做完了"；② 某 TODO 完成删除后，其唯一"来源"文档成孤立。

## 禁止

- ❌ 不经用户确认就 `git mv`
- ❌ 移动后不更新 `doc/README.md`
- ❌ 批量改动前不先 `git status` 确认干净（防止混入别的 uncommitted 改动）

## 与 `/todo` / `/summary` 的区别

| skill | 动作 |
|-------|------|
| `/todo` | 往 `doc/0_architecture/TODO-INDEX.md` 加新条目或关联现有 memory |
| `/summary` | 从对话抽决策写入 `memory/` |
| **`/archive-scan`** | **扫 `doc/2_pending/` 找已完成文档，移到 `archive/`** |