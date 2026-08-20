---
status: implemented-awaiting-independent-audit
next: independent-audit-and-real-cba-trial
scale: M
budget: 45_minutes_20k_tokens_unmeasured_1_auditor_2_validation_rounds
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
---

# Project Sync 显式适配事务需求

## 原始需求摘要

ClaudeBridgeAssist 1.4.22 真实 Apply 证明：Planner 能准确输出 `codex.precommit G1`，但 G 项只可
review、不可执行，CLI 没有把用户已经批准的新规则适配传入事务的入口。用户要求修复该骨架产品
缺陷，并选择只授权明确点名的 G 项。

调用来源：`$develop` 经 `$confirm` 收敛。

## 目标

- 为 project-sync 提供精确选择 G 项并事务执行的正式入口。
- 让 Apply 与后续 `$git-sync` 共同验证并消费同一显式适配证明。
- 保持当前单一 ownership 规则、项目所有内容、零写 fail-closed、回滚和 stamp-last。
- 覆盖 Stratus 退役 rule、M2 AGENTS、Causis hooks 与 CBA pre-commit 四类当前现场。

## 不做

- 不恢复历史 marker、region hash、旧 AGENTS projection 或旧 hooks ownership 规则。
- 不自动批准当前计划中的全部 G，不放行未选择、未知或漂移项。
- 不手工改真实项目文件、版本戳、Git index 或 Git 历史。
- 不处理 M2 另外 23 个普通 gap；它们继续按原规则 fail-closed。
- 不 commit 或 push 真实下游。

## 任务规模与预算

- 规模：M。
- 依据：逻辑跨 Planner 的 G 分类、Apply 选择/fingerprint、release evaluator、`$git-sync` 收据消费、
  Template/dogfood 与四类迁移回归；机械镜像、版本、CHANGELOG 和 manifest 不单独抬高规模。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算；平台无法可靠实测）。
- agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多 2 轮实质验证。
- 超预算停止点：必须引入长期 ledger、修改 Git 历史、改变用户已确认的单一 ownership 规则，或
  需要第三轮实质修复时停止并重新确认。

## 已核实事实

1. G 当前是不可执行 review 清单；`--selected-risk/--selected-action` 只接受 R/U 等既有可执行动作。
2. CBA 正式 Apply 使用紧邻 fingerprint 后返回
   `planned release preflight rejected the prospective update; zero writes performed`。
3. CBA Apply 前后 HEAD、6 项 dirty 清单、status SHA-256 和四个关键文件 hash 完全一致。
4. 四个目标项目的 `.runtime/` 均由项目 `.gitignore` 忽略，可承载不进入 Git 的本地一次性收据。
5. 当前四项目分别存在 Stratus 退役 rule、M2 AGENTS、Causis hooks、CBA pre-commit G 类卡点。
6. project-sync 与 `$git-sync` 若不共享适配证明，项目更新后仍会在提交入口再次阻断。

## 已确认规则

1. 只授权用户明确选择的 G ID，禁止“选择一个即放行全部”。
2. 每项授权必须绑定 G ID、stable asset id、目标路径、当前 HEAD、before/after hash、contract hash、
   aggregate fingerprint 与 selection fingerprint。
3. 未选择、消失、新增、重新编号或任一绑定字段漂移时，整轮零写阻断。
4. 只有 prospective/current 目标通过当前严格 validator，且可机判的项目区或 external projection
   保持不变时，才允许应用选中的 G。
5. `release_transition_review` 与能够确定性包裹旧内容的 `agents_ownership_review` 可进入显式适配；
   其他普通 gap 和未知 ownership 继续不可执行。
6. Apply 成功后在 `.runtime/bridgeforge-codex/` 写一次性适配收据。它只提供本地 transition proof，
   禁止纳入 Git。
7. `$git-sync` 只接受完全匹配当前 HEAD、contract、目标 hash 与 fingerprint 的收据；任一漂移即拒绝。
8. Git 提交生成后删除已消费收据；提交前失败保留可验证收据，内容漂移后自动失效。
9. 适配写入仍处于统一项目事务；validator 全过后最后写骨架戳，任何失败完整回滚。

