---
status: superseded-current-product-awaiting-real-downstream-validation
severity: high
scope: BridgeForgeCodex 1.4.5 end-to-end update, git-sync handoff, and user-skill migration
reported_at: 2026-08-17
last_reproduced_at: 2026-08-18
downstream: D:\Quant\ClaudeBridgeAssist
additional_downstream: D:\Quant\causis_risk_suite
factory_head: 304e6189a6724078351deea2c055b0bca52d80c1
product_version: 1.4.5
additional_product_version: 1.4.30
related_bug: BUG-git-sync-contract-transition-classification.md
transition_fix_version: 1.4.12
compatibility_retirement_version: 1.4.13
---

# BUG：BridgeForgeCodex 1.4.5 真实下游仍有一个提交阻断和一项迁移记账缺口

## 2026-08-21：当前产品处理方式

本文后续保留 1.4.5 现场与人工补救证据，但两条原推荐路线均已退出当前产品：

- 项目 contract transition 自 1.4.28 起由 current-only 边界取代；合法旧项目走一次
  `PreservationManifest` 破坏性重建，当前项目只接受 schema 3，不再维护 lineage adapter；
- 用户级 compatibility manifest、旧 ledger 接管与 retire-tree 已在 1.4.13 物理删除。当前 updater
  不读取旧账本；目标冲突时阻断，旧用户重新安装当前产品。

因此本 Bug 不再要求实现 transition proof、退休特例或 ledger 收口事务。当前剩余验收只包括：
在用户授权的真实 ClaudeBridgeAssist 副本中按 1.4.30 规则正规化项目 Hook、完成确认式重建与
no-op replan，再运行 `$git-sync` 和 runtime smoke。第二期没有真实写入该项目，以上仍未验证；
不得用本文历史方案重新扩张当前产品。

## 2026-08-19 用户级兼容链退役

用户随后明确改变产品边界：不再支持旧 `$bridgeforge` 用户级自动迁移，也不再保留
compatibility manifest。待发布 1.4.13 已删除 `shared-skill-manifest.json`、冻结兼容 payload、
旧入口和 `bridgeforge_codex_user_migrate.py`；正式 updater 只读取
`bridgeforge-codex-manifest.json`，也不再借旧 ledger 接管已存在目录。

因此本文的用户级记账缺口不再通过“active 退休特例”修复，而是通过物理删除产生该错误的
兼容迁移链关闭。旧 ledger、旧 `.bridgeforge` home 与旧 Claude Skill 以后保持用户所有，
当前产品不读取、不接管、不删除；旧用户必须重新安装当前产品。项目级 `0.86.0+` 骨架
lineage 与旧项目戳迁移不在本次退役范围内。

本节记录的是已实施边界；完整自动测试、fixture、独立审计和真实下游验证状态见后续关闭
证据，未执行项不得推断为通过。

自动验证收据：完整 unittest 250/250、已发布项目 lineage fixture 26/26、manifest `--check`、
factory metadata/structure/mirror/instruction 与 `git diff --check` 均通过。最终独立审计
blocker=0、high=0；确认旧 `.bridgeforge` 清理能力已删除，正式 updater 对 ledger ownership
漂移 fail-closed 且零写。真实旧用户重新安装、真实下游与 Desktop runtime 尚未执行；
compatibility manifest 已删除，不能再以旧 updater handoff 作为验收路径。

## 2026-08-19 产品修复状态

项目同步与 `$git-sync` 结论不一致的问题已在待发布 1.4.12 的产品层修复：两者共用
`version_release.py` ownership classifier，项目同步在写新骨架戳前以 prospective stamp 运行
只读 release preflight。hooks merge 与 managed Markdown 分别按受管投影证明，项目 handler、
项目章节和项目表格行继续保留并归入 project change；失败时本轮同步事务回滚并输出逐文件
`G*` 清单。

用户已将本文 5 个 Skill 的删除/ledger 现场视为 ClaudeBridgeAssist 专属特例，并要求从该下游
删除重装；1.4.12 未把该特例写成通用迁移规则。后续 1.4.13 按新的产品边界整体退役用户级
兼容迁移器和 transition manifest，不再读取、接管或删除旧用户资产。本状态不代表真实下游
复验通过，也不代表已 commit/push。

