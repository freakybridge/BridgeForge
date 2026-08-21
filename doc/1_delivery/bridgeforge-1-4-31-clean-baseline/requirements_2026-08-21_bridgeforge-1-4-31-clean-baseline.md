---
status: validated-audited-awaiting-user-trial
next: user-trial-or-git-sync
scale: L
budget: 230_minutes_75k_tokens_unmeasured_3_agents_4_validation_rounds
target_release: 1.4.33
clean_baseline: 1.4.31
---

# BridgeForge 1.4.31 清洁基线需求

## 原始需求摘要

用户要求为下一个发布版本调整骨架清洁基线。确认过程中，原拟定的 `1.4.32` 最低基线调整为 `1.4.31`：当前开发期间根 `VERSION` 保持 `1.4.31`，最终由 `$git-sync` 自动发布 `1.4.32`；低于 `1.4.31` 的项目统一执行破坏性重装，`1.4.31+` 只执行 schema 3 current-only 更新。

调用来源：用户直接调用 `$confirm`，经逐项确认形成本文档。

## 目标

- 将骨架最低清洁基线从 `1.4.28` 提升到 `1.4.31`。
- `<1.4.31` 项目不再走历史增量兼容，统一通过 `PreservationManifest` 执行破坏性重装。
- `>=1.4.31` 项目继续使用 schema 3 current-only 更新。
- 清除只服务 `1.4.28`～`1.4.30` 当前基线兼容的活动代码、测试和当前文档。
- 当前开发期间保持根 `VERSION=1.4.31`，最终由 `$git-sync` 生成 `1.4.32`。

## 不做

- 不保留 `1.4.28`～`1.4.30` 的专用兼容分支。
- 不把 schema 3 升为 schema 4。
- 不解析旧项目的 `.codex/managed-skeleton.json` 来恢复历史 ownership。
- 不删除 `1.4.31+` current-only 更新所需的相邻合同差集、受管资产删除事务和回滚能力。
- 不修改四个真实下游项目；只允许只读检查。
- 不修改历史 CHANGELOG 条目、旧需求卡、旧 debate、Bug 现场与 archive 文档。
- 未经用户显式调用 `$git-sync`，不 commit、不 push、不发布版本。

## 任务规模与预算

- 规模：L。
- 判定依据：改动涉及破坏性重装路由、版本身份、项目资产保留、Hook 正规化、事务回滚和发布边界。
- 时间预算：180 分钟。
- token 预算：60k，平台无可靠计量器，标记为未实测。
- agent 预算：最多 3 个子 Agent。
- 验证预算：最多 2 轮完整验证。
- 超预算停止点：预计超过任一预算，或发现必须引入长期迁移状态、schema 升级、真实下游写入、新的业务 ownership 决策时，停止并重新确认。
- 2026-08-21 经用户确认扩展预算：增加 30 分钟、10k 未实测 token、0 个新 Agent 和 1 轮完整验证；总上限更新为 210 分钟、70k 未实测 token、3 个 Agent、3 轮完整验证。
- 2026-08-21 窄复核发现 current stamp 最终写入前缺少 CAS；用户再次确认增加 20 分钟、5k 未实测 token、0 个新 Agent 和 1 轮完整验证，总上限更新为 230 分钟、75k 未实测 token、3 个 Agent、4 轮完整验证。

## 已核实事实

1. 当前仓库根版本为 `1.4.31`。
2. 当前受管合同使用 schema 3。
3. 当前活动实现仍以 `1.4.28` 作为最低 current baseline。
4. `$git-sync` 会先验证当前 `1.4.31` 状态，再自动生成下一个补丁版本。
5. 用户确认不存在必须继续增量维护的真实 `1.4.28`～`1.4.30` 下游项目。
6. 四个已知真实下游只允许只读检查；破坏性重装与 Hook 迁移只能在临时副本中验证。

## 已确认规则

