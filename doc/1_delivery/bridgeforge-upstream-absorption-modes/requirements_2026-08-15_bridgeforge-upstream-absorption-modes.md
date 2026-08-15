---
title: BridgeForge 上游吸收模式需求确认卡
status: implemented
date: 2026-08-15
source: confirm
handoff: user_trial
---

# BridgeForge 上游吸收模式需求确认卡

## 原始需求摘要

BridgeForge 完成核心更新后，不应再把“是否吸收上游变化”留成第二次人工提问。
用户希望把更新力度直接收敛到同一张选择卡：A 激进、B 温和、C 保守；激进模式
默认吸收上游变化，但必须逐项列出冲突文件并强烈警告风险。

## 目标

- 将风险修改、上游吸收和停止完善统一到一张 A/B/C 确认卡。
- 保持每轮 BridgeForge 业务确认总数为 0 次或 1 次。
- 让 A 默认吸收可信受管区块中的上游变化，并明确展示全部冲突影响。
- 让 B 同时接受稳定编号和同一回复中的逐项自然语言修改要求。
- 让 C 保留已完成的 safe 核心更新，不再执行其他修改。

## 不做

- 不允许 A 整文件覆盖项目本地定制。
- 不覆盖项目自有区块、业务规则、memory 正文或非受管文档内容。
- 不把“验证通过”解释为本地业务语义必然保持不变。
- 不为同一轮吸收决策追加第二张确认卡或第二次业务提问。
- 不自动 commit 或 push。

## 任务规模与预算

- 规模：M。
- 判定依据：跨 project-sync、switch、根 skill、模式参考和测试；会改变风险确认与资产
  ownership 的交互契约，但不引入新的同步执行器。
- 时间预算：45 分钟。
- token 预算：约 20k 新增 token，平台无可靠计量器，标记为未实测。
- agent 预算：0 个子 agent。
- 验证预算：最多两轮。
- 超预算停止点：若必须引入通用自然语言解释器、新 ownership 存储或无法在 schema v2
  表达受管区块边界，停止并由用户选择扩大预算或缩小范围。

## 已核实事实

- 当前 action card 只把 `R/C` 作为可选择执行项。
- 本地定制差异当前进入 `M` manual review，因此选择 A 后仍会留下“决定是否吸收”的
  第二阶段人工任务。
- `safe` 项自动执行；现有 A/B/C 分别通过全部确认、稳定编号部分确认和本轮拒绝实现。
- project-sync 与 switch 已有 aggregate fingerprint、事务快照、回滚和 stamp-last 防线。
- 现有双状态为 `execution_status` 与 `target_readiness`，旧 receipt 字段继续兼容。

## 未核实事实

- 各类历史下游文件是否已经包含稳定、可机器识别的 BridgeForge 受管区块边界。
- 自然语言自定义要求能否全部确定性映射到现有 CLI；无法确定时必须零风险写入停止。
- 真实 Codex UI 对超长冲突清单的展示效果尚未验证。

## 已确认业务规则

### 单卡选项

safe 核心更新继续自动执行。存在风险项或上游吸收项时，只展示一次确认卡：

- A 激进更新：执行全部推荐修改，并默认吸收全部可信 `U` 项中的上游受管区块。
- B 温和更新：展示逐项建议；接受稳定编号，也接受同一回复中的逐项文字要求。
- C 保守更新：保留已经完成的 safe 核心更新，本轮不再进一步修改。

当前无需增加第四档；B 的选择能力已经覆盖只选某类修改或只吸收部分区块的需求。

### 上游吸收项

新增 `U1...Un` 稳定编号表示“吸收上游变化”。每项必须包含：

- 冲突文件路径；
- 可识别的 BridgeForge 受管区块；
- 上游将覆盖的内容摘要；
- 本地定制可能受到的影响；
- 是否可事务回滚；
- 推荐与否及理由。

实现时每个 U 对应一个冲突受管区块；同一文件的多个 U 必须分组展示并在 apply 时合并为
一次事务写入，避免多次写入互相覆盖。

`U` 编号、选择和自定义结果必须绑定当前 aggregate fingerprint。未知、重复、过期编号
或计划漂移必须在风险写入前失败。

### A 激进模式

