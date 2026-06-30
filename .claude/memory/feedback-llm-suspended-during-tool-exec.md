---
name: feedback-llm-suspended-during-tool-exec
description: LLM 在 Claude Code 工具执行期间被 SUSPENDED——PostToolUse 才是最早干预窗口，而非「边等边想」
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5b768036-43aa-43eb-97a9-ca6f8fa62a01
---

## 事故模式

我错误声称「C2 工具超时时，agent 在 8 分钟卡顿期间会决定绕道」，据此认为 PostToolUse 注入太晚、C2 无价值。

## 正确执行模型

Claude Code 的 LLM 在工具执行期间完全挂起（**SUSPENDED**）——无法在工具运行时发起任何推理或决策。Agent 的「要不要绕道」决定，发生在 PostToolUse 执行完、**下一轮 LLM token 生成开始时**。

可用的注入窗口只有两个：
- **PreToolUse**（工具开始前）
- **PostToolUse**（工具完成后）

工具执行中间没有可插入的窗口。

## 对 C2 裁决的影响

C2 软超时方案的真正缺陷：
1. **硬超时时 PostToolUse 根本不触发**（hook 自身也被挂起，永远等不到）
2. PostToolUse 对软超时成立（慢但完成的操作是可以捕获的）
3. C3 文字红线已覆盖软超时后 agent 该做什么——C2 与 C3 重叠

「LLM 注入来不及」**不是** C2 不入产品层的理由；「硬超时 PostToolUse 不触发」才是。

## Why

把「网络请求 timeout 时客户端可以做别的」的并发心智模型套到了 Claude Code 上，错误地假设 LLM 可以边等边想。Claude Code 是单线程令牌流：一次只做一件事，工具执行期间 token 生成暂停。

## How to apply

讨论「超时时 agent 行为」时，先分类：
- 软超时（工具慢但完成）→ PostToolUse 可捕获；
- 硬超时（工具卡死/挂起）→ PostToolUse 不触发，只能靠 C3 文字约束 + 用户中断。

设计任何 hook 时，**不要假设「工具执行中可以插入干预」**——那个窗口不存在。