## 结论

BridgeForgeCodex 1.4.5 已能在 D:\Quant\ClaudeBridgeAssist 完成项目同步事务，并以
readiness=ready、gaps=[]、stamp_written_last=true 写入 1.4.5 版本戳；但同一工作树进入
标准 $git-sync 的版本分类阶段时仍被阻断。

同轮用户级迁移删除了 5 个同时属于当前 active manifest 的用户级 skill。用户已于
2026-08-18 明确确认：这 5 个 skill 可作为 ClaudeBridgeAssist 的专属退休特例，无需恢复。
官方迁移首次执行后留下了悬空 ledger；经用户明确授权，真实现场已精确清除对应 5 条记录，
但产品仍没有显式表达这项特例，也不能在官方事务内自行得到一致终态。

因此，本轮仍不能视为“真实下游验收通过”：

1. 项目同步器认为目标 ready，但官方提交入口仍无法消费该结果。
2. 五项删除本身不再构成阻断，真实现场的文件系统与 ledger 已人工收口；遗留产品问题是
   特例没有进入 manifest / receipt，官方迁移仍会生成不一致终态。

提交阻断与迁移记账缺口均发生在正式产品路径。后续 ledger 清理是用户明确授权的精确现场
补救，不代表产品缺口已修复。当前下游没有 commit 或 push，提交故障在远端副作用前
fail-closed。

## 2026-08-18 复现更新：1.4.11 在 causis_risk_suite 仍阻断

### 结论

BridgeForgeCodex 1.4.11 已修复 `ctx-budget` 退役注释冲突，并能在
`D:\Quant\causis_risk_suite` 将项目骨架从 0.94.2 更新至 1.4.11；项目同步事务与终态
replan 均报告 ready、gaps=[]、blockers=[]。但同一工作树进入项目标准 `$git-sync` 后，仍在
`version_release.py` 的 ownership contract transition 分类阶段被阻断。

这次复现证明本报告的“project_sync ready，但标准提交入口无法消费同一结果”问题在 1.4.11
仍未闭环。它不是 `ctx-budget` 修复的回归，也不是四个下游文件各自出现独立内容冲突，而是
transition classifier 对 merge、managed Markdown、legacy region 与 legacy AGENTS 的证明规则
仍未和项目同步器统一。

### 已核实环境

- 产品 home：`C:\Users\bridg\.bridgeforge-codex`
- 产品 source commit：`442bfc4c57a42d07d30d5c9a0a6b05286c9a7ef8`
- BridgeForgeCodex 产品版本：1.4.11
- 真实下游：`D:\Quant\causis_risk_suite`
- 下游 HEAD：`08830859c9605670c1f875604bffdb41af9f9b36`
- 下游分支 / upstream：`main` / `origin/main`
- 下游业务版本：0.73.6
- 下游升级前 / 后骨架版本：0.94.2 / 1.4.11
- Python：`D:\Quant\causis_risk_suite\.venv\Scripts\python.exe`，3.12.13
- 项目事务 aggregate fingerprint：
  `sha256:a6ab1cb0e645c9aa46368716d5f2323cf494592cdb7382d94a015e40ca8a6175`

### 项目同步与终态收据

用户级 migration planner 返回 actions=[]、blockers=[]；14 个有人工修改的 legacy Codex skill
按契约原样保留。项目同步执行用户确认的 A 模式，应用 4 项 safe 与 R1-R10，收据为：

    status=completed
    readiness=ready
    execution_status=completed
    project_readiness=ready
    previous_version=0.94.2
    current_version=1.4.11
    gaps=[]
    blockers=[]
    stamp_written_last=true
    rollback_performed=false

终态再次 plan 返回 safe=[]、risk=[]、upstream_absorption=[]、gaps=[]、blockers=[]；删除用户
明确退休的 `.claude/` 与 `CLAUDE.md` 后，`target_readiness` 也由非阻断 notice 收口为 ready。
`config_health_check.py --strict`、`git diff --check` 与
`pytest scripts/tests/test_root_hygiene.py -q --basetemp .runtime/pytest-bridgeforge-root-hygiene-20260818`
均通过，专项测试收据为 30 passed。

