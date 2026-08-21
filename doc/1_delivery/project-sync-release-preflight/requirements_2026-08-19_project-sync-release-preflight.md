---
status: regression-fixed-awaiting-real-downstream
next: publish_1.4.37_and_retest_causis_git_sync
scale: M
source_bug: doc/2_bugs/BUG-bridgeforge-codex-145-end-to-end-acceptance-gaps.md
---

# Project Sync 与 Release Preflight 统一迁移证明需求

## 原始需求摘要

修复 `bridgeforge-codex` 项目升级已经报告 ready，但同一工作树随后被标准 `$git-sync` transition classifier 阻断的问题。升级程序与提交检查程序必须共用同一套迁移证明；只有标准提交入口可以消费升级结果时，项目同步器才允许写新骨架版本戳并报告成功。

## 调用来源与后续交接

- 调用来源：用户先要求 `$plan`，确认技术计划后进入 `$develop`；本卡由 `$confirm` 固化。
- 后续交接：主对话完成实现与最多两轮验证；在预算内启动最多一个独立审计 agent；不自动 commit/push。

## 规模与预算

- 规模：M。原因是逻辑改动跨 `version_release`、`project_sync`、受管 contract 和端到端测试，但业务目标、失败边界与接口方向已经明确。
- 时间预算：60 分钟。
- token 预算：30k 新增 token（估算；平台不提供可靠实测）。
- agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多两轮；一轮允许包含多条预定验收命令。
- 超预算停止点：需要第三轮实质修复、改变版本戳最后写入顺序、添加下游路径特判/整文件白名单、或写真实下游时停止并重新确认。

## 已核实事实

1. `scripts/bridgeforge_codex_project_sync.py::_run_validation()` 当前只运行 memory、config、Markdown 与 Git whitespace 检查，没有执行 release transition preflight。
2. `templates/scripts/version_release.py` 已具有 hooks dispatcher 投影、managed Markdown/keyed table、region 和 AGENTS zone/legacy mapping 的解析能力。
3. contract transition 已支持未变化 merge target 的合法 no-op，但发生变化的 `merge` 仍可能进入 whole-file hash 分支。
4. managed Markdown 在普通 change ownership 路径可拆分受管/项目内容，但 contract transition 尚未完整复用该投影。
5. region、AGENTS 和部分 fail-closed 反例已有测试；缺少 project-sync apply 到 release preflight 的统一端到端断言。
6. 当前工作区已有未提交的 `1.4.12` native-memory 产品改动和用户原有文档修改，实施必须保留，不得回退或覆盖。

## 已确认业务规则

1. `$git-sync` 的 transition 判断是提交阶段的唯一标准；`project_sync` 必须复用同一实现，禁止复制第二套近似规则。
2. hooks merge 只验证 BridgeForge 受管 dispatcher；项目 handler 必须原样保留并分类为 project change。
3. managed Markdown 只验证受管标题和 keyed-table 行；项目章节与项目表格行必须原样保留。
4. region 只验证受管区块；项目 extension 必须原样保留。
5. AGENTS 继续使用公共区、项目专区与可信 legacy mapping 证明。
6. 未知、损坏、重复、哈希漂移或无法分类的内容必须 fail-closed，禁止通过路径特判、整文件白名单或一次性不可信 hash 放行。
7. `project_sync` 在资产 apply 后、写版本戳前运行只读 release preflight；预检不得 stage、commit、push、修改业务版本或提前写骨架戳。
8. 预检失败必须回滚本事务写入、保留旧骨架版本戳，并在收据中输出逐文件 action-required 清单。
9. 预检必须使用产品侧可信实现，禁止加载下游可能被人工修改的发布脚本。
10. 预检通过后才允许写骨架版本戳并报告 ready；之后 `$git-sync` 对同一工作树必须给出一致 ownership 结论。

## 数据与接口映射

- 输入：Git 工作树相对 HEAD 的真实 changed paths、HEAD contract/资产、当前 contract/资产、计划中的新骨架版本。
- 公共入口：`version_release.py` 提供只读 transition preflight；普通 `$git-sync` 使用实际 stamp，`project_sync` 使用 prospective stamp 参数。
- 输出：`skeleton-only`、`mixed`、`project` 或带 stable asset id/target/reason 的阻断项。
- `project_sync` 收据新增 release preflight 状态/分类/耗时；失败信息映射成非执行 `G*` action-required items。

