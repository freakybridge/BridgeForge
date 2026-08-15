# Switch 双骨架直接同步手册

仅当根 `SKILL.md` 命中显式 `switch` 时读取本文件。执行前必须已通过 Python 3.11+
preflight；本手册只使用本轮锁定的 `$HOOK_PYTHON`。switch 的固定含义是：把另一套
项目骨架的当前语义同步为当前宿主可执行的原生资产，然后留在当前宿主继续工作。

`.claude/` 与 `.codex/` 是长期共存的项目资产。source 始终保持不变；禁止通过删除、移动或归档 source 来完成 switch。

## 1. 唯一用户命令与宿主硬闸

用户只调用：

```text
/bridgeforge switch claude
/bridgeforge switch codex
```

target 必须等于实际承载本轮对话的宿主：

| 当前宿主 | 唯一合法命令 | 底层固定证据 |
|---|---|---|
| Claude | `/bridgeforge switch claude` | `--current-host claude` |
| Codex | `/bridgeforge switch codex` | `--current-host codex` |

入口 wrapper 必须固定传入当前宿主，禁止从用户参数推导、改写或省略 `--current-host`。target 与 current-host 缺失或不一致时，底层脚本必须在盘点同步输入或修改项目文件前报错。

主对话按当前宿主执行 command bundle 内对应模板脚本：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "scripts\bridgeforge_switch.py") `
  $CURRENT_HOST `
  --current-host $CURRENT_HOST `
  --template-root "$BRIDGEFORGE_HOME"
```

`--current-host`、`--template-root` 及其他底层参数不属于用户命令面。禁止要求用户创建、编辑或传入 manifest；direct-sync 没有人工 manifest 阶段，也不得新增或宣传 `migrate`、`migrate-layout` 等并行入口。

cwd 是唯一项目根。若 cwd 是 BridgeForge 源头仓库，立即拒绝。switch 不执行 `git add`、`commit`、`push`、`stash`、`merge` 或 `reset`。

## 2. 同步表面与单一事实源

每次 switch 都从当前真实文件重新盘点：

- source 骨架目录及其 `.bridgeforge-map.json`；
- target 骨架目录及其 `.bridgeforge-map.json`；
- 与两侧骨架相关的根入口文件，仅用于分类和报告。

真实 `.claude/`、`.codex/` 文件是资产正文的唯一事实源。map 不是正文副本，也不自证 provenance。

根 `CLAUDE.md` 与 `AGENTS.md` 不属于 direct-sync 自动写入表面：盘点到的根入口语义只报告为已保留或 `untranslated`，不得自动覆盖另一根入口。它们继续由各宿主的 init/adopt/update 流程维护。

根 `.githooks/pre-commit` 同样不属于 direct-sync 表面。switch 前后必须保持其字节哈希不变；项目专属提交检查只能由 init/adopt/update 的受管区块合并流程维护。

target map 固定放在目标骨架内：

```text
.claude/.bridgeforge-map.json
.codex/.bridgeforge-map.json
```

map 纳入 Git，使用确定性格式化 JSON；禁止写入绝对机器路径、时间戳、资产正文、命令、模块路径或可执行 patch。map 只记录稳定语义组、项目相对路径、内置 adapter id/version、selector、hash、映射状态和冲突/未转译原因。

同一语义组允许一对多和多对一。组内成员整体提交或整体进入冲突；禁止只更新一半后把该组标为成功。

## 3. 原生转译与回声抑制

禁止把另一宿主的专属资产原样复制到 target，包括 hooks、settings、agent 配置、skills、入口格式及其他只在 source 宿主生效的文件。可表达的项目意图必须通过内置 allowlist adapter 生成 target 宿主原生 projection；未知 adapter 绝不从项目或 map 动态加载。

每轮同时读取 source map 与 target map：

- source 中未被人工修改的 generated projection 必须抑制回声，不能反向当作新的项目意图；
- source projection 已偏离其生成 hash 时标记 `forked_projection`，保留真实 source，不自动回灌；
- target 只有在 live 文件或 JSON selector 的当前 hash 等于 map 中 `last_generated_sha256` 时，才允许自动更新或删除；
- target 被人工修改、map 缺失/非法、schema/path/hash/adapter/selector 校验失败或 map/live 不一致时，保留 target 并输出冲突；禁止把观测到的人工 hash 晋升为新生成基线。

共享 JSON 配置只允许内置 adapter 声明的非重叠 JSON Pointer selector。未支持的 TOML、自由文本共享配置或无法等价表达的宿主能力标记 `untranslated`，不得伪装为已同步。

## 4. 同步计划与受控提交

底层脚本支持 `--dry-run` 只读计划；主对话必须先把它与其他 planner 汇总，禁止边盘点边
询问。safe projection 在无 risk 时零确认 apply；确定性删除进入唯一 risk 卡；冲突只形成
gap。apply 仍由底层一次完成校验和提交，不向用户暴露可编辑 manifest：