下游全量 pytest 收据为 522 passed、3 failed；失败位于既有业务 UI 测试
`test_hedge_detection_help_dialog.py`、`test_t0_fac_check.py` 与
`test_table_interaction_baseline.py`。三处失败与本次四项 transition target 没有直接文件重叠，但
缺少升级前基线，因此只能标记为“尚未归因”，不能作为本 Bug 已通过完整下游测试的证据。

### `$git-sync` 实际阻断

项目标准脚本以提交消息
`chore: 升级 Codex 骨架与本地启动环境` 执行。首次 fetch 因沙箱无法写
`.git/FETCH_HEAD` 而失败；按 Skill 契约以完全相同命令窄范围提升权限重试后，fetch 成功，随后
自动版本发布阶段返回：

    [git-sync] automatic version release blocked:
    ownership contract transition is blocked:
    codex.doc.readme: current asset does not match its declared hash: doc/README.md;
    codex.hooks-config: HEAD asset does not match its trusted contract hash: .codex/hooks.json;
    codex.precommit: HEAD managed region does not match trusted transition history: .githooks/pre-commit;
    root.agents: legacy AGENTS managed section is not trusted: ## 0.5 专业表达风格

脚本在版本 bump、commit 与 push 前 fail-closed。失败后现场为：

    branch=main
    upstream=origin/main
    ahead=0
    behind=0
    HEAD=08830859c9605670c1f875604bffdb41af9f9b36
    VERSION=0.73.6
    staged=empty
    commit_created=false
    push_performed=false

工作树修改全部保留；本轮没有创建新 stash，也没有手工绕过发布器。

### 四项错误的同一产品根因

| stable asset id | 真实下游状态 | classifier 缺口 |
|---|---|---|
| `codex.doc.readme` | keyed-table 安全合并保留项目自有行 | transition 分支按整个 current 文件 hash 判定，没有使用既有 managed Markdown / keyed-table ownership 拆分 |
| `codex.hooks-config` | 新受管 dispatcher 已更新；项目自有 `root_hygiene_check.py` handler 保留 | transition 分支按整个旧 merge target hash 判定，没有复用 `merge_validation` 的受管 dispatcher 投影证明 |
| `codex.precommit` | 项目 extension 逐字保留，新受管 marker/region 已迁移 | current contract 的 region lineage 不能证明 HEAD 中旧 marker 对应的合法受管区块 |
| `root.agents` | project_sync 已将旧章节迁入公共区 / 项目专区并通过终态验证 | transition classifier 重新用独立的 legacy section hash 表判定，缺少当前真实旧章节的可信 lineage 或项目同步事务证明 |

`version_release.py` 已有 `_managed_markdown_parts`、`_validate_codex_hooks_merge_target`、region
拆分与 AGENTS legacy layout 验证能力，但 contract transition 路径没有统一复用这些 ownership
证明。结果是 project_sync 与 git-sync 对同一 before/current 资产再次给出相反结论。

### 对关闭条件的新增要求

除本文原有验收项外，关闭本 Bug 前必须加入 `causis_risk_suite` 的 0.94.2 -> 当前发布版本真实
迁移 fixture 或等价冻结快照，并证明：

1. keyed-table 文档保留项目独有行时，transition 只校验受管投影，不要求整个文件等于 Template。
2. hooks merge target 含项目自有 handler 时，transition 通过 `merge_validation` 证明受管 dispatcher，
   同时把项目 handler 正确分类为 project change。
3. pre-commit 的旧 / 新 marker 迁移由精确 region lineage 或共享事务证明消费，项目 extension 必须
   逐字保持。
4. AGENTS 的 legacy managed section、project section 与 residual 使用和 project_sync 相同的证明
   结果；未知内容继续 fail-closed，禁止添加下游路径特判或全文件白名单。
5. 完整 updater -> project apply -> no-op replan -> release preflight -> `$git-sync` 路径能生成 mixed
   release plan；在 commit 前的只读预检至少成功通过。
6. 修复必须进入产品层单一事实源并传播到 Template / dogfood；禁止只修改
   `causis_risk_suite/.codex/scripts/version_release.py` 或向其 manifest 写一次性 hash 豁免。

### 本次恢复边界

