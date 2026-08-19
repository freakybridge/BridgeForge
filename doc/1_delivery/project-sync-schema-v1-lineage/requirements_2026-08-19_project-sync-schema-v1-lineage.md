---
status: implemented-awaiting-user-acceptance
next: user_acceptance
scale: M
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
---

# Project Sync 可信 schema v1 Lineage 需求

## 原始需求摘要

修复真实下游 Git `HEAD` 仍为可信 schema v1、当前工作区已经持有可信 schema v2 contract 时，
release evaluator 在核对历史 hash 前先拒绝旧 schema，导致合法连续升级永久阻断的问题。

## 调用来源与后续交接

- 调用来源：九项问题逐项修复中的问题 #2；问题 #1 已由
  `project-sync-single-release-standard` 交付关闭。
- 后续交接：本卡只修 schema v1 lineage。完成针对性验证、产品传播和独立审计后返回主对话，
  再逐项处理 #3～#9；不自动更新真实下游、commit 或 push。

## 目标与用户可见行为

唯一 `evaluate_release_transition()` 必须先证明 schema v1 HEAD contract 属于可信发布历史，再将
旧 ownership 描述映射到 schema v2 的稳定 asset id 与 strategy。证明完整时允许继续执行同一套
asset transition 检查；证明不足时必须在 Planner 阶段零写阻断并输出具体 asset、target 与 reason。

StratusAgent 的只读 Planner 不再返回泛化的
`ownership contract transition requires schema v2`。这不等于强制显示 `ready`：若后续资产历史、
projection 或项目内容仍无法证明，必须显示更精确的 `G*` 项。

## 不做

- 不修 Causis pre-commit history、AGENTS projection/parser、hooks canonicalization、Native Memory
  runtime authority 或 M2 专项迁移。
- 不修改用户级 updater、用户 hooks、Native Memory 内容或远端。
- 不对四个真实项目执行 apply、写版本戳、stash、commit 或 push。
- 不用路径特判、宽松 hash、手工改戳或要求用户先提交混杂工作区绕过 lineage。

## 任务规模与预算

- 规模：M。逻辑跨 schema parser、contract transition、稳定 asset 映射、测试、产品 contract 与发布传播。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算；平台无法可靠实测）。
- agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多两轮；同一轮可包含多条预定验收命令。
- 超预算停止点：需要第三轮实质修复、必须改变本卡准入规则、或必须连带修复 #3～#9 时停止并重新确认。

## 已核实事实

1. StratusAgent Git `HEAD` 的 `.codex/managed-skeleton.json` 为 schema v1，工作区为可信
   schema v2 / release `1.4.11`，当前骨架戳为 `1.4.11`。
2. 1.4.15 Planner 已通过问题 #1 的统一 evaluator 在首次计划零写输出 G1；当前原因是
   `ownership contract transition requires schema v2`。
3. `_parse_managed_config()` 能解析 schema v1；`_classify_contract_transition()` 与
   `evaluate_release_transition()` 随后对 HEAD 调用 `_raw_contract()`，在读取
   `contract_historical_sha256` 前提前拒绝。
4. 当前 schema v2 contract 已登记历史 contract hash、最低支持版本、稳定 asset id、显式 target
   与 ownership strategy；这些证据必须同时使用，不能只凭单一文件 hash 放行。
5. 当前 BridgeForge 工作树包含尚未提交的 #1 与用户既有文档改动；本轮必须增量修改并保留。

## 已确认规则

1. 先验证 HEAD schema v1 原始 payload 命中当前可信 schema v2 contract 对旧版本登记的历史 hash。
2. 旧版本戳必须存在、格式合法且不低于 `minimum_supported_version`。
3. schema v1 的 whole-file / managed-region ownership 必须能唯一映射到 schema v2 的稳定 asset id、
   target 与 strategy；缺失、歧义或不兼容时 fail closed。
4. 映射成功后继续使用现有 asset transition 检查，不建立第二套 release 合格标准。
5. project-owned、未知和人工定制内容必须逐字保留；无法证明 ownership 时输出具体 G 项并零写停止。
6. validator 全部通过后才允许 stamp-last；任何失败保留旧戳并回滚事务。

## 拟修改

1. `templates/scripts/version_release.py` 与 `.codex/scripts/version_release.py`：增加可信 schema v1
   lineage 验证与确定性 legacy ownership 映射，接入唯一 evaluator。
2. `scripts/tests/test_git_sync_version_release.py`：增加可信迁移、伪造 hash、异常旧戳、映射缺失/歧义
   与 project-owned 内容保留测试。
3. `scripts/tests/test_bridgeforge_codex_project_sync.py`：覆盖 Planner 首次计划行为和真实 fixture 形态。
4. Template/dogfood contract、manifest、`VERSION`、`CHANGELOG.md`、本卡与源 Bug：同步产品事实。

## 验收标准

1. 可信 schema v1 HEAD + schema v2 当前/目标 contract 可进入 asset transition 分类。
2. HEAD 原始 payload 不命中历史 hash时，Planner 零写 fail-closed，并给出旧版本与 contract hash 原因。
3. 旧戳缺失、格式非法或低于最低支持版本时 fail-closed。
4. legacy ownership 到稳定 asset id 的映射缺失、歧义或 strategy 不兼容时 fail-closed。
5. schema v1 whole-file / region 中的 project-owned 内容保持不变；禁止把 glob ownership 传播到
   schema v2 contract。
