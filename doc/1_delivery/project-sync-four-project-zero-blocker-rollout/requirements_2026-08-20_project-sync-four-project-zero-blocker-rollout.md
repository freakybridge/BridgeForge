---
status: implementing
next: close-issue-9-and-run-product-audit
scale: L
budget: 4_hours_tokens_unmeasured_2_independent_agents_3_validation_rounds
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
supersedes_budget_and_automation_boundary: doc/1_delivery/project-sync-explicit-adaptation-transaction/requirements_2026-08-19_project-sync-explicit-adaptation-transaction.md
final_report: doc/1_delivery/project-sync-four-project-zero-blocker-rollout/report_2026-08-20_project-sync-four-project-zero-blocker-rollout.md
---

# Project Sync 四项目无卡点更新总需求

## 原始需求摘要

用户要求继续修复问题 #1～#9，完成 BridgeForgeCodex 产品测试、传播和独立审计后，依次为以下四个真实项目安装或更新协作骨架，最终不得遗留骨架卡点；如果出现产品缺陷，由主对话自行修复并恢复更新，只有需要业务 ownership 判断、扩大 Git 权限或超出预算时才停止请用户拍板。

目标项目：

1. `D:\Quant\ClaudeBridgeAssist`
2. `D:\Quant\causis_risk_suite`
3. `D:\Quant\StratusAgent`
4. `D:\Quant\CodexWorktree\1d62\StratusAgent`

项目 4 是项目 3 的 Git worktree；两者必须串行处理共享 Git 状态，禁止当成独立仓库并发修改。

## 目标

- 逐项证明问题 #1～#9 已关闭；发现回归时先修产品，再恢复下游更新。
- 完成 BridgeForge 产品层、Template、dogfood、Skill、文档和派生产物的一致传播。
- 通过针对性回归、完整测试、downstream fixture、全部硬闸和独立审计。
- 按 `CBA -> Causis -> Stratus -> M2` 顺序逐个完成真实项目的 `before -> plan -> apply -> validators -> stamp-last -> no-op replan`。
- 保留四项目自有 `AGENTS.md`、hooks、rules、业务代码和全部既有 dirty 修改；无法证明 ownership 时 fail-closed 并记录清单。
- 形成一份可复核的最终综合报告。

## 不做

- 未经用户明确要求，不 commit、不 push。
- 不执行 `reset`、`restore`、清理或覆盖用户内容，不用 stash 或临时提交混杂工作区绕过产品缺陷。
- 不手工修改骨架版本戳，不删除冲突文件，不跳过统一 release evaluator 或 validators。
- 不恢复已被用户否决的旧 ownership、旧 marker、旧 Region hash、旧 AGENTS projection 或旧 hooks 规则。
- 不把四项目未知内容自动吸收为骨架所有；ownership 无法证明时禁止写入该目标。
- 不并行执行 Native Memory 用户级 hooks 的 status、repair、setup 或 reconcile。

## 任务规模与预算

- 规模：L。
- 依据：范围横跨 #1～#9 产品闭环、Template/dogfood/Skill/文档传播、独立审计、四个 dirty 真实项目的串行事务更新，以及共享 Git worktree 和用户级 Native Memory hooks 的并发边界。
- 时间预算：4 小时。
- token 预算：平台无法可靠计量，不设数值硬限。
- agent 预算：最多 2 个独立 agent；只用于职责明确的实现或审计，不代替用户决策。
- 验证预算：最多 3 轮完整验证；定点回归不单独计入完整轮次。
- 超预算停止点：第三轮完整验证后仍存在产品级 High/Blocker、需要改变已确认的单一规则、无法证明下游写入 ownership，或必须取得 commit/push/业务语义授权。

## 已核实事实

1. 问题 #1 已统一 Planner、Apply 与 `$git-sync` 到 `evaluate_release_transition()`，且已通过独立审计；禁止重新实现。
2. 问题 #2～#8 已有实现和阶段审计证据，但在 #9 最终改动后仍必须整体回归，不能只沿用旧收据。
3. 问题 #9 的显式适配事务仍需闭合真实 Stratus retired rules 与 Causis hooks 无旧 managed projection 路径。
4. BridgeForge 当前工作树 dirty，属于本轮和用户既有内容；必须保留，禁止 reset、restore 或覆盖。
5. 四个真实项目均存在 dirty 状态；更新前必须保存可复核的 before 状态和关键 hash。
6. Stratus 与 M2 共享 Git repository 元数据，涉及 HEAD、index、refs、worktree 的动作必须串行。
7. Native Memory 用户级 hooks 是四项目共享资源，任何可能写它们的操作必须全局串行。

