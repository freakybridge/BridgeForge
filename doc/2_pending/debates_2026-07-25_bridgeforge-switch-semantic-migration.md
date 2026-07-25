# BridgeForge switch 项目级资产语义迁移辩论记录

> 状态：`researching`
> 确认卡：[requirements_2026-07-25_bridgeforge-switch-semantic-migration.md](../1_plan/bridgeforge-switch-semantic-migration/requirements_2026-07-25_bridgeforge-switch-semantic-migration.md)

## 目标

在 Claude 与 Codex switch 时，保全项目级硬约束：不直接复制平台文件，而是生成逐项、可验证、用户确认的目标原生语义迁移；任一硬约束不能等价转译或验证时，旧 live 骨架必须保持原状并阻断切换。

## 边界

- 只讨论当前项目的 switch；不触及用户级共享 skill 或其他项目。
- 纯平台细节可保留 archive 并标记不适用。
- 每项映射必须展示来源、目标位置、diff 与验证收据，并由用户逐项确认。
- 未经用户确认，不改代码。

## 待研读事实

- 当前 `scripts/bridgeforge_switch.py` 的 planning、archive、memory/settings 合并与 apply 顺序。
- Claude/Codex 模板的入口、rules、hooks、项目私有 skill 与测试差异。
- 哪些中间表示或 plan schema 能最少增加系统部件，同时满足逐项确认与原子性。

## 已研读事实

- 当前 `build_plan()` 只计划旧/目标骨架、memory 与 settings；`apply_plan()` 先 stage 旧骨架、安装目标、合并 memory/settings，最后才归档并删除旧 live 路径。hooks、rules、私有 skill 与入口没有语义迁移项或验证。
- Claude / Codex 的入口、hook 生命周期、settings schema、项目私有 skill 格式不同；部分 rules 与 hook 文件近似，但不能由路径或文件名断言语义等价。
- 现有 switch harness 已覆盖 archive、restore、dry-run、cleanup-only、memory/settings 与作用域；尚未覆盖语义迁移计划、目标 staging 验证或“硬约束未转译时旧 live 零变化”。
- 研究建议的最小模型是 `MigrationPlan` 中的逐项 `MigrationItem`：来源 path/hash、语义分类、目标 path、建议 diff、验证收据和确认状态；事务顺序为 analyze → propose → confirm → stage target → verify staged target → commit。

## 辩论参与者

- A（implementation-worker）：`/root/semantic_migration_proposal`
- B（review-auditor）：`/root/semantic_migration_challenge`

## 轮次记录

### 第 1 轮

- A（实现）：主张“两层方案”。主对话 / 用户产出逐项语义迁移 manifest，脚本只做资产盘点、hash 覆盖、审批校验、事务执行与验证。所有项目 delta / unknown 资产必须进入 manifest；hard 项缺目标实现或收据即阻断。旧 live 在目标验证完成前保持不动。
- B（审计）：反对把 LLM proposal 或用户看过 diff 当作等价证明。指出 target base 当前不完整、archive 整包恢复会倒退、staging 不等于真实宿主验证、没有 stable constraint ID 会导致往返漂移。要求安装基线 / provenance、目标模板加目标 archive delta 加来源语义的三方构造、事务 journal 与证据等级。
- 争点：是否需要持久 constraint registry / provenance，及其能否在不显著增加系统部件的前提下成为 manifest 的最小组成部分。

### 第 2 轮

- B 接受“逐次 manifest + 机械执行”，条件是成功 manifest 必须持久保留为 migration ledger：含 stable `constraint_id`、文件 ownership / last generated hash、最小语义契约、parent lineage 与操作逆向条件；无需另建 registry 或通用 merge engine。
- A 同意把 provenance 压入 `.bridgeforge/migrations/<migration_id>/receipt.json`，并以 path/hash 与 prior receipt 继承 constraint ID；未知或漂移项回到用户确认，脚本不猜语义。A 同时指出当前 Codex target install 面不完整，必须由 AgentSpec 明确 config files / dirs。
- 仍有分歧：A 认为目标 archive 应作为完整 target base，避免“archive + 新模板”派生第四份状态；B 认为整包 archive 会复活过时产品 / 安全配置，应以当前模板为 base、只叠加可证明的 target user delta。

### 第 3 轮与收敛

- A 接受 B 的安全论点：完整 target archive 不能作为 live base，会复活旧 managed hook / settings / scripts 并绕过当前模板升级。A 改为当前目标模板是唯一产品基线，archive 只提供 hash-guarded target delta。
- B 给出不引入独立 registry 或通用三方 merge 的最小 archive inventory：ownership 为 `template-managed`、`constraint-generated`、`user-owned` 或 `unknown-historical`；每项记录 last written hash 与 archive hash。旧 archive 没有 provenance 时必须 fail-closed，进行一次性逐项 adopt。
- 共识：成功 migration receipt 持久保存 lineage、constraint ID、ownership、hash、adapter / manual 来源、审批和验证收据。当前模板加经证明的 user-owned delta 加按 ID 重生成的 constraint projection 构成目标；禁止整包 archive restore。未知语义、历史 ownership 缺失、基线升级导致 base hash 不符、目标生命周期无法验证的 hard 约束均阻断。
