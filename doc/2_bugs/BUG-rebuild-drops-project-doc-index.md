---
status: fixed-awaiting-real-downstream-closure
severity: high
scope: bridgeforge-codex old-project destructive rebuild
reported_at: 2026-08-21
downstream: D:\Quant\ClaudeBridgeAssist
product_version: 1.4.33
---

# BUG：旧项目清洁重建丢失项目文档索引

## 现象

ClaudeBridgeAssist 从 1.4.26 重建到 1.4.32 后，同步器返回
`completed / ready / stamp_written_last=true`，随后的 no-op replan 也为空；但
`project_structure_check.py --root . --json` 报告两个
`unindexed-delivery-topic`：`onenote_range_conversion` 与
`poker_player_profiles`。

重建前 `doc/README.md` 含两个项目自有索引行，重建后只剩公共空模板。

## 根因

schema 3 已用 `managed_blocks.keyed_tables` 区分 `doc/README.md` 的公共受管行与项目自有行，
常规 update 会调用 `_plan_managed_markdown_blocks()` 保留项目内容；破坏性 rebuild 却把
所有非 `seed` 资产的 `current` 强制置空，绕过同一 ownership 合并，整文件安装公共模板。

因此版本戳与 current baseline 都能通过，但项目结构校验依据的真实索引已经丢失。

## 修复

- rebuild 对带 `managed_blocks` 的资产继续传入当前文件；
- 复用既有 schema 3 ownership 合并，只刷新公共受管标题/表格行；
- 项目自有标题与非受管表格行原样保留；解析或 ownership 不明确时继续 fail-closed；
- 回归测试在旧项目 `doc/README.md` 注入项目 delivery 行，确认重建后仍存在且 current
  baseline 可验证。

## 验证与关闭条件

- 定向 `test_old_stamp_routes_to_confirmed_rebuild_and_preserves_manifest` 通过；
- `scripts.tests.test_current_baseline_project_sync` 全量通过；
- 回归同时覆盖项目标题保留、公共 managed row 升级，以及重复标题在 Planner 零写阻断；
- downstream fixture 与发布硬闸通过；
- 独立 agent 审计本轮代码、测试、版本、传播面；
- ClaudeBridgeAssist 恢复项目索引后，结构检查无 error、更新 no-op，且 Vault、Memory、Skills
  保留证据不变。
