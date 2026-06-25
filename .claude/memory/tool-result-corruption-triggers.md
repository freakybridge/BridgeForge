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

**Why to apply**：凡多命令串/大中文出参的 shell，先做单步验真再下结论。
