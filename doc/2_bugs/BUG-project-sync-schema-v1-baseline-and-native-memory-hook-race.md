---
status: 1.4.37-product-fix-awaiting-real-downstream-validation
severity: high
scope: bridgeforge-codex project release preflight and user-level native-memory hook ownership
reported_at: 2026-08-19
downstream: D:\Quant\StratusAgent; D:\Quant\causis_risk_suite
factory_head: 639c55ee5320fc823620504bc6d4aa503100a7e8
product_version: 1.4.37
---

# BUG：可信 schema v1 基线阻断连续升级，native-memory hook 被跨项目解释器覆盖

## 2026-08-21：跨合同发布分类改为当前事实单一规则

1.4.35 在 Causis 真实工作区暴露了一个 current-only 后续缺口：Git HEAD 与工作区使用不同版本的
ownership contract 时，发布分类曾用当前 contract 解释两边，导致合法的旧骨架内容被错误当成项目
修改；旧 `explicit-adaptation.json` 又一度被考虑作为纠正分类的依据。这会重新建立一条可漂移、
可伪造的第二规则。

1.4.37 的唯一规则是：先独立验证当前 contract；HEAD payload 只用 HEAD contract 解析，当前
payload 只用当前 contract 解析，两边按稳定 asset id 对齐。当前 contract 损坏必须阻断；只有旧侧
无法由自身 contract 证明时，保守归类 `mixed`，禁止降为 `skeleton-only`。缺少 HEAD contract
表示合同首次引入，不再错误要求 HEAD 已包含当前受管资产。

`explicit-adaptation.json` 不再进入 `evaluate_release_transition()` 或 `build_release_plan()`，其旧
校验器及回归测试已删除。同步器只做语法与本地忽略检查，并且仅在 current-only evaluator 独立通过、
Git commit 成功后退休该废弃文件；分类失败或 commit 失败必须保留现场。该规则需经完整 factory、
fixture、发布硬闸和独立审计后发布，再以 Causis 完成真实 plan -> apply -> validators ->
stamp-last -> no-op replan 与 `$git-sync` 作为关闭证据。

发布前收据：定向发布回归 `32/32`、Native Memory wrapper 回归 `49/49`、完整 unittest
`266/266`、downstream fixture 三场景及全部发布硬闸通过；最终独立审计
Blocker / High / Medium / Low = `0/0/0/0`。真实 Causis 闭环仍待 1.4.37 发布后执行。

## 2026-08-21：1.4.30 current-only 边界取代历史 transition 修复路线

本文后续保留 1.4.14～1.4.26 的真实故障、回滚与调查证据，但不再作为当前实现说明。
1.4.30 已删除 schema v1/v2 transition、historical hash、adaptation 与版本谱系：合法
`<1.4.28` 旧项目只通过 `PreservationManifest` 做一次破坏性重建；`>=1.4.28` 项目只接受
schema 3 current baseline。缺戳、双戳、旧版本写在当前戳文件名或公共资产漂移都在写盘前阻断。

因此本文故障 A 的当前关闭口径不再是补齐 schema v1 → v2 adapter，而是：临时旧项目重建、
current update、stamp-last、回滚和 no-op replan 回归全部通过；真实 StratusAgent、Causis 与
ClaudeBridgeAssist 必须另行完成项目 Hook 正规化和确认式重建。第二期只做了四个 checkout 的
只读盘点，真实 apply 与 runtime smoke 仍未验证。

故障 B 的当前实现使用动态 Git 根定位项目 `.venv`，共享 writer 受用户锁、CAS 与回滚保护；
自动测试已覆盖，真实多项目顺序 lifecycle/status/repair 仍是本 Bug 唯一未闭合的 runtime 证据。
下文所有要求 historical transition/adaptation 的“推荐修复”和“关闭要求”均为历史记录，禁止
重新引入当前产品。

## 结论

BridgeForgeCodex 1.4.14 在真实下游 `D:\Quant\StratusAgent` 暴露了两个互相独立、但共同
阻断 `$bridgeforge-codex` 完整闭环的产品缺陷：

1. 项目工作区已经持有可信的 schema v2 / 1.4.11 ownership contract，但 Git `HEAD` 中仍是
   schema v1。1.4.14 planner 将三个受管更新全部分类为 safe，apply 阶段的 release preflight
   却在读取 HEAD contract 时直接要求 schema v2，事务只能回滚；
2. `repair-hook` 从当前调用项目的 Python 推导所谓 stable base interpreter，并把它写入全局
   `~/.codex/hooks.json`。不同项目使用不同 Python 基座时，后一次维护会覆盖前一次维护，导致
   刚报告 `changed=true` 的 hook 随即重新变成 `hookInstalled=false`。

前者使受支持的连续骨架升级进入“plan ready、apply 永远阻断”；后者使用户级 native-memory
hook 没有稳定的单一所有者。两项都不能靠重复执行、手工改戳、手工编辑 hooks 或提交整个混杂
工作区绕过。

## 2026-08-20：1.4.26 分离 HEAD 与 current-before 的版本轴

1.4.25 在 M2 闭环后重新运行真实 Causis Planner，`codex.hooks-config` G1 仍为
`adaptation_eligible=false`。精确证据为 HEAD 的无 ID legacy dispatcher 无法命中可信历史；这些
handler 的摘要实际登记在 HEAD 合同/旧戳版本，但实现错误使用冻结工作区 1.4.11 版本查询。

1.4.26 保持三态 ownership 不变，只修正版本来源：HEAD handler 仅按 HEAD 合同解析出的
`old_version` 查询 `historical_handler_sha256`；current-before handler 仍按冻结工作区合同的
`_trusted_release_version` 验证。新增回归构造 HEAD=0.90.0 published handler、
current-before=1.4.2 新 canonical handler，修复前精确失败、修复后通过；未知 HEAD payload 负例继续
fail-closed。相关 `version_release` 模块 55/55 通过，真实 Causis 只读 Planner 为
`safe=13 / risk=0 / gaps=0 / blockers=0 / G1/1 eligible`。

## 2026-08-20：1.4.25 以 HEAD / before / after 三态关闭写后时态别名

M2 在 1.4.24 上连续三次真实 Apply 均由事务完整回滚：先后暴露 README managed heading
顺序、写后 current-before 旧戳缺失，以及旧 Hook 被错误地按目标版本 `1.4.24` 查询发布历史。
第三次失败证明 `HEAD + 写后磁盘 + prospective stamp` 无法重建事务前现场；继续增加 stamp 或
版本启发式会伪造 lineage。

1.4.25 将显式适配 proof 升为唯一三态规则。同步器在任何写入前冻结受影响合同、旧/新版本戳与
所选目标的原始字节，以 base64 仅写入 Git 忽略的本地事务收据，并把 snapshot fingerprint 纳入
selection fingerprint。统一 `evaluate_release_transition()` 明确接收 Git HEAD provenance、不可变
before snapshot 与 prospective/applied after snapshot：prospective 复核使用真实磁盘 before + 内存
after；写后复核和 `$git-sync` 使用冻结 before + 真实磁盘 after。写前任一字节漂移、快照缺项、
收据跨库/HEAD/contract/target 漂移或 ownership projection 改变均 fail-closed。

