---
title: BridgeForge 双状态与可执行完善清单需求确认卡
status: confirmed
date: 2026-08-15
source: confirm
handoff: develop
---

# BridgeForge 双状态与可执行完善清单需求确认卡

## 原始需求摘要

用户反馈下游 `/bridgeforge` 虽完成核心更新，却以 `completed_with_gaps`、
`readiness=degraded` 作为主要结论；用户无法直接判断更新是否成功、距离完全就绪还差什么、
谁能处理以及需要怎样确认。用户要求引入双状态，保留整体 0 次或 1 次确认，并在存在可执行
完善项时提供 A 全部、B 自定义部分、C 本轮不再完善的统一选择。

## 目标

- 分开表达“BridgeForge 本轮是否执行完成”和“下游是否完全就绪”。
- 把剩余事项转换成带编号、影响、责任人、推荐值和完成标准的可操作清单。
- 保持 safe 自动执行；全部业务选择仍汇总为 0 次或 1 次确认。
- 同一张卡同时支持程序推荐清单和用户自定义编号组合。
- 让人工步骤保持可见但绝不冒充已执行或已验证。
- 保留现有机器收据兼容性，渐进增加面向用户的状态与 remediation 字段。

## 不做

- 不减少现有 safe / risk / gap 分类、事务回滚、apply 前 replan 或 fingerprint 防漂移。
- 不允许用户选择 planner 没有列出的路径、动作或任意命令。
- 不把 `/hooks` trust、重启、新会话 smoke 或其他人工操作自动标记为完成。
- 不为用户选择 C 新建永久 waiver ledger；C 只作用于本轮。
- 不把可忽略缓存、Git ignored 临时文件或无功能影响的清洁提示单独视为 readiness 降级。
- 不承诺 BridgeForge 能代替平台权限框、用户级 trust 或宿主重启。

## 任务规模与预算

- 规模：M。
- 判定依据：涉及根交互契约、项目同步收据、switch 收据、部分 risk 选择、产品镜像和
  下游 fixture；不改变项目业务数据或引入新的持久化状态系统。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算，平台无可靠精确计量器，未实测）。
- agent 预算：最多 1 个。
- 验证预算：最多两组。
- 超预算停止点：需要新增 waiver/选择 ledger、必须破坏旧 receipt 字段、无法把部分选择
  绑定到当前计划 fingerprint，或验证范围升为全新交互框架。

## 已核实事实

- 截图中的 `0.90.0` 收据把 Git ignored `.pyc` 和无法在沙箱复核的 native memories
  状态都压缩为 `completed_with_gaps / degraded`，但两者的影响与处理责任完全不同。
- 当前根契约只统一要求 `status`、`readiness` 和逐项 gaps，没有强制 remediation、责任人、
  是否必要、是否推荐或完成标准。
- `scripts/bridgeforge_project_sync.py` 当前只支持 `--confirmed-risk` 或 `--decline-risk`，
  不能表达同一张卡内的 risk 子集。
- project sync 与 switch 已有 deterministic plan、risk fingerprint、apply 前重算和漂移零写入
  边界，可以作为部分选择的安全基础。
- update 手册已要求 hook trust 与新会话 smoke 未完成时报告“未验证”，但没有规定如何进入
  面向用户的行动清单。

## 双状态模型

### 1. 执行状态

回答“BridgeForge 本轮能自动做的事情是否完成”。用户字段为 `execution_status`，至少支持：

- `completed`：本轮 safe 与已授权动作完成并通过对应验证。
- `failed`：planner、事务、回滚或必要验证失败。
- 只读 plan 可继续保留现有 `planned` 语义，但不得伪称执行完成。

### 2. 目标就绪度

回答“下游距离完全就绪还差什么”。用户字段为 `target_readiness`：

- `ready`：没有必要完善项或未完成的人工验证。
- `ready_with_advisories`：完全就绪，但仍有不影响功能的可选清理。
- `action_required`：核心更新已完成，仍有必要动作或人工步骤。
- `blocked`：核心更新或必要验证被阻断，不能宣称可继续完成。

旧 `status=completed|completed_with_gaps|failed` 与
`readiness=ready|degraded|blocked` 在兼容期内继续输出；面向用户的标题和行动清单以新字段
为准，旧字段移入技术收据，禁止继续作为主要结论。

## 清单数据映射

每个剩余事项必须归入且只归入以下一类：