1. 项目只有一个合法 BridgeForge 版本戳时，无论使用 `.codex/.bridgeforge_version` 还是 `.codex/.bridgeforge_codex_version`，只要版本 `<1.4.31` 就进入破坏性重装。
2. 双戳、非法版本、身份冲突、无法识别的项目结构必须零写阻断。
3. 旧项目的 `.codex/managed-skeleton.json` 直接丢弃，不参与 ownership 恢复或项目资产识别。
4. 项目资产只通过当前文件系统生成临时 `PreservationManifest`：
   - memory 和 Skill 必须保留，并按当前 `1.4.31+` 规则验证；
   - Rule、根 AGENTS 项目区、pre-commit 项目扩展与项目 Hook 必须显式登记；
   - 每个 `user-decision` 项必须明确 preserve 或 delete，禁止“未选择等于删除”；
   - 未知、损坏或无法闭合的结构必须阻断。
5. 旧的散落项目 Hook 由独立 Agent 整理为自包含的 `.codex/hooks/project_XXXX/` 目录；注册、入口脚本与私有资源作为不可拆分的同一资产确认。
6. `PreservationManifest` 只服务一次破坏性重装；成功后不保留长期迁移清单或历史映射状态。
7. Planner 必须零写；Apply 前重新核对 inventory fingerprint；安装 fresh canonical 后才回灌已确认资产；任一可捕获失败必须回滚本轮全部写入；版本戳最后写。
8. 成功重装和 current-only 更新后，立即重跑 Planner，结果必须为 no-op。

## 版本与数据映射

| 输入状态 | 目标路径 |
|---|---|
| 单一合法版本戳 `<1.4.31` | `PreservationManifest` 破坏性重装 |
| 单一合法版本戳 `>=1.4.31` | schema 3 current-only 更新 |
| 双戳、非法戳、身份冲突 | 零写阻断 |
| 旧 managed contract | 重装时丢弃，不读取 ownership |
| 散落项目 Hook | 经独立 Agent 映射到 `.codex/hooks/project_XXXX/` 自包含目录 |
| memory / Skills | 自动保留，并使用当前可信校验器验证 |

## 拟修改范围

- `templates/scripts/current_baseline.py` 及 dogfood 镜像：最低基线与共用验证规则。
- `scripts/bridgeforge_codex_project_sync.py`：版本身份路由、旧项目重装、PreservationManifest 和 Hook 正规化入口。
- `skills/bridgeforge-codex/**`：当前同步流程及用户确认说明。
- `templates/managed-skeleton.json`、dogfood contract 和相关派生产物：通过现有构建流程同步。
- `scripts/tests/**`：版本矩阵、零写阻断、保留清单、Hook 正规化、回滚与 no-op 回归。
- `README.md`、`INSTALL.md`、当前架构与运行手册、`CHANGELOG.md` 新发布段及本需求卡。

## 验收

1. 两个合法版本戳文件名在版本 `<1.4.31` 时均进入破坏性重装；`1.4.31+` 只进入 current-only 更新。
2. 双戳、非法戳、未知项目结构、无法闭合的 Hook 或知识资产全部零写阻断。
3. 旧合同即使缺失或损坏也不影响旧项目重装的 ownership 发现，因为重装不读取它。
4. 所有待决项目资产必须形成完整 preserve/delete 决策，遗漏选择不能执行 Apply。
5. 临时旧项目中的散落 Hook 能正规化为 `.codex/hooks/project_XXXX/`，注册和目录原子保留或删除，不产生悬空注册。
6. memory 和 Skills 在保留后通过当前兼容性检查；孤儿目录、非法 metadata、reparse 或未知结构 fail-closed。
7. 故障注入证明 Planner 零写、Apply 全事务回滚、版本戳最后写。
8. 成功重装和 current-only 更新后 no-op replan。
9. 完整 unittest、downstream fixture、factory dogfood、manifest、structure、mirror、文档索引与 `git diff --check` 全部通过。
10. 独立审计达到 Blocker 0 / High 0 / Medium 0；Low 必须明确处置。
11. 四个真实下游只读检查前后 Git 与文件状态不变；未执行真实 runtime smoke 时不得宣称其已通过。

## 合理假设与风险