1. 校验 target/current-host、模板来源、项目边界、双 map schema、相对路径、Windows canonical collision、link/junction/reparse point、adapter、selector 与 hash。
2. 盘点 source/target 当前真实文件，识别 clean projection、forked projection、目标人工修改、untranslated 与可安全更新的语义组。
3. 在临时区生成 target 原生 projection；提交前重读双 map、source 项和全部 target write/delete pre-state，任一输入漂移都使相关组保留并冲突。
4. 以同目录临时文件和原子替换提交单文件。先完成写入/更新，再删除已由 target map 和 live hash 共同证明为 clean generated projection 的旧输出。
5. map 最后原子替换；随后核对 map 与 live target 的完整关系。只有核对通过才报告该语义组完成。

source 全程只读并在结束时复核 hash。禁止移动、删除、重写或归档 source；source hash 漂移时停止使用旧计划，不得把旧盘点结果强行落到 target。

历史 `stall_warning.py` 只有在 target 字节 hash 等于 BridgeForge 冻结的 LF/CRLF 受管
副本时才可列为退役 risk；人工修改副本必须保留并报告
`gap:retired-file-modified`。获准后应重跑 `--dry-run` 并核对 aggregate fingerprint，再执行
apply，并传该计划输出的 `--confirmed-risk-fingerprint`；脚本缺少或收到旧 fingerprint 时
必须零写入失败。禁止因“已退役”无条件强删。

## 5. 缺口、冲突与 readiness

`untranslated`、`stale`、`forked_projection`、`conflict` 或 `interrupted-or-modified` 不阻断其他无路径碰撞、无共享成员的语义组同步。

输出状态固定为：

| 结果 | `status` | `readiness` |
|---|---|---|
| 所有已识别语义组均完成且无缺口 | `completed` | `ready` |
| 已完成安全同步，但仍有未转译、过期、分叉或冲突 | `completed_with_gaps` | `degraded` |
| 宿主不匹配、项目边界/路径安全失败或执行异常无法安全完成 | `failed` | `blocked` |

`completed_with_gaps` 是完成态，不是整体失败；必须列出每个 gap/conflict 的 source、target、状态和原因。它只表示当前宿主可以继续工作，不表示两侧能力完全等价。

target map 缺失、损坏或不可解析时，仍可写入与现有 target 无歧义、无碰撞的新资产；对任何可能属于用户或旧生成结果的 target 一律保留并报告冲突。禁止因 map 异常静默覆盖或删除。

这类新建项标为 `created_unowned`：可以存在于新 map 中用于报告，但不写 `last_generated_sha256`，因此不会取得后续自动更新、删除或 ownership 认领资格。

## 6. 遗留根目录与故障边界

若项目根存在旧 `.bridgeforge/`，只检查其路径是否存在并提示“旧 direct-sync 不使用该目录，可由用户另行手工处理”。switch 禁止读取目录内容、写入、迁移、归档或删除它，也不得创建新的根 `.bridgeforge/`。

direct-sync 不创建 archive、migration receipt、lineage、active marker、transaction journal 或恢复目录。目标 map 是唯一持久同步元数据，但不保存资产正文。

对 Python 能捕获的异常，脚本必须用本次临时备份精确恢复全部 target 写入、新建、删除和旧 map，并逐项核对提交前 hash；回滚核验失败时报告 blocked，禁止伪称成功。

kill、强制终止、系统崩溃或断电不承诺跨文件原子性，也不自动恢复。下次运行发现 map/live 不一致时，受影响语义组必须：

- 保留现有文件；
- 报告 `conflict: interrupted-or-modified`；
- 不覆盖、不删除、不认领 ownership；
- 不自动重建缺失输出；
- 不推进 `last_generated_sha256`。

不共享成员且无路径碰撞的独立语义组仍可继续同步。

## 7. 最低收据

最终报告必须列出：

- 实际底层命令与退出码；
- target/current-host 匹配结果；
- source 与 target map 的实际路径和校验结果；
- source 盘点数量及同步前后 hash 不变断言；
- created、updated、deleted、preserved、untranslated、forked 与 conflict 的逐组结果；
- `status`、`readiness` 和 gaps/conflicts 数量；
- target 原生 projection 校验，以及未原样复制宿主专属资产的断言；
- 旧根 `.bridgeforge/` 是否存在及“未读写删”断言；
- 是否发生可捕获异常回滚，或是否检测到硬中断残态。

只有给出真实命令、断言和覆盖场景，才能写“验证通过”。`readiness=degraded` 时必须直接说明仍有哪些能力缺口，禁止用“全部同步成功”掩盖未转译或冲突。
