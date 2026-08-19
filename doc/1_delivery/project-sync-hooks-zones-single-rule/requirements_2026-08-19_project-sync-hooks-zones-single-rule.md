---
status: implemented-awaiting-user-acceptance
next: user_acceptance
scale: M
budget: 45_minutes_20k_tokens_unmeasured_1_auditor_2_validation_rounds_plus_user_approved_repair_round
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
---

# Project Sync Hooks Zones 单规则需求

## 背景与目标

问题 #5 的真实现场位于 ClaudeBridgeAssist `.codex/hooks.json`：项目自有 vault handler 与
BridgeForge dispatcher 混组，同时又存在第二份相同 dispatcher。当前 Planner 只检查第一个同
matcher group，先漏报；release evaluator 扫描全部 group 后才输出 `codex.hooks-config G1`。

用户确认 Hooks 必须采用与 AGENTS zones 相同的 ownership 原则：用户级和项目级 JSON 都只把
可稳定识别的 BridgeForge handler 视为受管区，其余内容分别归用户、第三方或项目所有。受管 handler
必须唯一、canonical 且独占 group；非受管内容必须保留。

## 当前唯一规则

1. BridgeForge handler 使用稳定 `bridgeforgeCodexId`；无该 ID 的 handler 不得仅凭相似路径被
   当前规则收编。
2. 一个受管 handler 必须独占一个 group；同一 scope / event / matcher / stage / id 只能有一份。
3. parser 必须遍历全部 group；禁止只取第一个 matcher group。
4. managed projection 必须命中当前 contract / generator；非受管 projection 的对象值、数组顺序和
   相对顺序必须保持。JSON 空白和 object key 顺序允许 canonical render。
5. 重复或混组的可信 BridgeForge handler可确定性拆分、去重；身份、hash 或 group 归属无法证明时
   零写 fail-closed。
6. 当前 contract 只保留 zones v2。旧无 ID 结构只允许在可信 HEAD contract 证明下执行一次显式
   transition；迁移后只接受 v2。

## 范围

- 项目级：Template hooks、hooks merger、Planner、release evaluator、contract rebuild 与 dogfood。
- 用户级：Native Memory hooks 的结构划分、canonicalization 与 health 判断。
- 产品版本、CHANGELOG、源 Bug、doc 索引、fixture、完整测试与独立审计。

## 非目标

- 不在 #5 决定用户级 Python runtime authority。
- 不实现跨项目 repair 全局锁、compare-and-swap 或 drift receipt；这些属于 #6。
- 不写真实 `~/.codex/hooks.json`，不对真实项目 apply、写戳、commit 或 push。

## 用户可见行为

- ClaudeBridgeAssist Planner 在写入前解释混组与重复 dispatcher，并生成可证明的 canonicalization；
  `vault_junction_check.py` 与 `vault_snapshot.py` 保持非受管 projection 不变。
- 合法迁移后每个 stage 只剩唯一 managed-only group；二次 plan 为 no-op。
- 未知或漂移 handler 继续输出稳定 G 项，禁止猜测删除。

## 实施计划

1. 建立共享 hooks ownership parser 与 zones v2 contract。
2. 让 Planner、hooks merger、release evaluator 与用户级 merger 统一调用同一投影规则。
3. 传播 Template / dogfood / manifest，补齐 CBA 正例和漂移负例。
4. 运行针对性与完整验证、四项目零写 replan，并由独立 agent 审计。

## 验收

1. CBA 混组 + 重复 fixture 产生确定性迁移，不再 plan ready / apply blocked。
2. 非受管 projection 迁移前后相同；同名未标记第三方 handler 不被收编。
3. duplicate id、hash drift、invalid JSON、duplicate JSON key、非法 group 全部零写阻断。
4. Planner 与真实 evaluator 等价；fingerprint 漂移零写，失败回滚，stamp-last。
5. 用户级 merger 保留第三方 handler，把 managed handler 拆为唯一独立 group，并保持幂等。
6. 相关测试、完整 factory、downstream fixture、发布硬闸与独立审计全部通过。
7. CBA 1.4.20 零写 Planner 不再出现原 `codex.hooks-config` G1；其他三个项目对无法证明的
   历史 ownership 继续稳定 fail-closed，不发生未知内容自动写入。

