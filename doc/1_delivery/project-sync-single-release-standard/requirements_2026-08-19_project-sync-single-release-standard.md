---
status: implemented-awaiting-user-acceptance
next: user_acceptance
scale: M
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
---

# Project Sync 单一 Release 验收标准需求

## 2026-08-21 current-only 跨合同发布补充标准

- 发布分类必须先验证当前 ownership contract，再分别用 Git HEAD contract 解析 HEAD、用当前
  contract 解析当前工作区；跨版本资产只能按稳定 asset id 对齐，禁止用任一侧合同代替另一侧。
- 当前 contract 损坏必须 fail-closed；旧侧 contract 不可验证时必须保守归类 `mixed`，禁止推断为
  `skeleton-only`。HEAD contract 缺失视为合同首次引入，不得要求 HEAD 已持有当前受管资产。
- `explicit-adaptation.json` 及任何历史适配收据不得作为 release evaluator 输入，也不得覆盖
  current-only 分类。产品不得保留并行旧判定器。
- 废弃收据只能在 current-only evaluator 独立通过且 Git commit 成功后退休；任何预检、分类或
  commit 失败都必须保留现场，不得借删除收据绕过阻断。
- 真实下游仍必须完成 plan -> apply -> validators -> stamp-last -> no-op replan；只有随后运行项目
  自带 `$git-sync` 并证明工作区与远端同步，才算端到端关闭。

## 原始需求摘要

修复 `bridgeforge-codex` Planner 先报告 `ready`、Apply 才被严格 release preflight
阻断的问题。Planner、Apply 与后续 `$git-sync` 的骨架 transition 必须直接调用同一个
核心验收函数；三者只允许输入快照来源不同，禁止复制或维护第二套合格标准。

## 调用来源与后续交接

- 调用来源：用户逐项审阅已收敛的问题清单后，要求先修问题 #1；经 `$plan` 明确方案，
  再由 `$develop` 调用 `$confirm` 固化本卡。
- 后续交接：主对话完成 discovery、实现和最多两轮验证；在预算内使用最多一个独立审计
  agent；不自动修改真实下游、commit 或 push。

## 目标与用户可见行为

建立唯一入口 `evaluate_release_transition(repo, snapshot, prospective_version)`，统一返回
是否通过、ownership 分类、稳定问题 ID、逐文件原因和 action-required 清单。

- Planner 传入模拟更新后的内存快照；只有该函数通过时才显示 `ready`。
- Apply 传入事务写入后的真实工作区快照；结果与计划不一致时完整回滚。
- `$git-sync` 在骨架 transition 场景传入提交前 Git / 工作区快照，使用同一函数判断。
- 失败必须在首次 plan 中显示稳定 `G*` 清单，禁止再出现 `ready -> apply blocked`。

## 规模与预算

- 规模：M。逻辑改动跨 project sync、release classifier、Git transition 调用、收据和测试，
  但目标、接口和非目标已经明确。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算；平台无法可靠实测）。
- agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多两轮；同一轮可包含多条预定验收命令。
- 超预算停止点：需要第三轮实质修复、必须改变本卡用户行为、或必须连带修复问题 #2～#9
  时立即停止并重新确认。
- 独立审计发现确认后的 risk / absorption 尚未在写盘前构造最终 prospective overlay；用户追加批准
  `20 分钟 / 8k token 估算 / 1 次修补验证与复审`。平台无可靠 token 计量，未实测。

## 已核实事实

1. `build_plan()` 当前在资产规划后直接生成 readiness，没有运行 release preflight。
2. 严格 preflight 当前在 Apply 已写入事务文件后、写骨架戳前才运行。
3. `version_release.py::preflight_contract_transition()` 直接读取工作区，尚不能消费 Planner
   的内存 prospective payload。
4. StratusAgent、causis_risk_suite 与 ClaudeBridgeAssist 均出现 plan `ready`、Apply
   `blocked`；现有事务回滚和 stamp-last 行为正确，必须保留。
5. 当前 Template 中的 `version_release.py` 是受信任产品实现，下游安装副本是其受管传播
   结果；两者必须保持逐字一致。