| 类别 | 编号 | 是否影响完全就绪 | 能否进入 A/B | 示例 |
|---|---|---:|---:|---|
| 必要可执行项 | `R1...Rn` | 是 | 是 | 可确定修复、重新验证、受控迁移 |
| 可选可执行项 | `C1...Cn` | 否 | 是 | 无功能影响的缓存清理 |
| 人工步骤 | `M1...Mn` | 按事项 | 否 | `/hooks` trust、重启、新会话 smoke |
| blocker | `B1...Bn` | 是 | 否 | 不安全路径、planner 失败、无法回滚 |

每项至少包含：

- `id`、`title`、`category`；
- 当前状态、目标状态与直接证据；
- 是否影响完全就绪；
- 动作、source / target（适用时）、影响与可恢复性；
- `executor=bridgeforge|user`；
- `recommended=true|false` 与推荐理由；
- 完成后的机器可核验标准；
- 是否可能触发独立的平台权限提示。

Git ignored 且不影响受管资产的 `__pycache__` / `.pyc` 只能进入 `C` 类 advisory；它可以被
A 全选，但保留时不得阻止 `ready` / `ready_with_advisories`。

## 单次确认契约

safe 项始终自动执行，不进入业务确认卡。存在 `R` 或 `C` 可执行项时，只展示一张按稳定
编号排序的统一卡：

```text
推荐清单：R1、R2
全部可执行项：R1、R2、C1

A. 全部确认：执行 R1、R2、C1
B. 部分确认：在同一次回复中填写编号，例如 B：R1、C1
C. 不再进一步完善：本轮不执行这些项目
```

- A 执行卡片中全部 `R` 与 `C` 项，包括可选清理。
- B 接受程序推荐组合，也接受用户在同一回复中给出的任意合法 `R/C` 编号组合。
- C 只对本轮有效；safe 继续，未执行项进入本轮收据，下次 `/bridgeforge` 重新盘点并展示。
- 用户的一次 A/B/C 回复是唯一业务授权；禁止随后逐项追问。
- 只有 `M` 人工项或 blocker、没有 `R/C` 时，业务确认次数为 0，不展示空的 A/B/C 卡。
- B 缺编号、包含未知/重复编号或选择 `M/B` 项时，风险写入为零并提示合法语法；无效输入
  不算授权。
- 不可避免的平台权限框必须在项目卡中提前标注，但不得再制造第二轮 BridgeForge 业务选择。

## Fingerprint 与部分 apply

- 统一卡必须包含当前 canonical plan 的 `aggregate_fingerprint`。
- A/B/C 返回后，所有 planner 必须紧邻重跑；plan fingerprint 不一致时风险项零写入并停止。
- B 的 canonical selected IDs 必须排序、去重并验证属于当前卡；选集与 aggregate fingerprint
  一同绑定到 selection receipt，禁止把旧卡选集套到新计划。
- apply 只接收已验证的 selected IDs；未选 risk 原样保留并进入本轮 receipt。
- 任一选中动作失败时继承现有事务回滚与 stamp-last 规则，禁止只完成一部分却报告成功。

## 用户文案契约

最终输出顺序固定为：

1. 一句话结论：核心更新是否完成、距离完全就绪还差几项。
2. 双状态摘要：`execution_status` 与 `target_readiness`。
3. 已自动完成清单。
4. `R/C/M/B` 分区行动清单。
5. 推荐组合与唯一 A/B/C 卡（仅有可执行项时）。
6. 选择后的已执行、未选择、人工待办和验证收据。
7. 默认折叠的兼容机器字段与诊断证据。

用户标题只使用：

- `完全就绪`；
- `核心更新完成，还需用户完成 N 项`；
- `完全就绪，另有 N 项可选清理`；
- `更新被阻断`。

人工步骤必须明确“需用户手动完成”。A/B 只授权 BridgeForge 可执行项；即使选择 A，也
禁止把 M 项写成完成。收到真实 trust / restart / smoke 收据后才能更新其状态。

## 拟修改

- `skills/bridgeforge/SKILL.md`
- `skills/bridgeforge/references/update.md`
- `skills/bridgeforge/references/switch.md`
- `scripts/bridgeforge_project_sync.py`
- `scripts/bridgeforge_switch.py`
- `templates/claude/scripts/bridgeforge_switch.py`
- `tests/harness/test_bridgeforge_root_skill.py`
- `tests/harness/test_bridgeforge_project_sync.py`
- `tests/harness/run_downstream_fixture.py`
- 必要的 shared manifest、managed contract、parity 文档与本 topic 记录

实现时若 init/adopt 或用户级 maintenance 仍由自然语言编排而非共享 renderer 输出，必须在
根契约中复用同一字段与文案顺序；禁止复制出第二套含义不同的状态模型。

## 验收

