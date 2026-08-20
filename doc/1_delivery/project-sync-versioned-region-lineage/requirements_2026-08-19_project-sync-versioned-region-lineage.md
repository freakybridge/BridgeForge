---
status: implemented-awaiting-user-acceptance
next: user_acceptance
scale: M
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
---

# Project Sync Pre-commit Region 单规则需求

## 2026-08-19 用户变更决定：退役历史 Region 规则

用户不接受把旧 marker 与按版本 region hash 作为长期兼容规则。问题 #3 的原 1.4.17 方案保留为
历史实施记录，但不再是目标架构；当前实现必须收敛为以下唯一规则：

1. `codex.precommit` 只声明当前 marker、当前整文件 hash 与当前 managed region hash；禁止在 asset
   或 `region` 中保存 `historical_sha256`。
2. 项目同步器只识别当前 marker。旧 marker 不再自动迁移，必须零写入 fail-closed，等待项目被
   显式适配。
3. release evaluator 必须先严格证明当前文件的 managed region 等于当前 contract。若 Git `HEAD`
   还不是当前 marker，则把这次显式适配保守归类为 `mixed`，不得解析或信任旧 marker/hash。
4. Git `HEAD` 与工作区都使用当前 marker 时，只有 HEAD managed region 也命中当前 hash，才允许
   比较 managed region 与 project extension；漂移、缺失、重复或倒序继续 fail-closed。
5. CausisRiskSuite 当前工作区已经显式使用新 marker；本轮以其为真实项目验收样本，必须证明
   `PROJECT_EXTENSION` 逐字保留。不得手工改戳、commit 或 push。

本变更规模仍为 M：45 分钟、20k 新增 token（估算，未实测）、最多 1 个独立审计 agent、最多
2 轮实质验证。用户已明确选择开始实施。

## 1.4.17 历史方案（已被 1.4.19 单规则方案取代）

以下内容只保留 1.4.17 的问题现场、当时方案与验收记录，不再描述当前产品行为。

## 原始需求摘要

修复问题 #3：当前 manifest 重建器只用当前 contract 的 region marker 扫描所有历史发布，
并按 digest 全局去重，导致使用旧 marker 的可信发布无法在自己的版本名下获得 region 凭证。
同步器因此无法证明 CausisRiskSuite Git `HEAD` 中官方 `0.94.2` pre-commit 受管区。

## 任务规模与预算

- 规模：M。改动跨历史 contract 读取、region lineage 重建、release evaluator fixture、产品传播和独立审计。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算；平台无法可靠实测）。
- agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多 2 轮实质验证；权限重试和代码未变的同集补跑不单独计轮次。
- 超预算停止点：需要修改 #4 AGENTS 证明规则、需要真实下游 apply、或需要第二次实质修复后再次验证。

## 已核实事实

1. CausisRiskSuite Git `HEAD` 的旧戳为 `0.94.2`，旧 contract 使用稳定 asset id
   `codex.precommit`、strategy `region` 和旧 marker
   `BRIDGEFORGE_MANAGED_BEGIN/END`。
2. 当前 contract 的同一 asset 使用新 marker `BRIDGEFORGE_CODEX_MANAGED_BEGIN/END`；其
   `region.historical_sha256` 没有 `0.94.2` 条目。
3. BridgeForge 官方 `0.94.2` revision 为 `f16792cb5ab72608daa81f9efeba5c95cf37f209`。
   官方受管区与 CausisRiskSuite `HEAD` 受管区 SHA-256 均为
   `55EFDC67B19805CD224F56601276BF7A04E9A0F0CD432BD4F1C90650C2BB9B8B`。
4. 两份整文件不同是因为 CausisRiskSuite 的 project extension；该扩展不属于 BridgeForge
   region ownership，必须逐字保留。
5. `_merge_region_history()` 当前固定使用当前 asset 的 begin/end，并用跨版本 `known` 集合跳过
   重复 digest；因此 marker 改名和多个版本共享同一内容时都可能缺失精确版本凭证。

## 目标与用户可见行为

1. 重建器必须按稳定 asset id 读取每个官方历史版本自己的 contract、source 和 region marker，
   从该版本官方 source 提取受管区并把 hash 登记到同一个历史版本名下。
2. 每个支持且声明该 region asset 的版本都必须有自己的精确凭证；禁止因为 digest 与其他版本
   相同而省略版本键。
