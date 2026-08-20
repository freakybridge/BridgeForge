---
status: superseded-current-only-awaiting-real-downstream-validation
severity: high
scope: BridgeForgeCodex hooks template, managed hook merge, and downstream update readiness
reported_at: 2026-08-18
downstream: D:\Quant\causis_risk_suite
factory_head: 352f227f477c234de18bef3e6f0ba2c73f1d450d
factory_version: 1.4.9
fixed_version: 1.4.10
current_product_version: 1.4.30
installed_product_version: 1.4.7
---

# BUG：过期的 context budget hook 注释阻断下游完成升级

## 2026-08-21：当前产品边界

本文后续保留 1.4.9/1.4.10 的退休故障与修复证据，但 `retirement` strategy、历史 hash 和
R1..R9 已不属于 1.4.30。当前合同中没有 `context_warning.py`；合法 `<1.4.28` 项目通过
`PreservationManifest` 破坏性重建，`>=1.4.28` 项目只接受 schema 3 current baseline。

因此当前产品不再要求“contract 继续 retirement”或恢复 legacy fixture。源码、Template、
dogfood 与 current-only fixture 已验证；真实 `causis_risk_suite` 尚未获得写入授权，也未执行
Hook 正规化、确认式重建和 no-op replan，故本 Bug 只保留真实下游验证缺口，不视为 resolved。

## 结论

BridgeForgeCodex 已在产品层退休 `context_warning.py`、`[ctx-budget]` AGENTS 章节及相关
runtime 路由，但 `templates/hooks.json` 的 `UserPromptSubmit` dispatcher 注释仍宣称会注入
`context budget`。

下游把这句注释改成与真实 runtime 一致的表述后，
`bridgeforge_codex_project_sync.py` 因 handler 字典不再与 Template 完全相等而报告
`hooks.UserPromptSubmit.dispatcher[user-prompt]` 冲突。即使其余资产均可安全迁移，目标仍为
`completed_with_gaps / degraded / action_required`，版本戳不能从 0.94.2 更新到 1.4.7。

该问题不是下游自定义冲突，而是同一产品版本内“退休契约”和“活跃 Template 注释”自相矛盾。
用旧注释强行通过会把已退休能力写成仍在运行，不能作为合法修复。

## 已核实环境

- 工厂仓库：`D:\Quant\BridgeForge`
- 工厂 HEAD：`352f227f477c234de18bef3e6f0ba2c73f1d450d`
- 工厂 VERSION：`1.4.9`
- 当前用户产品 home：`C:\Users\bridg\.bridgeforge-codex`
- 已安装产品版本：`1.4.7`
- 真实下游：`D:\Quant\causis_risk_suite`
- 下游升级前骨架版本：`0.94.2`
- 下游 Python：`.venv\Scripts\python.exe`，3.12.13
- 下游最终复算 fingerprint：
  `sha256:0c9ab8baac81f3973cd783916841c486a0b8268af02e5d3e9218531a134c3b97`

工厂 1.4.9 与已安装产品 1.4.7 均保留相同的过期注释，因此问题在当前工厂 HEAD 仍可复现。

## 直接证据

### 1. runtime 能力已退休

`templates/managed-skeleton.json` 将 `.codex/hooks/context_warning.py` 声明为
`strategy: retirement`。当前 `templates/AGENTS.md` 不再包含 `[ctx-budget]` 活跃章节；下游新
`hook_dispatcher.py` 的 `user-prompt` 路由只保留 repository state、clarify 与 focus，不再调用
`context_warning.py`。

下游已按用户明确决定删除 `.codex/hooks/context_warning.py`，并从 AGENTS、参考文档与
dispatcher 中退休对应能力。

### 2. 活跃 hooks Template 仍宣称能力存在

`templates/hooks.json:81` 当前内容为：

```text
Routes 3-5 project-memory candidates, then injects repository state, context budget, clarification, and focus signals.
```

真实 runtime 已无 context budget，因此这条 active Template 注释失真。

### 3. 同步器把注释差异当作 dispatcher 冲突

下游将同一字段更正为：

```text
Routes 3-5 project-memory candidates, then injects repository state, clarification, and focus signals.
```

同步器返回唯一剩余 gap：

```text
asset_id=codex.hooks-config
target=.codex/hooks.json
reason=preserved conflicting JSON field: hooks.UserPromptSubmit.dispatcher[user-prompt]
```

最终计划摘要：

```text
status=completed_with_gaps
readiness=degraded
target_readiness=action_required
previous_version=0.94.2
current_version=1.4.7
gaps=1
recommended_selection=R1..R9
```

`anti_drift_hooks.md` 的项目内容已经迁入原生 AGENTS 与参考文档，并恢复为受信任历史副本，
因此重新规划后只剩上述 hooks comment gap。

### 4. 触发机制

`_merge_codex_hooks()` 按 dispatcher stage 查找 handler；候选只有在整个 handler dict 与
Template 完全相等时才视为已满足。`comment` 与命令字段共同参与相等比较，所以纯注释差异也会
进入 `conflicts`，最终由 `_plan_merge()` 转成 readiness gap。

这一 fail-closed 机制本身合理；错误在于 canonical Template 的注释没有随能力退休同步更新。

## 影响