## 已确认规则与接口

1. Planner、Apply、`$git-sync` 的骨架 transition 必须直接调用同一个核心函数。
2. 唯一核心函数可以调用纯解析 helper，但最终合格结论、分类和问题 ID 只能由该函数返回。
3. `project_sync` 禁止自行复制 contract、ownership 或 release 合格判断。
4. `snapshot` 统一表示读取视图：Planner 使用内存 overlay，Apply 使用真实工作区，
   `$git-sync` 使用提交前 Git / 工作区视图。
5. Planner 的模拟视图必须覆盖创建、替换、删除、contract 更新和 prospective stamp，且零写入。
6. 模拟验收结果必须进入 aggregate fingerprint；规划后漂移时 Apply 零写入停止。
7. Apply 后复核用于防止规划与执行之间发生漂移，不得成为另一套标准。
8. 任一失败必须 fail-closed、保留项目内容、输出 stable asset id / target / reason，
   禁止路径特判或不可信 hash 放行。

## 拟修改

1. `templates/scripts/version_release.py` 与 `.codex/scripts/version_release.py`：建立统一
   snapshot 读取边界和唯一 `evaluate_release_transition()` 入口。
2. `scripts/bridgeforge_codex_project_sync.py`：根据计划动作构造 prospective overlay，
   plan/apply 均调用唯一入口，并把结果纳入 plan、收据和 fingerprint。
3. `$git-sync` 使用的 transition 路径：改为调用同一入口，删除或收口重复判断入口。
4. `scripts/tests/test_bridgeforge_codex_project_sync.py` 与
   `scripts/tests/test_git_sync_version_release.py`：增加 plan/apply/git-sync 一致性、零写、
   漂移回滚和同版本更新测试。
5. `skills/bridgeforge-codex/SKILL.md`：明确 `ready` 已通过模拟严格预检，Apply 只作同标准复核。
6. Template/dogfood contract、manifest、`VERSION`、`CHANGELOG.md`、本卡和源 Bug：同步产品事实。

## 非目标

- 不修复 schema v1 lineage、Causis region history、AGENTS parser precedence、hooks
  canonicalization、Native Memory runtime authority或 M2 专项迁移。
- 不放宽现有 fail-closed 分类器。
- 不修改四个真实下游、用户级目录、业务版本、Git index 或 Git 历史。
- 不自动 commit/push。

## 验收标准

1. Planner、Apply、`$git-sync` 的骨架 transition 在测试中均命中同一个核心函数。
2. Planner 模拟检查前后，项目文件、Git index、版本戳和 Git 历史逐字不变。
3. 相同 transition 的模拟快照与真实快照返回相同分类、问题 ID 和路径。
4. 模拟检查失败时 plan 为 `action_required`，首次输出完整稳定 G 清单，禁止显示 `ready`。
5. Apply 前发生 fingerprint 漂移时零写入；写入后检查失败时完整回滚且旧戳保持。
6. 当前戳已等于目标版本但仍修改受管资产时，也必须使用同一验收函数。
7. init、正常 update、no-op、risk decline 与 degraded 路径不回归。
8. Template、dogfood 和分发副本的 `version_release.py` SHA-256 一致。
9. StratusAgent、Causis 与 ClaudeBridgeAssist 当前现场只读 planner 从假 `ready` 变为准确
   `action_required`；本卡不要求它们在其他缺陷未修时升级成功。
10. 定向测试、完整 factory unittest、downstream fixture、manifest `--check`、mirror、metadata、
    project structure、instruction source、`git diff --check` 与独立审计通过。

## 合理假设、风险与自动化边界

- 更早暴露 `action_required` 是纠正旧假阳性，不是新增升级阻断。
- prospective overlay 漏掉删除、stamp 或 contract 会再次制造双标准，因此这些场景必须有正反例。
- 产品同步器继续加载 Template 中受 contract 保护的可信 release 模块，不加载下游漂移副本。
- 真实下游本轮只允许只读 planner 验证；没有后续明确授权时禁止 apply。

