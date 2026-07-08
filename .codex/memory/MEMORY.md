# Memory Index

<!-- 自动生成索引，勿手改（改动会被下次重建覆盖）。新增 memory：在 .codex/memory/ 下新建 .md 文件，本索引会自动收录；写法见 ~/.codex/AGENTS.md「auto memory」段。满 40 条自动滚入冷区，用 /find-memory 搜。 -->

> Active: 6 | Cold: 0

## Active（按新增时间，新在前；满 40 自动滚入 Cold）
- [bom-free-encoding-gate](bom-free-encoding-gate.md) — BridgeForge 全 repo 文本统一 UTF-8 without BOM，并用编辑后 hook + pre-commit 双层防线防模板污染。
- [bridgeforge-command-model](bridgeforge-command-model.md) — BridgeForge 对外命令心智收敛为 /bridgeforge 与 /bridgeforge switch <agent>，入口先刷新 ~/.bridgeforge，发现另一套骨架时先确认再切换。
- [codex-harness-parity-closure](codex-harness-parity-closure.md) — Codex 迁移兼容闭环验收：parity 覆盖 memory/skills，20 个差异必须归类，报告状态以未分类为 0 才算 OK。
- [codex-model-routing-policy](codex-model-routing-policy.md) — Codex 成本路由权威落点：主对话用 config.toml，子 agent 用 .codex/agents/*.toml，hook 只做漂移机检。
- [skill-metadata-precommit-gate](skill-metadata-precommit-gate.md) — 通用 skill 可调用 metadata 漏标事故的制度化修复：用 pre-commit 硬闸检查 skills/*/SKILL.md。
- [codex-bridgeforge-slash-entry-debug](codex-bridgeforge-slash-entry-debug.md) — Codex /bridgeforge slash 入口排障：旧 .codex/skills 残留、BOM frontmatter、~/.bridgeforge 完整工厂与薄 wrapper 的最终布局。
