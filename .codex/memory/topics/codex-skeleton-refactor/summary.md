---
category: topic
topic: codex-skeleton-refactor
status: completed
description: BridgeForge Codex 骨架已收敛为 schema v2 单事务执行器，并完成独立审计、全量 fixture 与双真实样本回滚和幂等验收。
kind: delivery
tags:
  - bridgeforge
  - codex
  - skeleton
  - transaction
  - migration
related_paths:
  - doc/1_delivery/codex-skeleton-refactor/requirements_2026-08-15_codex-skeleton-refactor.md
  - doc/0_architecture/design/codex-project-sync.md
  - scripts/bridgeforge_project_sync.py
  - templates/codex/managed-skeleton.json
  - tests/harness/test_bridgeforge_project_sync.py
---

# Codex 骨架系统性重构

## 已验收结论

- Codex `init`、`adopt`、`update` 共用 `bridgeforge_project_sync.py`。schema v2 对每个资产使用稳定 id、显式 target 和 `whole`、`merge`、`region`、`retirement` ownership，禁止 glob ownership。
- planner 把动作统一分类为 safe、risk、gap；apply 前重跑并比较 aggregate fingerprint。memory 移动和已发布受管副本删除进入唯一 risk 确认，未知或人工修改内容保留为 gap。
- apply 对受管状态做事务快照；失败恢复路径和字节。只有 `readiness=ready` 才在验证后最后写 `.bridgeforge_version`，degraded 保留旧戳或无戳。
- 历史 lineage 从 Git 的 `VERSION` 变更提交枚举全部实际 `0.86.0+` 发布版本。manifest、schema dogfood 与发布 hash 由同一重建器维护，`--check` 零写入。
- Codex 项目内重复 `bridgeforge_switch.py` 与两个未注册 no-op hook 已退役；`create-worktree` 已登记为 Codex global entry。
- 工厂 AGENTS、产品变更 rule、skill metadata fail-closed hook、harness parity 和 schema 回归测试构成防复发链。通用 hook 语义同步到模板与 dogfood，工厂专属约束不下沉。

## 验收收据

- 用户于 2026-08-15 明确执行 `$summary 同意验收`。
- 主验证组 112 项全部通过；git-sync/schema v2 修复组 20 项全部通过；完整 downstream fixture 37 项全部通过。
- manifest `--check`、harness parity `--check`、mirror drift、skill metadata 和 `git diff --check` 均通过。
- 独立 review-auditor 找到发布 lineage 漏版本、memory move 误列 safe、degraded 提前写戳、root reparse 检查失效、validator 错误码放行过宽和 metadata gate fail-open；对应实现与回归均已修复。
- CausisRiskSuite 低定制样本完成 8 safe、3 risk、2 gap；StratusAgent 高定制样本完成 7 safe、3 risk、18 gap。两边故障注入均完整回滚，所有 gap hash 未变，pre-commit 受管区外内容未变，第二次运行 safe/risk 都为 0。
- 两个真实样本均因保留 gap 而维持 degraded 与旧 `0.90.0` 版本戳；没有 commit、push 或 prune 下游工作树。

## 保留边界

- Codex Desktop deep-link 实际显示、`/hooks` trust 与新会话 lifecycle 没有现场收据，`runtime trust 未验证`；用户明确验收后不作为本交付 blocker。
- CausisRiskSuite 在旧事故中已经丢失的业务版本递增段不能由 BridgeForge 猜测恢复；BridgeForge 防复发已闭环，下游业务恢复仍需该项目单独确认。
