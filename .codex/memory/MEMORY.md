# Memory Index

<!-- 自动生成索引，勿手改（改动会被下次重建覆盖）。新增 memory：在 .codex/memory/ 下新建 .md 文件，本索引会自动收录；写法见 ~/.codex/AGENTS.md「auto memory」段。达到条目或字符预算后自动滚入冷区，用 $find-memory 搜。 -->

> Active: 7 | Cold: 14

## Active（按新增时间，新在前；主索引上限 6000 字符）
- [architecture/bridgeforge-switch-direct-sync](architecture/bridgeforge-switch-direct-sync.md) — BridgeForge switch 采用双骨架直接同步；目标端 map 只记录可验证映射与生成基线，绝不替代真实项目资产。
- [engineering/confirm-workflow](engineering/confirm-workflow.md) — BridgeForge 的统一需求确认工作流：confirm 先核验事实并生成确认卡，develop/debate/collab 必须复用有效确认卡。
- [engineering/codex-ctx-budget-window](engineering/codex-ctx-budget-window.md) — Codex ctx-budget 口径：复用 Claude 成熟机制，但 Codex 窗口按 /status 实测 353K 校准，hook 用 transcript usage 计算比例。
- [architecture/codex-model-routing-policy](architecture/codex-model-routing-policy.md) — Codex 平台默认调度：BridgeForge 只定义 agent 职责，不固定模型或思考强度。
- [engineering/bom-free-encoding-gate](engineering/bom-free-encoding-gate.md) — BridgeForge 全 repo 文本统一 UTF-8 without BOM，并用编辑后 / pre-commit / shell 中转 hook 防编码污染。
- [engineering/skill-metadata-precommit-gate](engineering/skill-metadata-precommit-gate.md) — 通用 skill 可调用 metadata 漏标事故的制度化修复：用 pre-commit 硬闸检查 skills/*/SKILL.md。
- [operations/codex-bridgeforge-slash-entry-debug](operations/codex-bridgeforge-slash-entry-debug.md) — Codex /bridgeforge slash 入口排障：旧 .codex/skills 残留、BOM frontmatter、~/.bridgeforge 完整工厂与薄 wrapper 的最终布局。

## 🔍 Cold（14 条，用 $find-memory 搜索）
详见 MEMORY_COLD.md