旧错误测试“写后 current-before 应为目标版本”已改为同一旧现场在写前、写后都必须识别为
`0.90.0`。最终真实 M2 零写 Planner 为 `safe=43 / risk=4 / gaps=0 / blockers=0`，一次列出
`G1-G32` 且 `32/32 adaptation_eligible=true`，fingerprint 为
`sha256:0f32d86b6f289920920f025b995089e775fc7e90cba95c1d272b3db4a39ca3a6`。

产品完整测试 `311/311 OK`，downstream fixture `status=passed`，发布硬闸均 exit 0；最终独立复审
`Blocker/High/Medium/Low=0/0/0/0`。真实 M2 Apply 返回 `completed/ready`，统一 preflight
`passed/mixed`，`stamp_written_last=true`、`rollback_performed=false`；终态为新戳 `1.4.25`、旧戳
退役，no-op replan 的 safe/risk/absorption/gap/blocker/G 均为 0。完整收据记录在四项目更新报告中。

## 2026-08-20：M2 真实 Apply 补齐风险项预检与逐版本凭证

M2 将 23 个项目适配 gap 清零后，1.4.23 Planner 错误报告 `ready / preflight=not_required`，但确认
4 个 risk 后的 Apply 才由统一 evaluator 发现：M2 HEAD 的 `0.86.7` schema v1 contract hash 没有登记
在 `contract_historical_sha256["0.86.7"]`。Apply 保持零写，旧戳与项目内容未被半更新。

根因有两层。Planner 曾因“仍待用户确认 risk”而完全跳过推荐结果预检，Apply 却会物化已确认 risk
后预检；历史生成器又跨版本去重相同 hash，导致内容未变的后续发布版本没有自己的版本键，而 evaluator
按旧戳精确查版本。1.4.24 改为 Planner 先物化完整推荐动作集并共用固定点/evaluator，同时让 whole、
AGENTS public、Markdown section 与 residual 历史逐版本留证。风险项仍需用户确认，未知或项目内容仍
fail-closed；本修复只消除“Planner 看不见、Apply 才卡住”和合法发布版本缺凭证。

永久回归覆盖“存在 risk 时 Planner 必须提前预检”及“相同字节在 0.86.0、0.86.7 都有版本凭证”。
M2 的最终 Apply、validators、stamp-last 与 no-op replan 收据记录在四项目更新报告中。

真实复验还发现非阻断 `N1 unsupported_legacy_notice` 被旧条件误当成“不得预检”的项目要求；1.4.24
现只让 `affects_readiness=true` 的要求阻止预检。固定点随后一次展开 32 项：对于 HEAD、worktree 与
prospective 都不存在的 current-only retirement，使用绑定三方 absent 的 no-write attest；对于 M2
可信 schema-v1 current-before，先精确验证旧戳与该版本 contract hash，再仅按稳定 Hook ID 或明确
Markdown ownership 重建项目/external baseline。任何未知 ID、重复 ID、错误 event/matcher/stage、
未登记顶层字段、项目区变化、非可信旧合同或退休目标实际存在，仍然零写阻断。真实 M2 最新只读
Planner 为 `safe=43 / risk=4 / gaps=0 / blockers=0 / G=32 / eligible=32`。

## 2026-08-19：问题 #1 的 plan/apply 双标准已在 1.4.15 修复

1.4.15 把 Planner、Apply 与 `$git-sync` 的骨架 transition 收敛到唯一
`evaluate_release_transition()`。Planner 现在用内存 prospective snapshot 提前执行严格预检，
失败在首次计划输出 stable `G*` 清单并保持零写；Apply 只用同一函数复核真实结果。

三个真实下游已完成只读 Planner 复验：StratusAgent、causis_risk_suite、ClaudeBridgeAssist
均不再错误报告 `ready`，而是提前列出本报告已经确认的 schema v1、pre-commit / AGENTS 与
hooks dispatcher 阻断项。没有对真实下游执行 apply。

本状态只关闭“plan 与 apply 使用不同验收时点/入口”的问题 #1，不代表本 Bug resolved：schema v1
lineage、Causis 历史与 parser、hooks canonicalization、Native Memory runtime authority 仍按后续问题
分别修复。六类证据未全部闭合前，本报告继续保持 partial-fix 状态。

## 2026-08-19：问题 #7 已更正为 #4 的 Stratus 下游适配项

#7 不是新的 BridgeForgeCodex 产品缺陷。问题 #4 已把 `AGENTS.md` ownership 收敛为唯一
`agents_zones` 规则。最新零写 Planner 显示：Stratus 主工作区把 8 个不命中 schema v1 可信 hash 的
旧 rule 列为稳定 `G1`～`G8`；M2 工作树同时保留旧格式 `AGENTS.md` 和同一批内容不命中已发布
hash 的退役 `.codex/rules/*.md` gaps。这表示两个 checkout 尚未把项目自有规则显式迁入当前项目区，
而不是同步器还缺少第二套旧规则兼容逻辑。

该项并入 #4 的真实下游关闭条件：产品阶段继续保持 fail-closed，不放宽 ownership，也不新增旧 rule
解析或自动删除。待四项目更新阶段依次轮到 Stratus 主工作区与 M2 时，分别保存 before 状态，显式
适配 `AGENTS.md` 项目区并逐项证明旧 rule 内容的归属；两者共享 Git 状态，必须串行处理。最后各自经
同步器完成 plan -> apply -> validators -> stamp-last -> no-op replan。当前未写两个 checkout、未删除
旧 rule、未 commit 或 push；因此 #7 的产品问题已关闭，但 Stratus 下游验收仍未完成。

## 2026-08-19：问题 #8 已更正为 #5 的 Causis 下游适配项

#8 不是新的 BridgeForgeCodex 产品缺陷。问题 #5 已建立唯一 Hooks Zones v2 规则：只有稳定
`bridgeforgeCodexId` 才能证明 BridgeForge ownership，无 ID handler 保持项目或未知所有，可信旧
whole-file HEAD 才允许一次性 transition。最新 Causis 零写 Planner 的
`codex.hooks-config G1` 表示其旧 HEAD 无 ID 且不命中可信 whole hash，工作区同时包含项目自有
`root_hygiene_check.py` handler；同步器继续 fail-closed 是既定安全行为。

该项并入 #5 的真实下游关闭条件：最终更新 Causis 时显式适配可信 dispatcher、保留无 ID 项目
handler 与全部未知内容，并完成 before -> plan -> apply -> validators -> stamp-last -> no-op replan。
当前未写 Causis、用户级 hooks、Git index 或 remote；因此 #8 的产品问题已关闭，但 Causis 下游
验收仍未完成。

## 2026-08-19：CBA 真实 Apply 证明问题 #9 仍是产品缺口

