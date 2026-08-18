---
status: implemented-awaiting-user-acceptance
next: user_acceptance
scale: M
---

# 用户级 Skill 旧兼容链退役需求

## 原始需求摘要

用户要求删除全部用户级 Skill 兼容名单，今后不再支持旧 `$bridgeforge` 到
`$bridgeforge-codex` 的自动兼容迁移，只保留 `bridgeforge-codex-manifest.json`
正式清单。用户已确认这意味着旧入口、旧 ledger、旧 Claude Skill 与旧产品目录不再由
BridgeForgeCodex 自动迁移或清理。

调用来源：`$develop` 经 `$confirm` 收敛。

## 目标

- 以 `bridgeforge-codex-manifest.json` 作为用户级 Skill 分发的唯一事实源。
- 删除 `shared-skill-manifest.json` 及其生成、消费和校验链。
- 删除旧 `$bridgeforge` 过渡入口和用户级旧资产迁移器。
- 消除 active Skill 因兼容 transition 被误删并留下 ghost ledger record 的路径。
- 保持正式 updater 的安装、刷新、hash ownership、fingerprint 与回滚能力。

## 不做

- 不删除真实用户目录中的 `.bridgeforge`、旧 ledger、`.claude` 或任何 Skill。
- 不操作真实下游项目、测试 worktree、Git commit 或 push。
- 不退役项目级 `0.86.0+` schema lineage、旧项目骨架版本戳迁移或项目同步能力。
- 不恢复或再次删除 ClaudeBridgeAssist 曾人工处理的 5 个 Skill。
- 不增加“按下游项目退休用户级 active Skill”的第二套策略。

## 任务规模与预算

- 规模：M。
- 依据：逻辑跨用户级 manifest、旧迁移器、根 Skill、安装说明、测试与发布契约；机械删除、版本和派生文件不单独抬高规模。
- 预算：45 分钟；20k 新增 token 为估算且平台无法实测；最多 1 个独立审计 agent；最多 2 轮验证。
- 停止点：若旧兼容协议仍承担正式安装、当前 updater 依赖兼容 manifest，或必须写入真实用户目录才能验收，停止并重新确认。

## 已核实事实

- 当前兼容 manifest 含 21 个 Codex transition Skill。
- 其中 19 个也在 active manifest；真正不在 active manifest 的只有 `bridgeforge` 与 `harvest`。
- 当前用户迁移器把 compatibility transition name 直接当作退休候选，能够删除仍为 active 的目录。
- apply 只在 `new_ledger` 被写入时验证新账本，不能普遍保证“每条当前账本记录均有存在且 hash 匹配的目标”。
- 当前用户机器上 `collab`、`create-worktree`、`debate`、`escalate`、`plan` 均为目录存在且当前 ledger 有记录；现场暂时没有 ghost record。

## 已确认规则

1. 用户级 Skill 的唯一正式清单是 `bridgeforge-codex-manifest.json`。
2. compatibility manifest 不再保留空壳，不再作为冻结历史面；文件与生成逻辑一起删除。
3. 旧 `$bridgeforge` 不再自迁移；旧用户必须按当前安装说明重新安装 `$bridgeforge-codex`。
4. 新产品不再读取、迁移或删除旧 Codex/Claude ledger、旧 `.bridgeforge` home 或旧用户级 Skill。
5. 正式 updater 只能操作 active manifest 明确登记且通过 ownership/hash 校验的目标。
6. 项目级旧骨架升级继续受支持，与本次用户级兼容退役严格分离。

## 拟修改

- 删除 `shared-skill-manifest.json`。
- 删除 `scripts/bridgeforge_codex_legacy_entry.SKILL.md`。
- 删除 `scripts/bridgeforge_codex_user_migrate.py` 及专项测试。
- 从 `scripts/rebuild_shared_skill_manifest.py` 删除 compatibility manifest builder/check。
- 从 `scripts/bridgeforge_codex_shared_update.ps1` 删除 `legacy_transition` 兼容分支，只消费 active manifest。
- 从 `skills/bridgeforge-codex/SKILL.md` 和 references 删除旧用户迁移 planner/apply。
- 更新安装、架构、Bug、测试、版本与 CHANGELOG；重建 active manifest。

## 验收

