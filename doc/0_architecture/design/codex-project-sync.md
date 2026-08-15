# Codex 项目骨架事务架构

> 状态：implemented（BridgeForge 0.92.0）
> 入口：`scripts/bridgeforge_project_sync.py`
> ownership SoT：`templates/codex/managed-skeleton.json` schema v2

## 结论

Codex 的 `init`、`adopt`、`update` 共用一个项目事务执行器。`/bridgeforge` 只负责平台检查、用户级分发、模式判断和一次 risk 决策，不再由 agent 人工串联 copy、merge、memory lint、finalizer 和版本戳。

`switch` 使用 command bundle 根 `scripts/bridgeforge_switch.py`；Codex 项目内副本已退役。用户级 native memories 与 `create-worktree` 保持独立事务，因为它们分别拥有外部授权/Git 远端和永久 worktree 边界。

## 五个执行域

| 域 | 唯一执行入口 | 边界 |
|---|---|---|
| 用户级 skill 分发 | `bridgeforge_shared_update.ps1` | 用户目录、mutex、账本、目录事务 |
| Codex 项目骨架 | `bridgeforge_project_sync.py` | `init/adopt/update`、逐资产 ownership、ready-only stamp-last |
| 双宿主投影 | 根 `bridgeforge_switch.py` | `.claude` / `.codex` live projection 与 map |
| Codex native memories | `codex_memory_sync.py` | 用户级 memories、GitHub、consent |
| 永久 worktree | `create_worktree.ps1` | Git worktree 与 Codex Desktop deep-link |

## 项目事务

```text
detect mode/version
  -> load schema v2 contract
  -> plan every asset as safe/risk/absorption/gap
  -> plan canonical memory organization
  -> emit aggregate fingerprint
  -> optional single A/B/C decision (aggressive all / selected Rn+Un / conservative)
  -> replan and compare fingerprint
  -> snapshot owned pre-state
  -> apply file/region/merge/memory actions
  -> run canonical validators
  -> ready: write .bridgeforge_version last
  -> degraded: preserve old/no stamp
  -> JSON receipt
  -> caught failure restores every owned pre-state
```

### 行动清单与双状态

planner 把 risk 以稳定 `R1...Rn`、每个上游受管区块吸收以 `U1...Un` 编号输出，并附
`required_actions`、`upstream_absorption_actions`、`conflict_file_items`、`manual_steps`、
`recommended_selection` 和单卡 confirmation contract。A 沿用 `--confirmed-risk` 激进全选；
B 以重复的 `--selected-action <Rn|Un>` 绑定当前 aggregate fingerprint；逐项文字要求必须
被确定解析为每个已选 U 的 `absorb` 或 `preserve` 决策后参与执行，歧义或区块内再细分必须
零写入失败，禁止只存 receipt 而忽略语义。同一文件选中多个 U 时合并为一次事务写入。C 以
`--decline-risk` 本轮全拒绝。全部冲突文件、区块效果和
强风险警告必须在选择前一次展示，禁止 apply 后第二次询问。
`confirmation.options` 是不可改写的用户文案契约；C 始终执行 safe，只拒绝 R/C/U。
`conflict_file_groups` 必须逐 U 展开完整项目相对路径、区块、上游效果、本地影响与可恢复性，
禁止用编号范围或 basename 省略审阅信息。

receipt 同时输出：

- `execution_status=planned|completed|failed`：本轮执行是否完成；
- `target_readiness=ready|ready_with_advisories|action_required|blocked`：距离完全就绪还差什么。
- `conflict_file_items` 与 `managed_block_effects`：完整回显冲突卡及每个 U 的实际吸收/保留结果。

旧 `status/readiness` 字段继续兼容既有消费者，但不再承担用户主标题。人工 trust/restart/smoke
只进入 `manual_steps`，没有真实运行时收据时不得标记完成。

区块渲染按目标位置决定边界：非末尾受管区块与下一标题之间保留一个空行，文件末尾受管
区块只保留一个终止换行。写版本戳前，对本轮实际修改的受管路径执行
`git diff --check HEAD -- <targets>`；失败必须纳入同一事务回滚，禁止留下新版本戳。

### 分类