## 数据与接口映射

| 输入/状态 | 目标行为 |
|---|---|
| Planner `G1..Gn` | 保持稳定 ID 和完整原因，并标记是否具备确定性 adaptation payload |
| `--selected-adaptation G1` | 只选择该精确 G；可重复传入多个 ID |
| aggregate fingerprint | 绑定完整计划与 G 清单 |
| selection fingerprint | 绑定已选 G、适配 payload 和预检结果 |
| `.runtime/bridgeforge-codex/explicit-adaptation.json` | 保存一次性、本地、严格可验证的 transition proof |
| `$git-sync` release preflight | 验证并只消费完全匹配的 receipt items |

## 拟修改

- `scripts/bridgeforge_codex_project_sync.py`：G eligibility、精确选择、适配 payload、fingerprint、事务与收据。
- `templates/scripts/version_release.py` 及 dogfood 镜像：只接受经严格验证的精确 adaptation proof。
- `templates/scripts/codex_git_sync.py` 及 dogfood 镜像：验证、消费和清理一次性收据。
- `skills/bridgeforge-codex/SKILL.md`、`skills/git-sync/SKILL.md`：单次确认与收据边界。
- 相关 tests、downstream fixture、contract、manifest、VERSION、CHANGELOG、源 Bug 与索引。

## 验收

1. CBA 选择 G1 后成功更新，`PROJECT_EXTENSION` 逐字保持，validators 通过，最后写戳，二次 Planner
   为 no-op；未选择 G1 时继续零写阻断。
2. G ID、HEAD、before/after hash、contract hash、aggregate/selection fingerprint 任一漂移时零写阻断。
3. Stratus rule、M2 AGENTS、Causis hooks、CBA pre-commit 四类 fixture 均覆盖正反例。
4. M2 的普通 gap 不因选择 AGENTS G 而被吸收、删除或放行。
5. `$git-sync` 测试证明只消费匹配收据；未知、过期、跨仓库或漂移收据 fail-closed。
6. 收据不进入 Git；成功创建提交后删除，失败/回滚边界有明确收据。
7. 相关测试、完整自动测试、downstream fixture、manifest `--check`、mirror、instruction、structure、
   metadata、`git diff --check` 与独立审计通过。
8. 真实 CBA 完成 plan -> selected adaptation apply -> validators -> stamp-last -> no-op replan；不 commit/push。

## 合理假设与风险

- `.runtime/` 是四个当前项目的本地忽略区；若目标项目未忽略该目录，收据写入必须 fail-closed。
- 收据是短生命周期的事务证明，不是长期 ownership ledger 或第二套 contract。
- 对 retired rule 内容是否已经人工迁入项目区，机器只能绑定用户选择与精确 before/after hash，不能
  替代业务语义判断；未被用户精确选择时禁止删除。
- 跨机器移动未提交工作区不保证携带本地收据；该场景必须重新形成可验证适配计划，禁止静默放行。

## 自动化边界

- 允许修改当前 BridgeForge 产品源码、测试、Template、dogfood、文档和派生产物。
- 允许在产品修复与独立审计通过后，按用户授权重新更新真实 CBA 并写其忽略区收据。
- 禁止修改其他真实项目，直至 CBA 完整闭环通过；禁止任何真实下游 commit/push。

## 后续交接

- `$develop` 主对话完成 discovery、实现和最多两轮验证。
- 因项目硬规则要求，本轮使用最多一个独立 `review-auditor` 审计自身改动。
- 审计通过后返回真实 CBA 试用闭环。

## 实施记录

- 1.4.23 为 Planner 增加 `adaptation_eligible` 与稳定 G 编号，Apply 增加可重复的
  `--selected-adaptation GID`；缺项、重复、未知、不可执行或计划漂移均在事务前阻断。