3. release evaluator 继续使用 `old_version` 精确凭证；不得退回“任意历史版本 hash 都可放行”。
4. CausisRiskSuite 的官方 `0.94.2` 受管区应通过只读 Planner；project extension 变化不得造成
   region 身份失败，且必须保持原字节。
5. 受管区任意字节漂移、marker 缺失/重复、历史 asset id/strategy/source 不可证明时继续零写
   fail-closed，并输出稳定 asset/target/reason。

## 不做

- 不为 CausisRiskSuite 写路径、仓库名或固定 hash 特判。
- 不手工编辑生成后的 contract hash，不从真实下游反向吸收凭证。
- 不修 #4 AGENTS projection/parser、#5 hooks canonicalization 或后续 Native Memory/M2 问题。
- 不对四个真实项目执行 apply、写版本戳、commit 或 push。

## 实施计划

1. 修改 `scripts/rebuild_shared_skill_manifest.py`：region history 按历史 stable asset id 获取当时
   contract/source/marker，并按版本登记 digest；无法验证历史 region contract 时 fail-closed 或跳过
   明确未声明该 asset 的版本，禁止静默借用其他版本凭证。
2. 在 `scripts/tests/test_bridgeforge_codex_project_sync.py` 覆盖官方历史 contract 的 marker 迁移、
   `0.94.2` 精确凭证和每版本登记；在 `scripts/tests/test_git_sync_version_release.py` 覆盖旧 marker
   transition、project extension 保留和受管区漂移阻断。
3. 产品升至 1.4.17；用官方重建器传播 Template、dogfood contract 和 active manifest，更新
   CHANGELOG、本卡、源 Bug 与文档索引。
4. 运行相关回归、manifest 与发布硬闸；对 CausisRiskSuite 只读 replan，确认 pre-commit G 项
   消失而 #4 AGENTS 项仍保留；最后由独立 agent 审计本轮改动。

## 验收标准

1. 当前 contract 的 `codex.precommit.region.historical_sha256["0.94.2"]` 包含官方旧 region hash。
2. 所有可从官方历史 contract 唯一证明的 region baseline 都在自己的版本键下登记 hash。
3. 官方旧 region + 任意 project extension 可完成 transition，项目扩展逐字保留并正确分类。
4. 旧 region 内改一个字节、旧 marker 缺失/重复或 hash 只属于其他版本时零写阻断。
5. Template/dogfood contract 相同，manifest `--check`、mirror drift、skill metadata、project
   structure、instruction source 与 `git diff --check` 通过。
6. CausisRiskSuite 只读 Planner 不再输出 `codex.precommit` lineage G 项；不执行 apply。
7. 独立审计无 Blocker / High，Medium 必须修复或明确经用户接受后才能关闭 #3。

## 风险与回滚边界

- region history 会由“只记录变化点”改为“每个可证明版本都有凭证”，contract 体积会增加，
  但换取 `old_version` 精确验证与可审计性。
- 历史 contract 若声明 region asset 但 source/marker 无法唯一提取，重建必须报错，禁止生成宽松凭证。
- 任何实现失败仅回滚本轮 BridgeForge 文件；禁止 reset/restore 用户既有 dirty 内容。
- 本轮不自动 `git add`、commit 或 push。

## 实施记录

- `scripts/rebuild_shared_skill_manifest.py::_merge_region_history()` 现按稳定 asset id 读取每个
  baseline revision 自己的 contract、source 与 region markers；声明不完整、source 缺失或 markers
  无法唯一提取时直接报错，明确未声明该 region asset 的版本才跳过。
- 相同 region digest 会在每个可证明的版本键下分别登记，不再跨版本去重。
- 产品已升至 1.4.17；Template、dogfood contract 与 active manifest 已由官方生成器传播。

## 验证记录

- 最小正反例：
  `.venv\\Scripts\\python.exe -B -m unittest -v scripts.tests.test_git_sync_version_release.VersionReleaseTests.test_contract_transition_uses_versioned_region_and_preserves_project`
  为 1/1 通过。
- 正式相关回归：
  `.venv\\Scripts\\python.exe -B -m unittest scripts.tests.test_git_sync_version_release scripts.tests.test_bridgeforge_codex_project_sync`
  第二轮为 88/88 通过。
