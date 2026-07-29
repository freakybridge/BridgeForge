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
| `2_bugs/` | 已知故障及其修复记录 | 3 条故障记录 |
| `3_reference/` | 外部资料与可复用参考实现 | `examples/antifab-deny-hook.py` |
| `4_archive/` | 已完成或已失效的历史材料 | 既有历史档案；后续按 `delivery/`、`bugs/` 分类归档 |

## 架构

- 设计资料：[`0_architecture/design/`](0_architecture/design/)，包括 `design-rationale.md`、同步/反哺 playbook、harness、memory 与文档体系设计。
- `$bridgeforge` 的运行手册属于产品源码，位于 [`skills/bridgeforge/references/`](../skills/bridgeforge/references/)，不纳入 `doc/`。

## Delivery topic

| Topic | 主要记录 |
|---|---|
| `bridgeforge-command-clarity`、`bridgeforge-home-layout` | 入口与用户级目录演进 |
| `bridgeforge-switch-direct-sync`、`bridgeforge-switch-semantic-migration` | 双宿主切换；各含 `debates/`；Markdown Rule 投影增强建议（2026-07-30） |
| `codex-harness-parity`、`codex-model-routing`、`codex-model-routing-56`、`codex-cost-routing`、`codex-subscription-routing` | Codex harness 与模型路由；下游骨架版本统一为 BridgeForge 根 `VERSION`（2026-07-30） |
| `codex-skill-routing-dispatch` | skill routing 设计与 `debates/` |
| `confirm-workflow`、`develop-demand-discovery`、`explain-skill` | 需求确认与通用 skill 演进；后两者含 `research/` |
| `cross-project-write-guard`、`non-ascii-shell-guard` | 安全防护；各含 `research/` |
| `ctx-management`、`token-context-optimization` | 上下文与 token 治理；Stall Warning 已裁定从双宿主骨架及下游更新中移除（2026-07-30） |
| `doc-unification`、`document-lifecycle` | 文档体系演进 |
| `memory-rule-organization` | 下游 memory / rule 分类、topic memory 与渐进加载；项目级双宿主 memory junction hook（2026-07-28）；Rule 索引 hook 批次 A 上游增强已采纳（2026-07-29） |
| `shared-skill-distribution` | 用户级 shared skill 分发 |

每个 topic 内以 `requirements_*.md` 保存确认卡；实现计划、验收方案、协作记录和正式讨论分别与该确认卡同域保存。仅 topic 内路径可作为该事项的工作上下文。

## Bug records

- [`BUG-switch-codex-left-claude-live-dir.md`](2_bugs/BUG-switch-codex-left-claude-live-dir.md)
- [`BUG-git-sync-sandbox-permission.md`](2_bugs/BUG-git-sync-sandbox-permission.md)
- [`BUG-shared-skill-manifest-line-endings.md`](2_bugs/BUG-shared-skill-manifest-line-endings.md)
- [`BUG-summary-writes-global-memory-instead-of-project-memory.md`](2_bugs/BUG-summary-writes-global-memory-instead-of-project-memory.md)

## 归档与参考

`4_archive/` 内现有文件为迁移前历史档案，继续保持可追溯性；新归档按 `4_archive/delivery/<topic>/` 或 `4_archive/bugs/` 落位。外部资料与仅供参考的实现放入 `3_reference/`，不作为运行时资产。
