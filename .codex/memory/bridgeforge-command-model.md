---
description: BridgeForge 对外命令心智收敛为 /bridgeforge 与 /bridgeforge switch <agent>；显式 switch 时目标完整但旧骨架残留要 cleanup-only。
---

# BridgeForge Command Model

2026-07-08，BridgeForge 命令心智确认收敛为两个用户入口：

- `/bridgeforge`：维护当前正在运行的 agent 骨架。Codex 中默认维护 `AGENTS.md + .codex/`，Claude Code 中默认维护 `CLAUDE.md + .claude/`。
- `/bridgeforge switch <claude|codex>`：显式切换当前项目使用的 agent 骨架。

入口新鲜度红线：

- Codex / Claude 的薄入口 wrapper 必须先对 `~/.bridgeforge` 执行 `git pull --ff-only`，成功后才读取完整 `SKILL.md`。
- pull 失败时停止，不继续用旧模板执行；根 `SKILL.md` 也保留 Step -2 兜底，避免旧 wrapper 或显式 `switch` 绕过刷新。

普通 `/bridgeforge` 的判场语义：

- 空项目：安装当前 agent 骨架。
- 已托管项目：按 `.bridgeforge_version` 走更新模式，只同步上游 `[product]` 增量。
- 旧 BridgeForge 骨架缺戳：走收编，登记纳管，不覆盖已有内容。
- 当前 agent 入口/rules 已存在但不像 BridgeForge：按既有项目首次接入处理，让用户选择保留补缺、备份覆盖或退出。
- 当前 agent 骨架不存在但另一套 agent 骨架存在：先提示继续会执行 `switch <当前agent>`，用户确认后才启动 switch，不静默多铺一套。
- Claude / Codex 两套 live 骨架同时存在：停止，让用户明确选择维护方向或先清理。

显式 `/bridgeforge switch <agent>` 的例外语义：

- 只有“目标 agent 完整存在，且旧 agent live 路径不存在”才算 already target，可短路回普通维护。
- 目标 agent 完整存在但旧 agent live 仍残留时，不是 already target；进入 `bridgeforge_switch.py` 的 cleanup-only 路径。
- cleanup-only 只归档/删除旧 agent，并把旧 memory/settings 按既有确认规则合入目标；禁止为了清理旧骨架而覆盖目标 `AGENTS.md` / `.codex/` 或 `CLAUDE.md` / `.claude/`。
- 目标 agent 只存在一部分时仍按目标冲突阻断，不能把半套骨架当可用目标。

设计理由：`bridgeforge` 可以引导用户进入 switch，但不能静默切换或静默多铺。这样保留“用户只记两个命令”的简单心智，同时避免已有项目被误判为空项目。

落地文件：`SKILL.md`、`README.md`、`INSTALL.md`、`CHANGELOG.md`、`doc/1_plan/bridgeforge-command-clarity/requirements_2026-07-08_bridgeforge-command-clarity.md`。