1. 活跃源码和产品文档不再引用 `shared-skill-manifest.json`、`legacy_transition`、旧过渡入口或用户迁移器；历史归档与 Bug 证据可保留并明确标注历史。
2. updater 只读取 `bridgeforge-codex-manifest.json`，并继续验证 source hash、目标 ownership、fingerprint、事务回滚与 ledger 终态。
3. 正式清单中的 Skill 刷新后，目标目录与当前 ledger 一致。
4. 旧兼容文件不再由 manifest 重建器生成，`--check` 对 active manifest 与受管 contract 返回成功。
5. 相关定向测试、完整自动测试、downstream fixture、factory dogfood、skill metadata、project structure、mirror drift 与 `git diff --check` 通过。
6. 独立审计覆盖“active/transition 重叠误删路径已物理消失”和“项目级旧版本升级仍保留”。

## 风险与合理假设

- 这是明确的破坏性兼容变更；旧用户不能再通过旧入口无感迁移。
- 用户机器可能遗留旧目录与 ledger；本产品只停止管理，不自动删除。
- 假设当前安装器与 active updater 已能独立完成新安装和刷新；若代码检查否定该假设，按停止点处理。
- 删除兼容 manifest 后，历史测试与文档必须区分“活跃协议”与“事故证据”，禁止为了搜索零命中而篡改历史记录。

## 自动化边界

- 允许修改当前仓库产品源码、测试、需求卡、设计文档和派生 manifest。
- 禁止写入 `%USERPROFILE%`、真实下游、测试 worktree、remote、Git index、commit 或 push。

## 实施记录

- 删除 compatibility manifest、旧 `$bridgeforge` 入口、用户级旧资产迁移器、专项测试和
  `scripts/compat/legacy-shared-skills/**` 冻结 payload。
- manifest 重建器只维护 active manifest 与 managed contract；正式 updater 删除
  `legacy_transition` 过滤和旧 ledger adoption，只接受当前账本 ownership。
- 根 Skill 删除一次性用户迁移 planner/apply，用户维护说明与安装文档改为“不支持自动迁移，
  旧用户重新安装”。
- 正式 manifest 已重建；VERSION 升至 1.4.13，CHANGELOG 记录破坏性兼容退役。
- 安装器已物理删除旧 `.bridgeforge` junction 清理能力；正式 updater 在生成 upsert/remove
  计划前验证现存受管目录的实际 hash 与当前正式 ledger 完全一致，漂移时整轮零写入。
- 未写入真实用户目录、真实下游、Git index、commit 或 remote。

## 验证记录

- 第一轮定向测试 84 项中 81 通过、3 失败：两项把 Windows 遗留空目录误当作仍有兼容
  payload，一项 active manifest 尚未完成受保护 dogfood contract 重建；产品逻辑测试未失败。
- 第二轮完整 discovery 在机械修补前运行 204 项：发现项目同步 fixture 仍从 manifest builder
  读取已删除的用户级兼容常量，以及同一空目录断言；按预算闸停止后，用户批准增加一次机械
  修复与完整复测。
- 扩展轮完整自动测试：
  `.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`，
  最终 250/250 通过。覆盖 active-only updater、unmanaged conflict、正式账本、事务回滚、
  现存受管目录漂移时 refresh/retirement 均零写阻断、项目
  `0.86.0+` lineage、Memory、project sync 与 release classifier。
- downstream fixture：`.venv\Scripts\python.exe -B scripts/tests/run_downstream_fixture.py`，
  `status=passed`，已发布 lineage 26/26 可执行迁移；报告 29 个发布版本、无失败。
- `.venv\Scripts\python.exe -B scripts/rebuild_shared_skill_manifest.py --check`：exit 0，
  `already current`。
- `.codex/hooks/skill_metadata_check.py`、`project_structure_check.py`、
  `mirror_drift_check.py`、`instruction_source_check.py`：全部 exit 0；structure 只有既有 archive
  advisory。
- `git diff --check`：exit 0；仅有 CRLF/LF 提示。
- 未验证：真实旧用户重新安装、真实下游、Codex Desktop runtime、commit/push。
- 最终独立审计：通过，blocker=0、high=0。复审确认旧 `.bridgeforge` 清理能力已物理删除；
  正式 updater 在事务前执行 `actual_hash == ledger.content_hash` ownership 校验，active refresh
  与 manifest retirement 两个漂移反例均保持 Skill、ledger、command home 和事务日志零写。
  独立最小复测 6/6、manifest `--check`、skill metadata、mirror drift、instruction source 与
  `git diff --check` 全部通过。