## 拟修改

1. `templates/scripts/version_release.py` 与 `.codex/scripts/version_release.py`：补全 changed merge、managed Markdown transition，并暴露只读 preflight 单一入口。
2. `scripts/bridgeforge_codex_project_sync.py`：在写戳前调用可信 preflight，失败时事务回滚并生成清单。
3. `scripts/tests/test_git_sync_version_release.py`：增加 changed merge、keyed Markdown、投影漂移与统一分类测试。
4. `scripts/tests/test_bridgeforge_codex_project_sync.py`：增加 preflight 成功、失败回滚、旧戳保持和 ready 后可消费测试。
5. Template/dogfood contract、active/compat manifest：同步受管哈希。
6. `VERSION`、`CHANGELOG.md`、本卡、源 Bug 与相关设计说明：同步产品事实和验证边界。

## 非目标

- 不重写现有文件合并器。
- 不修改用户级 shared updater、native Memory 或五个 Skill 的退休特例/ledger。
- 不修改 `$git-sync` 的 fetch、commit、push 流程。
- 不修改真实下游、业务代码或用户级目录。
- 不自动 commit/push。

## 验收

1. changed hooks merge 同时含项目 handler 时 transition 通过；受管 dispatcher 缺失、重复或漂移时阻断。
2. managed README 保留项目章节/表格行时 transition 通过并正确分类；受管行漂移时阻断。
3. region 与 AGENTS 继续使用同一证明语义且不弱化现有 fail-closed 行为。
4. update 收据为 ready 后，release preflight 对同一 changed paths 通过；存在业务改动时为 `mixed`，纯骨架更新为 `skeleton-only`。
5. preflight 失败时本轮资产写入全部回滚、旧骨架版本戳保持、`stamp_written_last=false`，并输出逐文件 G 清单。
6. preflight 本身零写入，不更新业务版本、CHANGELOG、index 或 Git 历史。
7. 定向测试、完整 factory unittest、完整 downstream fixture、manifest `--check`、mirror、metadata、project structure、instruction source 与 `git diff --check` 全部通过。
8. 独立审计无 blocker/high。

## 合理假设、风险与自动化边界

- 实施使用产品 Template 中的可信 `version_release.py`，不得 import 下游工作树中可能漂移的副本。
- prospective stamp 只能作为只读证明输入；实际 stamp 仍由项目同步事务在所有验证完成后最后写入。
- Git changed-path 扫描必须与 repo-local `$git-sync` 的 unstaged、staged、untracked 三类集合语义一致。
- 当前未提交的 native-memory 改动不属于本需求，但机械 manifest/version 传播可能与其共享文件；必须合并保留，不得回退。
- 真实 ClaudeBridgeAssist/causis_risk_suite 复验需要单独授权；未运行时必须标记未验证。

## 2026-08-21 回归补充

1. 1.4.31 current-only 重构保留了统一 `evaluate_release_transition()` 入口，但删除双 contract
   projection 后又让当前 asset 解析 HEAD 旧 marker，CausisRiskSuite 1.4.35 首次 `$git-sync`
   在版本发布前 fail-closed。
2. 1.4.37 恢复最小双 contract 语义，不恢复历史兼容包：HEAD 只读取同一 Git HEAD 自带的 contract，
   当前侧仍只读取 current-only contract。
3. 两侧资产按 stable id 对齐并分别投影；当前 contract 坏 JSON、重复 id/target、资产非对象或
   当前基线漂移时仍阻断。
4. 同合同旧基线漂移继续阻断；跨合同旧侧无法用旧证据解释时必须保守归入 `mixed`，不得归为
   `skeleton-only`，也不得要求永久维护旧 parser。
5. schema-2 显式适配收据不得进入 `evaluate_release_transition()` 或降低 current-only 分类。旧
   fingerprint 只证明字段自洽，不构成 ownership 信任根；任何项目修改都必须由当前合同和真实
   HEAD/工作树内容重新分类。
6. `$git-sync` 只把 ignored 普通 JSON 收据识别为过期运行时产物。current-only evaluator 独立通过
   且 commit 成功后才删除；evaluator 阻断、JSON 异常或 commit 失败时必须保留。