## 实施记录

- `templates/scripts/version_release.py` 新增唯一公开 evaluator
  `evaluate_release_transition(repo, snapshot, prospective_version, changed_paths=...)`；真实工作区与
  prospective overlay 均通过 `_current_bytes()` 进入同一 `_classify_snapshot()`，原
  `classify_changes()` / `preflight_contract_transition()` 仅保留为薄兼容委托。
- `$git-sync` 的 `build_release_plan()`、project-sync Planner 和 Apply 均直接调用唯一 evaluator。
- Planner 根据 safe actions 构造创建 / 替换 / 删除 overlay，prospective stamp 作为同一函数输入；
  阻断结果进入 Plan、JSON、`action_required_items` 与 aggregate fingerprint，Apply 在任何写入前
  拒绝已知 blocked plan。
- Apply 写入后使用同一 evaluator 复核真实结果；若与 Planner 的 classification 不一致则事务回滚，
  版本戳仍保持 stamp-last。
- 用户确认 A / B 后，Apply 先物化 safe + 已选 risk / absorption 的最终内存快照；删除以
  `target=None` 表示，随后在创建事务前调用同一 evaluator。阻断时不进入 `before-apply`，项目文件、
  版本戳和 Git 状态零写入。该 prospective 快照摘要和预检结论同时进入 selection fingerprint；真实
  写入后的同一 evaluator 结果必须与其一致。
- Template 与 dogfood `version_release.py` 已逐字同步；产品版本升至 1.4.15，Skill、CHANGELOG、
  contract 和 active manifest 已传播。未修改四个真实下游、用户级目录或 Git 历史。

## 验证记录

- 开发态新增回归 3/3：兼容入口委托唯一 evaluator、prospective/真实 snapshot 分类一致且零写、
  plan preflight 失败首次输出 G1 且 apply 前零写。
- 第 1 轮相关模块 79 项出现 4 个测试契约失败：旧测试未隔离它原本要验证的 Git diff 路径、
  init 项目本就有 project requirements、耗时可能四舍五入为 0.0、baseline 集合缺已发布 1.4.14；
  没有发现唯一 evaluator 行为回退。
- 第 2 轮：`.venv\\Scripts\\python.exe -B -m unittest scripts.tests.test_bridgeforge_codex_project_sync scripts.tests.test_git_sync_version_release`，79/79 通过。
- 三个真实下游只读 Planner：StratusAgent 从假 ready 变为 G1/schema v1 `action_required`；
  causis_risk_suite 变为 G1 pre-commit + G2 AGENTS `action_required`；ClaudeBridgeAssist 变为
  G1 hooks dispatcher `action_required`。三处均未运行 `--apply`。
- 首次完整 factory：253/253；downstream fixture：27 个已发布迁移基线全部通过。
- 首次独立审计发现 1 个 High：确认后的 risk 删除 / absorption 仍可能先写后回滚；其余相关测试
  79/79 与硬闸通过。该 finding 已按上段实现关闭。
- 追加修补验证首次仅有 2 个旧断言仍期待“写后回滚”；修正验收契约后，同一相关模块命令
  80/80 通过。新增删除与吸收正反例均断言 checkpoint 未进入、目标字节不变、清单
  `recoverability=zero writes were performed`；吸收用例另显式断言旧戳字节不变，删除用例由
  checkpoint 尚未进入证明事务与版本戳写入路径均未启动。
- 追加硬闸：manifest `--check`、mirror drift、skill metadata、project structure、instruction source、
  `git diff --check` 全部 exit 0；project structure 仅输出既有 archive advisory。
- 最终独立复审：原 High 已关闭，未发现新的 Blocker / High；独立最小复测 3/3、
  `git diff --check`、Template / dogfood `version_release.py` 镜像均通过。产品实现可进入用户验收。

## 2026-08-20 M2 现场补充验收

- M2 的 1.4.23 Planner 在仍有 4 个待确认 risk 时跳过 release preflight，错误报告 ready；正式 Apply
  物化同一批 risk 后才阻断。1.4.24 要求 Planner 对完整推荐动作集提前运行同一 evaluator，用户是否
  确认仍只决定能否写入，不得决定 Planner 是否能看见阻断。