- `causis_risk_suite` 当前仍未 commit、未 push，业务版本保持 0.73.6。
- BridgeForgeCodex 骨架戳已是 1.4.11，项目同步 replan 为 no-op / ready。
- 当前工作树包含经用户确认的 Codex 骨架迁移、Claude 资产退休、vendored uv 与启动引导改动；
  不得为绕过本 Bug 拆分手工 Git 操作。
- 正确修复层级仍是 BridgeForge 产品 transition proof；下游只作为真实回归输入，不接受路径特判。

## 2026-08-18 再复现：ClaudeBridgeAssist 1.4.11 的 hooks merge transition 仍阻断

### 结论

BridgeForgeCodex 1.4.11 已在 `D:\Quant\ClaudeBridgeAssist` 完成项目同步，终态为
ready、gaps=[]、blockers=[]，并最后写入 1.4.11 骨架戳；但同一工作树进入项目标准
`$git-sync` 后，仍被 `version_release.py` 的 `codex.hooks-config` ownership contract
transition 阻断。

本次报告只补充 Git 提交入口与 hooks merge ownership proof 不一致的问题。此前 5 个用户级
Skill 的旧 ledger 错误是 ClaudeBridgeAssist 的已授权项目特例，现场已经人工收口；本节不要求
把该特例推广到产品 manifest、Template 或其他下游，也不要求恢复这些 Skill。

### 已核实现场

- 产品 source commit：`442bfc4c57a42d07d30d5c9a0a6b05286c9a7ef8`
- BridgeForgeCodex 产品版本：1.4.11
- 真实下游：`D:\Quant\ClaudeBridgeAssist`
- 下游 HEAD：`eba2fe264b6870c5f865ac344e5f5f63f3bf9005`
- 下游分支 / upstream：`master` / `origin/master`
- ahead / behind：0 / 0
- 项目同步收据：`status=completed`、`readiness=ready`、`gaps=[]`、`blockers=[]`、
  `stamp_written_last=true`、`current_version=1.4.11`
- 当前 staging 为空，没有 commit，也没有 push。

项目同步后的工作树只保留 6 项受管骨架变化：

- 修改 `.codex/.bridgeforge_codex_version`
- 修改 `.codex/hooks.json`
- 修改 `.codex/hooks/hook_dispatcher.py`
- 删除 `.codex/hooks/target_cleanup.py`
- 修改 `.codex/managed-skeleton.json`
- 修改 `.codex/scripts/hooks_merge.py`

其中 `.codex/hooks.json` 相对 HEAD 只有一处注释变化：删除已退休的 `context budget` 描述；
现有项目自有 `vault_snapshot.py` Stop hook 被逐字保留，受管 dispatcher 路径也仍存在。

### `$git-sync` 实际阻断

项目标准同步脚本使用提交消息 `chore: 同步 BridgeForgeCodex 受管 hook` 执行，自动版本发布
阶段返回：

    [git-sync] automatic version release blocked:
    ownership contract transition is blocked:
    codex.hooks-config: HEAD asset does not match its trusted contract hash: .codex/hooks.json

脚本在版本 bump、commit 与 push 前 fail-closed；工作树与暂存区均保持原状。

### 根因证据

当前 `codex.hooks-config` 契约明确声明：

    strategy=merge
    merge_policy=codex-hooks
    merge_validation.format=codex-hooks-dispatchers-v1

repo-local `version_release.py` 已实现 `_validate_codex_hooks_merge_target()`，可以按 required
dispatcher 投影验证 merge target，并在 unchanged merge transition 路径调用它。可是在
`_transition_asset_ownership()` 中，`merge` 与 `whole`、`retirement` 进入同一分支；该分支先要求
HEAD 整个目标文件的 hash 命中旧 contract 声明值，未复用 hooks merge 的受管投影证明。

对 merge 资产而言，完整 `.codex/hooks.json` 合法包含项目自有 handler，因此整个文件不等于
Template 是预期状态，不足以证明受管 dispatcher 漂移。结果是 project_sync 接受“受管部分更新、
项目部分保留”并判定 ready，git-sync 却把同一合法 HEAD 当成不可信 whole-file asset。

### 推荐修复与回归

1. `strategy=merge` 且 `merge_policy=codex-hooks` 的 transition 必须分别用旧 / 新 contract 的
   required dispatcher 投影验证 HEAD / current；禁止要求整个 merge target 等于 Template。
