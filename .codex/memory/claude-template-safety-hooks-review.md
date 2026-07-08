---
description: Claude 模板从 StratusAgent 反哺的三个轻量 hook 审查结论：产品层和 dogfood 成套、注册事件合理、以伪 payload 和阻断路径验收。
---

# Claude Template Safety Hooks Review

2026-07-08 审查下游 agent 反哺到 BridgeForge 的 Claude hook 改动：

- `git_add_all_guard.py`：`PreToolUse/Bash`，只阻断 `git add -A`、`git add --all`、`git add .` 这类 bulk add 在会带入凭证类文件或 `.runtime/` 产物时的风险；精确路径 `git add <path>` 仍放行。
- `memory_dup_check.py`：`PreToolUse/Write|Edit|MultiEdit` 注册，但脚本只对 `Write` 生效；用途是新建 `.claude/memory/*.md` 前提示同主题碎片化，`exit 0`，不阻断。
- `cargo_default_run_check.py`：`PostToolUse/Edit|Write|MultiEdit`，仅在 `Cargo.toml` 有多个 `[[bin]]` 且缺少 `default-run` 时软提醒。

审查口径：

- 产品层和 dogfood 必须成套：`templates/claude/hooks/` 与 `.claude/hooks/` 都要有文件，脚本本体逐字一致。
- settings 命令前缀允许不同：模板用 `.venv/Scripts/python.exe`，BridgeForge 自身 dogfood 用系统 `python`。
- 产品层 hook 改动要同步 `templates/claude/VERSION`、`templates/claude/CHANGELOG.md`、根 `VERSION` / `CHANGELOG.md` 和入口 skill 版本。
- 验收不能只看 diff：至少跑 `python -m py_compile`、settings JSON parse、伪 Claude hook payload；对阻断型 hook 要构造一次真阻断路径再清理临时文件。

本次判断：改动整体合理，可以保留。唯一小瑕疵是 `memory_dup_check.py` 的 settings matcher 比实际处理范围宽，但属于无害冗余。
