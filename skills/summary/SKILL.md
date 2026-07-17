---
name: summary
description: 总结当前对话的关键决策、经验、完成项与遗留问题，并按价值写入 memory、rules 或 docs；用户调用 /summary、$summary 或要求沉淀本轮成果时使用。
user_invocable: true
argument: 可选的本次总结重点提示
model: sonnet
---

# summary — 沉淀对话成果

## 定位与边界

只保留值得跨对话复用的内容，并同步对应索引。低频的 rule-memory 对账与已解决事项清理按需读取 [`references/deep-steps.md`](references/deep-steps.md)，不要预加载整份参考。

## 输入

- 当前对话中的架构决策及原因、已验证根因、已完成事项和遗留问题。
- `$ARGUMENTS`：用户指定的总结重点。
- 当前 agent 的 memory、rules、文档索引和 Git 实际状态。

## 核心流程

1. 回顾本轮，区分已确认事实、推断、已完成和未验证项。
2. 写入当前 agent memory：架构归 `project`，踩坑归 `feedback`，外部资料归 `reference`；先查重，再新建或更新，并同步 `MEMORY.md`。
3. 检查 rules：只有“必须 / 禁止”的稳定红线才进入 rule；案例进入 memory，长示例进入 doc。与既有约束重叠时合并，保持单一正文和窄 `paths` 触发。
4. 若本轮修改了 rule，只读取 `references/deep-steps.md` 的“对账”节执行局部 memory 对账。删除候选必须用单题选择式用户确认结束当前回合；未确认前禁止删除。
5. 按项目 `rules/workflow.md` 的同步映射更新相关设计文档；需要独立流程时调用 `sync-docs`。
6. 仅当代码已合并且用户明确确认解决时，读取参考文件的“清理”节列出 TODO / pending 文档候选。必须以用户确认结束当前回合；未确认前禁止删条目或归档。
7. 发现跨项目也成立的经验时，先向用户确认，再把一行候选追加到当前 agent 的 `harvest-inbox.md`；这里只捕捉，不反哺上游。

## 输出与收据

列出：

- 新增或更新的 memory 类型、路径和一句话内容。
- 修改的 rules、同步的 docs 与索引。
- 经用户确认后清理的 memory / TODO / pending 文档。
- 写入的 harvest 候选。
- 尚未验证或留待处理的问题。

## 停止条件

- 发现任何删除候选时，呈现候选并等待用户选择，当前回合立即结束。
- 没有满足“已合并 + 用户确认”的清理项时跳过清理，不凑数。
- 缺少写入依据或真实状态无法核验时，标为未验证并停止对应写入。

## 禁止事项

- 禁止把推断写成已确认事实。
- 禁止因内容上升为 rule 就机械删除支撑它的 memory。
- 禁止未确认删除 memory、TODO 或 pending 文档；归档必须使用 `git mv`。
- 禁止重复写入同一规则、案例或索引条目。

$ARGUMENTS