## 已确认规则

1. 先修 BridgeForge 产品缺陷，完成定点验证、传播、文档更新和独立审计，随后才允许写真实项目。
2. 每个产品问题必须更新源 Bug 与对应需求卡，并记录源码、产品传播、dogfood、fixture、真实下游和 runtime 六类证据；未执行项明确标为未验证。
3. 每个真实项目更新前记录分支、HEAD、upstream、工作树清单、骨架版本戳、计划 fingerprint 和关键目标 hash。
4. Apply 必须使用刚生成且未漂移的计划；selected adaptation 只接受明确的稳定 G ID，普通 gap 继续整轮零写 fail-closed。
5. Apply 成功必须经过 validators，最后写骨架戳，并立即 no-op replan；任一失败必须回滚本事务写入并保留用户原内容。
6. 下游出现骨架卡点时，先把现场和根因落入本报告，再返回 BridgeForge 修复产品、验证、传播和独立审计；禁止在下游手工绕过。
7. 项目自有专区、external handlers、nested `AGENTS.md`、业务代码和未知内容只允许逐字保留或列为 gap；没有 ownership 证明时禁止收编、删除或格式化。
8. Native Memory status/repair/setup/reconcile 必须串行，并使用当前项目合规 `.venv`；共享 hooks 的锁、CAS、回滚和严格 JSON 规则不得旁路。
9. 不产生 commit 或 push；最终报告必须明确 Git 工作树和远端状态仍未由本轮改变。

## 执行顺序

1. 完成问题 #9 的产品修复，并对 #1～#9 运行整体回归、传播和独立审计。
2. 更新 `ClaudeBridgeAssist`；若闭环成功，再更新 `causis_risk_suite`。
3. 更新主 `StratusAgent`，完成后再更新其 M2 worktree。
4. 汇总四项目收据、未解决风险和未执行权限，写入最终报告。

## 验收

### 产品验收

1. #1～#9 每项都有当前代码、测试、文档和独立审计状态，不以历史记忆代替本轮验证。
2. #9 覆盖 CBA pre-commit、Causis hooks、Stratus retired rules、M2 AGENTS 与 ordinary gaps 的真实形态正反例。
3. Planner 的 `adaptation_eligible` 与实际可构造 action/evidence 完全一致；不得显示可执行却在 proof 阶段必然失败。
4. selected retirement、legacy hooks canonicalization、project/external projection、HEAD/current/contract/aggregate/selection fingerprint 任一漂移均零写阻断。
5. Template 与 dogfood 镜像一致，manifest `--check`、mirror、instruction、structure、skill metadata、`git diff --check`、完整 unittest 与 downstream fixture 全部通过。
6. 独立审计为 Blocker 0 / High 0 / Medium 0；Low 若存在必须先判断是否影响永久回归覆盖，再决定是否关闭。

### 每项目验收

1. before 状态有路径、分支、HEAD、dirty 清单、骨架版本、计划 fingerprint 和关键 hash 收据。
2. Planner 明确 `ready`，或只包含本轮已精确授权且可执行的 adaptation；普通 gap 不得被隐式放行。
3. Apply 使用同一 aggregate fingerprint，事务成功且用户/项目所有内容 hash 保持。
4. validators 全部通过，骨架版本戳最后写入当前产品版本。
5. no-op replan 的 safe/risk/gap/action-required 均为 0，且 release evaluator 返回通过。
6. 更新后 Git dirty 内容只包含 before 已有内容和可解释的骨架事务增量；没有未知删除、覆盖、吸收或格式化。

### 最终报告验收

最终报告必须至少包含：

- #1～#9 的状态、根因、修复位置、验证和独立审计结论。
- BridgeForge 产品版本、传播哈希、完整测试与硬闸收据。
- 四项目各自的 before、plan fingerprint、selected items、实际写入、validators、stamp-last、no-op replan、dirty 保留和剩余风险。
- 所有运行中发现并修复的新增产品卡点；无法关闭的项目或风险必须给出精确清单和停止原因。
- 明确说明本轮未 commit、未 push、未 reset、未 restore。

