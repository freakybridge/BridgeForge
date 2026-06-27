---
name: tool-result-corruption-triggers
description: 工具传结果线腐蚀的两类触发器：shell for+pipe 批处理大输出 + AskUserQuestion 大段中文参数；区别于 hook 编码腐蚀（utf8-garble）
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5c24cf4c-21d5-4ad4-8692-9e7b9b3e767d
---

## 机制

**这不是文件损坏，是"结果传递层"抽风**。磁盘/工作树全程完好；只有工具把结果返回给 agent 时的这一段会出问题。

与 [[utf8-garble-rootcause]] 的区别：
- utf8-garble = hook stdout 在 GBK Windows 读成乱码，注入 context
- 工具传结果线腐蚀 = 工具调用返回结果本身被截断/幻影/结构损坏

## 已知触发条件

**① 自拼 shell 批处理大输出**：`for` 循环 + 管道 / 多命令 `;` 串，产出大量文本一次性通过工具结果通道 → 同段重影、命中 0 假空、幻影文件名、结构截断。

**② AskUserQuestion 大段中文参数**：选项/入参含长中文字符串 → JSON 序列化成 `\uXXXX` 超长转义串 → `__unparsedToolInput` 解析失败。

## 防护（已入 templates/CLAUDE.md §2.5）

- 检索/大输出拆成受控 Grep / Glob 单命令
- AskUserQuestion 选项保持短、纯文本
- 工具返回出现重影/0命中/不认识文件名/`__unparsedToolInput` → 先 `wc -c`/`git status`/受控 Grep 二次验真，**禁止**直接拍板

## 教训：dry-run ≠ 已改

会话 e1a00860 腐蚀样本：工具报"81 处已改"，bash 验证 = 0 处实际写盘。**dry-run 报的 N 处不等于已改 N 处**。任何靠 dry-run 输出数字做的决策都是在沙堆上盖楼。

## 脏会话审计恢复模式（2026-06-27 补）

若怀疑整个会话工具传结果线抽风（工具回执/统计值/哈希可能伪造），正确姿势：

1. **新起会话**，不继承任何旧会话结论
2. **真相源只认两类**：① Read 工具逐字读全文（不信任何"已验证/统计值/哈希"摘要）；② `git status + git diff`（不经工具传结果线，直接看磁盘变更）
3. **验收顺序**：先确认文件实际内容，再比对预期；哈希相等只证明两者相同，不证明内容正确——必须先确认母版内容
4. **独立 agent 对抗审计**：对同一份文件再起一个不带预判的 reviewer，防止主 agent 被旧结论锚定

实例：v0.35.0 审计，audit_handoff 文档主动交代"原会话曾被伪造成功回执骗过"，新会话重读 4 个 skill 文件 + VERSION + CHANGELOG 全文，git diff 确认工作区实况，发现版本号撞车（0.34.0 已被无关工作占用）。

**Why to apply**：凡历史会话怀疑抽风，不要在旧结论上继续推理，用新会话 + 以上两类真相源重建。
