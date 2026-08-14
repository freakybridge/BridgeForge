---
description: Codex 平台默认调度：BridgeForge 只定义 agent 职责，不固定模型或思考强度。
category: architecture
status: active
---

# Codex Platform-default Policy

2026-07-31，用户在连续高 token 消耗后要求撤销 BridgeForge 的项目级模型与思考强度固定值。此后标准骨架保持 Codex 平台默认调度。

- `.codex/config.toml` 和 `.codex/agents/*.toml` 不写 `model`、`model_reasoning_effort` 或 `plan_mode_reasoning_effort`。
- named custom agent 仅定义职责、工具边界和确认门槛；未指定模型或 effort 时，Codex 按父会话与平台默认解析。
- skill-routing 仍是工作流分工契约，不是 `$skill -> model` 自动路由器；`xhigh` 仍需要用户当次明确选择。
- BridgeForge 不读取或写入用户级 `~/.codex/config.toml`。用户若要固定模型或强度，必须在骨架外自行明确配置。
- 子 agent 仍有独立成本；没有 root + children 汇总 token 遥测时，不对节省幅度作量化承诺。
