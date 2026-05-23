---
name: todo
description: 对话中冒出的新问题或情报，不打断主线前提下归档到正确位置（默认落 doc/0_architecture/TODO-INDEX.md）。todo 是新问题的开始，summary 是老问题的结束。
user-invocable: true
argument: 问题描述（可带提示词："新问题" / "之前遇过" / "查下 memory" 等）
---

# /todo — 新问题的开始

把对话中冒出的问题/情报归档到正确位置（默认主表 `doc/0_architecture/TODO-INDEX.md`）。和 `/summary`（对话收尾批量总结）互补：/todo 做**零散单条的沉淀**。

## 调用

```
/todo <问题描述>                      # 默认陌生路径
/todo <描述> — 这是新问题             # 强制陌生
/todo <描述> — 之前遇过 / 查下 memory # 触发熟路径
```

**关键词信号**：
- 熟 → "之前"、"遇过"、"讨论过"、"查下"
- 陌生 → "新问题"、"没见过"、"第一次"
- 无提示 → 默认陌生

## 三档行为

### 1. 陌生路径（默认 / 用户说"新问题"）

**先判"短期 vs 远期"**：
- **短期（已识别但暂时没空做的具体问题 / bug / 改进）** → 落 `doc/0_architecture/TODO-INDEX.md` §完整清单 主表
- **远期（功能尚未排到 Milestone，需要先有设计文档展开）** → 落 `doc/1_plan/<模块>/<主题>.md`（不带日期前缀），并在 `TODO-INDEX.md` §远期 Backlog 索引 加一行链接

**短期路径**：
1. 按主题判定分组（参考 TODO-INDEX 现有主题；不匹配就用"其他"）
2. `doc/0_architecture/TODO-INDEX.md` §完整清单 末尾加新行，给新 #（不复用已删除编号）
3. 结束

**远期路径**：
1. 选 / 创建 `doc/1_plan/<模块>/` 目录（模块不存在时新建 + README）
2. 写设计文档 `<主题>.md`（不带日期前缀 = 远期标记）
3. `TODO-INDEX.md` §远期 Backlog 索引 对应分类表加一行（链接 + 关联 Milestone + 备注）
4. 结束

### 2. 熟路径（用户给线索 或 skill 自查命中）
1. 自查：读 `MEMORY.md` 索引 → read 命中的 memory 全文 → 必要时 grep 项目源码
2. 找到方案后按 `rules/workflow.md` §1-§3 更新：
   - 新增 / 更新相关 memory
   - 同步 `MEMORY.md` 索引描述
   - 必要时在源 doc（如 `doc/2_pending/2026-XX-XX_*.md`）加标注
   - 必要时在 `TODO-INDEX.md` 加行（若仍需未来处理）
3. 结束

### 3. 半熟路径（查到相关但无完整方案）
1. 在最相关的 memory 末尾追加段落：`YYYY-MM-DD: <问题描述>，与 X 相关，方案待定`
2. `TODO-INDEX.md` 加一行，"来源"列指向上条 memory（交叉引用）
3. 若 memory 描述有实质变化，同步 `MEMORY.md` 索引
4. 结束

## 自查范围

**默认轻扫**（3-4 个工具调用内）：
- 读 `MEMORY.md` 索引
- grep `doc/2_pending/` 关键词
- 必要时 grep `.claude/rules/`

**深查**（用户明说"熟"或给出明确线索时）：
- 以上 + read 命中的 memory 全文
- grep 项目源码
- 必要时 read 多个文件验证

## 反馈格式

完工输出**分行清单**，每行 = 一个文件改动，用 markdown 链接便于点击：

```
✓ [memory/feedback_xxx.md](.claude/memory/feedback_xxx.md) 追加段落（相关线索）
✓ [TODO-INDEX #42](doc/0_architecture/TODO-INDEX.md) 新增（交叉引用上条）
✓ [MEMORY.md](.claude/memory/MEMORY.md) 索引同步
```

一行不超过 80 字符。

## 禁止

- 展开讨论：完工即止，不追加"要不要再做 X"
- 修改代码：只动文档、memory、TODO；代码问题只**记录**不**修**
- 嗅觉触发：用户的"btw"/"顺便"**不**触发 /todo（避免和日常语气冲突）
- 静默删除：已有 TODO / memory 条目**不得**删除或覆盖，只能追加或新增
- 跳过索引同步：参考 `rules/workflow.md` §5

## 使用约束

- skill 完工后**不会自动回到主任务**。若 /todo 前有进行中的主任务，用户需明说"继续 X"才恢复。
- 想"真不打断"的场景建议**另开对话框**调用 /todo，主对话框保持原任务 context。

$ARGUMENTS