7. 无 HEAD contract、当前有合法 contract 的首次安装属于 contract introduction；旧侧资产集合为空，
   不得错误要求 HEAD 已存在当前 whole asset。当前 baseline 仍须严格通过。
8. 精确 fixture 同时断言纯 marker 迁移为 `skeleton-only`、叠加项目源码为 `mixed`；真实 Causis
   dirty 现场只读返回 `mixed`。
9. 本卡只有在 1.4.37 发布、Causis 更新、标准 `$git-sync` 完成 commit/push 且最终 clean、0/0 后
   才能再次进入用户验收状态。

## 实施记录

- `templates/scripts/version_release.py` 新增只读 `preflight_contract_transition()`：统一收集 unstaged、staged、untracked 路径，并以 prospective skeleton stamp 调用同一个 `classify_changes()`。
- changed hooks merge 改为分别证明旧/新受管 dispatcher 投影；项目 handler 从投影中剥离并单独比较。managed Markdown 改为分别证明受管标题/keyed rows 投影与项目内容。
- `TransitionBlocked` 保留原聚合错误文本，同时携带 stable asset id、target、reason，供项目同步器生成非执行 `G*` 清单。
- contract 重建器为 hooks merge 和 managed Markdown 生成 current/historical projection SHA-256，历史只来自已发布基线。
- 第三轮审计修补后，managed Markdown 的每个历史投影改为读取该版本自己的 contract/asset 规则计算；相同摘要允许逐版本登记，禁止用最新版标题规则套旧文件。
- `scripts/bridgeforge_codex_project_sync.py` 在资产/Markdown/memory/Git whitespace 验证后、写戳前加载产品 Template 中已受 contract hash 验证的 release 模块。预检失败由原事务回滚；成功后才写新戳。
- 当前戳已等于目标版本但本轮实际修改受管资产时，也会以真实 changed paths 运行预检；若标准 `$git-sync` 会因缺少 stamp 变化阻断，则本轮同步回滚并返回 stable asset `G*` 清单。
- 动态可信模块加载期间强制 `sys.dont_write_bytecode=True` 并恢复原值；Skill 入口显式传 `-B`。本轮产生的两份 `version_release.pyc` 已精确删除，实际产品预检后均未再生成。
- 收据新增 `release_preflight_status`、`release_preflight_classification` 和 `timings_ms.release_preflight`；无 Git HEAD 的首次初始化为 `not_applicable`，本就不写戳的 degraded/no-op 为 `not_required`。
- 没有修改真实下游、用户级目录、fetch/commit/push 流程或 native-memory/五 Skill 特例。

## 验证记录

- 第 1 轮定向完整模块：`.venv\\Scripts\\python.exe -B -m unittest scripts.tests.test_bridgeforge_codex_project_sync scripts.tests.test_git_sync_version_release`，74/74 通过。
- 已覆盖：Git 项目写戳前预检、失败回滚/G 清单、changed/unchanged hooks merge、项目 handler 保留、managed Markdown 项目内容保留、受管投影漂移阻断。
- 第 2 轮完整 unittest 初次为 255/256；唯一失败揭示投影摘要不能跨版本去重，修复后相关 5/5 通过。完整 downstream fixture 26/26，manifest/mirror/metadata/structure/instruction/diff gates 全部 exit 0。
- 首次独立审计发现 2 High + 1 Medium：历史 parser 错配、同版本受管修复跳过 preflight、动态 import 生成 pyc。用户明确授权第三轮修补。
- 第 3 轮：审计三项核心 7/7；实际产品预检后两份 version_release.pyc 均不存在；project-sync + version-release 完整相关模块 76/76；完整 downstream fixture 26/26；manifest/mirror/metadata/structure/instruction/diff gates 全部 exit 0。schema v1 兼容错误文案也已回归。
- 独立复审：blocker=0、high=0。审计逐版重算 11 个 schema-v2 发布基线，`root.agents` 与 `codex.doc.readme` 均 `bad=[]`；同版本受管退休回滚、stable G id 与 bytecode 零写均通过。
- 真实 ClaudeBridgeAssist/causis_risk_suite 未写入、未复验；完整 factory 256 项未在第三轮重复，沿用第二轮 255/256 + 修复后相关回归、第三轮 76/76 和 fixture 26/26 的组合收据。