- 冲突区块采用上游优先。
- 只能覆盖文件中可可靠识别的 BridgeForge 受管区块。
- 项目自有区块继续保留，禁止整文件替换。
- 无受管区块边界、边界不可信或路径存在风险的文件不得自动吸收，必须保持未改动并
  进入 manual 或 blocker 清单。
- 执行前建立事务快照；任何验证失败必须完整回滚；全部验证完成后才能写版本戳。

### 强风险提示

A/B/C 选项之前必须在同一张卡中显示醒目警告：

> A 为激进模式：冲突内容以上游版本为准，可能改变或丢失受管区块内的本地定制。
> BridgeForge 会建立事务备份；验证失败会回滚，但验证通过不代表本地业务语义完全保留。

警告后必须逐项列出全部冲突文件与区块影响。禁止先让用户选择 A，再追加文件审阅或
吸收确认。

### B 温和模式

- 支持稳定编号，例如 `B：R1、U2`。
- 支持同一回复中的逐项自然语言要求，例如
  `B：U1；U2 只吸收 hooks 规则，保留模型配置`。
- 自定义要求必须先被解析成明确的逐项执行计划，并与当前 fingerprint 绑定。
- 若要求存在歧义、超出可识别区块或无法确定执行效果，必须零风险写入停止并报告原因；
  禁止猜测、禁止先写一部分后追问。

### C 保守模式

- 只跳过本轮进一步完善，不保存为永久偏好。
- 未选择的风险项和吸收项保持原状，并继续反映在 `target_readiness` 中。
- C 不撤销此前已经成功完成的 safe 核心更新。

## 数据与 receipt 映射

| 语义 | 稳定编号 / 字段 | 执行性 | 备注 |
|---|---|---:|---|
| 必要风险修改 | `R1...Rn` | 是 | 保留现有契约 |
| 可选修改 | `C1...Cn` | 是 | 保留现有契约 |
| 上游吸收 | `U1...Un` | 是 | 仅可信受管区块 |
| 人工步骤 | `M1...Mn` | 否 | 无可信边界或 runtime 操作 |
| blocker | `B1...Bn` | 否 | 路径、ownership、解析或回滚风险 |

receipt 至少新增或扩展：

- `upstream_absorption_actions`；
- `selected_absorption_ids`；
- `custom_absorption_directives`；
- `conflict_file_items`；
- `managed_block_effects`。

旧 `status`、`readiness`、`confirmed-risk`、`selected-risk` 和 `decline-risk` 字段与调用方式
必须继续兼容。

## 拟修改范围

- `scripts/bridgeforge_project_sync.py`：规划、`U` catalog、选择绑定、事务 apply 与 receipt。
- `scripts/bridgeforge_switch.py` 及要求存在的模板 / dogfood 镜像。
- `skills/bridgeforge/SKILL.md` 与 `init/adopt/update/switch` 参考文档。
- `doc/0_architecture/design/codex-project-sync.md`。
- actionable readiness、project-sync、switch、root skill、fixture 与分发测试。
- 产品改动完成后的 manifest、VERSION 与 CHANGELOG。

## 传播四问

1. 该功能属于产品层执行器与用户级 BridgeForge skill，必须进入 `scripts/`、`skills/` 及
   所需模板镜像；需求卡和设计说明属于元文档。
2. 通用交互与执行契约必须写入产品层，不能只修改 BridgeForge 自身配置或文案。
3. 产品层变化必须 bump 版本并记录 `[product]` CHANGELOG。
4. 若实现触及模板 hook/settings，必须同步 dogfood；当前预计不修改 hook/settings。

## 验收标准

- A/B/C、强警告和全部冲突文件清单在一次交互中完整展示。
- A 一次确认即可执行全部推荐风险项与可信上游吸收项，不再二次提问。
- A 仅覆盖受管区块；项目自有区块逐字保留。
- 每个冲突文件均展示路径、区块、覆盖效果和本地影响。
- B 可按编号选择，也可在同一回复中提交逐项文字要求。
- C 不执行进一步修改，且不会持久化拒绝偏好。
- 无边界、歧义输入、未知编号、fingerprint 漂移和路径风险均为零风险写入。
- apply 失败或验证失败完整回滚，验证通过后才写版本戳。
- 整体业务确认保持 0 次或 1 次。
- 双状态和旧 receipt / CLI 兼容测试通过。
- skill metadata、manifest `--check`、mirror drift、harness parity、完整 fixture 与独立发布
  审计通过；真实下游和 runtime 缺少的维度必须标为未验证。

