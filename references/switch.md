# Switch 模式操作手册

仅当根 `SKILL.md` 判定为显式或经用户确认的隐式 `switch` 时读取本文件。目标是把当前项目的 Claude / Codex 项目级约束翻译成目标平台原生实现；禁止直接复制另一平台的入口、rules、hooks、skills、memory 或 settings。

## 1. 唯一用户入口与前置判定

用户只调用：

```text
/bridgeforge switch claude
/bridgeforge switch codex
```

`--manifest`、`--dry-run`、`--project-root`、`--template-root` 都是底层脚本的受控参数，不是用户命令面。禁止新增或宣传 `bridgeforge migrate-layout`、`bridgeforge migrate` 等迁移 CLI；manifest 是本次 `switch` 过程中的审核产物。

先同时检查目标 agent 与旧 agent 的 live 路径：

- 目标完整、旧 agent 不存在：不调用脚本，回根入口按普通维护判场。
- 目标入口或配置目录已部分/完整存在，且旧 agent 仍 live：阻断；不得覆盖目标、归档旧 live 或猜测如何合并。
- 目标 surface 不存在：进入语义迁移流程。
- 当前项目仍有 `.agents/`：先按根入口 Step 2.5 完成专用布局迁移；switch 不读取、不归档、不修改 `.agents/`。

## 2. 生成零写入提案

主对话优先调用当前项目脚本；不存在时调用 command bundle 内模板脚本：

```powershell
python scripts/bridgeforge_switch.py <claude|codex> --template-root "$BRIDGEFORGE_HOME"
```

```powershell
python (Join-Path $BRIDGEFORGE_HOME "templates\$TEMPLATE_AGENT\scripts\bridgeforge_switch.py") `
  <claude|codex> `
  --template-root "$BRIDGEFORGE_HOME"
```

cwd 若是 BridgeForge 源头仓库，脚本必须拒绝。存在旧 live 或目标 archive 且未提供 manifest 时，脚本必须：

1. 盘点旧 live 全部文件、当前目标模板、最新目标 archive 与历史成功 receipt。
2. 输出 `BEGIN_BRIDGEFORGE_MIGRATION_MANIFEST` 和 `END_BRIDGEFORGE_MIGRATION_MANIFEST` 之间的完整 JSON 提案。
3. exit `2`，并确认旧 live、目标 pre-state 和 archive 均为零写入。

若旧 live 与目标 archive 都为空，脚本可直接从当前目标模板安装并写成功 receipt；此分支没有待迁移项目约束。

## 3. 基线、archive 与 lineage

- 当前 `$BRIDGEFORGE_HOME/templates/<target>/` 的完整安装面是唯一 target base，必须包含目标入口、配置文件/目录和 `.bridgeforge_version`；禁止以旧 target archive 整包恢复或覆盖当前模板。
- 只有 schema v2 成功 receipt 才可提供 provenance；旧 schema、解析失败或非成功 receipt 一律忽略，其 archive 按 legacy unknown 处理。
- archive 只提供经 schema v2 receipt 证明的 delta：receipt 与 archive 必须按 canonical Windows 路径、双向 inventory 和逐文件 hash 完全对账。只有 proven `user-owned` 可机械 `replay-archive`；`constraint-generated` archive 没有已注册 adapter 时必须阻断，禁止 replay 旧 bytes。
- `template-managed` archive 内容由当前模板取代；只有 stable constraint ID 相同的 lineage duplicate 才可作为 `not-applicable` 跳过，三跳往返不得按路径或内容相似度放宽。
- legacy archive 没有有效 provenance 时一律保持 `source_owner=unknown-historical` 并 fail-closed；只能逐项完成语义说明、目标原生 `write`、用户确认与证据，禁止把未知 ownership 改写为 user-owned 后 replay。
- manifest 必须覆盖旧 live 与目标 archive 的精确 inventory，并携带 source、target template、target pre-state、target archive 的 snapshot。执行前后任一 hash 漂移都阻断。
- `source_owner` 描述输入 provenance，`target_owner` 描述目标产物；目标原生 `write` 必须为 `constraint-generated`，proven user-owned replay 才保持 `user-owned`。禁止用一个 ownership 字段混淆两端或降级提案冻结字段。
- 成功 receipt 持久保存 stable `constraint_id`、parent migration lineage、source / target ownership、hash、adapter 来源、approval 与 evidence，供下一次往返迁移去重和追溯。
- 所有项目相对路径按 Windows 语义检查大小写/Unicode 碰撞、尾随点空格、保留名与 ADS；live、archive、migration 和目标 surface 内存在 symlink、junction、reparse point 或越出当前项目时均 fail-closed。

