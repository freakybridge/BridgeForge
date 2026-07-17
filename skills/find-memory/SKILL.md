---
name: find-memory
description: 按关键词检索当前 agent 项目的完整 memory 目录，并按需读取最相关记录；MEMORY.md 热区未命中、用户询问历史决策或实现前需要召回旧经验时使用。
user_invocable: true
argument: 搜索关键词
model: sonnet
---

# 按需检索 memory

## 定位与边界

检索当前 agent 的 memory 热区与冷区，不修改索引或原始 memory。`MEMORY.md` 已足够回答时无需调用。

## 输入

从 `$ARGUMENTS` 或当前任务提取 2–4 个核心关键词，优先保留英文技术词和稳定标识符。

## 核心流程

1. 判断当前 agent 目录：Claude 使用 `.claude/`，Codex 使用 `.codex/`。
2. 运行对应搜索脚本：

   ```bash
   # Claude
   python .claude/scripts/memory_search.py <关键词>
   # Codex
   python .codex/scripts/memory_search.py <关键词>
   ```

3. 列出相关度最高的 5 个文件名及 description 摘要。
4. 只读取最相关的 1–2 个文件，并用命中内容回答当前问题。
5. 首次无结果时换一组关键词再试；仍无结果则明确说明没有找到记录。

## 输出与验证

输出命中的文件、相关摘要和实际采用的结论；区分“memory 有记录”和“根据记录推断”。搜索覆盖当前 agent memory 目录下全部 `.md`，不只覆盖热区。

## 停止条件

- 两组关键词均无结果：停止搜索，说明该知识可能尚未记录。
- 搜索结果互相冲突：呈现冲突及文件来源，不自行合并成确定结论。

## 禁止事项

- 禁止逐文件反复 grep memory 目录绕过搜索脚本。
- 禁止因读取冷区文件就声称它会自动升回热区；热区由 `memory_rebuild_index.py` 确定性重建，常驻项需在 frontmatter 标记 `pinned`。
- 禁止一次读取超过 2 个候选文件，除非用户扩大范围。
