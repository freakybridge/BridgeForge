---
description: Codex 成本路由权威落点：主对话用 config.toml，子 agent 用 .codex/agents/*.toml，hook 只做漂移机检。
---

# Codex Model Routing Policy

2026-07-08，用户反馈 Codex 骨架 token 消耗偏快，要求仿 Claude 的模型 / effort 治理，但进一步明确“不能只靠 md，hook 约束更可靠”。

确认后的 Codex 方案：

- 主对话默认落 `.codex/config.toml`：`model = "gpt-5.5"`，`model_reasoning_effort = "medium"`。
- 子 agent 档位落 `.codex/agents/*.toml`：
  - `light-explorer`: `gpt-5.4-mini + low`
  - `implementation-worker`: `gpt-5.5 + high`
  - `review-auditor`: `gpt-5.5 + high`
  - `xhigh-auditor`: `gpt-5.5 + xhigh`
- `xhigh` 默认必须用户当轮明确确认；agent 不能静默启用。
- `model_policy_check.py` 负责机检：SessionStart 只提示，pre-commit 模式 exit 2 硬拦漂移。

关键边界：

- Codex `SKILL.md` frontmatter 里的 `model:` 不作为本骨架自动切换模型的依据；官方 Codex skill 文档只确认 `name` / `description` 等 skill 发现机制。
- hook 不负责“当轮动态切模型”，它负责检查配置是否被改坏。配置负责选档，hook 负责防漂。
- `xhigh` 机检必须分别检查 `description` 和 `developer_instructions` 都写明用户确认；不能把两段文本拼起来只看总体命中。

落地文件：`templates/codex/config.toml`、`templates/codex/agents/*.toml`、`templates/codex/hooks/model_policy_check.py`、`templates/codex/AGENTS.md`、`templates/codex/rules/portability.md`，以及 dogfood `.codex/` 对应副本。