6. Planner prospective snapshot 与 Apply 真实 snapshot 仍由同一 evaluator 得到相同结论。
7. StratusAgent 只读 Planner 不再返回 schema v2 泛化 G1；未修的其他问题仍可产生具体 G 项。
8. Template/dogfood `version_release.py` 和 managed contract 镜像一致；manifest `--check` 通过。
9. 针对性单测、必要硬闸、`git diff --check` 与独立审计通过。

## 合理假设、风险与自动化边界

- schema v1 没有稳定 asset id；映射只能由可信 v2 contract 的显式 target/strategy 与旧 ownership
  描述确定性构造。不能唯一证明时保持阻断属于预期安全行为。
- 修复 #2 后可能暴露更靠后的资产级 G 项；这代表诊断变精确，不代表 #2 失败。
- 本轮不读取或改写四个项目的业务代码、项目自有 hooks、AGENTS 内容或 Native Memory。
- 禁止自动 `git add`、commit 或 push。

## 实施记录

1. `version_release.py` 新增 `_transition_source_contract()`，允许 transition 读取可信 schema v1
   HEAD，但当前/目标 contract 仍必须是 schema v2。
2. `_classify_contract_transition()` 先读取旧戳、验证 `minimum_supported_version` 和
   `contract_historical_sha256[old_version]`，证明旧 contract 后才检查新戳并进入资产映射。
3. `_legacy_contract_assets()` 用当前 schema v2 的稳定 id/target/strategy 构造旧资产视图：
   - v1 whole-file / region 只能映射到兼容 strategy；whole 与 region 重叠、重复 region 均阻断；
   - v1 漏登记的既有 whole-file 只有命中对应旧版本 asset hash 才能映射；
   - managed projection / region 资产继续使用现有历史 projection/region hash 证明；
   - 未登记、未命中历史 hash 的既有整文件目标按稳定 asset id 输出 G 项。
4. 未被 schema v2 显式 asset 接管的旧 glob 路径保持 project-owned；内容变化分类为 `mixed`，
   不把 schema v1 的 glob ownership 传播进新 contract。
5. Template 与 dogfood 脚本逐字同步；产品升至 1.4.16，contract 与 active manifest 由
   `rebuild_shared_skill_manifest.py` 确定性重建。

## 验证记录

- 新增回归 3 组：可信 schema v1 lineage 与 project-owned 变化、伪造 hash / 低于最低支持旧戳、
  whole-region 歧义 / 未授权整文件接管；另覆盖旧 schema 漏登记但新 contract 仅管理可信 region。
- 第 1 轮：`.venv\\Scripts\\python.exe -B -m unittest scripts.tests.test_git_sync_version_release scripts.tests.test_bridgeforge_codex_project_sync`，83/83 通过。
- 收口自查补充“漏登记可信 region”正例后，第 2 轮同命令再次 83/83 通过。
- StratusAgent 真实只读 Planner：schema v2 泛化 G1 消失；计划继续零写阻断于 8 个
  `codex.rule.*` 资产，其 HEAD 内容不命中 0.90.0 官方 hash。该结果证明 lineage 已进入具体资产层，
  同时保留未修 M2 ownership 问题，没有执行 apply。
- `rebuild_shared_skill_manifest.py --check` 为 `already current`；mirror drift、skill metadata、
  project structure、instruction source 与 `git diff --check` 均 exit 0。project structure 仅输出既有
  archive advisory。
- 首次独立审计：无 Blocker，发现 1 个 High、1 个 Medium。High 证实 schema v1 synthetic old
  asset 的 merge / managed Markdown / region 嵌套历史仍可能接受非 `old_version` 的 hash；Medium
  指出缺少“其他历史版本 hash”负例和 schema v1 prospective / real evaluator 等价回归。
- 用户批准追加预算后，synthetic old asset 删除当前 release 的 projection / region 凭证，只保留
  `old_version` 对应历史；whole-file 完整内容只有命中 `old_version` asset hash 时才能反证其 projection。
- 新增 merge、managed Markdown、region 三种“旧戳为 0.90.0、hash 只登记在 0.91.0”的负例，
  以及 schema v1 prospective snapshot / real evaluator 等价回归。
- 最终组合回归：`.venv\\Scripts\\python.exe -B -m unittest scripts.tests.test_git_sync_version_release scripts.tests.test_bridgeforge_codex_project_sync`，85/85 通过。
- 官方重建器以窄权限完成 Template / dogfood contract 与 active manifest 传播；随后 manifest
  `--check` 返回 `already current`。mirror drift、skill metadata、project structure、instruction source
  与 `git diff --check` 全部 exit 0；project structure 仅输出既有 archive advisory。
- 最终独立复审：无 Blocker / High / Medium，原 High 与 Medium 均关闭；独立最小复测 5/5，
  Template / dogfood 脚本与 contract 一致，active manifest canonical hash 逐项一致。#2 技术实现可关闭，
  等待用户验收。
