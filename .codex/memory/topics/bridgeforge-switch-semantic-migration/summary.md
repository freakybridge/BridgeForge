---
description: BridgeForge 跨 Claude/Codex 切换采用语义迁移 manifest 与可回滚事务；可执行约束在无可信沙箱时必须 fail-closed。
category: topic
topic: bridgeforge-switch-semantic-migration
status: superseded
---

# BridgeForge Switch Semantic Migration

2026-07-25，`/bridgeforge switch <claude|codex>` 从“归档并复制骨架”升级为语义迁移流程：先输出零写入 proposal，再由用户确认 manifest，最后才执行 stage、校验与事务提交。用户入口保持只有 `/bridgeforge` 与 `/bridgeforge switch <agent>`；`--manifest` 是受控内部参数，不是新增用户命令。

## 不变量

- 当前目标模板是唯一产品基线；archive 只能按 receipt 中证明过的 ownership 与 hash 重放 delta，不能整树恢复旧模板。
- receipt 使用 schema v2，位于 `.bridgeforge/migrations/<migration_id>/receipt.json`；必须分开记录 `source_owner` 与 `target_owner`。
- hard constraint 的翻译、确认、source/target hash、证据等级任一不满足都必须阻断，旧 live 不得变化。
- 当前没有 trusted sandbox runner：manifest 的 `evidence.command` 永不执行；所有需要 `contract-smoke` 或 `native-host` 的可执行资产以 `sandbox-unavailable` fail-closed。纯文本约束可通过已确认的文本差异迁移。
- archive、target 与 source 的完整树在关键阶段都要精确重验；rollback 只删除本事务创建且已证明归属的路径，绝不能清理预存 archive 或父目录。
- Windows 路径需要按 NFC + casefold 等价判断，并对 symlink/junction/reparse point fail-closed。

## 验证收据

- `tests/harness/run_downstream_fixture.py`：43/43 通过，覆盖 proposal 零写入、双向/三跳 lineage、archive inventory、TOCTOU、事务回滚、预存 archive 所有权与可执行证据阻断。
- `tests/harness/test_shared_skill_distribution.py`：13/13 通过。
- 五份 `bridgeforge_switch.py` 镜像最终 SHA-256：`0b85bf32260db05bcd7c60448388c7b739c9b4c3edaa977c7e7e3a8285b77c2c`。

## 未验证边界

- 当前 Windows 环境没有创建 symlink 的权限，link/junction 仅完成静态 fail-closed 检查。
- 真实 Claude/Codex 宿主生命周期、并发修改和进程强杀/断电恢复未在真实项目实测。