先前把 #9 标记为“#3 已解决、只剩 CBA 下游适配”是不完整结论，现已由 1.4.22 正式路径推翻。
Planner 能准确识别 `codex.precommit G1`，但 G 项被产品定义为不可执行 review 清单，CLI 没有任何
参数能把用户已经批准的“采用当前 managed region、保留 PROJECT_EXTENSION”变成受 fingerprint
保护的事务动作。结果是方案存在、执行器缺失。

CBA 紧邻计划 fingerprint 为
`sha256:04853d8dac6726f1cccd3908b080a0f2501d574808d3fe8a6c8bc42d5c5423c0`。正式 Apply 返回
`planned release preflight rejected the prospective update; zero writes performed`，并记录
`release_preflight_status=blocked`、`stamp_written_last=false`、`rollback_performed=false`。
Apply 前后 HEAD、6 项 dirty 清单与 status SHA-256
`1572749f3373a11f37d6601719dd6d8dbdf4ceed5db516df01f6fc4997a45739` 完全一致；pre-commit、
版本戳、hooks.json 和 managed contract 的 SHA-256 也逐项未变。

因此 #9 重新打开为产品缺口：必须提供可审计、可选择、纳入 aggregate/selection fingerprint，且由
project-sync 与后续 `$git-sync` 共用的显式适配证明。禁止恢复历史 region hash、手工改受管区、
先提交混杂工作区或写戳绕过。CBA 当前仍为 1.4.11，项目 Apply 未发生任何写入。

## 2026-08-19：问题 #9 已在 1.4.23 实现，等待独立审计与 CBA 真实闭环

Planner 现在为每个 G 输出稳定 ID 与 `adaptation_eligible`。只有用户逐项传入
`--selected-adaptation GID` 才能执行；缺项、重复、未知、不可执行、重新编号或 fingerprint 漂移
均整轮零写。普通 gap 不会因选择 G 被放行。

Apply 与 `$git-sync` 继续只调用统一 `evaluate_release_transition()`。显式适配证明绑定项目根、
Git HEAD、current contract、目标前后 hash、project/external projection、独立 transition
fingerprint、aggregate fingerprint 和 selection fingerprint；每项必须真实消费一个 blocked
transition，额外或未命中的证明会反向阻断。存在任何普通 gap 时显式适配整轮零写。成功 Apply
将证明写入 Git 忽略的 `.runtime/bridgeforge-codex/explicit-adaptation.json`，commit 创建成功后才删除。

首轮独立审计发现的项目区旁路、AGENTS CRLF、ordinary gap 未经预检写证明、覆盖不足与 aggregate
无外部锚五项 finding 均已修复，等待同一审计 agent 复审。当前相关回归 116/116、完整自动测试
300/300 与 downstream fixture 均通过；Template、dogfood、
manifest 已传播到 1.4.23，manifest/mirror/instruction/structure/metadata/diff 硬闸均 exit 0。
独立审计和真实 CBA `plan -> apply -> validators -> stamp-last -> no-op replan` 尚未执行，因此本节
暂不宣称 #9 完全关闭。

## 2026-08-20：问题 #9 的 Stratus retirement 与 Causis hooks 真实形态已闭合

复审真实下游后补齐了两个不能只靠合成 fixture 证明的路径。Stratus 的 schema v1 退役 rule 现在只有
在目标工作树已经删除且 HEAD 内容仍精确命中可信旧资产时，才生成绑定 before/after-null 的事务
retirement；dirty、未知或未选择目标继续零写。Causis 的 hooks 适配改为由 HEAD 证明旧 managed
dispatcher，另以 Apply 前当前工作树的 external handlers 为项目区基准，并在写前和 evaluator 消费时
复算；其项目自有 `root_hygiene_check.py` 不再因为未出现在 HEAD 而被误判或吸收。

按用户对实际内容的裁决，`.codex/hooks.json` 顶层 `description` 描述 BridgeForge 整套 Hook 注册，属于
骨架 ownership。合同生成器现在从每个可信发布基线提取精确历史值；当前值或登记过的历史骨架值可以
迁移到当前 canonical，任意未登记自定义值仍 fail-closed。Causis 的旧大小写描述已由其历史骨架提交
和发布基线共同证明，不按项目自定义处理；无 ID 项目 handler 仍保持 external。

当前真实 Causis 零写 Planner 为 `safe=13 / risk=0 / gaps=0 / blockers=0`，唯一 `G1` 已变为
`adaptation_eligible=true`，计划 fingerprint 为
`sha256:a3780f925a3bd6a329086b9ba439bd30ee7970b93f43067f5b0053097fff891b`。相关 project-sync、release
evaluator 与 hooks 单一来源定向回归为 135/135，manifest `--check` 已 current。完整回归、独立复审
和四个真实项目写入闭环仍待后续步骤，故本节只关闭 #9 的已知产品卡点，不提前宣称总 Bug resolved。

独立复审随后在真实 Stratus 发现首层目录并非固定点：初始 Planner 只列 8 个 retirement，累计 proof
通过后 evaluator 才暴露另外 24 个 transition issues。1.4.23 最终实现改为有界递归运行累计 proof，
直到统一 evaluator 通过或无法新增；所有 G 只在完整 closure 通过时才标记 executable，并在固定点后
一次性稳定编号。已是 current canonical 但 Git changed-path 未显式出现的目标使用 proof-only attest：
绑定 HEAD/current/contract 与项目 projection，进入 validator 集但不执行同字节写入；`$git-sync`
在真实无 snapshot 路径中也必须独立重算并消费该证明。

真实 Stratus 最终只读 Planner 一次列出 32 个 G，`32/32 adaptation_eligible=true`，且仍为
`gaps=0 / blockers=0`；CBA、Causis 均保持唯一 G1 可执行。M2 仍保留 23 个 ordinary gaps，即使其
AGENTS G1 可适配也必须整轮零写。新增 partial-upgrade 回归复现“8 个 retirement 后暴露 proof-only
目标”，验证清单固定点、selected apply、统一 evaluator、no-op replan 以及 attest 未进入
`transaction.write`。

## 2026-08-19：问题 #6 已按项目 `.venv` 单一 Runtime 规则实现并通过独立复审

用户否决了“为用户级 Native Memory Hook 选择一个固定基础 Python”的旧方案。1.4.21 将每个
BridgeForgeCodex 项目自己的 CPython 3.11+ `.venv` 定为全部骨架脚本、validator、项目 Hook 与
用户级 lifecycle Hook 的唯一 runtime。只有 init/adopt 且 `.venv` 完全不存在时，允许 PATH 中
经验证的 CPython 3.11+ 一次性执行 `-m venv`；创建后立即切换。update、status、repair 与稳态
Hook 均不再回退 PATH，已存在但损坏、低版本或非 CPython 的 `.venv` 直接零写阻断。

用户级三个 Native Memory handler 不再保存任何项目 Python 绝对路径，而是在触发时从当前 Git 根
定位 `<root>/.venv/Scripts/python.exe`，再调用产品受管脚本。status、repair 与 setup 共用用户级
互斥锁；writer 在锁内严格重读 Hooks Zones、写前比较原始字节并在写后复验，稳定返回
`applied / unchanged / conflicted / rolled_back`。未标记 handler 与第三方字段继续保留，repair
保持 local-only；不读取 GitHub 或 memories 正文，也不触发 reconcile。