## 拟修改范围

- BridgeForge：`scripts/`、`templates/`、`.codex/` dogfood、`skills/`、测试、manifest、`VERSION`、`CHANGELOG.md`、源 Bug、需求卡与 `doc/README.md`。
- 下游：只修改 project-sync 事务证明属于骨架 ownership 的目标，以及 Git 忽略的本地收据；项目所有内容只保留不吸收。
- 报告：`doc/1_delivery/project-sync-four-project-zero-blocker-rollout/report_2026-08-20_project-sync-four-project-zero-blocker-rollout.md`。

## 自动化边界

- 允许修改 BridgeForge 产品源码、Template、dogfood、Skills、测试、文档和派生产物。
- 允许在产品独立审计通过后，按既定顺序写入四个真实项目并运行其项目内 validators。
- 允许对共享 Native Memory 用户级 hooks 执行产品流程要求的 status/repair/setup/reconcile，但必须串行、锁内重读并保留第三方 hooks。
- 禁止 commit、push、force、reset、restore、stash、清理用户文件或扩大到四项目以外的真实仓库。

## 合理假设与停止条件

- `.runtime/` 在目标项目中保持 Git 忽略；若未忽略，一次性 proof 必须 fail-closed。
- 项目自有 validators 可在现有依赖环境运行；缺少业务依赖时先证明是否为骨架问题，禁止擅自安装或修改业务依赖。
- 只有遇到业务 ownership 语义选择、需要 commit/push 权限、预算超限或无法证明写入安全时才停止并一次只向用户询问一个问题。

## 后续交接

- 推荐进入 `$develop`，由主对话按本卡执行产品闭环、独立审计、四项目 rollout 和最终报告。
- 如实现中出现需要多个立场裁决的新架构冲突，再单独调用 `$debate`；明确可并行且文件边界无依赖的工作才调用 `$collab`。

## 实施计划

1. 闭合 #9：让 retirement 与 legacy hooks 显式适配的 Planner eligibility、prospective action、ownership evidence 和 evaluator 复验完全一致；项目 external projection 以 Apply 前当前内容为基准并在事务后保持不变。
2. 传播并验证 #1～#9：同步 Template/dogfood、contract 与 manifest，运行定点回归、完整 unittest、downstream fixture、发布硬闸和独立审计。
3. 按 CBA、Causis、Stratus、M2 串行保存 before、执行 plan/apply/validators/stamp-last/no-op replan；新增产品卡点返回第 1 步修复。
4. 更新源 Bug、专项需求卡与本卡验证状态，写最终综合报告。

## 实施记录

- 2026-08-20：确认卡按 L 级预算开工。只读复核证明 Stratus 八个 retired rules 已可构造事务适配，相关 retirement 与 legacy hooks 定点回归 4/4 通过。
- 2026-08-20：真实 Causis Planner 仍将唯一 hooks G1 标为不可执行。根因已收敛为 evaluator 错把 HEAD external handlers 当作当前项目区基准，因而拒绝当前工作区合法新增且被 prospective 原样保留的 `root_hygiene_check.py`；修复正在进行。
- 2026-08-20：#9 已补齐 Stratus retirement 和 Causis hooks 当前工作树 external 基线。按用户裁决，
  hooks 顶层 `description` 属于骨架；产品只接受 current 或可信发布历史中的精确描述值，拒绝任意
  自定义值。真实 Causis 零写 Planner 现为 `safe=13 / gaps=0 / blockers=0`，唯一 G1 可执行；
  定向回归 135/135、manifest `--check` 已通过，等待完整产品回归和独立复审。
- 2026-08-20：独立复审发现真实 Stratus 的 8 个 retirement 只是首层，累计 proof 后还会暴露 24 个
  transition issues。产品已改为递归展开至 evaluator 固定点，并为精确 current canonical 目标加入
  不写盘的 proof-only attest。最终 Stratus 一次列出 32 个 G 且全部可执行；CBA/Causis 保持唯一
  G1 可执行；M2 的 23 个 ordinary gaps 未被放宽。等待最终审计后进入真实项目写入。
