---
delivery_layout: flat
---

# BridgeForge Documents

本仓库采用 BridgeForge 五层文档体系。`1_delivery/` 采用扁平布局：每个 topic 直接位于该目录下；若未来交付规模需要里程碑，可改为 `milestone` 并迁入 `M1/<topic>/`。

## 索引

| 目录 | 作用 | 当前内容 |
|---|---|---|
| `0_architecture/` | 架构与设计依据 | `design/` |
| `1_delivery/` | 需求确认、计划、验收、协作与专题讨论 | 见下方 topic 索引 |
| `2_bugs/` | 已知故障及其修复记录 | 11 条故障记录 |
| `3_reference/` | 外部资料与可复用参考实现 | `examples/antifab-deny-hook.py` |
| `4_archive/` | 已完成或已失效的历史材料 | 既有历史档案；后续按 `delivery/`、`bugs/` 分类归档 |

## 架构

- 设计资料：[`0_architecture/design/`](0_architecture/design/)，包括 [`codex-project-sync.md`](0_architecture/design/codex-project-sync.md)、`design-rationale.md`、上游同步 playbook、harness、memory 与文档体系设计。
- `$bridgeforge` 的运行手册属于产品源码，位于 [`skills/bridgeforge/references/`](../skills/bridgeforge/references/)，不纳入 `doc/`。

## Delivery topic

| Topic | 主要记录 |
|---|---|
| `bridgeforge-command-clarity`、`bridgeforge-home-layout` | 入口与用户级目录演进 |
| `bridgeforge-latency-optimization` | 用户级 sparse canonical fast path、项目 planner 去重、并行终态验证与阶段计时收据（2026-08-15） |
| `bridgeforge-actionable-readiness` | 双状态更新结果、可执行完善清单、程序推荐与用户自定义部分确认，并保持整体 0/1 次确认（2026-08-15） |
| `bridgeforge-upstream-absorption-modes` | A 激进吸收、B 温和自定义、C 保守停止的单卡上游受管区块吸收契约（2026-08-15） |
| `bridgeforge-single-confirmation` | `init`、`adopt`、`update`、`switch` 的零确认安全路径、单次风险确认与 Codex 窄权限规则需求（2026-08-15） |
| `bridgeforge-switch-direct-sync`、`bridgeforge-switch-semantic-migration` | 双宿主切换；各含 `debates/`；Markdown Rule 投影增强建议（2026-07-30） |
| `codex-harness-parity`、`codex-model-routing`、`codex-model-routing-56`、`codex-cost-routing`、`codex-subscription-routing` | Codex harness 与模型路由；下游业务版本与 BridgeForge 骨架版本分离（2026-07-30） |
| `codex-skeleton-refactor` | Codex 骨架系统性重构、11 条 Bug 全量闭环、`0.86.0+` 迁移、`create-worktree` 与双真实下游验证（2026-08-15） |
| `codex-skill-routing-dispatch` | skill routing 设计与 `debates/` |
| `confirm-workflow`、`develop-demand-discovery`、`explain-skill` | 需求确认与通用 skill 演进；后两者含 `research/` |
| `cross-project-write-guard`、`non-ascii-shell-guard` | 安全防护；后者新增 [memory writer stdin 编码旁路报告](1_delivery/non-ascii-shell-guard/research/2026-08-04_memory-writer-stdin-encoding-bypass-report.md) |
| `ctx-management`、`token-context-optimization` | 上下文与 token 治理；Stall Warning 已裁定从双宿主骨架及下游更新中移除（2026-07-30） |
| `doc-unification`、`document-lifecycle` | 文档体系演进 |
| `git-sync-latency-optimization` | `$git-sync` 单脚本直跑、失败前置、重复重建消除与完整同步收据（2026-08-01） |
| `git-sync-version-automation` | BridgeForge 与下游项目双版本域的 `$git-sync` 自动 bump、原生字段同步与统一 CHANGELOG 需求；新增 [下游项目 Rule 被误判为受管骨架的所有权缺口报告](1_delivery/git-sync-version-automation/research/2026-08-12_downstream-rule-managed-skeleton-boundary-gap.md)（2026-08-12） |
| `memory-lifecycle-governance` | 统一 memory schema、模块/topic 分工、`$summary` 双模式与 topic 生命周期治理（2026-08-02） |
| `memory-rule-organization` | 下游 memory / rule 分类、topic memory 与渐进加载；项目级双宿主 memory junction hook（2026-07-28）；Rule 索引 hook 批次 A 上游增强已采纳（2026-07-29）；Codex hook 单一注册源与全量承载迁移、Summary 职责收口与 memory 颗粒度治理需求已确认（2026-08-01）；新增项目 memory 确定性加载、自动召回及 Codex 原生 memories GitHub 同步确认卡（2026-08-14） |
| `shared-skill-distribution` | 用户级 shared skill 分发 |
| `skill-runtime-efficiency` | 非根 skill 的确定性 fast path、重复 agent/索引消除与高频 Git 单进程优化（2026-08-15） |
| `create-worktree-skill` | Windows Codex 永久 worktree 创建、独立 `codex/` 分支与无槽位路径需求（2026-08-15） |

每个 topic 内以 `requirements_*.md` 保存确认卡；实现计划、验收方案、协作记录和正式讨论分别与该确认卡同域保存。仅 topic 内路径可作为该事项的工作上下文。

## Bug records

- [`BUG-switch-codex-left-claude-live-dir.md`](2_bugs/BUG-switch-codex-left-claude-live-dir.md)
- [`BUG-git-sync-sandbox-permission.md`](2_bugs/BUG-git-sync-sandbox-permission.md)
- [`BUG-shared-skill-manifest-line-endings.md`](2_bugs/BUG-shared-skill-manifest-line-endings.md)
- [`BUG-summary-writes-global-memory-instead-of-project-memory.md`](2_bugs/BUG-summary-writes-global-memory-instead-of-project-memory.md)
- [`BUG-migration-drops-project-pre-commit-extension.md`](2_bugs/BUG-migration-drops-project-pre-commit-extension.md)
- [`BUG-downstream-business-version-rule-without-enforcement.md`](2_bugs/BUG-downstream-business-version-rule-without-enforcement.md)
- [`BUG-bridgeforge-references-omitted-from-user-skill.md`](2_bugs/BUG-bridgeforge-references-omitted-from-user-skill.md)
- [`BUG-update-stamped-before-memory-migration.md`](2_bugs/BUG-update-stamped-before-memory-migration.md)
- [`BUG-codex-native-memory-empty-snapshot-reconcile.md`](2_bugs/BUG-codex-native-memory-empty-snapshot-reconcile.md)
- [`BUG-finalizer-timeout-protected-host-tempfile.md`](2_bugs/BUG-finalizer-timeout-protected-host-tempfile.md)
- [`BUG-create-worktree-sandbox-half-created.md`](2_bugs/BUG-create-worktree-sandbox-half-created.md)

## 归档与参考

`4_archive/` 内现有文件为迁移前历史档案，继续保持可追溯性；新归档按 `4_archive/delivery/<topic>/` 或 `4_archive/bugs/` 落位。外部资料与仅供参考的实现放入 `3_reference/`，不作为运行时资产。
