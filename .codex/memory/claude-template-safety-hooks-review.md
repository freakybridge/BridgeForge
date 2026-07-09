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

2026-07-08 后续移植：三份 hook 已增加 Codex 适配版，进入 `templates/codex/hooks/` 与 `.codex/hooks/`，并接入两份 Codex `settings.json`。Codex 版输入读取遵守现行范式：stdin JSON 优先，`CODEX_TOOL_INPUT` / `CODEX_TOOL_NAME` 次之，`CLAUDE_*` 仅作 legacy fallback；memory 路径改为 `.codex/memory/`。

2026-07-10 追加：`non_ascii_shell_guard.py` 与 `cross_project_write_guard.py` 都按同一产品层闭环落地：Claude/Codex 模板各一份、BridgeForge `.claude/.codex` dogfood 各一份，模板 settings 用 `.venv/Scripts/python.exe`，dogfood settings 用系统 `python`。这次独立复核发现一个容易漏的点：除了根 `CHANGELOG.md`，还必须同步两份模板自己的 `templates/{claude,codex}/CHANGELOG.md`，否则下游只看模板流水账会漏掉新能力。

阻断型 hook 验收补充口径：用 stdin JSON 构造正反 payload，至少覆盖“项目内放行、项目外阻断、只读放行、危险操作阻断”。`cross_project_write_guard.py` 的最小通过集为：项目内 `Write` exit 0、项目外 `Write` exit 2、外部 `git status` exit 0、外部 `git commit` exit 2、外部 `Set-Content` / `Remove-Item` / shell redirection exit 2、外部 `Get-Content` exit 0。若 `py_compile` 因 `__pycache__` 权限失败，可用不落盘 `compile()` 做语法验证，但要在交付记录里说明。
