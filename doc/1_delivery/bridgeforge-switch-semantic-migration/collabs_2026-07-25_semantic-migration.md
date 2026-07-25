# BridgeForge switch 语义迁移协作记录

> 状态：`completed`
> 确认卡：[requirements_2026-07-25_bridgeforge-switch-semantic-migration.md](requirements_2026-07-25_bridgeforge-switch-semantic-migration.md)
> 辩论结论：[debates_2026-07-25_bridgeforge-switch-semantic-migration.md](../../2_pending/debates_2026-07-25_bridgeforge-switch-semantic-migration.md)

## 目标与边界

实现项目级资产的 Claude / Codex 语义迁移：当前目标模板为唯一产品基线；旧 archive 仅按已证明 ownership 作为 delta 输入；每项 hard constraint 必须先获得用户确认与验证收据；旧 live 骨架在成功前保持不变。

不直接复制来源平台文件，不跨项目，不处理用户级共享 skill，不自动 git 操作。

## 已复用的研读结论

已完成 debate 的只读研读：当前 `build_plan()` / `apply_plan()` 不包含语义资产，target 模板安装面不完整，archive 整包恢复会复活陈旧 managed 文件。详细证据见辩论记录，不重复扫描。

## 拆分与接口

| 顺序 | 负责人 | 文件边界 | 接口 / 产出 |
|---|---|---|---|
| 1 | implementation-worker | 根 switch 脚本及其四份镜像、switch harness | 持久 migration receipt、完整 target install surface、资产 inventory、逐项 manifest 验证、可恢复 transaction 与测试 fixture |
| 2 | 主线程或独立 worker | 根入口、switch 手册、版本 / CHANGELOG、需求卡 | 调用语义计划、逐项确认与收据展示；与核心 CLI / JSON schema 对齐 |
| 3 | review-auditor | 只读真实 diff | 核对 hard constraint fail-closed、archive delta、往返 lineage 与回滚测试 |

核心代码与 harness 共享数据模型和事务接口，不能安全并行修改；因此采用单 owner 顺序执行，避免伪并行导致的接口漂移。文档更新在核心接口冻结后进行。

## 核心接口约定

- receipt：`.bridgeforge/migrations/<migration_id>/receipt.json`，持久记录 lineage、constraint ID、ownership、source / target hash、approval、adapter / manual 来源与 evidence。
- target base：当前目标模板完整安装面；archive 仅提供经 ownership / hash 证明的 user delta。
- 事务：analyze → propose → approve → stage / verify → archive old → commit；任一 hard 项未覆盖、未确认、验证失败或输入 hash 漂移，旧 live 与原 target 必须保持不变。
- legacy archive：无 provenance 时 fail-closed，进入一次性逐项 adopt；禁止整包恢复。

## 验收

- 双向 switch 产生逐项计划；未知 / hard blocked 时旧 live 全树不变。
- 目标模板完整安装；archive 的过时 managed 文件不得覆盖当前模板。
- 收据 lineage 防止 Claude→Codex→Claude 或反向往返重复 constraint。
- 所有 mutation 点故障注入后可恢复到完整 pre-state 或可续接 committed state。
- 每条 hard constraint 有与其证据等级相符的收据；无法取得目标宿主验证时不得夸大为通过。

## 执行记录

- schema v2 核心脚本、Claude / Codex 镜像、switch 产品手册、版本与 `[product]` CHANGELOG 已完成；当前版本明确拒绝所有 manifest external command，并在缺少 trusted sandbox runner 时以 `sandbox-unavailable` 阻断可执行约束。detached source 与 finalized archive 都复核 approved source state，archive destination 排他 claim，rollback 只清理本事务 owned 路径和父目录，预建空父保留。独立实现 worker 的 43 项 downstream fixture 与共享分发的 13 项测试全部通过。