1. 正确退休 ctx-budget 的旧下游无法达到 ready，也不能写入新骨架版本戳。
2. 若用户接受上游旧注释，配置会公开宣称不存在的 runtime 能力，违反证据与配置真实性。
3. 每个从含 ctx-budget 的旧版本升级、并纠正此注释的下游都会遇到同一人工 gap。
4. 项目同步器把产品内部一致性错误呈现为“用户手工冲突”，导致用户无法通过正式事务收口。
5. 当前 `causis_risk_suite` 已完成其他骨架迁移和硬闸验证，但必须保留 0.94.2 旧戳，不能宣称
   升级完成。

## 历史推荐修复（1.4.10，已被 current-only 取代）

1. 将 `templates/hooks.json` 的 user-prompt 注释改为只列真实能力：repository state、
   clarification 与 focus。
2. 同步工厂 dogfood `.codex/hooks.json`，保证 Template 与自身配置一致。
3. 运行 `scripts/rebuild_shared_skill_manifest.py` 更新 `codex.hooks-config` 的
   `current_sha256`、`required_handlers` 中 user-prompt handler hash 及兼容 manifest。
4. 增加回归测试：active AGENTS、active hooks Template、dispatcher stage 和受管 handler
   description 不得再宣称 ctx-budget 存在；历史 migration lineage 可保留旧 hash，不应被误删。
5. 增加真实旧下游 fixture：从含 ctx-budget 的可信 0.94.2 现场更新，正确退休后 plan 必须
   `gaps=[]`，R1..R9 可由一次确认事务执行，并最后写入当前产品版本戳。
6. 作为产品层修复 bump 根 `VERSION`，在 `CHANGELOG.md` 标记 `[product]`，再刷新用户产品
   home 复验真实下游。

不建议放宽 `_merge_codex_hooks()` 对 handler dict 的一致性检查。修正 canonical source 比忽略
comment 差异更简单，也不会削弱 dispatcher 重复、命令漂移或 stage 冲突的 fail-closed 保护。

## 历史验收场景

1. `rg` 检查 active `templates/hooks.json` 和工厂 `.codex/hooks.json`，user-prompt 注释不再包含
   `context budget`；`context_warning.py` 继续保持 retirement。
2. manifest rebuild `--check`、skill metadata、mirror drift、instruction source、project
   structure、factory dogfood 与完整自动测试全部通过。
3. `D:\Quant\causis_risk_suite` 使用刷新后的产品重新 plan，
   `codex.hooks-config` 不再产生 user-prompt conflict。
4. 同一紧邻 plan 的 fingerprint 执行 R1..R9 后，旧 Rule 与旧版本戳按事务退休，
   `stamp_written_last=true`、`rollback_performed=false`。
5. apply 后再次 plan 必须 `safe=[] / risk=[] / gaps=[] / blockers=[]`，项目版本戳等于新产品
   VERSION。
6. 下游 `.codex/hooks.json` 的注释、dispatcher 实际调用链和存在的 hook 文件三者一致。

## 历史六类关闭证据

| 证据类别 | 当前状态 | 关闭要求 |
|---|---|---|
| 源码 | 已验证 | Template 与 dogfood 注释已删除 `context budget`；dispatcher 仍无旧路由；1.4.30 current contract 已完全移除该资产 |
| 产品传播 | 本地发布树已完成 | VERSION 1.4.10、CHANGELOG、handler hash、两份 contract 与 manifests 已同步；产品 home 尚未刷新 |
| dogfood | 已验证相关面 | 相关模块 63/63、mirror、instruction、metadata、structure、manifest 与 diff 硬闸通过；未运行全量 discovery |
| fixture | 已验证 | 0.94.2 legacy AGENTS/ctx-budget 退休场景达到 ready；发布谱系 fixture 25/25 通过 |
| 真实下游 | 未复验 | causis_risk_suite 尚未使用新产品执行 replan/apply/replan，保持原现场 |
| runtime | 配置与模拟已验证 | active user-prompt 注释和 dispatcher 调用链一致；真实 Codex 新会话尚未 smoke |

本表仅记录 1.4.10 时点。当前报告保持 active，只因上文真实下游确认式重建尚未执行；不得
据此恢复 retirement contract 或历史迁移谱系。

## 当前恢复边界

- `D:\Quant\causis_risk_suite` 尚未执行 R1..R9，也未写入新版本戳；本轮未读取后写入该项目。
- 下游保留真实的 hooks 注释，没有用失真 wording 绕过同步器。
- 下游其他硬闸已通过；完整测试为 522 passed、3 个未修改业务 UI 模块的既存失败，已明确不
  纳入本次骨架升级。
- BridgeForge 本地修复已落盘，尚未 commit/push 或刷新用户 product home；失败时可整体回退
  Template、dogfood、contract、tests、VERSION 与 CHANGELOG 的本轮修改。

## 传播四问

1. 层级：产品层，源头是 active Template 与 retirement contract 不一致。
2. 通用性：所有从 ctx-budget 旧版本升级、且保持配置真实的下游均可能受影响。
3. 发布：需要 bump 根 VERSION 并在 CHANGELOG 标记 `[product]`。
4. dogfood：必须同步 `templates/hooks.json`、`.codex/hooks.json`、manifest 与真实下游 fixture。

## 关联记录

- `doc/1_delivery/codex-agents-structure-reorganization/requirements_2026-08-16_codex-agents-structure-reorganization.md`
- `doc/2_bugs/BUG-bridgeforge-codex-145-end-to-end-acceptance-gaps.md`
- `doc/0_architecture/design/codex-project-sync.md`
