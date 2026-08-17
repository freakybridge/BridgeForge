---
status: reported
severity: high
scope: BridgeForgeCodex 1.4.5 end-to-end update, git-sync handoff, and user-skill migration
reported_at: 2026-08-17
downstream: D:\Quant\ClaudeBridgeAssist
factory_head: 304e6189a6724078351deea2c055b0bca52d80c1
product_version: 1.4.5
related_bug: BUG-git-sync-contract-transition-classification.md
---

# BUG：BridgeForgeCodex 1.4.5 真实下游仍有一个提交阻断和一项迁移记账缺口

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

## 推荐修复

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

## 回归与验收场景

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

## 六类关闭证据

| 证据类别 | 当前状态 | 关闭要求 |
|---|---|---|
| 源码 | 未修复 | transition proof 单一事实源；active 退休默认保护、显式特例和 ledger 事务一致 |
| 产品传播 | 未修复 | Template、skills、manifest、VERSION、CHANGELOG 同步 |
| dogfood | 未验证 | 工厂自身 manifest / ledger 不变量通过 |
| fixture | 现有 fixture 未覆盖真实反例 | 增加默认阻断与显式特例两类端到端回归 |
| 真实下游 | A 仍失败；B 已用授权补救收口 | ClaudeBridgeAssist preflight 通过；官方事务可让 5 skill 保持删除且 ledger 收口 |
| runtime | 未验证 | 新会话不再暴露 5 个入口；$git-sync 只读 preflight 通过 |

六类证据全部满足前，本报告不得标记 resolved。

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
