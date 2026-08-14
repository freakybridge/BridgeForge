---
description: BridgeForge switch 采用双骨架直接同步；目标端 map 只记录可验证映射与生成基线，绝不替代真实项目资产。
category: architecture
status: active
---

# BridgeForge Switch Direct Sync

2026-07-25，项目级 switch 从 root `.bridgeforge/` archive / receipt / lineage 模型改为 `.codex` 与 `.claude` 长期共存的 direct-sync 模型。用户只在当前宿主执行 `/bridgeforge switch <当前宿主>`；入口固定传 `--current-host`，不匹配时零写入失败。

## 稳定边界

- 目标端 map 固定为 `.<host>/.bridgeforge-map.json`，纳入 Git、确定性 JSON、只存相对路径、hash、adapter、selector、状态和原因；禁止存正文、绝对路径、时间戳、命令或模块路径。
- 每轮同时读 source / target map：clean generated projection 必须 suppress，drift projection 是 `forked_projection`，不得自动回灌。仅当 live hash 等于 `last_generated_sha256` 时才允许更新或删除 target。
- target map 缺失或非法时，只可在完全缺失、无碰撞路径创建 `created_unowned` 项；该项不生成 `last_generated_sha256`，因此永不自动取得 update/delete ownership。既有 target 永远 preserve + conflict。
- whole-file adapter 仅允许 portable `.*/memory/**/*.md`；共享配置仅支持 `settings.json#/permissions` JSON Pointer。hooks、入口、agents、scripts 等宿主专属资产不得 raw-copy，统一报告 `untranslated`。
- 可捕获异常必须精确回滚；回滚核验失败只能报告 `rollback incomplete` 并输出 RECOVERY 证据。强杀/断电不承诺跨文件原子性，下次 map/live 不一致时保留并报告 `interrupted-or-modified`。
- commit 前必须重验 source/target map、输入 hash、路径边界和 link/junction；五份 switch 脚本（root、双 template、`.claude`、`.codex`）保持字节一致。

## 验证收据

- `D:\Quant\veighna_studio\python.exe tests\harness\run_downstream_fixture.py`：33/33 PASS。
- `D:\Quant\veighna_studio\python.exe tests\harness\test_shared_skill_distribution.py`：13/13 PASS。
- `git diff --check` 通过；独立审计无 P0/P1。