实现已传播到 Template、dogfood、ownership contract、Skill、公共 AGENTS、VERSION / CHANGELOG
与文档索引。两项实现任务分别通过 32/32 与 46/46 定向测试；集成测试第二轮暴露的三个失败均为
旧测试 fixture 未建立项目 `.venv`，已按新规则修正，未放宽产品 contract。

首次独立审计给出 Blocker / High / Medium / Low = 0 / 6 / 2 / 1，发现 lifecycle 失败码、Windows
abandoned mutex、Git/Memory Skill 裸 Python、dispatcher 身份、pre-commit PATH fallback、锁外 config、
decline ledger 锁、旧文档规则与三版本接受 fixture 等遗漏。当前补丁已逐项封闭：所有活跃入口复用
项目 runtime contract；用户共享 state 在同一锁内读取/写入；旧固定用户级 authority 明确退役；新增
错误 runtime、锁状态、锁边界与版本正反例。同一独立 agent 复审最终为
Blocker / High / Medium / Low = 0 / 0 / 0 / 0，独立定向测试 192/192 通过。

获用户批准增加的第 4 轮最终验证中，完整 unittest 291/291 通过；downstream fixture 返回
`status=passed`，覆盖 init stamp-last、27 个历史版本、8 个 apply -> no-op replan 和 19 个旧
pre-commit 显式适配分类；manifest `already current`，mirror / instruction source / project structure /
skill metadata / `git diff --check` 均 exit 0。第 3 轮唯一失败是 fixture 自身未创建新规则要求的
`.venv`，最终只修测试现场并保持产品 fail-closed。

本轮没有调用真实 Native Memory status/repair、写真实用户级 hooks、apply 真实下游、commit 或
push，因此 #6 暂不标记关闭。

## 2026-08-19：问题 #5 已收敛为 Hooks Zones 单一规则并通过独立复审

1.4.20 为用户级与项目级 hooks 引入同一逻辑 ownership parser。BridgeForge handler 以稳定
`bridgeforgeCodexId` 标识，必须唯一且独占 group；未标记 handler 归用户、第三方或项目所有。
Planner、项目 merger、release evaluator 与 Native Memory merger 均按同一规则遍历全部 group，
可信混组 / 重复可确定性拆分去重，未知 id、hash 漂移、非法 JSON / group 继续零写 fail-closed。

当前 contract 只保留 `codex-hooks-zones-v2`，不保留并行旧规则。无 ID legacy 结构只允许通过可信
transition 一次性迁移：旧 contract 有 handler projection 时逐项证明；更早 contract 只有 whole hash
时必须整文件精确命中。Causis HEAD 的旧 hooks 不命中其无 projection contract 的 whole hash，故稳定
输出 G1，不猜测删除；这符合 fail-closed，不是自动兼容缺口。

CBA 1.4.20 零写 Planner 已为 `ready / passed / skeleton-only`，原 hooks G1 消失；计划前后两个 vault
handler 的对象、event、matcher 与顺序完全相同。首次独立审计发现普通 JSON 解析吞 duplicate key、
独立 merger 仍按路径删除无 ID handler 两个 High；现已统一严格 JSON 入口并删除旧路径剥离，3/3
正反例与完整自动测试 273/273、downstream fixture、发布硬闸均通过。Template、dogfood、contract、
manifest、VERSION / CHANGELOG 均已传播。独立复审最终 Blocker / High / Medium / Low 为
0 / 0 / 0 / 0，并独立重跑完整测试、fixture、CBA external projection 与发布硬闸。未对真实下游
apply、写戳，未改真实用户级 hooks，未 commit / push。#5 技术实现可关闭，等待用户验收；
源 Bug 因 #6～#9 仍未解决继续保持 partial-fix。

## 2026-08-19：问题 #4 的 AGENTS ownership 已收敛为单一 zones 规则

1.4.18 删除 `root.agents` 当前 contract 中并行存在的 `managed_blocks`、`section_layout`、
`trusted_legacy_sha256` 与 `legacy_section_migrations`，只保留 `agents_zones`。同步器不再根据旧标题
猜测项目区：无分区文件保持原样、输出显式 ownership review 且不写新戳；合法 zones 文件继续只更新
可信公共区并逐字保留项目区。

release evaluator 现在优先按 zones 验证。无分区 HEAD -> 当前 zones 保守归类为 `mixed`；旧、新
contract 均采用 zones 且目标文件未变时，ownership metadata transition 可通过严格合法 no-op，避免
要求无意义地重写 `AGENTS.md`。当前公共区必须命中 exact current hash；marker 缺失、重复、倒序或
公共区漂移继续 fail-closed。

针对性回归 103/103、完整自动测试 264/264、完整 downstream fixture passed；manifest 已 current，
mirror / metadata / structure / instruction source / diff 硬闸均 exit 0。四项目只读 Planner 证明：
Stratus 主工作区与 Causis 的 `root.agents` 阻断消失，Causis 已 `readiness=ready`；M2 旧格式稳定输出
唯一 AGENTS `G1` 且零写；ClaudeBridgeAssist 的 root AGENTS 合法 no-op 已放行。未对真实项目 apply、
写戳、commit 或 push。首次独立审计唯一 Low 为 Planner 缺少重复、倒序 marker 的直接回归；补齐
missing、duplicate、reversed 三个零 action + 单一 `G1` 子例后复审通过，最终 Blocker / High /
Medium / Low 均为 0。#4 技术实现可关闭；源 Bug 因 #5～#9 仍未修复继续保持 partial-fix。

## 2026-08-19：问题 #3 已收敛为唯一当前 Region 规则

用户拒绝把 1.4.17 的按版本 region lineage 作为长期兼容层。1.4.19 已删除
`codex.precommit` asset 与 `region` 的全部 `historical_sha256`，删除历史 region 重建器，并让项目
同步器只识别当前 `BRIDGEFORGE_CODEX_MANAGED_BEGIN/END`。只有旧 marker 的项目不再自动迁移，
必须保持零写并先完成显式适配。

release evaluator 仍可读取经整体 contract hash 证明的历史 contract，以确认版本迁移范围，但旧
region marker/hash 不再参与 ownership 判断。当前工作区 managed region 必须精确命中 current hash；
HEAD 无当前 marker 时，显式适配保守归类 `mixed`；HEAD 已有当前 marker 时，HEAD region 也必须命中
current hash，缺失、重复、倒序或内容漂移全部 fail-closed。

最终相关回归 106/106 通过，manifest `already current`，mirror / metadata / structure /
instruction source / diff 硬闸均 exit 0。CausisRiskSuite 1.4.19 零写 Planner 返回
`readiness=ready`、`release_preflight_status=passed`、classification `mixed`，无 gap、blocker、
required action 或 `codex.precommit` 写入 action；项目 extension 保持不变。未执行真实下游 apply、
写戳、commit 或 push。独立审计首次发现的 current-marker HEAD/current hash High 与 dogfood 传播
High 已修复，等待最终复审；整个源 Bug 因 #5～#9 尚未解决，继续保持 partial-fix。