- 用户提供的事实成立：不存在需要继续保留 `1.4.28`～`1.4.30` 增量更新路径的真实项目。
- 非 Python、跨目录或动态依赖的旧 Hook 不能自动证明闭包；独立 Agent 必须显式整理，无法证明时阻断。
- 提升最低基线会使任何 `<1.4.31` 项目失去增量更新资格，这是已确认的破坏性边界。
- 当前版本保持 `1.4.31` 是 `$git-sync` 能先验证现态、再生成 `1.4.32` 的必要发布边界。

## 自动化边界

- 最多 3 个子 Agent，职责限于只读调研、边界明确的实现或独立审计，不代替用户决策。
- 破坏性重装、Hook 搬迁和故障注入只在临时项目或临时副本中执行。
- 真实下游只读，不创建 `.venv`、不运行会写盘的 Planner/Apply/Hook，不修改 Git index。
- 不自动 commit 或 push；只有用户最终再次调用 `$git-sync` 才允许发布 `1.4.32`。

## 后续交接目标

- 推荐交接 `$develop`：按本卡完成调研、实现、传播、两轮以内验证、独立审计和用户试用说明。
- 若实现前需要重新论证架构，交接 `$debate`。
- 若用户希望以多 Agent 文件边界并行推进，交接 `$collab`。

## 实施记录

- 2026-08-21：将 `MINIMUM_CURRENT_BASELINE` 提升到 `1.4.31`，并保持 Template 与 dogfood 检查器逐字一致。
- 2026-08-21：同步器删除本地阈值副本，改为读取可信检查器常量；两个戳文件名统一按版本路由。
- 2026-08-21：补充旧戳 `1.4.31+` prospective 校验与事务内迁移，旧戳删除纳入 CAS/rollback，当前戳仍最后写。
- 2026-08-21：rebuild 不读取旧 managed contract；未知 `.codex/**` 结构改为 blocker，canonical 项目 Hook bundle、Rule、AGENTS 项目区、pre-commit 扩展、memory 与 Skills 保持原有清单边界。
- 2026-08-21：同步器未新增历史 Hook 解析器；活动 Skill 和架构文档明确散落 Hook 必须先由独立 Agent 在临时副本或受控前置步骤中正规化。
- 2026-08-21：新增版本矩阵、旧合同缺失/损坏、未知结构、Hook 正规化闭环、旧戳迁移回滚与 no-op 定向测试；真实下游未写入。
- 2026-08-21：独立审计发现关键叶子 reparse 校验不完整；同步器改为在解析链接前检查版本戳、`AGENTS.md` 与 `.githooks/pre-commit` 的词法路径、祖先和叶子，Planner 与 Apply 均 fail-closed。
- 2026-08-21：README/INSTALL 将 `1.4.31` 改述为长期有效的“最低清洁基线”，避免最终 `$git-sync` 发布 `1.4.32` 后活动文档立即过期。
- 2026-08-21：Plan 新增 current stamp 的预期缺失状态或 SHA256，并纳入 aggregate fingerprint；Apply 开始和最终写戳前均重新检查 lexical 路径、plain-file 状态与 hash，事务中途漂移时回滚本事务且不吸收外部戳修改。
- 2026-08-21：真实 ClaudeBridgeAssist 重建暴露 `doc/README.md` 项目索引丢失；1.4.33 让 rebuild 对 `managed_blocks` 继续复用 schema 3 ownership 合并，公共行升级、项目标题与非受管索引行保留，详见 `BUG-rebuild-drops-project-doc-index.md`。

## 验证记录

