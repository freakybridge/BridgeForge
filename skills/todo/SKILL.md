---
name: todo
description: 归档对话中新出现的问题、情报或待办，不打断当前主线；用户调用 /todo、$todo，或明确要求记录新问题、历史线索、待查事项时使用。
user_invocable: true
argument: 问题描述（可注明“新问题”“之前遇过”“查下 memory”等线索）
model: haiku
---

# todo — 归档新问题

## 定位与边界

把单条问题沉淀到项目文档或 memory。默认只记录，不修代码；`todo` 负责新问题，`summary` 负责对话收尾。

## 输入

- `$ARGUMENTS`：问题描述及可选线索。
- “之前 / 遇过 / 讨论过 / 查下”表示熟路径。
- “新问题 / 没见过 / 第一次”表示陌生路径；无提示时也按陌生路径处理。

## 核心流程

1. 判断陌生、熟或半熟路径。
2. 陌生路径先按类型归档：
   - Bug：新建 `doc/2_bugs/BUG-<id>-<topic>.md`，只记录现象、影响、线索与待验证项。
   - 已确认需求的附加事项：追加至该 delivery topic 的 `README.md` 或 `plan.md`。
   - 尚未确认的新需求：停止并建议进入 `confirm`，禁止凭空建立 delivery 包。
3. 熟路径把 related-record lookup 显式分派给 `light-explorer`，在 3-4 次只读调用内轻扫 `MEMORY.md`、`doc/1_delivery/`、`doc/2_bugs/` 和当前 agent rules；用户给出明确历史线索时，再读命中 memory、源码及必要文档。
4. 主 agent 根据只读收据分类并写入。找到完整方案时，按项目 `rules/workflow.md` 更新相关 memory、`MEMORY.md` 索引、必要的源文档和 TODO。
5. 只找到相关线索时，在最相关 memory 末尾追加 `YYYY-MM-DD: <问题描述>，与 X 相关，方案待定`，同时新增 TODO 交叉引用；描述发生实质变化时同步索引。

## 输出与收据

按文件逐行输出可点击链接和动作，每行不超过 80 字，例如：

```text
✓ [memory/feedback_xxx.md](<agent-dir>/memory/feedback_xxx.md) 追加相关线索
✓ [BUG-042](doc/2_bugs/BUG-042_<topic>.md) 新增待处理记录
✓ [MEMORY.md](<agent-dir>/memory/MEMORY.md) 同步索引
```

## 停止条件

- 完成归档后立即停止，不自动恢复先前主任务；需要继续时由用户明确指示。
- 找不到可靠归档位置或写入会覆盖既有语义时，报告候选位置并等待用户决定。

## 禁止事项

- 禁止修改代码；代码问题只能记录。
- 禁止删除或覆盖既有 TODO / memory 条目，只能追加或新增。
- 禁止跳过 `MEMORY.md` 或项目文档索引同步。
- 禁止把“btw / 顺便”等日常语气当作自动触发信号。
- 禁止完成后追加扩展任务或“要不要再做”式追问。

$ARGUMENTS