## 2026-08-19：问题 #2 的可信 schema v1 lineage 已修补并通过独立复审

1.4.16 不再在历史 hash 之前要求 HEAD contract 已是 schema v2。唯一 release evaluator 现在先读取
schema v1 旧戳，验证最低支持版本和 `contract_historical_sha256[old_version]`，再用当前 schema v2
contract 的稳定 asset id、显式 target 与 strategy 构造旧 ownership 视图。

whole-file / region 重叠、重复 region、strategy 不兼容、未授权整文件接管或旧版本 asset hash
不匹配时继续按稳定 asset id 零写 fail-closed。旧 schema 漏登记但具有 projection / region 历史证明
的资产仍须通过现有严格解析器；schema v1 glob 中未被 schema v2 显式接管的未知路径保持
project-owned，禁止把 glob ownership 延续到新 contract。

新增正反例和两轮相关模块回归均为 83/83。StratusAgent 真实只读 Planner 已不再输出
`ownership contract transition requires schema v2`，而是继续阻断于 8 个内容不匹配 0.90.0 官方
hash 的退役 rule 资产；这属于后续 M2 ownership 问题，不在 #2 中放宽。没有执行真实下游 apply、
commit 或 push。Template、dogfood、1.4.16 contract 与 active manifest 已传播。

首次独立审计发现的 1 个 High、1 个 Medium 已修补并通过独立复审。synthetic old asset 现在删除
当前 release 的 projection / region 凭证，只保留 `old_version` 对应历史；只有 whole-file 完整内容
命中 `old_version` asset hash 时，才允许由完整文件反证其 projection。新增 merge、managed Markdown、
region 三种“旧戳为 0.90.0、hash 只登记在 0.91.0”的负例，以及 schema v1 prospective Planner /
真实 Apply evaluator 等价回归。最终相关模块 85/85，manifest `already current`，发布硬闸全部 exit 0；
独立复审无 Blocker / High / Medium，最小复测 5/5。#2 技术实现可关闭，等待用户验收；整个源 Bug
因 #3～#9 尚未解决，继续保持 partial-fix。

2026-08-19 在第二个真实下游 `D:\Quant\causis_risk_suite` 使用同一 1.4.14 工厂提交复验后，
原先四个 release transition 卡点中的 `doc/README.md` 与 `.codex/hooks.json` 已不再阻断，
说明 1.4.14 的修复已覆盖部分迁移路径；但 `.githooks/pre-commit` 与 `AGENTS.md` 仍无法通过
可信历史 / managed projection 证明，项目同步事务继续回滚。因此本 Bug 仍未闭环。

## 已核实环境

- 工厂仓库：`D:\Quant\BridgeForge`
- 工厂 HEAD：`639c55ee5320fc823620504bc6d4aa503100a7e8`
- 产品版本：`1.4.14`
- 真实下游：`D:\Quant\StratusAgent`
- 下游分支：`master`
- 下游骨架戳：`1.4.11`
- 下游 Git HEAD contract：schema v1
- 下游工作区 contract：schema v2 / release 1.4.11
- native-memory 长期授权：`approved`，policy version 1
- native-memory：`enabled=true`、`remoteConfigured=true`
- 本轮未执行 remote reconcile，收据为 `remote_reconcile=not_requested`
- 本报告只新增元文档并更新索引；不修改产品代码、VERSION、CHANGELOG，不提交或推送。

## 追加复验：causis_risk_suite 仍被两个 ownership transition 卡点阻断

### 复验环境

- 真实下游：`D:\Quant\causis_risk_suite`
- 下游分支：`main`
- 下游骨架戳：`1.4.11`
- 工厂 HEAD：`639c55ee5320fc823620504bc6d4aa503100a7e8`
- 产品版本：`1.4.14`
- 项目 Python：`D:\Quant\causis_risk_suite\.venv\Scripts\python.exe`（Python 3.12.13）
- apply 前计划：`safe=3`、`risk=[]`、`gaps=[]`、`blockers=[]`
- aggregate fingerprint：
  `sha256:44e892c9d2c419240819da91ea72cae7d7a58e476cd21b5bb8ef698224842ce6`

三个 safe 目标为：

- `contract.managed-skeleton` -> `.codex/managed-skeleton.json`
- `codex.hook.skill-metadata-check` -> `.codex/hooks/skill_metadata_check.py`
- `codex.script.version-release` -> `.codex/scripts/version_release.py`

### apply 收据

使用同一 fingerprint 执行 apply 后，1.4.14 release preflight 返回：

```text
BLOCKED: transaction failed and was rolled back: release preflight blocked:
ownership contract transition is blocked:
codex.precommit: HEAD managed region does not match trusted transition history:
.githooks/pre-commit;
root.agents: current managed Markdown does not match its managed projection:
AGENTS.md
```

结构化收据为：

- `execution_status=failed`
- `target_readiness=action_required`
- `release_preflight_status=blocked`
- `stamp_written_last=false`
- `rollback_performed=true`

两个稳定 G 项为：

| ID | asset | target | reason | action | recoverability |
|---|---|---|---|---|---|
| G1 | `codex.precommit` | `.githooks/pre-commit` | HEAD managed region does not match trusted transition history | `review-release-transition` | transaction rolled back |
| G2 | `root.agents` | `AGENTS.md` | current managed Markdown does not match its managed projection | `review-release-transition` | transaction rolled back |

回滚后骨架戳仍为 `1.4.11`，没有 `.bridgeforge-codex-sync-*` 临时文件残留，
`git diff --check` 通过（只有行尾格式警告）。未提交、未推送，也未清理下游原有混杂工作区。

### 与 StratusAgent 首次复现的差异

causis_risk_suite 的失败形态表明 1.4.14 已从“笼统拒绝 schema v1 HEAD”推进到按资产输出
transition review 项，并且此前出现的 `doc/README.md` 与 `.codex/hooks.json` 两个卡点已消失。
但剩余 G1 / G2 仍属于同步器必须自行证明或明确分类的 ownership transition，不应转嫁为用户逐文件
审核，更不能要求用户先提交混杂工作区。产品仍需要补齐以下能力：

1. 对 `.githooks/pre-commit` 的 managed region 建立可追溯 historical hash / transition lineage；
2. 对根 `AGENTS.md` 的公共受管区执行稳定 projection 比较，同时逐字保留项目级专区；
3. 在 plan 阶段产出与 release preflight 一致的 G 项，禁止先报告 `target_readiness=ready`、
   到 apply 才改判 `action_required`；
4. 修复后在两个真实下游完成 apply -> no-op replan，证明不是针对单一仓库特判。

### Native Memory 本轮证据

causis_risk_suite 本轮最终 repair 收据为：

