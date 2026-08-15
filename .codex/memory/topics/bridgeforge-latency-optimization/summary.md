---
category: topic
topic: bridgeforge-latency-optimization
status: completed
description: BridgeForge 下游更新已采用 canonical sparse fast path、项目 planner 去重、并行终态验证和阶段计时收据，并由用户明确验收。
kind: delivery
tags:
  - bridgeforge
  - performance
  - updater
  - transaction
related_paths:
  - doc/1_delivery/bridgeforge-latency-optimization/requirements_2026-08-15_bridgeforge-latency-optimization.md
  - doc/0_architecture/design/codex-project-sync.md
  - scripts/bridgeforge_shared_update.ps1
  - scripts/bridgeforge_project_sync.py
  - tests/harness/test_shared_skill_distribution.py
  - tests/harness/test_bridgeforge_project_sync.py
---

# BridgeForge 下游更新延迟优化

## 已验收结论

- 用户级 shared updater 始终从 GitHub `main` 建立临时 canonical probe，但稳态只 materialize 根 manifest；两套 ledger 和实际受管目录一致时直接 no-op，不展开完整 source、不建事务日志、不重写账本。
- 远端 commit 变化、本地 drift、受管集合变化或账本缺口时才关闭 sparse checkout、逐文件验证 source 并进入事务。新 commit 下内容未变的 skill 只刷新 ledger，不重复换包。
- Codex CLI apply 删除同一进程内背靠背的重复 planner；公开库接口仍强制自行 replan，避免形成可绕过 fingerprint 重检的旁路。
- canonical memory schema 与 strict config health 验证器并行执行，但两个结果都参与 ready 判定；任一失败仍回滚，版本戳只在全部验证通过后最后写入。
- updater、project plan 和 apply 输出结构化 `timings_ms`，可以区分 source probe、目标 hash、source validate、transaction、cleanup、replan 和 validators。

## 验收收据

- 用户于 2026-08-15 明确执行 `$summary 同意验收`。
- 核心回归 50/50 通过；全量 harness 208 项中 207 项首轮通过，唯一 `.runtime/harness/downstream-codex` ACL 阻止 fixture 创建，核验目标仍在仓库后对该精确测试窄权限重跑并通过，最终所有业务断言通过。
- manifest `--check`、PowerShell/Python 语法、strict config health、dogfood mirror、skill metadata 与 `git diff --check` 均通过。
- 本地 canonical bare-remote fixture：首次更新 `941.9ms`，稳态 no-op `707.4ms`；Codex 项目 init/apply `513.0ms`。这些数值只证明脚本结构开销，不代表真实 GitHub 网络耗时。
- drift 修复、commit-only ledger 更新、fingerprint 漂移零写入、事务回滚、validator 非预期退出均有回归覆盖。

## 发布与现场边界

- 交付代码已完成但验收时仍未 commit、push 或合入 GitHub `main`；真实下游只有在发布到 canonical `main` 后再次运行 `/bridgeforge` 才能获得 `0.92.0`。
- 真实 GitHub 网络下的端到端 no-op 时延尚未验证；发布后的 phase receipt 是后续现场判断依据。
- 本轮未修改 lifecycle hook；Codex Desktop `/hooks` trust 与新会话 smoke 不属于本交付验证面，`runtime trust 未验证`。