2. 项目自有 handler 继续原样保留；受管 dispatcher 缺失、重复、stage 不符或 hash 漂移时仍应
   fail-closed。
3. 在 `scripts/tests/test_git_sync_version_release.py` 增加真实 transition 反例：HEAD 与 current
   都含项目额外 handler、whole-file hash 不等于 Template，但受管投影分别匹配旧 / 新 contract；
   classification 应成功。再注入 dispatcher 漂移，确认仍阻断。
4. 若修复进入产品层，`templates/scripts/version_release.py` 与 dogfood 镜像必须保持一致，并完成
   manifest check；禁止向 ClaudeBridgeAssist 写一次性路径特判或历史 whole-file hash 豁免。
5. 最终用 `D:\Quant\ClaudeBridgeAssist` 现有工作树运行 repo-local `$git-sync` 只读发布预检；
   必须能生成 release plan，且项目自有 `vault_snapshot.py` hook 不丢失。

### 本次恢复边界

- ClaudeBridgeAssist 当前仍未 commit、未 push，分支与 upstream 保持 0 / 0。
- 6 项骨架变化全部留在工作树；没有 stash、手工 Git 绕过或下游代码补丁。
- 本次只向 BridgeForge 追加故障证据，不修改工厂实现，也不继续执行下游 `$git-sync`。
- 旧 ledger 项目特例已经收口，不属于本轮产品修复范围。

## 已核实环境

- 工厂仓库：D:\Quant\BridgeForge
- 工厂 HEAD：304e6189a6724078351deea2c055b0bca52d80c1
- BridgeForgeCodex 产品版本：1.4.5
- 真实下游：D:\Quant\ClaudeBridgeAssist
- 下游 HEAD：c33125b1a00571edc0429728e1469f097d9f3d3b
- 下游分支 / upstream：master / origin/master
- 下游升级前骨架版本：1.4.3
- 下游升级后骨架版本：1.4.5
- Python：D:\Quant\ClaudeBridgeAssist\.venv\Scripts\python.exe，3.11.9
- 用户选择：A，执行唯一风险卡的全部项目
- 用户级迁移 fingerprint：
  sha256:226c0c2c0ca3763ae8f6dfa8032651e6dc81bfeac7415ab223119c74e6a19edf
- 项目事务 fingerprint：
  sha256:c63c833e3f2d3bccaa3c8b6e66a8d1fc78a76dd20cbb5f23844d69c1a9aa5240

## 端到端复验收据

### 1. 官方 updater

用户级 updater 成功刷新产品 home：

    source_commit=304e6189a6724078351deea2c055b0bca52d80c1
    mode=updated
    action_count=1
    status=completed

产品 home 为普通、干净 Git 仓库，origin 指向
https://github.com/freakybridge/BridgeForgeCodex.git。

### 2. 用户级迁移

bridgeforge_codex_user_migrate.py 以确认 fingerprint 执行后返回：

    status=completed_with_gaps
    applied=5 retire-tree actions
    gaps=14 preserved modified legacy Codex skills
    rollback_performed=false

被删除的 5 个目录：

- C:\Users\bridg\.codex\skills\collab
- C:\Users\bridg\.codex\skills\create-worktree
- C:\Users\bridg\.codex\skills\debate
- C:\Users\bridg\.codex\skills\escalate
- C:\Users\bridg\.codex\skills\plan

用户已明确授权把这 5 项作为 ClaudeBridgeAssist 专属退休特例；以下分析不再要求恢复这些目录。

14 个有人工修改的旧 skill 均按计划保留，没有被删除。

### 3. 项目同步

首次普通权限 apply 因 Windows 拒绝替换 .codex/managed-skeleton.json 而失败，并报告
rollback incomplete。随即核对 contract、version_release.py、版本戳哈希及事务临时文件：
三个目标仍为 apply 前值，未发现残留临时文件。

使用同一 fingerprint 窄范围提升权限重试后成功：

    status=completed
    readiness=ready
    execution_status=completed
    target_readiness=ready
    project_readiness=ready
    safe_applied=contract.managed-skeleton,codex.doc.readme,codex.script.version-release
    gaps=[]
    blockers=[]
    stamp_written_last=true
    rollback_performed=false