## 合理假设与风险

- 假设 schema v2 可以扩展为区块级 ownership；若只能表达整文件 ownership，则不得用
  字符串启发式冒充可信边界。
- 上游优先会有真实语义风险，事务回滚只能处理技术失败，无法证明业务语义未变化。
- 自然语言 B 不能以不可审计的自由编辑替代确定计划；执行前必须落成可对账 receipt。
- 冲突文件较多时卡片会变长，但禁止为了简短而隐藏文件或把清单延后到第二问。

## 自动化边界

- 允许后续修改当前仓库的产品执行器、skill、模板镜像、测试、manifest 与设计文档。
- 禁止自动修改用户级已安装 BridgeForge 或真实下游项目，除非另有明确验收授权。
- 禁止自动 commit、push、合并主分支或删除 worktree。
- 发布前必须按项目级 AGENTS.md §7 完成产品传播和发布完整性检查。

## 调用来源与后续交接

- 调用来源：用户针对 BridgeForge `0.93.0` 更新反馈截图提出的交互调整。
- 确认方式：`$confirm` 单题访谈，用户最终选择 A 确认本卡。
- 后续交接：产品实现、用户验收与独立发布复审均完成；进入 `$git-sync`。

## 实施 / 验证记录

- 用户于 2026-08-15 明确调用 `$summary 同意验收`，产品行为验收成立；独立发布审计仍是
  VERSION、CHANGELOG、commit 与 push 前的发布硬闸。
- 已实现 A/B/C 单卡决策、逐受管区块 `U1...Un` 清单、强风险提示、A 全量吸收、B 编号选择与
  同回复自定义指令、C 保守跳过，以及 aggregate fingerprint、事务回滚和 stamp-last 约束。
- 已将 Markdown whole 资产扩展为显式 `managed_blocks`；同一文件选中的多个区块在 apply 时
  合并为一次事务写入，未选区块与项目自有内容保持不变。`.codex/memory/MEMORY.md` 改为
  `seed`：只在缺失时创建，已有内容归项目所有。
- 产品传播已覆盖执行器、Codex schema、BridgeForge skill、设计文档、dogfood schema、四份
  version-release 镜像、测试与 `shared-skill-manifest.json`；本轮未修改 hook/settings。
- 完整回归（区块级重构前）：67 项测试全部通过；完整 downstream fixture 37/37 通过；
  skill metadata、manifest `--check`、mirror drift、harness parity 与 `git diff --check` 通过。
- 区块级最终定向验证：
  `.venv\\Scripts\\python.exe -B -m unittest tests.harness.test_bridgeforge_project_sync`，
  20/20 通过；
  `.venv\\Scripts\\python.exe -B tests\\harness\\run_downstream_fixture.py --case project-sync-absorption-card`，
  真实 CLI 用例通过；manifest `--check` 与 `git diff --check` exit 0。
- 首轮独立 `review-auditor` 未通过并发现三个发布阻断：B 自定义文字未参与执行、
  version-release 把 `managed_blocks` 误判为整文件 ownership、apply receipt 缺少
  `conflict_file_items` / `managed_block_effects`。
- 三个阻断均已修复：B 指令必须确定解析为单个 U 的 `absorb` 或 `preserve`，歧义与区块内
  再细分零写入拒绝；四份 version-release 分离受管标题区块与项目区块并把 `seed` 视为项目所有；
  apply receipt 完整回显冲突卡和逐区块实际效果。
- 修复后验证：相关回归 43/43、完整 downstream fixture 37/37、manifest `--check`、
  harness parity、mirror drift、skill metadata 与 `git diff --check` 全部通过。
- 修复后独立 `review-auditor` 复审通过：真实 CLI 的 preserve / ambiguous / absorb 三条路径、
  四份 version-release ownership、receipt 对账、schema dogfood 与全部发布静态闸均独立验证通过。
- 未验证：真实下游项目中的 Codex UI 展示、runtime trust 与新会话 smoke；这些是已明确的
  非阻塞运行时边界，不替代后续真实使用反馈。
- 尚未执行 VERSION bump、CHANGELOG、commit 或 push；这些属于后续发布 / `$git-sync` 阶段。