- `safe`：缺失资产创建、已发布历史 hash fast-forward、显式 region 更新、只增不删 JSON merge。
- `risk`：已知受管历史副本的删除，以及明确/高置信 memory 归位。全轮只允许一次接受或拒绝。
- `absorption`：未知 whole-file hash 但 schema v2 已为该资产登记可信 Markdown 标题区块；A
  在区块内上游优先，区块外项目内容逐字保留。
- `gap`：无可信区块、JSON 冲突、ambiguous memory、非普通文件或 ownership 不足。原样保留，收据降级。
- `blocker`：版本低于 `0.86.0`、版本倒退、路径逃逸/reparse、contract 损坏、验证器不可用。

## schema v2

每个资产必须有稳定 `id`、显式 `target` 和一个 strategy：

| strategy | 所有权语义 |
|---|---|
| `whole` | 仅当前 hash 或已发布历史 hash 可自动替换 |
| `whole` + `managed_blocks` | 未知 whole-file hash 可生成 U 项；只替换逐资产登记的 Markdown 标题区块 |
| `merge` | 只补缺失受管值；冲突字段保留为 gap |
| `region` | 只替换唯一 marker 区域；区域外逐字节保留 |
| `seed` | 只在缺失时创建；既有项目生成内容不再由上游覆盖，例如 memory 索引 |
| `retirement` | 只删除命中已发布历史 hash 的副本，并进入 risk |

禁止 glob ownership。版本戳只参与兼容边界判断，不作为覆盖证据。

历史 lineage 由 manifest 重建器维护：保留既有历史集合，并从 Git 的 `VERSION` 变更提交枚举全部 `0.86.0+` 已发布版本；当前工作版本只进入 `current_sha256`，下次 bump 后自动成为历史基线。`--check` 只比较，不写 manifest 或 contract。

## 事务与验证红线

- apply 必须携带刚展示的 aggregate fingerprint；执行器紧邻 replan，漂移零写入。
- 部分确认的 selected Rn/Un 必须来自同一计划的 canonical executable 排序，并与 aggregate fingerprint
  一同形成 selection receipt；未选项不得写入。
- memory 迁移计划只接受 canonical auditor 的 `explicit` / `high-confidence` 动作并统一列为 risk；ambiguous 结果保留为 gap。
- 验证器必须从 command bundle canonical 模板执行，禁止信任被下游修改的目标 hook 自证通过。
- memory tree 在迁移前纳入事务快照；迁移后任一验证或写戳失败必须恢复路径与字节。
- 仅 `readiness=ready` 时写 `.codex/.bridgeforge_version`，且必须是最后一次写入；存在 gap 或拒绝 risk 时保留旧戳/无戳。

## 性能路径

- 用户级分发始终从 GitHub `main` 建立临时 canonical probe，但稳态只 materialize 根 manifest；两套 ledger 和实际受管目录全部匹配时不展开完整 source、不建事务日志、不重写账本。
- 远端 commit 变化、本地 drift、受管集合变化或账本缺口才关闭 sparse checkout 并验证完整 source。内容 hash 未变的 skill 只刷新 ledger commit，不做目录换包。
- CLI apply 的 plan 本身就是紧邻 fingerprint 校验的唯一 replan；库级 `apply_plan()` 对外部调用仍默认自行 replan，防止展示与执行之间的状态漂移。
- memory schema auditor 与 strict config health validator 在写入后并行启动，两个结果仍全部进入 ready 判定；任何一个失败都回滚，禁止用并行化弱化 stamp-last。
- updater、planner 和 apply 均输出机器可读 `timings_ms`，性能回归以 phase receipt 为证，不以整轮主观等待时间代替脚本耗时。

## 发布防线

- `skill_metadata_check.py` 硬拦 Codex 分发集合、routing 集合、两份 routing 镜像和 global entry 的 AGENTS 登记漂移。
- `managed-skeleton.json` 与 dogfood 镜像由同一重建器生成。
- harness parity 只允许显式 expected-missing、Codex-only 和已分类 adapter。
- Bug 状态必须拆分源码、传播、dogfood、fixture、真实下游和 runtime；静态测试不得冒充 Desktop/hook trust 现场收据。

## 当前现场边界

自动化不能证明 Codex Desktop deep-link 已显示正确项目，也不能替代 `/hooks` trust 与新会话 lifecycle 现场观察。没有现场收据时必须标为未验证。