终态再次 plan：

    previous_version=1.4.5
    current_version=1.4.5
    safe=[]
    risk=[]
    gaps=[]
    blockers=[]

配置、instruction source、project structure、memory lint 与 git diff --check 均 exit 0；
project structure 仅输出既存 doc/4_archive/.gitkeep advisory。

## 阻断 A：项目同步 ready，但 $git-sync 仍无法分类同一结果

### 实际复现

使用下游当前 repo-local version_release.py，对 Git 实际 changed paths 调用与
codex_git_sync.py 相同的 classify_changes / build_release_plan 路径。changed paths 共 50 个。

实际结果：

    version_release.ReleaseError:
    ownership contract transition is blocked:
    codex.doc.readme: HEAD asset does not match its trusted contract hash: doc/README.md;
    codex.hooks-config: target migration is missing changed paths: .codex/hooks.json;
    codex.precommit: HEAD managed region does not match trusted transition history: .githooks/pre-commit;
    codex.rule.anti-fabrication: HEAD asset does not match its trusted contract hash;
    codex.rule.meta-rule-design: HEAD asset does not match its trusted contract hash;
    codex.rule.portability: HEAD asset does not match its trusted contract hash;
    codex.rule.workflow: HEAD asset does not match its trusted contract hash;
    root.agents: managed Markdown contains an unclosed fenced code block

这证明 1.4.4 / 1.4.5 transition classifier 已从“只报第一个 marker 错误”进步为聚合报告，
但 D:\Quant\ClaudeBridgeAssist 的正式 update -> git-sync 路径仍未闭环。

### 产品契约矛盾

同一组 HEAD、工作树和 contract 产生两个相反结论：

| 阶段 | 产品结论 |
|---|---|
| bridgeforge_codex_project_sync.py apply + replan | ready，gaps=[]，允许最后写 1.4.5 戳 |
| version_release.py classify_changes | transition blocked，禁止进入 commit |

fail-closed 本身是正确方向；问题是产品没有在写 ready 版本戳前暴露“该结果无法被标准提交入口
消费”，也没有提供受支持的恢复动作。用户完成官方更新后仍停在无法提交的死路。

### 具体缺口

1. doc/README.md、4 个已退休 Rule 和 pre-commit 的真实历史摘要未进入 classifier 可接受
   lineage；项目同步器可以完成迁移，classifier 却不能证明同一迁移。
2. contract transition 要求 .codex/hooks.json 出现在 changed paths，但本次项目同步没有修改
   该文件，说明 contract 迁移要求与实际 project_sync 动作集合不一致。
3. HEAD 旧 AGENTS.md 含未闭合 fence。项目同步器已安全生成新的合法双区 AGENTS 并报告 ready，
   classifier 仍直接解析旧损坏结构，没有复用项目同步器已经完成的可信迁移证据。
4. 现有 Bug 记录已明确把真实下游预检列为验收项；真实下游当前仍失败，因此
   resolved-awaiting-user-acceptance 不能升级为用户验收完成。

## 非阻断缺口 B：特例删除已获确认，但悬空 ledger 未收口

### 交叉证据

当前 bridgeforge-codex-manifest.json 把以下 5 个名称列为 active Codex skills：

- collab
- create-worktree
- debate
- escalate
- plan

同一 commit 的 shared-skill-manifest.json 又把同名、同目标目录记录为
legacy_transition=true。两份旧 / 新 Codex ledger 中，这 5 个名称的 content_hash 逐项相等。

bridgeforge_codex_user_migrate.py 当前逻辑：

1. 从 current manifest 读取 active。
2. 从 compatibility manifest 读取 transition_names。
3. 遍历旧 ledger；只要 name 位于 transition_names，且当前目标目录哈希仍等于旧记录，就生成
   retire-tree。
4. 没有排除 name 同时属于 active 的情况，也没有区分相同 name / target 下的新旧生命周期。
5. current ledger 已存在且 consent 已存在时，new_ledger 保持 None；删除目录后不会同步移除
   current ledger 中的记录。

### 官方迁移初次终态

执行 A 后逐项核对：

| Skill | 目录存在 | current ledger 仍有记录 |
|---|---:|---:|
| collab | false | true |
| create-worktree | false | true |
| debate | false | true |
| escalate | false | true |
| plan | false | true |