- `codex.precommit.region.historical_sha256["0.94.2"]` 包含
  `sha256:55efdc67b19805cd224f56601276bf7a04e9a0f0cd432bd4f1c90650c2bb9b8b`；
  Template 与 dogfood contract 无差异。
- manifest `--check` 返回 `already current`；mirror drift、skill metadata、project structure、
  instruction source 与 `git diff --check` 均 exit 0。project structure 只有既有归档 advisory。
- 对 `D:\\Quant\\causis_risk_suite` 的 1.4.17 只读 update plan 中，`codex.precommit` 不再出现
  gap、blocker 或 required action；唯一 G1 为后续 #4 的 `root.agents`。未执行 apply 或写入。
- 首次独立审计发现 1 个 High、1 个 Medium：损坏历史 contract 与“明确未声明 asset”未区分，
  且缺少错误版本凭证、marker 缺失/重复反例。实现现已区分 schema v1 显式 target region、
  schema v2 stable asset id、合法 absence 与损坏/重复/歧义，并补齐对应 fail-closed 测试。
- 独立复审确认先前 findings 已关闭，最终 Blocker / High / Medium / Low 均为 0；最小复审
  4/4 通过。#3 技术实现可关闭，等待用户验收。

## 1.4.19 当前实施结果

- `codex.precommit` 当前 contract 的 asset 与 `region` 均不再携带 `historical_sha256`；仅保留
  当前 source hash、当前 marker 与当前 managed region hash。
- 官方重建器已删除 `_merge_region_history()`，不再读取或生成任何历史 region contract/hash；
  Template、dogfood 与 active manifest 已传播至 1.4.19。
- 项目同步器只识别 `BRIDGEFORGE_CODEX_MANAGED_BEGIN/END`。仅有旧 marker 的工作区保持原样，
  输出 region ownership gap，禁止自动迁移或写戳。
- release evaluator 允许读取已由整体 contract hash 证明的历史 contract，但不使用其中的旧
  region marker/hash 作决策。当前工作区 managed region 必须命中 current hash；HEAD 无当前
  marker 时视为显式适配并归类 `mixed`；HEAD 已有当前 marker 时也必须命中 current hash，
  否则 fail-closed。
- 相关回归最终 106/106 通过；manifest `--check` 为 `already current`，mirror drift、skill
  metadata、project structure、instruction source 与 `git diff --check` 均 exit 0。structure 仅有
  既有 archive advisory。
- CausisRiskSuite 1.4.19 零写 Planner 返回 `readiness=ready`、
  `release_preflight_status=passed`、`release_preflight_classification=mixed`，无 gap、blocker 或
  required action；`codex.precommit` 不在写入 actions 中，现有项目 extension 保持不变。
- 未对 CausisRiskSuite 执行 apply、写戳、commit 或 push；其他真实项目与 Native Memory hooks
  均未触碰。独立审计首次发现的 current-marker HEAD/current hash 与 dogfood 传播两个 High 均已
  修复；最终 Blocker / High / Medium / Low 均为 0。

## 2026-08-19 CBA 真实 Apply 复验：显式适配没有事务入口

- 先前把问题 #9 归并为“只有 CBA 下游尚未适配”是不完整结论，现由真实 Apply 推翻。1.4.22
  Planner 能准确输出 `codex.precommit G1`，但 G 项按产品契约不可执行，CLI 也没有传入显式适配
  决定的参数；因此用户已经批准当前单规则后，仍无法通过官方事务完成适配。
- CBA 紧邻计划 fingerprint 为
  `sha256:04853d8dac6726f1cccd3908b080a0f2501d574808d3fe8a6c8bc42d5c5423c0`；正式 Apply 返回
  `planned release preflight rejected the prospective update; zero writes performed`，
  `release_preflight_status=blocked`、`stamp_written_last=false`、`rollback_performed=false`。
- Apply 前后 HEAD 均为 `eba2fe264b6870c5f865ac344e5f5f63f3bf9005`，dirty 路径数均为 6，
  status SHA-256 均为
  `1572749f3373a11f37d6601719dd6d8dbdf4ceed5db516df01f6fc4997a45739`；pre-commit、版本戳、
  hooks.json 与 contract 四个关键文件 hash 逐项未变。
- 关闭 #9 需要产品提供受 fingerprint 保护、可审计且能被 project-sync 与后续 `$git-sync` 共用的
  显式适配路径；不得恢复历史 region 规则、手工改受管区、先提交混杂工作区或写戳绕过。
