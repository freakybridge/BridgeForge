---
title: BridgeForge 下游更新延迟优化需求确认卡
status: confirmed
date: 2026-08-15
source: conversation
handoff: direct-development
---

# BridgeForge 下游更新延迟优化需求确认卡

## 背景

用户反馈无参数 `/bridgeforge` 在下游更新经常超过 6 分钟。只读审计确认稳态仍会创建完整浅 clone、校验 Codex/Claude 两套分发并重复运行项目 memory planner，缺少分阶段耗时证据。

## 已确认目标

1. 保留 GitHub `main` canonical source、双平台一致性、manifest 完整性、事务恢复、fingerprint 重检与 ready-only stamp-last。
2. 稳态 no-op 不再展开完整仓库；只读取 canonical commit/manifest 并校验两套 ledger 与实际受管目录。
3. 远端变化、本地 drift、受管集合变化、账本缺口或恢复日志存在时仍走完整 source 校验和事务。
4. 消除 Codex apply 同一进程内背靠背的重复 planner；终态 memory/config 验证可并行，但两者都必须成功。
5. shared updater、项目 plan/apply 输出结构化 phase timing receipt，能够区分网络、hash、事务、validator 与 agent 编排延迟。

## 非目标

- 不使用持久 clone、本地工作副本、TTL-only 缓存或后台 daemon。
- 不只更新当前宿主，不放弃 Codex/Claude 收敛到同一 commit。
- 不跳过本地受管目录 drift 检测，不降低 source hash、回滚或版本戳条件。
- 不承诺异常网络下固定总耗时。

## 验收

- canonical no-op 收据为 `mode=noop`、`action_count=0`，不包含 `source_validate` 或 `transaction` 阶段。
- 任一受管文件 drift 会进入完整 source 校验，只换包实际变化的 skill，并恢复 canonical 内容。
- 新 commit 但 skill 内容未变时只更新 ledger commit，注入 swap 失败点不得触发。
- CLI apply 只调用一次紧邻 planner；库级调用仍默认自行 replan 并检测 fingerprint drift。
- memory schema 与 config health 同时启动，任一非预期退出仍阻断并回滚。
- manifest、版本、CHANGELOG、运行手册和定向回归测试同步更新。