当前项目没有这 5 个 project-local skill 副本。用户确认相应入口不再需要，因此目录缺失是
本下游的预期终态；但官方 apply 后 managed ledger 仍错误声称这些目录由当前产品管理，文件系统
与单一事实源不一致。

### 用户确认后的现场清理

2026-08-18 再次执行 shared updater 时，产品按 active manifest 重新安装了这 5 个 skill，收据为：

    source_commit=304e6189a6724078351deea2c055b0bca52d80c1
    action_count=5
    status=completed

随后使用官方用户迁移器和锁定 fingerprint
sha256:226c0c2c0ca3763ae8f6dfa8032651e6dc81bfeac7415ab223119c74e6a19edf
事务删除 5 个目录：status=completed_with_gaps、rollback_performed=false；14 个有人工修改的
legacy skill 继续保留。官方事务仍未改写 current ledger。

在用户明确授权“清理干净”后，对 current ledger 做了哈希保护的精确补救：只移除上述 5 个
record，总记录由 20 变为 15，consents.native_memories=approved 与其余记录逐项保持不变。
最终核验为 5 个目录均不存在、5 条 ledger record 均不存在、临时文件与备份均已清理；终态
ledger SHA256 为 9960F979472C9F22090BD95383BD7B5E41D8BD6696BE3DE43EF83DF30C57BE0A。

这 5 个名称仍存在于产品 active manifest，因此未来再次运行 shared updater 时会重新安装；这是
用户接受的行为。产品缺口仍是后续 migration 无法在同一事务中表达特例并同步收口 ledger。

### 根因

- active manifest 与 compatibility transition manifest 允许同名、同 target、同 hash 重叠，却没有
  表达“默认保护”与“经用户确认的精确退休特例”。
- migration planner 只用 name + 当前目录 hash 识别退休对象，既没有先执行
  transition targets - active targets 的默认保护，也没有记录逐目标例外授权。
- apply 后缺少“每条 current ledger record 的目标必须存在且哈希匹配”的终态不变量。
- 当前 ledger 的重写与 retire-tree 不在同一必需事务内，导致成功收据也能留下 ghost record。

## 历史推荐修复（已被 current-only 边界取代）

### A. 统一 project_sync 与 git-sync 的 transition 事实源

1. project_sync 在判定 ready 前必须运行等价的 git-sync release preflight，或两者调用同一个
   transition proof 模块；禁止各自维护不同 lineage / marker / changed-path 判断。
2. 若终态无法被 repo-local build_release_plan 消费，project_sync 必须在写新版本戳前报告
   action_required，而不是 ready。
3. changed paths 必须由实际 project_sync plan / receipt 推导；禁止 contract 要求一个同步器
   根本没有修改的目标文件。
4. 对已发布但结构损坏的可信历史资产，只能依靠精确历史 hash、stable asset id 和事务迁移映射
   放行；禁止弱化当前工作树的 marker / fence 校验。
5. 若真实下游必须先做一次内容恢复，应由 planner 给出精确文件、可信来源、保留项和受支持的
   recover action，不能只在 git-sync 阶段给出死路错误。

### B. 支持显式退休特例，并事务更新 ledger

1. 默认情况下，retire-tree 候选必须从 transition targets - active targets 生成；未获例外授权的
   交集必须成为 blocker。
2. 产品应支持按精确 name + target 声明一次性退休特例，并把用户确认、作用域和 fingerprint 写入
   plan / receipt；禁止把全局 active 名称静默解释为所有下游都应删除。
3. active / transition 同名但语义不同的资产必须使用稳定 lifecycle id 或不同 target，禁止只靠
   相同 name 复用生命周期。
4. 任何 retire-tree 与 current ledger 更新必须处于同一事务；成功后 ledger 不得保留已删除目标。
5. apply 终态必须逐条验证 current ledger record：目标是普通目录、存在、内容哈希匹配；明确退休的
   target 必须已从 ledger 移除。
6. 本次 5 个 skill 不需要恢复；上游只需提供受支持的 ledger 收口事务，并保留 14 个有人工修改的
   legacy skill。

## 历史回归与验收场景（不再是当前产品合同）

