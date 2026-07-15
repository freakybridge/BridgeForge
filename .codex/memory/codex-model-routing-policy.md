---
description: Codex 成本路由权威落点：主对话用 config.toml，子 agent 用 .codex/agents/*.toml，hook 只做漂移机检。
---

# Codex Model Routing Policy

2026-07-08，用户反馈 Codex 骨架 token 消耗偏快，要求仿 Claude 的模型 / effort 治理，但进一步明确“不能只靠 md，hook 约束更可靠”。2026-07-10，用户确认把同一策略升级到 GPT-5.6 代际，并按任务成本重新分流。

确认后的 Codex 方案：

- 主对话默认落 `.codex/config.toml`：`model = "gpt-5.6-terra"`，`model_reasoning_effort = "medium"`。
- 子 agent 档位落 `.codex/agents/*.toml`：
  - `light-explorer`: `gpt-5.6-luna + low`
  - `implementation-worker`: `gpt-5.6-terra + high`，用于明确开发或跨文件判断
  - `review-auditor`: `gpt-5.6-sol + high`
  - `xhigh-auditor`: `gpt-5.6-sol + xhigh`
- `xhigh` 只由用户当次自行选择；骨架不得静默启用。
- `model_policy_check.py` 负责机检：SessionStart 只提示，pre-commit 模式 exit 2 硬拦漂移。

关键边界：

- Codex `SKILL.md` frontmatter 里的 `model:` 不作为本骨架自动切换模型的依据；官方 Codex skill 文档只确认 `name` / `description` 等 skill 发现机制。
- hook 不负责“当轮动态切模型”，它负责检查配置是否被改坏。配置负责选档，hook 负责防漂。
- 用户级 `~/.codex/config.toml` 只读不写：`user_config_write_guard.py` 拦截显式工具写入，模型策略检查与下游 fixture 共同验证该保护。
- 用户级路径保护不能只匹配绝对盘符：必须同时覆盖 `$HOME`、`$env:USERPROFILE`、`~` 和重定向写入；pre-commit 还必须解析 settings，确认 Bash、PowerShell、Write/Edit/MultiEdit 三类事件均注册 guard。
- `xhigh` 机检必须分别检查 `description` 和 `developer_instructions` 都写明用户确认；不能把两段文本拼起来只看总体命中。

落地文件：`templates/codex/config.toml`、`templates/codex/agents/*.toml`、`templates/codex/hooks/model_policy_check.py`、`templates/codex/AGENTS.md`、`templates/codex/rules/portability.md`，以及 dogfood `.codex/` 对应副本。

## 2026-07-15：skill 分段路由

模型档位存在不等于 skill 会实际使用它。下游 18 个通用 skill 的阶段路由现以 `.codex/skill-routing.json` 为单一事实源：主对话按 manifest 显式分派 named custom agent，等待其有限证据摘要，并保留用户确认、决策和跨阶段整合。它是工作流契约，不是 Codex 平台级的 `$skill -> model` 自动路由器。

- `light-explorer`（Luna / low）只做独立、只读的检索与事实摸底；写入、用户确认与独立审计不得降到 Luna。
- `implementation-worker`（Terra / high）做明确实现；`review-auditor`（Sol / high）做独立复核；manifest 禁止自动路由 xhigh。
- `$git-sync` 的受控机械阶段使用 `mechanical-sync-worker`（Luna / low），它只允许运行 `codex_git_sync.py`；分叉、冲突、失败和所有决策必须交回主对话。
- `$bridgeforge` 是用户级全局入口，不属于下游复制的 18 个 skill；它涉及 init/update/adopt/switch、迁移和用户确认，保持主对话编排。
- `model_policy_check.py` 与 downstream fixture 只能校验 manifest、TOML 档位和关键负例，不能证明运行时真的 spawn 了指定 agent。发布前需在真实下游 Codex app 的 Subagents 面板验证 `$find-doc`、`$archive-scan`、`$develop` 的 agent 名称与阶段边界。
- 子 agent 有独立模型与工具调用成本。没有 root + children 汇总 token 的等价对照遥测时，只能声称隔离主线程检索噪声 / 成本待验证，不能声称总 token 已节省。