## 4. 逐项语义审核

主对话必须逐项展示来源、语义分类、目标原生位置、target template 基线上的 diff、`source_owner`、`target_owner`、确认状态和验证方式：

- `platform-detail`：仅当内容确属源平台实现细节或当前源模板原样资产时标为不适用；保留在 archive / receipt，不复制到目标。
- 可翻译约束：生成 `target_owner=constraint-generated` 的目标平台原生 projection；禁止把旧 live 文件逐字节复制到另一平台。
- hard constraint：语义未解析、目标 projection 缺失、provenance 不成立、用户未明确批准或证据等级不足，任一条件成立都阻断整个 switch。
- 证据最低等级取 source 与 target 可执行面的较高者；可执行面判定按 Windows NFC + casefold 语义处理。任一侧是可执行文件或 hook 的 hard constraint至少需要 `contract-smoke`。
- 当前版本没有代码注册且可验证的 trusted sandbox runner。任何 manifest `evidence.command` 都禁止执行并立即阻断；`contract-smoke` / `native-host` 均以 `sandbox-unavailable` fail-closed，禁止用普通 subprocess 或文本确认冒充 sandbox。只有纯文本 hard constraint 可用状态为 passed 的 `text-review` 完成本环境迁移。

manifest 必须由主对话根据用户审核结果保存为本次受控临时输入；禁止要求用户手写 JSON，禁止把“已生成提案”当成“已批准迁移”。

## 5. 受控执行与事务

仅全部项目满足第 4 节后，由主对话调用：

```powershell
python scripts/bridgeforge_switch.py <claude|codex> `
  --template-root "$BRIDGEFORGE_HOME" `
  --manifest <approved-manifest.json>
```

执行顺序固定：

1. 重新验证 schema v2、精确 inventory、冻结的 provenance / constraint 字段、lineage、approval、evidence、diff、Windows 路径和全部 snapshot。
2. 先把旧 live 复制到项目外的临时 source backup，并确认 backup 与 approved source state 完全一致且复制期间 source 未漂移；再在同一临时区从当前目标模板构建 target，并应用已批准 projection。
3. 记录 approved staged target 的 exact tree（目录、文件和逐文件 hash）。本版本不执行任何 manifest 外部命令；纯文本 review 通过后 staged exact tree 仍必须逐项不变。
4. 再次检查所有输入 hash 和 staged exact tree；确认目标 live surface 仍为空。
5. 把旧 live 移入 detached transaction state，并在启用目标前确认 detached source tree 与 approved source state 完全一致；不一致立即回滚。
6. 维护事务内 target move journal并启用 staged target；即使入口已移动而配置目录移动失败，也必须进入完整回滚。
7. 验证真实 live target 的 exact tree 与 approved stage 完全一致；对 `.bridgeforge/archive/<source-agent>/<timestamp>-<migration_id>/` 执行排他 claim，目标已存在或竞态出现即阻断，禁止覆盖。
8. 仅把 detached source 移入本事务已 claim 的 archive，并再次确认 finalized archive exact tree 与 approved source state 一致；随后写入 `.bridgeforge/migrations/<migration_id>/receipt.json`。

任何校验、evidence 或 mutation 失败都必须删除 partial target；source backup 只有仍与 approved source state 一致时才可恢复，恢复后再次逐项核对旧 live 完整 bytes 与目标 pre-state。rollback 只允许删除本事务成功 claim 的 archive；`<archive>/<agent>` 空父目录也只有确认由本事务创建时才可删除，预建空父与预存/竞态创建的同名路径绝对不动。无法证明恢复完整时保留 transaction state，禁止清理最后一份可恢复证据。不得留下伪成功 receipt。真实 switch 只改当前工作区，不运行 `git add` / `commit` / `push`。

## 6. 退出码与收据

- exit `0`：目标已是唯一完整 live、空项目直接安装成功、manifest dry-run 验证成功，或真实迁移成功。只有真实成功且目标检查通过才可称 “Validation passed”。
- exit `2`：正常提案待审核，或因目标冲突、旧 schema / manifest 不完整、hard constraint、approval、provenance、Windows 路径/link、diff、`evidence.command`、`sandbox-unavailable`、hash/tree 漂移而安全阻断；应明确报告零写入或 pre-state 已保留。
- exit `1`：执行阶段异常；应明确报告事务已回滚。

最终必须报告脚本退出码、迁移 ID、manifest 审批状态、target base 来源、hard constraint 证据结果、目标完整安装面、旧 live 是否消失、archive 实际路径、receipt 实际路径，以及是否发生回滚。成功 receipt 的固定位置是：

```text
.bridgeforge/migrations/<migration_id>/receipt.json
```