1. 使用 D:\Quant\ClaudeBridgeAssist 当前 HEAD 和更新前快照执行完整
   updater -> user migration -> project plan/apply -> release preflight；最后 classification 必须为
   mixed，build_release_plan 成功生成业务版本计划。
2. 若同一真实现场仍无法分类，project_sync 必须在写 1.4.5 戳前返回 action_required，并给出
   可执行恢复清单。
3. project_sync 与 version_release 对每个 stable asset id 的 before/current ownership 结论必须
   一致；测试逐项比较，不只比较最终字符串。
4. compatibility manifest 中 transition name / target 与 active manifest 重叠且没有精确特例时，
   用户迁移 plan 必须 blocker 且 action_count=0。
5. 对 ClaudeBridgeAssist 明确传入这 5 个 name + target 的已确认特例时，plan 可以生成 retire-tree，
   receipt 必须记录授权作用域与 fingerprint。
6. 允许退休的 target 必须在同一事务中从 ledger 移除；注入失败时目录和 ledger 一起回滚。
7. apply 成功后，对 current ledger 每条 record 做 target exists + directory hash 校验，并确认 5 个
   特例目标已不存在于 ledger。
8. 真实下游复验时，5 个 skill 保持删除、ledger 不再含悬空记录，新会话不再暴露对应入口。
9. 14 个有人工修改的 legacy skill 在收口流程中继续逐字保留。
10. 完整自动测试、factory dogfood、manifest --check、mirror、instruction、project structure、
    downstream fixture 与 git diff --check 全部通过。
11. 独立审计必须覆盖“同名 active / transition”与“project_sync ready 但 release blocked”两个反例。

## 历史六类关闭证据

| 证据类别 | 当前状态 | 关闭要求 |
|---|---|---|
| 源码 | 未修复 | transition proof 单一事实源；active 退休默认保护、显式特例和 ledger 事务一致 |
| 产品传播 | 未修复 | Template、skills、manifest、VERSION、CHANGELOG 同步 |
| dogfood | 未验证 | 工厂自身 manifest / ledger 不变量通过 |
| fixture | 现有 fixture 未覆盖真实反例 | 增加默认阻断与显式特例两类端到端回归 |
| 真实下游 | A 仍失败；B 已用授权补救收口 | ClaudeBridgeAssist preflight 通过；官方事务可让 5 skill 保持删除且 ledger 收口 |
| runtime | 未验证 | 新会话不再暴露 5 个入口；$git-sync 只读 preflight 通过 |

本表仅记录 1.4.5～1.4.13 的旧边界，不能用于要求恢复已删除的 migration/ledger 机制。当前
报告保持 active，只因为上文列出的真实下游重建与 runtime 尚未执行。

## 当前恢复边界

- ClaudeBridgeAssist 项目修改仍在工作树中，没有 commit 或 push。
- 项目骨架戳已是 1.4.5，project_sync replan 为 no-op / ready。
- $git-sync 仍被 release classifier 阻断，禁止手工绕过版本自动化。
- 5 个用户级 skill 目录已删除；用户确认这是 ClaudeBridgeAssist 的预期特例，不恢复。current ledger
  中对应 5 条记录已按授权精确移除，其余 15 条记录与 native memories consent 保留。
- 14 个 modified legacy skills 已保留。
- 用户级现场已经干净，但依赖一次性人工补救；上游仍需把特例授权与 ledger 收口纳入产品事务。

## 传播四问

1. 层级：提交阻断与迁移记账缺口均属于产品层，不是 BridgeForge 工厂自用配置。
2. 通用性：所有从旧 contract 更新的高定制下游，以及需要对 legacy/current ledger 重叠项做
   精确退休特例的用户，均可能受影响。
3. 发布：修复需要 bump 根 VERSION，并在 CHANGELOG 标记 product。
4. dogfood：必须同步 Template / skills / manifests / 工厂镜像并执行完整发布硬闸。

## 关联记录

- doc/2_bugs/BUG-git-sync-contract-transition-classification.md
- doc/1_delivery/codex-project-zone-ownership/requirements_2026-08-17_codex-project-zone-ownership.md
- doc/1_delivery/git-sync-version-automation/requirements_2026-08-12_git-sync-version-automation.md
