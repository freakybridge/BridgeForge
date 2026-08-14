<!-- MEMORY_COLD.md — 冷区索引 | 用 /find-memory <关键词> 搜索 -->

- [topics/memory-rule-organization/summary](topics/memory-rule-organization/summary.md) — BridgeForge 双 memory 架构交付完成：项目 memory 可确定性加载和召回，Codex 原生 memories 可经可选用户级 hook 与私有 GitHub 最新整树快照同步。
- [topics/bridgeforge-doc-runtime-packaging/summary](topics/bridgeforge-doc-runtime-packaging/summary.md) — BridgeForge 的运行手册统一位于 doc/0_playbook；只有该编号子树随 bridgeforge command bundle 分发，其余 doc 只留在工厂仓库。
- [topics/bridgeforge-switch-semantic-migration/summary](topics/bridgeforge-switch-semantic-migration/summary.md) — BridgeForge 跨 Claude/Codex 切换采用语义迁移 manifest 与可回滚事务；可执行约束在无可信沙箱时必须 fail-closed。
- [topics/bridgeforge-command-model/summary](topics/bridgeforge-command-model/summary.md) — BridgeForge 对外命令心智收敛为 /bridgeforge 与 /bridgeforge switch <agent>；显式 switch 时目标完整但旧骨架残留要 cleanup-only。
- [topics/claude-template-safety-hooks-review/summary](topics/claude-template-safety-hooks-review/summary.md) — Claude 模板从 StratusAgent 反哺的三个轻量 hook 审查结论：产品层和 dogfood 成套、注册事件合理、以伪 payload 和阻断路径验收。
- [topics/codex-harness-parity-closure/summary](topics/codex-harness-parity-closure/summary.md) — Codex 迁移兼容闭环验收：parity 覆盖 memory/skills，20 个差异必须归类，报告状态以未分类为 0 才算 OK。
