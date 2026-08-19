---
status: implemented-awaiting-user-acceptance
next: return_to_issue_3_acceptance
scale: M
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
---

# Project Sync AGENTS Zones 单规则需求

## 背景与用户决定

问题 #4 来自 `root.agents` 同时声明 `managed_blocks`、`section_layout` 与
`agents_zones`，release evaluator 在资产 transition 中先进入旧 Markdown projection 分支，
使合法的新 zones 文件被旧规则错误拒绝。

用户明确拒绝长期双规则兼容，并确认全局边界：AGENTS 后续只使用 `agents_zones`；未适配的
旧项目不再自动迁移，必须先做一次显式、可审计的新格式适配。

## 规模与预算

- 规模：M，跨 evaluator、project sync contract、fixture、传播与独立审计。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算；平台无法可靠实测）。
- agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多 2 轮实质验证；权限重试和代码未变的同集补跑不单独计轮次。

## 已核实现场

1. 当前 `root.agents` contract 同时带 `managed_blocks`、`section_layout` 与 `agents_zones`。
2. `_asset_transition()` 在 `agents_zones` 分支之前执行 `managed_blocks` 分支；当前 Causis
   只读 Planner 因此返回 `current managed Markdown does not match its managed projection`。
3. Stratus 主工作区与 Causis 工作区已是 zones 格式但未提交；ClaudeBridgeAssist HEAD 已是
   zones；M2 worktree 仍是旧标题格式。
4. Stratus 主工作区与 M2 属于同一 Git 仓库的不同 worktree，未来真实迁移必须串行。

## 目标行为

1. `root.agents` 当前 contract 只声明 `agents_zones`，不再携带 AGENTS 专用的
   `managed_blocks`、`section_layout`、`trusted_legacy_sha256` 或
   `legacy_section_migrations`。
2. 当前文件带合法 zones 时，仅按 zones 验证公共区与项目专区；公共区漂移继续 fail-closed。
3. HEAD 仍是旧格式、当前工作区已显式适配 zones 时，不再调用旧标题 parser；transition
   保守分类为 `mixed`，不得宣称 skeleton-only。
4. 当前文件不带 zones 时，项目同步器不得自动猜测迁移，必须输出显式 action-required/gap。
5. 项目专区始终 project-owned；同步器不得覆盖、吸收或重新格式化。

## 非目标

- 不删除 `doc/README.md` 等其他资产仍在使用的通用 `managed_blocks` 能力。
- 本轮不对四个真实项目执行写入、apply、写戳、commit 或 push。
- 不顺手修复 #5～#9。

## 实施计划

1. 收敛 Template/dogfood `root.agents` contract，只保留 zones ownership；删除 AGENTS 旧布局
   自动迁移路径或使其对 `root.agents` 不再可达。
2. 修改唯一 release evaluator：当前 zones 严格验证；旧 HEAD -> 新 zones 保守判 mixed；缺失、
   重复、倒序 marker 或公共区 hash 漂移继续阻断。
3. 增加双规则退役、旧 HEAD、新 zones、项目区变化与无 zones fail-closed 回归。
4. 产品升至 1.4.18，传播 Template、dogfood、manifest、VERSION、CHANGELOG 和文档。
5. 运行相关验证，对四项目只读 replan，并由独立 agent 审计本轮改动。

## 验收标准

1. contract 与源码不再为 `root.agents` 选择旧 Markdown ownership。
2. Causis 只读 Planner 的 `root.agents` G 项消失；项目专区不被列为受管写入。
3. M2 旧格式被明确列为需要显式适配，不发生自动写入。
4. zones 公共区合法通过；项目区变化为 mixed；公共区或 marker 漂移零写阻断。
5. Template/dogfood、manifest、相关回归与发布硬闸通过。
6. 独立审计无 Blocker / High；Medium 必须修复或由用户明确接受。

## 风险与停止点

- 这是全局兼容性收缩：未适配 zones 的其他旧项目会 fail-closed，用户已明确接受。
- 若实现需要新增长期迁移 ledger、第二事实源或提交真实项目才能工作，立即停止，不引入隐藏复杂度。
- 不得 reset/restore 现有 dirty 内容，不自动 git add、commit 或 push。