## 风险与停止点

- Codex runtime 不接受稳定 ID 字段时停止，不使用未证明的替代字段。
- 任一非受管 projection 发生变化时停止，不写盘。
- 需要真实用户级 hook repair、范围扩入 #6 或进入第三轮实质修复时停止并重新确认。

## 2026-08-19 实施与验证收据

- 产品版本已升至 1.4.20。Template、dogfood、两份 managed contract 与 active manifest 已传播
  `hooks_ownership.py`、zones v2 contract 和稳定 `bridgeforgeCodexId`。
- Planner、项目 hooks merger、release evaluator 与用户级 Native Memory merger 统一使用共享
  ownership parser；managed handler 被拆为唯一独立 group，external handler 保持对象值与相对顺序。
- CBA 零写 Planner 返回 `readiness=ready`、`release_preflight_status=passed`、classification
  `skeleton-only`，无 gap / blocker / required action；计划产物中的两个 vault handler 与 before 对象、
  event、matcher 和顺序完全相同。
- 可信 legacy whole-file HEAD 可一次性迁移；whole hash 不匹配仍 fail-closed。Causis HEAD 的旧
  `UserPromptSubmit` 与其无 projection contract 的 whole hash 不一致，因此稳定保留
  `codex.hooks-config G1`，未猜测归属或写盘。
- 首次独立审计发现 2 个 High：普通 JSON 解析吞重复 key、独立 merger 按路径删除无 ID handler。
  两项均已修补：所有 JSON 入口统一 duplicate-key 硬拒绝，旧路径剥离已删除；新增正反例 3/3 通过。
- 审计修复后完整自动测试 273/273 通过。downstream fixture passed：8 个 current-marker
  基线完成迁移，19 个旧 pre-commit marker 基线按 #3 单规则稳定要求显式适配。
- manifest `--check` 为 already current；mirror、instruction source、project structure、skill metadata、
  `git diff --check` 均 exit 0。未写真实项目、用户级 hooks 或版本戳，未 commit / push。
- 独立复审最终 `Blocker / High / Medium / Low = 0 / 0 / 0 / 0`。复审独立重跑完整测试
  273/273、downstream fixture、CBA external projection 与全部发布硬闸，#5 技术实现可关闭，等待
  用户验收。

## 后续编号归并

- 原清单问题 #8 不是独立产品缺陷，而是本问题 #5 在 Causis 的真实下游适配与验收项。最新零写
  Planner 仍稳定输出 `codex.hooks-config G1`：旧 HEAD 无稳定 ID，且不命中可信 legacy whole-file
  hash，当前规则不能证明 managed projection。
- 最终项目阶段必须把可信 BridgeForge dispatcher 显式适配为 zones v2，保留无 ID 的项目自有
  `root_hygiene_check.py` handler 和其他未知内容，再执行完整事务闭环。当前未写 Causis、用户级
  hooks、Git index 或 remote。

## 后续编号归并

- 原清单问题 #8 不是独立产品缺陷，而是本问题 #5 在 Causis 的真实下游适配与验收项。最新零写
  Planner 仍稳定输出 `codex.hooks-config G1`：旧 HEAD 无稳定 ID，且不命中可信 legacy whole-file
  hash，当前规则不能证明 managed projection。
- 最终项目阶段必须把可信 BridgeForge dispatcher 显式适配为 zones v2，保留无 ID 的项目自有
  `root_hygiene_check.py` handler 和其他未知内容，再执行完整事务闭环。当前未写 Causis、用户级
  hooks、Git index 或 remote。

## 后续编号归并

- 原清单问题 #8 不是独立产品缺陷，而是本问题 #5 在 Causis 的真实下游适配与验收项。最新零写
  Planner 仍稳定输出 `codex.hooks-config G1`：旧 HEAD 无稳定 ID，且不命中可信 legacy whole-file
  hash，当前规则不能证明 managed projection。
- 最终项目阶段必须把可信 BridgeForge dispatcher 显式适配为 zones v2，保留无 ID 的项目自有
  `root_hygiene_check.py` handler 和其他未知内容，再执行完整事务闭环。当前未写 Causis、用户级
  hooks、Git index 或 remote。