- `version_release.py::evaluate_release_transition()` 现在只接受 schema v1 一次性证明，并严格验证
  project root、Git HEAD、current contract、每个目标的 HEAD/current hash 与 selection fingerprint；
  每项证明必须真实命中一个原本会阻断的 transition，未消费证明反而报错。
- Apply 在 validator 与 release preflight 通过、stamp-last 完成后，事务写入 Git 忽略的
  `.runtime/bridgeforge-codex/explicit-adaptation.json`；`codex_git_sync.py` 将同一证明传回统一
  evaluator，并只在 commit 创建成功后删除。
- 无分区 AGENTS 只有在当前规则能确定性包裹旧文件、公共区严格 current 且旧字节在项目区恰好
  保留一次时才标记可执行；unclosed fence 等不可证明内容继续不可执行。
- 首轮独立审计后，evaluator 会独立重算 project/external projection 与 transition fingerprint；
  收据即使同步改写 selection hash 也不能绕过。AGENTS 包裹保留原始 CRLF bytes，存在普通 gap 时
  显式适配在任何写入前阻断。
- Stratus 退役资产只在工作树已删除、HEAD 命中可信旧资产且用户精确选择时生成
  before/after-null 事务动作；dirty 或未知目标保持不可执行。
- Causis hooks 的 HEAD 只负责证明旧 managed dispatcher；Apply 前当前 external handlers 作为项目区
  基线，prospective、事务后与 `$git-sync` 复验均必须保持一致。
- hooks 顶层 `description` 按实际语义归骨架管理。当前合同登记全部可信发布基线的精确历史值；只有
  current 或已登记历史值可迁移，任意自定义值零写阻断，无 ID 项目 handler 仍保持 external。
- Planner 对累计 proof 做有界固定点展开，直到统一 evaluator 真正通过或无法推进；不会只展示首层
  G 后在 Apply 暴露第二层。proof-only attest 只证明当前目标精确 canonical，并由 evaluator 与
  `$git-sync` 消费，不执行同字节写入；managed Markdown、hooks 与 generic merge 分别按 current-before
  项目区、external handlers 和 exact-whole 规则 fail-closed。

## 验证记录

- 针对性 transaction 正例：精确选择 G1 后 Apply、preflight、收据、no-op replan 通过；不选择
  G1 保持零写。
- evaluator 正反例：exact blocked region 被唯一消费；after hash 漂移拒绝。
- git-sync 单测：证明传入 release plan，commit 创建后删除收据。
- G 选择顺序负例：相同 ID 集合被重排时整轮零写阻断。
- project-sync、release evaluator 与 root Skill 相关回归：116/116 通过。
- 完整自动测试：300/300 通过；downstream fixture 返回 `status=passed`，覆盖 29 个已发布版本，
  其中 19 个旧版本保持显式 pre-commit 适配要求。
- manifest `--check`、mirror、instruction source、project structure、skill metadata 与
  `git diff --check` 均 exit 0；structure 只报告既有归档 advisory。
- 首轮独立审计的 4 High/1 Medium 已修复，等待同一 auditor 复审；真实 CBA、Git index 与 remote
  尚未写入。
- 2026-08-20 真实 Causis 零写 Planner 为 `safe=13 / gaps=0 / blockers=0`，唯一 hooks G1
  `adaptation_eligible=true`；Stratus 真实 Planner 的八个 retirement G 项均可构造。更新后的
  project-sync、release evaluator 与 hooks 定向回归 135/135，manifest `--check` 为 current。
  产品完整回归、独立复审和真实项目 Apply 尚未执行。
- 独立复审发现 Stratus 首层 8 个 retirement 后还会暴露 24 个 transition issues。修复后真实 Stratus
  Planner 一次列出 32 个 G 且 32/32 可执行；新增集成 fixture 验证第二层 proof-only 目标不会写盘，
  真实 CBA/Causis 仍为 0 gaps/0 blockers、唯一 G1 可执行，M2 的 23 个 ordinary gaps 继续零写。
  等待最终独立复审和第二轮完整自动测试。