- evaluator 按旧戳精确查询版本化凭证，因此生成器必须为每个可信发布版本写入其 whole、AGENTS
  public、Markdown section 与 residual hash；相邻发布内容相同也不得跨版本去重。
- 永久回归必须证明：存在 risk 时 Planner 已调用 preflight；同一 payload 在 `0.86.0` 与 `0.86.7`
  两个版本键下均有凭证；M2 重新完成 plan -> apply -> validators -> stamp-last -> no-op replan。
- `affects_readiness=false` 的 N 类通知不得关闭 Planner preflight。完整推荐 snapshot 必须同时包含 safe、
  R 与 U 的实际 prospective 状态，但写入仍须原有 all/partial/decline 确认。
- current-only retirement 仅在 HEAD/current/prospective 三方均 absent 时允许 no-write attest；可信
  schema-v1 current-before 只有在旧戳和逐版本 contract hash 精确命中后，才能按稳定 Hook ID 或明确
  Markdown ownership 生成项目基线，未知/重复/漂移内容继续 fail-closed。

## 2026-08-20 M2 写后复核三态补充规则

- 单一 `snapshot` 只表示 after 视图，禁止在资产已写入后用新磁盘和 prospective stamp 反推
  current-before。
- 显式适配的唯一 evaluator 输入必须分为 Git HEAD provenance、不可变 before snapshot 与 after
  snapshot；before 至少覆盖受影响合同、合同声明的旧/新 stamp 和全部所选目标。
- before snapshot 必须在任何事务写入前冻结并复验，其 fingerprint 必须进入 proof 和 selection
  fingerprint；收据必须携带可由 `$git-sync` 独立重放的严格编码内容。
- prospective 复核使用磁盘 before + 内存 after；post-apply 复核使用冻结 before + 真实磁盘 after；
  两次必须调用同一 `evaluate_release_transition()` 并返回相同分类。
- 禁止把旧 handler hash 补入目标版本历史、提前写 stamp，或用额外启发式猜旧版本。
- 永久回归必须覆盖 `0.90.0` schema-v1 合同、dirty current-before、1.4.25 after 的完整
  plan -> proof -> write -> post-apply 路径，并证明旧 Hook 在两个检查时点都按 `0.90.0` 验证。

## 2026-08-20 M2 最终验收收据

- 产品完整测试 `311/311 OK`；downstream fixture `status=passed`；manifest、mirror、structure、
  instruction、skill metadata 与 diff 硬闸均通过；独立审计最终为 `0/0/0/0`。
- 真实 M2 plan 为 `safe=43 / risk=4 / gaps=0 / blockers=0 / G=32/32 eligible`；按用户 A 选择
  执行后为 `completed/ready`，统一 release preflight `passed/mixed`，无回滚并最后写入 1.4.25 戳。
- 终态 no-op replan 为 `safe=0 / risk=0 / upstream_absorption=0 / gaps=0 / blockers=0 / G=0`。
  项目结构硬闸另发现的两个项目自有 delivery 索引缺项已只补索引并复验 exit 0，不属于骨架
  ownership 放宽。
- Native Memory 使用 hook 实际指向的 installed product authority 串行验证：`enabled=true`、
  `hookInstalled=true`、`pending=false`、`remoteConfigured=true`；本轮没有 reconcile 或远端写入。

## 2026-08-20 Causis 三态版本轴补充规则

- HEAD provenance 的 handler 历史必须按 HEAD 合同与旧戳解析出的版本查询；禁止借用 dirty
  current-before 合同版本，也禁止用 current-before 已升级事实改写 HEAD 身份。
- current-before handler 仍必须按冻结 before 合同/stamp 版本验证，两条版本轴不得互相替代。
- 永久回归必须包含“HEAD 旧 published handler 仅登记在旧版本、current-before 为更高版本新
  canonical handler”的正例，以及 HEAD/current-before 任一未知 payload 的零写负例。