```text
[memory-sync] hooks repaired; changed=true;
hook_python=D:\Quant\causis_risk_suite\.runtime\python-portable\python.exe;
remote_reconcile=not_requested
```

随后 status 为 `enabled=true`、`hookInstalled=true`、`pending=false`、
`remoteConfigured=true`、`consent=approved`。本轮没有再次复现“repair 后立即变回
`hookInstalled=false`”，因此不能把该竞态描述为本轮已复现；但全局 hook authority 仍被写成
项目目录内的 portable Python，继续印证其生命周期依附于当前项目，原设计缺陷与跨项目覆盖风险
均未消除。

## 追加复验：ClaudeBridgeAssist 暴露 hooks merge G1，并再次捕获全局 hook 覆盖

### 复验环境

- 真实下游：`D:\Quant\ClaudeBridgeAssist`
- 下游分支 / upstream：`master` / `origin/master`
- 下游 HEAD：`eba2fe264b6870c5f865ac344e5f5f63f3bf9005`
- 下游骨架戳：`1.4.11`
- 工厂 HEAD：`639c55ee5320fc823620504bc6d4aa503100a7e8`
- 产品版本：`1.4.14`
- 项目 Python：`D:\Quant\ClaudeBridgeAssist\.venv\Scripts\python.exe`（Python 3.11.9）
- 项目工作区原有 6 项骨架变化，staging 为空，ahead / behind 为 0 / 0。

用户级 updater 收据为 `status=completed`、`mode=updated`、`action_count=2`。Native Memory
初始状态为 `enabled=true`、`hookInstalled=true`、`pending=false`、
`remoteConfigured=true`、`consent=approved`、`consentPolicyVersion=legacy`；配置的 remote 仍是
原受管仓库 `freakybridge/bridgeforge-codex-memories`。

### 项目 planner 与 apply 收据

1.4.14 planner 返回：

```text
previous_version=1.4.11
current_version=1.4.14
safe=3
risk=[]
gaps=[]
blockers=[]
target_readiness=ready
aggregate_fingerprint=sha256:b78378a23bc7eacc1f0da03276870505dcef3a17a34f7d1ae8fe832ce331ae6f
```

三个 safe 目标为：

- `contract.managed-skeleton` -> `.codex/managed-skeleton.json`
- `codex.hook.skill-metadata-check` -> `.codex/hooks/skill_metadata_check.py`
- `codex.script.version-release` -> `.codex/scripts/version_release.py`

普通权限 apply 首先因 Windows 拒绝替换 `.codex/managed-skeleton.json` 失败，并返回
`rollback incomplete`。只读复核确认两个已报告事务临时路径均不存在、骨架戳仍为 1.4.11、
重新规划 fingerprint 完全一致；随后使用完全相同命令窄范围提升权限重试。

提升权限后的事务进入产品侧 release preflight，返回：

```text
BLOCKED: transaction failed and was rolled back: release preflight blocked:
ownership contract transition is blocked:
codex.hooks-config: current merge target managed dispatcher drifted:
SessionStart//session-start: .codex/hooks.json
```

结构化收据为：

- `execution_status=failed`
- `target_readiness=action_required`
- `release_preflight_status=blocked`
- `stamp_written_last=false`
- `rollback_performed=true`

稳定 G 项为：

| ID | asset | target | reason | action | recoverability |
|---|---|---|---|---|---|
| G1 | `codex.hooks-config` | `.codex/hooks.json` | current merge target managed dispatcher drifted: `SessionStart//session-start` | `review-release-transition` | transaction rolled back |

回滚后骨架戳仍为 1.4.11，Git 工作区仍是原有 6 项骨架变化；未 commit、未 push、未 stash，
也没有手工修改版本戳或受管脚本。

### hooks merge 现场

当前 `.codex/hooks.json` 的 `SessionStart` 有两个 `hook_dispatcher.py session-start` 注册：

1. 第一组同时包含项目自有 `vault_junction_check.py` 与受管 `session-start` dispatcher；
2. 第二组再次包含一份独立、文本相同的受管 `session-start` dispatcher。

`Stop` 也存在同构布局：第一组同时包含项目自有 `vault_snapshot.py` 与受管 `stop` dispatcher，
第二组再含一份独立受管 `stop` dispatcher。1.4.14 Template 对两个 event 都只声明一份独立
managed dispatcher。

因此 release preflight 拒绝当前 managed projection 是 fail-closed 的合理结果；产品缺口在于：

1. planner 没有把 `.codex/hooks.json` 列入 safe、risk、gap 或 G 项，先报告 ready，直到 apply
   才发现同一资产无法证明；
2. project hooks merge 没有在计划阶段解释“项目 handler 与 managed dispatcher 混组 + managed
   dispatcher 重复”的现有布局，也没有提供保留项目 handler 的受支持收口动作；
3. 当前重复布局由哪一次历史同步产生尚未验证，禁止把它直接归咎于用户或某个具体版本。

推荐补充 fixture：HEAD / current hooks 同时包含项目自有 handler、与其同组的 managed
dispatcher，以及第二份独立 managed dispatcher。plan 必须在写入前稳定输出 G 项或可执行迁移动作；
若允许迁移，结果必须逐字保留 `vault_junction_check.py` / `vault_snapshot.py`，并使每个 stage 只剩
唯一 canonical managed dispatcher。缺失、重复或 hash 漂移继续 fail closed。

### Native Memory 覆盖再次复现

本轮 `repair-hook` 使用已保存的长期授权，把 legacy consent 迁移为 policy version 1，收据为：

```text
[memory-sync] hooks repaired; changed=false;
hook_python=C:\Users\bridg\AppData\Local\Programs\Python\Python311\python.exe;
remote_reconcile=not_requested
```

紧邻 status 为 `hookInstalled=true`、`consentPolicyVersion=1`。但稍后在同一
ClaudeBridgeAssist 中再次执行只读 status，结果已经变为 `hookInstalled=false`；期望解释器仍是
用户级 `Python311\python.exe`，而 `C:\Users\bridg\.codex\hooks.json` 中三项正式 managed
marker 的实际命令全部重新指向：

```text
D:\Quant\causis_risk_suite\.runtime\python-portable\python.exe
```

受影响 marker 为 `SessionStart`、`Stop`、`SessionEnd`。这次证据把原报告的“跨项目最后写入者
覆盖全局 hook”从设计风险升级为第三个下游中的实际状态跃迁：同一轮 repair 后曾健康，之后无需
ClaudeBridgeAssist 自己改配置便再次漂移。

本报告仍未证明具体覆盖进程与发生时刻；可以确认的是，全局 managed hook 的实际 runtime 被另一个
项目目录内解释器占用，而当时 status 以另一 Python 为 authority，因此稳定返回 false。当时提出的
固定用户级 runtime 方案已被用户否决；1.4.21 改由动态 Git 根定位当前项目合规 `.venv`，并以
全局锁 / compare-and-swap 和可解释 drift 收据防止各项目反复抢最后写入权。

### 本次恢复边界与新增验收