- 无 `R/C` 时确认次数为 0；存在 `R/C` 时只出现一张卡和一次有效 A/B/C 授权。
- A 执行全部当前可执行项；B 只执行同一回复中的合法编号；C 本轮全部跳过。
- 程序同时输出推荐组合并接受不同的用户自定义组合。
- B 的 selected IDs 与当前 aggregate fingerprint 绑定；漂移、未知 ID 和旧卡均零风险写入。
- safe、未选项、manual、blocker 和 optional advisory 在收据中可独立对账。
- 人工步骤始终保持未验证，直到真实 runtime 收据存在。
- 无害缓存不再单独触发 degraded；必要 gap 仍不得被 advisory 掩盖。
- 旧 status/readiness 字段和既有下游解析继续通过，新增字段驱动清晰用户输出。
- project sync 的全部确认、部分确认、全部拒绝、回滚、fingerprint drift 与幂等均有测试。
- switch 的状态映射、风险选集和镜像一致性有测试或下游 fixture 收据。
- 两组验证必须记录真实命令、断言和覆盖场景；缺少 runtime smoke 时明确标记未验证。

## 合理假设与风险

- 当前 BridgeForge 没有统一的 UI renderer；第一版可能由结构化 receipt + 根 skill 文案契约
  共同实现，但字段语义必须只有一份事实源。
- 部分 risk apply 会扩大执行器状态空间，必须优先保证 transaction、rollback 与 stamp-last，
  不能为了交互灵活牺牲原子性。
- 平台审批不完全受 BridgeForge 控制；只能提前披露，不能承诺绝对没有系统权限提示。
- 用户选择 C 不持久化，因此相同未解决项会在下次运行再次出现，这是已确认行为。

## 自动化边界

- 允许修改当前仓库的产品 skill、同步执行器、模板镜像、测试、manifest 与本 topic 文档。
- 禁止在确认卡交付阶段修改代码、版本、CHANGELOG、用户级 BridgeForge 或任何下游项目。
- 后续实现不得自动 commit / push；发布仍须用户显式调用 `$git-sync`。

## 调用来源与后续交接

- 调用来源：用户针对 `0.90.0` 下游收据截图的交互反馈，经 `$confirm` 单题访谈收敛。
- 后续交接：待用户选择 `develop`、`debate` 或 `collab`。

## 实施记录

- 2026-08-15：用户选择 `$develop` 开始实施；保持 M 级 45 分钟 / 20k token 估算（未实测）/
  最多 1 agent / 最多两组验证预算，实施阶段不启用子 agent。
- 实施计划：先扩展 project-sync 的兼容 receipt 与部分 risk 选集，再同步 switch 与根文案契约，
  最后重建 manifest 并执行两组定向验证。
- 2026-08-15：project-sync 新增 `execution_status / target_readiness / required_actions /
  manual_steps / recommended_selection / selected_action_ids / selection_fingerprint`，并支持重复
  `--selected-risk <Rn>`；旧全部确认和全部拒绝参数保留。
- 2026-08-15：switch 新增同一 R 编号、推荐清单、`action_card`、部分选择和本轮全拒绝；
  command bundle、Claude 模板与 dogfood 三份脚本一致。
- 2026-08-15：根 skill 与 init/adopt/update/switch 手册统一采用双状态、R/C/M/B 分区和
  单张 A/B/C 卡；无害 `__pycache__` / `.pyc` 只能作为 advisory。

## 验证记录

- 第一组：`.venv\\Scripts\\python.exe -B -m unittest
  tests.harness.test_bridgeforge_actionable_readiness
  tests.harness.test_bridgeforge_project_sync tests.harness.test_bridgeforge_root_skill`，29 项全部通过；
  覆盖全部/部分/拒绝、未知与重复编号、selection fingerprint、事务/版本戳、switch 选集、
  双状态和根 0/1 次确认契约。首次发现 schema 基线测试漏列已发布 `0.92.0`，补齐后通过。
- 第二组：`test_shared_skill_distribution` 25 项全部通过；下游 fixture
  `switch-retired-stall-warning` 与 `switch-script-mirrors` 全部 PASS，覆盖受管退役、人工修改
  保留、双状态/action_card 和三份脚本镜像。fixture 首次仅因沙箱 ACL 无法创建临时目录，
  同命令窄权限重跑后进入断言；随后补齐 dogfood 镜像并通过。
- `rebuild_shared_skill_manifest.py --check`、`harness_parity_check.py --check`、
  `skill_metadata_check.py`、`mirror_drift_check.py` 与 `git diff --check` 最终均 exit 0。
- 未验证：真实 Codex UI 对 A/B/C 文案的人工试用、平台权限提示和新会话 hook/trust smoke。