## 实施结果

- 产品版本升至 1.4.18；Template 与 dogfood 的 `root.agents` contract 只保留
  `agents_zones`，并由重建器拒绝 `managed_blocks`、`section_layout` 或
  `legacy_section_migrations` 与 zones 并存。
- 项目同步器遇到无分区 `AGENTS.md` 时只输出一项显式 ownership review，原文件保持不变且不写
  新戳；已分区文件仍只替换精确可信的公共区，项目区逐字保留。
- release evaluator 对无分区 HEAD 保守归类 `mixed`；对旧、新 contract 都已采用 zones 且目标文件
  无内容变化的 ownership metadata transition 允许经过严格验证的合法 no-op。
- 针对性回归：103/103；完整自动测试：264/264；完整 downstream fixture：passed，29 个发布版本中
  27 个可执行迁移样本全部完成。
- 发布硬闸：manifest `already current`；mirror drift、skill metadata、project structure、instruction
  source 与 `git diff --check` 全部 exit 0。structure 仅报告既有 archive advisory。
- 独立审计首次仅发现 1 个 Low（Planner 测试名未真实覆盖重复、倒序 marker）；补齐 missing、
  duplicate、reversed 三个 fail-closed 子例后复审通过，最终 Blocker / High / Medium / Low 均为 0。
- 四项目只读 Planner：Stratus 主工作区无 `root.agents` 项；Causis `readiness=ready` 且
  `release_preflight=mixed`；M2 对无分区 AGENTS 输出唯一 `G1` ownership review；ClaudeBridgeAssist
  的 root AGENTS 合法 no-op 已放行，只剩独立的 hooks dispatcher G 项。
- 未对四个真实项目执行 apply、写戳、commit 或 push；Native Memory 用户级 hooks 未触碰。

## 后续编号归并

- 原清单问题 #7 不是独立产品缺陷，而是本问题 #4 在 Stratus 主工作区与 M2 工作树的真实下游
  适配与验收项。产品阶段不得恢复旧 `.codex/rules/*.md` 兼容规则或放宽 fail-closed ownership。
- 最新零写 Planner 中，Stratus 主工作区把 8 个不可信旧 rule 列为稳定 `G1`～`G8`；M2 同时保留
  无分区 `AGENTS.md` 和同一批退役 rule gaps。两个 checkout 尚未实际迁移，且因共享 Git 状态必须
  在最终项目阶段串行执行 before -> plan -> apply -> validators -> stamp-last -> no-op replan。

## 后续编号归并

- 原清单问题 #7 不是独立产品缺陷，而是本问题 #4 在 Stratus 主工作区与 M2 工作树的真实下游
  适配与验收项。产品阶段不得恢复旧 `.codex/rules/*.md` 兼容规则或放宽 fail-closed ownership。
- 最新零写 Planner 中，Stratus 主工作区把 8 个不可信旧 rule 列为稳定 `G1`～`G8`；M2 同时保留
  无分区 `AGENTS.md` 和同一批退役 rule gaps。两个 checkout 尚未实际迁移，且因共享 Git 状态必须
  在最终项目阶段串行执行 before -> plan -> apply -> validators -> stamp-last -> no-op replan。

## 后续编号归并

- 原清单问题 #7 不是独立产品缺陷，而是本问题 #4 在 Stratus 主工作区与 M2 工作树的真实下游
  适配与验收项。产品阶段不得恢复旧 `.codex/rules/*.md` 兼容规则或放宽 fail-closed ownership。
- 最新零写 Planner 中，Stratus 主工作区把 8 个不可信旧 rule 列为稳定 `G1`～`G8`；M2 同时保留
  无分区 `AGENTS.md` 和同一批退役 rule gaps。两个 checkout 尚未实际迁移，且因共享 Git 状态必须
  在最终项目阶段串行执行 before -> plan -> apply -> validators -> stamp-last -> no-op replan。