- 第一轮定向测试在可信合同源哈希校验处统一停止：`templates/scripts/current_baseline.py` 已修改，而 `templates/managed-skeleton.json` 尚未通过受控构建流程重建。该停止发生在测试项目写入前；待主 Agent 重建合同与 dogfood manifest 后复跑定向测试。
- 主 Agent 完成受控合同与 manifest 重建后，`.venv\Scripts\python.exe -B -m unittest scripts.tests.test_current_baseline_project_sync`：34/34 通过。
- `.venv\Scripts\python.exe -B scripts/tests/run_downstream_fixture.py`：3/3 通过，覆盖散落 Hook blocker、临时正规化输入、PreservationManifest 重建与 no-op。
- `git diff --no-index -- templates/scripts/current_baseline.py .codex/scripts/current_baseline.py`：零差异。
- `.venv\Scripts\python.exe -B -m unittest scripts.tests.test_current_baseline_release`：14/16 通过；剩余 2 项暴露工厂同版本合同已重建但 HEAD anchor 仍是旧合同，release evaluator 在 prospective patch bump 前阻断。该问题涉及 `templates/scripts/version_release.py` / `$git-sync` prospective snapshot，已交主 Agent 处理，禁止通过放宽测试掩盖。
- 主 Agent 保留同版本合同自证阻断，仅允许 factory 在已按提交消息算出下一版本时构造内存 prospective contract；同一 current checker 继续核对 HEAD 前进、source hash、dogfood 与 ownership。`test_current_baseline_release` 修复后 16/16 通过，并证明当前 `VERSION=1.4.31` 可规划 `1.4.32`。
- 第一轮完整验收：`.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`，248/248 通过。
- 第一轮完整验收：`.venv\Scripts\python.exe -B scripts/tests/run_downstream_fixture.py`，3/3 通过。
- 第一轮完整验收：`.venv\Scripts\python.exe -B scripts/rebuild_shared_skill_manifest.py --check`，manifest unchanged。
- 第一轮完整验收：`.venv\Scripts\python.exe -B templates/hooks/project_structure_check.py --root . --json`，`errors=[]`；仅有与本需求无关的既有归档 advisories。
- 第一轮完整验收：Template/dogfood 的 `current_baseline.py`、`version_release.py`、`codex_git_sync.py` 三组 `git diff --no-index` 均为零差异；`git diff --check` 通过。
- 第二轮完整验收在目录 reparse 修复后运行全量测试，249/249 通过；fixture、manifest、structure、三组镜像与 `git diff --check` 同轮通过。
- 独立审计结论为 Blocker 0 / High 0 / Medium 2 / Low 0；两个 Medium 分别为关键叶子 reparse 检查缺口和活动文档版本措辞会随发布过期，均已在用户批准的扩展预算内修复。
- 修复定向验证：`.venv\Scripts\python.exe -B -m unittest scripts.tests.test_current_baseline_project_sync`，37/37 通过，覆盖 reparse `.codex/**` 目录、`AGENTS.md`、`.githooks/pre-commit` 与 obsolete 版本戳零写阻断。
- 第三轮完整验收：`.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`，251/251 通过。
- 第三轮完整验收：downstream fixture 3/3、manifest unchanged、project structure `errors=[]`、三组 Template/dogfood 镜像零差异、`git diff --check` 通过；structure 输出仅含与本需求无关的既有归档 advisories。
- 第二次窄复核确认原两个 Medium 已关闭，但发现 current stamp 在事务中途可被外部改写并于最后静默覆盖；修复定向测试注入 `after-memory-index` 漂移，验证 Apply 回滚且外部 `1.4.30` 戳原样保留，project-sync 38/38 通过。
- 第四轮完整验收：全量 unittest 252/252、downstream fixture 3/3、manifest unchanged、project structure `errors=[]`、三组 Template/dogfood 镜像零差异、`git diff --check` 全部通过。
- 最终独立窄复核：Blocker 0 / High 0 / Medium 0 / Low 0；独立注入 `after-memory-index: 1.4.31 -> 1.4.30` 后，Apply 以 `current version stamp drifted during apply` 阻断，本事务回滚且外部 `1.4.30` 原样保留。未运行真实 `$git-sync`。
- 真实下游验证状态已更新：ClaudeBridgeAssist 后续已完成 1.4.26 → 1.4.32 重建并暴露文档索引缺陷；本需求内其余三个真实 checkout 仍不得据此宣称已完成 apply/runtime smoke。
- 1.4.33 文档索引修复定向用例通过；project-sync 39/39、release 16/16、补测后全量 unittest 253/253、downstream fixture 3/3、manifest unchanged、project structure `errors=[]`、Template/dogfood contract 零差异、`git diff --check` 均通过。
- 第一轮独立审计为 Blocker 0 / High 0 / Medium 2 / Low 0；补齐项目标题、公共行升级、歧义 Markdown 零写回归和真实下游记录后，最终独立窄复核为 Blocker 0 / High 0 / Medium 0 / Low 0。
