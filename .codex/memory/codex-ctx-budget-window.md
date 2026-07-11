---
description: Codex ctx-budget 口径：复用 Claude 成熟机制，但 Codex 窗口按 /status 实测 353K 校准，hook 用 transcript usage 计算比例。
---

# Codex ctx-budget window

2026-07-09，用户反馈 BridgeForge 的 Codex ctx 管理没有像 Claude 骨架那样有效，几次仍触发自动 compact。排查后确认：

- Claude 侧 `context_warning.py` 机制工作效果可接受，且用户确认 Claude 可以继续硬编码 `WINDOW = 1_000_000`。
- Codex 侧不能照抄 Claude 1M。Codex 官方手册只说明线程必须放入模型 context window、窗口因模型而异，且 `config.toml` 支持 `model_context_window`；手册没有确认当前 Codex Desktop + GPT-5.6 家族的 app 实际 compact 上限就是 1M。
- Codex `/status` 起初显示“背景信息：剩余 39%（已使用 158,829 / 共 258K）”，因此 2026-07-09 先把 Codex ctx-budget 默认窗口校准为 `DEFAULT_CODEX_WINDOW = 258_000`。2026-07-10 用户反馈当前上限已升至 `353K`，默认窗口同步更新为 `DEFAULT_CODEX_WINDOW = 353_000`。
- hook 不直接调用 `/status`。`/status` 是交互命令，不是稳定 hook API；`context_warning.py` 从 hook payload 的 `transcript_path` 读取最近 assistant `usage`，用 `input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens` 除以默认窗口计算百分比。
- Codex hook 输出必须带 `surface=codex`、`token_source`、`window_source`，便于后续对照 `/status` 校准。
- 若未来实测窗口变化，只改 `DEFAULT_CODEX_WINDOW` 或设置 `BRIDGEFORGE_CODEX_CTX_WINDOW`，不要重写机制。

落地文件：`templates/codex/hooks/context_warning.py`、dogfood `.codex/hooks/context_warning.py`、`templates/codex/rules/anti_drift_hooks.md`、`templates/codex/AGENTS.md`、`doc/1_plan/ctx-management/requirements_2026-07-09_codex-ctx-budget.md`。
