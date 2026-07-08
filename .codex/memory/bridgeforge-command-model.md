---
description: BridgeForge 对外命令心智收敛为 /bridgeforge 与 /bridgeforge switch <agent>，普通入口发现另一套骨架时先确认再切换。
---

# BridgeForge Command Model

2026-07-08，BridgeForge 命令心智确认收敛为两个用户入口：

- `/bridgeforge`：维护当前正在运行的 agent 骨架。Codex 中默认维护 `AGENTS.md + .codex/`，Claude Code 中默认维护 `CLAUDE.md + .claude/`。
- `/bridgeforge switch <claude|codex>`：显式切换当前项目使用的 agent 骨架。

普通 `/bridgeforge` 的判场语义：

- 空项目：安装当前 agent 骨架。
- 已托管项目：按 `.bridgeforge_version` 走更新模式，只同步上游 `[product]` 增量。
- 旧 BridgeForge 骨架缺戳：走收编，登记纳管，不覆盖已有内容。
- 当前 agent 入口/rules 已存在但不像 BridgeForge：按既有项目首次接入处理，让用户选择保留补缺、备份覆盖或退出。
- 当前 agent 骨架不存在但另一套 agent 骨架存在：先提示继续会执行 `switch <当前agent>`，用户确认后才启动 switch，不静默多铺一套。
- Claude / Codex 两套 live 骨架同时存在：停止，让用户明确选择维护方向或先清理。

设计理由：`bridgeforge` 可以引导用户进入 switch，但不能静默切换或静默多铺。这样保留“用户只记两个命令”的简单心智，同时避免已有项目被误判为空项目。

落地文件：`SKILL.md`、`README.md`、`INSTALL.md`、`CHANGELOG.md`、`doc/1_plan/bridgeforge-command-clarity/requirements_2026-07-08_bridgeforge-command-clarity.md`。
