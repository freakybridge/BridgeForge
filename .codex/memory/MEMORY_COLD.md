<!-- MEMORY_COLD.md — 冷区索引 | 用 $find-memory <关键词> 搜索 -->

- [topics/codex-project-zone-ownership/summary](topics/codex-project-zone-ownership/summary.md) — BridgeForgeCodex 通过公共只读区与项目专区分离根 AGENTS ownership，并对旧项目执行零损失、fail-closed 迁移。
- [topics/bridgeforge-actionable-readiness/summary](topics/bridgeforge-actionable-readiness/summary.md) — BridgeForge 更新反馈已采用双状态、可执行 R/C/M/B 清单和单次 A/B/C 部分确认，并由用户明确验收。
- [topics/bridgeforge-latency-optimization/summary](topics/bridgeforge-latency-optimization/summary.md) — BridgeForge 下游更新已采用 canonical sparse fast path、项目 planner 去重、并行终态验证和阶段计时收据，并由用户明确验收。
- [topics/bridgeforge-single-confirmation/summary](topics/bridgeforge-single-confirmation/summary.md) — BridgeForge 四种维护模式统一为常规零确认、风险最多一次汇总确认；人工差异保留为 gap，用户级权限仅开放封闭入口。
- [topics/bridgeforge-upstream-absorption-modes/summary](topics/bridgeforge-upstream-absorption-modes/summary.md) — BridgeForge 上游吸收采用 A/B/C 单次确认，并以稳定键合并索引表，吸收同键官方行时保留下游独有条目。
- [topics/codex-skeleton-refactor/summary](topics/codex-skeleton-refactor/summary.md) — BridgeForge Codex 骨架已收敛为 schema v2 单事务执行器，并完成独立审计、全量 fixture 与双真实样本回滚和幂等验收。
- [topics/create-worktree-skill/summary](topics/create-worktree-skill/summary.md) — Codex-only create-worktree 已验收：支持斜杠位置调用、安全创建永久 worktree，并通过 Windows 协议激活 Codex Desktop。
- [topics/skill-runtime-efficiency/summary](topics/skill-runtime-efficiency/summary.md) — BridgeForge 非根 skill 已通过条件式 fast path、Git 子进程合并和 memory 索引去重降低固定运行开销，并由用户明确验收。
- [topics/memory-rule-organization/summary](topics/memory-rule-organization/summary.md) — BridgeForge 双 memory 架构与 Native Memory 私有云同步已完成验收；Windows Codex App 生命周期 hook 通过独立 cmd wrapper、运行收据和远端 commit 实机闭环。
- [topics/bridgeforge-doc-runtime-packaging/summary](topics/bridgeforge-doc-runtime-packaging/summary.md) — BridgeForge 的运行手册统一位于 doc/0_playbook；只有该编号子树随 bridgeforge command bundle 分发，其余 doc 只留在工厂仓库。
- [topics/bridgeforge-switch-semantic-migration/summary](topics/bridgeforge-switch-semantic-migration/summary.md) — BridgeForge 跨 Claude/Codex 切换采用语义迁移 manifest 与可回滚事务；可执行约束在无可信沙箱时必须 fail-closed。
- [topics/bridgeforge-command-model/summary](topics/bridgeforge-command-model/summary.md) — BridgeForge 对外命令心智收敛为 /bridgeforge 与 /bridgeforge switch <agent>；显式 switch 时目标完整但旧骨架残留要 cleanup-only。
- [topics/claude-template-safety-hooks-review/summary](topics/claude-template-safety-hooks-review/summary.md) — Claude 模板从 StratusAgent 反哺的三个轻量 hook 审查结论：产品层和 dogfood 成套、注册事件合理、以伪 payload 和阻断路径验收。
- [topics/codex-harness-parity-closure/summary](topics/codex-harness-parity-closure/summary.md) — Codex 迁移兼容闭环验收：parity 覆盖 memory/skills，20 个差异必须归类，报告状态以未分类为 0 才算 OK。