- ClaudeBridgeAssist 项目事务已回滚，骨架戳保持 1.4.11；不得手工删除重复 dispatcher 后冒充
  project-sync 已修复。
- 项目自有 vault hooks 必须保留；任何 canonicalization 都要给出精确 before / after 与 ownership
  证明。
- Native Memory 本轮没有执行 remote reconcile，也没有读取或改写 memories 正文。
- 修复后须在 StratusAgent、causis_risk_suite、ClaudeBridgeAssist 三个下游顺序运行
  status / repair，证明全局 hook runtime 始终不随调用项目变化。
- ClaudeBridgeAssist 必须完成 plan -> apply -> release preflight -> no-op replan；plan 与 apply
  对 `codex.hooks-config` 的 readiness 结论必须一致。

## 故障 A：release preflight 拒绝可信的 schema v1 HEAD

### 用户可见过程

1. 用户级 updater 成功，产品 home 位于 1.4.14 / commit `639c55e`；
2. 项目 planner 返回：
   - `previous_version=1.4.11`
   - `current_version=1.4.14`
   - `safe=3`
   - `risk=[]`
   - `gaps=[]`
   - `blockers=[]`
   - `target_readiness=ready`
3. 三个 safe 目标均匹配已发布历史 hash：
   - `contract.managed-skeleton`
   - `codex.hook.skill-metadata-check`
   - `codex.script.version-release`
4. 同 fingerprint apply 在 release preflight 阶段失败：

```text
release preflight blocked: ownership contract transition requires schema v2:
D:\Quant\StratusAgent\.codex\managed-skeleton.json
```

5. 收据返回：
   - `execution_status=failed`
   - `target_readiness=action_required`
   - `release_preflight_status=blocked`
   - `stamp_written_last=false`
   - `rollback_performed=true`
6. 回滚后三个目标恢复原 hash，骨架戳仍为 1.4.11，事务临时文件不存在。

### 直接证据

对同一个 contract 路径读取 Git HEAD 与工作区：

```text
head_schema_version=1
head_release_version=
current_schema_version=2
current_release_version=1.4.11
```

工作区 `.codex/managed-skeleton.json` 的 SHA-256 为 planner 认可的已发布 1.4.11 hash：

```text
34C0A6A7CC316CCFFF00D083065D41A0A7810FF1FC0EAE7D90C0C942C53E7A52
```

因此问题不是当前 contract 损坏，也不是项目手工伪造 schema v2；阻断来自 preflight 对
HEAD 历史格式的读取顺序。

### 源码根因

`templates/scripts/version_release.py::preflight_contract_transition()` 在 prospective skeleton
version 存在时：

1. 加载工作区 schema v2 contract；
2. 从 Git HEAD 读取同一路径 payload；
3. `_parse_managed_config(...)` 允许解析 schema v1；
4. 随后无条件调用 `_raw_contract(...)`；
5. `_raw_contract(...)` 只接受 `raw_contract.schema_version == 2`，因此在进入稳定 asset id、
   historical hash 和 stamp transition 证明前就抛错。

这与 schema v2 contract 自带的 `contract_historical_sha256` 设计冲突：历史 hash 本应用于证明
旧 contract 是可信发布基线，但当前代码在查询这份 lineage 前先拒绝了 schema v1。

现有 `BUG-git-sync-contract-transition-classification.md` 已要求使用 HEAD contract 解析 before、
工作区 contract 解析 current，并用历史 hash 证明迁移。1.4.14 当前实现只完成了
schema v2 -> schema v2 transition，没有闭合“HEAD 仍为已支持 schema v1、工作区已是可信
schema v2”的真实连续升级路径。

### 影响

- 先前完成但尚未提交的 v1 -> v2 骨架迁移会阻断后续安全版本更新；
- planner 把可替换资产全部分类为 safe，却无法提前产生实际 G 项，执行阶段才回滚；
- 用户若被迫先提交，会把数百项既有业务修改、退役删除和骨架迁移混入一个非原子提交；
- 手工改戳或绕过 release preflight 会破坏版本与 ownership 安全边界；
- 重复运行不会改变 HEAD，因此必然重复失败。

### 推荐修复

1. 在 `_raw_contract()` 之前识别 schema v1 -> schema v2 transition；
2. 用当前 schema v2 contract 的 `contract_historical_sha256` 验证 HEAD contract 原始 payload；
3. 同时验证 HEAD 旧戳属于受支持版本、当前 contract 为已发布可信 hash、当前 stamp 与目标版本
   一致；
4. 用旧 schema 的 ownership 描述解析 before，用当前 stable asset id 和 strategy 解析 current；
5. 无法证明历史 hash、旧戳、asset 映射或 project-owned 内容完整时继续 fail closed；
6. plan 阶段至少运行等价的 transition probe。若 apply 必然阻断，应直接输出稳定 G 项，而不是
   `target_readiness=ready`；
7. 禁止要求用户先提交混杂工作区作为产品升级前置条件。

## 故障 B：用户级 native-memory hook 被调用项目反复改写

### 用户可见过程

在长期授权为 approved、native-memory enabled 的状态下运行本地-only repair：

```text
[memory-sync] hooks repaired; changed=true;
hook_python=D:\Python\miniconda3\python.exe;
remote_reconcile=not_requested
```

紧接着重新运行 status：

```json
{
  "enabled": true,
  "hookInstalled": false,
  "pending": false,
  "hookPython": "D:\\Python\\miniconda3\\python.exe",
  "remoteConfigured": true,
  "consent": "approved"
}
```

此时 `C:\Users\bridg\.codex\hooks.json` 中三个带正式 managed marker 的 handler 均已指向：

```text
D:\Quant\causis_risk_suite\.runtime\python-portable\python.exe
```

三个 marker 本身仍正确：

- `bridgeforge-codex.native-memory-sync.v1:SessionStart`
- `bridgeforge-codex.native-memory-sync.v1:Stop`
- `bridgeforge-codex.native-memory-sync.v1:SessionEnd`

本报告没有证明是哪一个进程在什么时刻完成覆盖；已证明的是：同一用户级 managed hook 可被
不同项目推导出的解释器合法重写，repair 的成功收据不能保证下一次 status 仍健康。

### 源码根因

`scripts/codex_memory_sync.py::stable_hook_python()` 从当前 `sys.executable`、
`sys._base_executable` 和 `sys.base_prefix` 推导 hook Python。它只排除“候选解释器仍位于当前
venv 内部”，没有排除候选解释器属于另一个项目目录，也没有读取用户级持久化 runtime authority。

结果是：

```text
项目 A 的 .venv -> base A -> 写入全局 hooks.json
项目 B 的 .venv -> base B -> 覆盖同一全局 hooks.json
再次检查项目 A -> 期望 base A -> hookInstalled=false
```

`repair_user_hooks()` 只在自己的原子写之后立即校验；它没有跨进程全局锁、compare-and-swap、
持久 runtime identity 或写后稳定期验证。多个 BridgeForge 项目因此可以轮流成为全局 hook
的“最后写入者”。

