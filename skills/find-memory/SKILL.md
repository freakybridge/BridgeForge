---
name: find-memory
description: 按关键词和 metadata 递归检索当前 agent 项目的分类 memory 与 delivery topic memory，并按需读取最相关记录；MEMORY.md 热区未命中、用户询问历史决策或实现前需要召回旧经验时使用。
user_invocable: true
argument: 搜索关键词
---

# 按需检索 memory

## 定位与边界

检索当前 agent 的 memory 热区、分类目录与 `topics/`，不修改索引、frontmatter
或原始 memory。Codex 常规会话由 UserPromptSubmit router 先给候选；本 skill 只在
热索引与自动候选不足时做深度检索。当前任务锚或确认卡能唯一确定一个 delivery topic
时，才可额外读取对应 `memory/topics/<exact-slug>/`。`MEMORY.md` 已足够回答时无需
递归检索。

## 输入

从 `$ARGUMENTS` 或当前任务提取 2–4 个核心关键词，优先保留英文技术词和稳定标识符。

## 核心流程

1. 使用 bridgeforge-codex 唯一项目目录 `.codex/`。
2. 主对话先核对热区和 router 候选；若现有索引已足够回答，或当前任务锚/确认卡唯一命中
   一个 topic，可直接读取该 topic
   目录内最相关的 1–2 个文件。存在多个候选或 slug 不确定时禁止猜测，
   先让用户单选。
3. 热区、router 与唯一 topic 仍不足时，才把递归冷区搜索和候选摘要显式分派给
   `light-explorer`，由它运行对应搜索脚本：

   ```bash
   .venv/Scripts/python.exe .codex/scripts/memory_search.py <关键词>
   ```

4. 脚本必须递归覆盖 `memory/**/*.md`，并检索正文及
   `description`、`category`、`topic`、`status`、`kind`、`tags`、
   `related_paths` metadata；列出相关度最高的 5 个相对路径及摘要。
5. 只读取最相关的 1–2 个文件，并用命中内容回答当前问题。
6. 首次无结果时换一组关键词再试；仍无结果则明确说明没有找到记录。

## 输出与验证

输出命中的相对路径、`category` / `topic` / `status`、相关摘要和实际采用的
结论；区分“memory 有记录”和“根据记录推断”。递归搜索覆盖当前 agent memory
目录下全部 `.md`，不只覆盖热区。`completed` / `superseded` topic 仍可检索，
不会因冷却而移动目录。

## 停止条件

- 两组关键词均无结果：停止搜索，说明该知识可能尚未记录。
- 搜索结果互相冲突：呈现冲突及文件来源，不自行合并成确定结论。
- 当前 topic 不唯一：在读取任一 topic 正文前让用户单选。
- 热索引或 router 候选已经足够：直接返回，禁止为了形式完整启动递归搜索 agent。

## 禁止事项

- 禁止逐文件反复 grep memory 目录绕过搜索脚本。
- 禁止因读取冷区文件就声称它会自动升回热区；热区由 `memory_rebuild_index.py` 确定性重建，常驻项需在 frontmatter 标记 `pinned`。
- 禁止一次读取超过 2 个候选文件，除非用户扩大范围。
- 禁止把 `completed` / `superseded` topic 移到 `memory/_archive/`；该目录不属于契约。