现有测试只验证“从一个 venv 选择其 base interpreter”和“拒绝 venv 内部 base”，没有覆盖
两个项目拥有不同 base interpreter、共同维护同一用户级 hooks.json 的场景。

### 影响

- Native-memory readiness 随最近运行 `$bridgeforge-codex` 的项目而变化；
- 项目被移动、删除或其 portable runtime 被清理后，全局生命周期 hook 会失效；
- 每个项目都可能把其他项目刚修好的 hook 再次判定为漂移并覆盖，形成永久抖动；
- `changed=true` 不是持久健康证明，最终收据可能错误暗示用户级同步已闭环；
- 多个项目同时运行时存在 hooks.json 的全局竞争窗口。

### 历史废案（已被问题 #6 的用户决策取代）

本节旧版曾建议建立额外的用户级固定 Python authority，并禁止项目 `.venv` 成为 lifecycle
runtime。用户已明确否决该方案，1.4.21 不再保留这套规则或其兼容实现。唯一当前规则是：三个
用户级 handler 只保存通用的动态 Git 根命令，触发时使用当前 BridgeForgeCodex 项目的 CPython
3.11+ `.venv`；共享 hooks/ledger writer 使用同一用户锁、锁内重读、CAS 与回滚收据。完整当前
契约以 `project-venv-hook-runtime-single-rule` 需求卡及本文顶部 #6 实施章节为准。

## 验收场景

### A. ownership contract transition

1. Git HEAD 为受支持 schema v1、工作区为可信 schema v2 / 1.4.11，更新到 1.4.14+ 成功；
2. HEAD schema v1 payload 命中当前 contract historical hash，允许进入 transition classifier；
3. HEAD payload 不命中 historical hash 时 fail closed，并给出稳定 asset id、路径和原因；
4. HEAD 旧戳不受支持时 fail closed，禁止仅凭文件 hash 放行；
5. 只含受管更新时分类为 skeleton-only，不 bump 下游业务版本；
6. 同批含 project-owned 修改时分类为 mixed，但 project-owned 内容逐字保留；
7. apply 验证通过后最后写戳；任何失败恢复三个受管资产与旧戳；
8. 同一真实下游更新完成后再次 plan 为 no-op。

### B. user-level hook ownership

9. 项目 A 与项目 B 使用不同的合规 `.venv`，顺序运行 status / repair 后用户 handler 保持同一
   动态 Git 根 contract，不写入任一项目 Python 绝对路径；
10. 两个进程并发 repair 时只有一个 writer，另一方返回 unchanged 或 conflicted，不发生丢失更新；
11. 当前触发项目缺少或损坏 `.venv` 时 lifecycle 零写阻断并返回失败，不回退 PATH；
12. handler 无法定位 BridgeForgeCodex Git 根时 fail closed，不猜测或静默切换解释器；
13. hooks.json 中非 BridgeForge handler 字节语义保持；三项 managed marker 唯一；
14. repair 后 status 为 `hookInstalled=true`，第二次 repair 为幂等 no-op；
15. repair 路径对 GitHub、Git、memory 读取和 reconcile 设置 fail-if-called；
16. `remote_reconcile=not_requested` 与实际调用链一致。

### C. 端到端

17. 从一个 HEAD schema v1、工作区已完成 schema v2 迁移且带大量 project-owned 修改的真实下游
    运行 updater -> plan -> apply -> no-op replan，项目 readiness 为 ready；
18. 同轮 native-memory hook 由动态 Git 根调用当前项目合规 `.venv`，真实 runtime smoke 与最终
    status 均为 healthy；
19. 不要求提交、stash、clean、reset 或手工修改下游工作区；
20. factory unittest、manifest、dogfood、完整 fixture、真实下游和 runtime smoke 全部给出收据。

## 历史六类关闭证据（已被 1.4.30 边界取代）

| 证据类别 | 当前状态 | 关闭要求 |
|---|---|---|
| 源码 | #2～#6 已通过独立复审；#6 最终 0 / 0 / 0 / 0 | 等待用户验收 #6，再逐项关闭 #7～#9 |
| 产品传播 | #6 已传播至 1.4.21，Template / dogfood / contract / manifest 一致；整体未闭环 | 后续问题继续同步版本与六类证据 |
| dogfood | 完整 factory unittest 291/291；manifest、mirror、instruction、structure、metadata、diff 全部通过 | #6 技术证据已闭合 |
| fixture | downstream fixture passed：init stamp-last；27 个历史版本中 8 个 apply/no-op、19 个显式适配 | 后续真实项目阶段执行同一完整闭环 |
| 真实下游 | CBA #5 Planner ready/passed/skeleton-only且 vault projection 不变；其余三项目只读 replan，未知 ownership 保持 G 项 | 四个项目最终均须显式处理清单并完成 apply / no-op replan |
| runtime | 临时 fixture 已验证动态项目 `.venv`、错误 runtime fail-closed、共享 writer 并发/冲突/回滚；真实用户 runtime 未执行 | 后续真实项目阶段顺序运行 lifecycle/status/repair，证明跨项目调用后仍 healthy |

本表只记录 1.4.21 时点的证据，不再驱动当前实现。当前状态仅等待上文列出的真实下游确认式
重建与 native-memory runtime 验证；未执行前本报告保持 active。

## 恢复与回滚边界

- StratusAgent 项目同步器已回滚本轮三个受管资产，骨架戳保持 1.4.11；
- causis_risk_suite 项目同步器也已回滚本轮三个受管资产，骨架戳保持 1.4.11；
- 两个同步器事务临时文件均不存在；
- 不得用 `git reset --hard`、stash、clean、手工 copy 或手工写戳处理故障 A；
- 不得手工把 hooks.json 固定到某个项目 runtime 处理故障 B；
- 正式 hook 修复失败时必须恢复原 hooks、ledger 与 state，禁止触碰 memories 内容或远端；
- 本报告不授权对真实下游进行新的 apply、commit 或 push。

## 传播四问

1. 层级：两项均属于 BridgeForgeCodex 产品层；本文件本身是元文档。
2. 通用性：影响所有未提交完成 schema v1 -> v2 迁移后继续升级的下游，以及使用不同 Python
   基座维护同一用户级 native-memory hook 的多项目用户。
3. 发布：正式修复必须 bump 根 VERSION，并在 CHANGELOG 标记 `[product]`；本次仅报告，不 bump。
4. dogfood：release preflight、Template、用户级脚本、dogfood、fixture、真实下游与 runtime
   都必须同步验证。

## 关联记录

- `doc/2_bugs/BUG-git-sync-contract-transition-classification.md`
- `doc/2_bugs/BUG-native-memory-maintain-misclassified-safe-data-egress.md`
- `doc/2_bugs/BUG-bridgeforge-codex-145-end-to-end-acceptance-gaps.md`
- `templates/scripts/version_release.py`
- `scripts/bridgeforge_codex_project_sync.py`
- `scripts/codex_memory_sync.py`
- `scripts/tests/test_git_sync_version_release.py`
- `scripts/tests/test_memory_native_sync.py`
