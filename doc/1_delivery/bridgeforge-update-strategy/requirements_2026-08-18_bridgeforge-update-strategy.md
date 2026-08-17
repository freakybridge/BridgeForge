---
status: implemented-awaiting-user-acceptance
next: user_acceptance
size: M
confirmed_at: 2026-08-18
source_bug: doc/2_bugs/BUG-bridgeforge-codex-145-end-to-end-acceptance-gaps.md
---

# BridgeForgeCodex AGENTS 迁移与 git-sync 合法 no-op

## 原始需求摘要

按用户确认的方向重新更新骨架：旧 `AGENTS.md` 不能简单覆盖或整份搬入项目专区，必须先按所有权分类，再清理可信旧公共内容、精确去重并合并项目内容；`$git-sync` 不得把 contract 变化但目标已满足新版要求的合法 no-op 误判为漏迁移。

调用来源：`$develop` 经 `$confirm` 收敛。后续交接目标：主对话实施、定向验证和一次独立审计。

## 目标

1. 旧 `AGENTS.md` 迁移按“分类 -> 清理 -> 精确去重 -> 合并 -> 验证”执行。
2. 无法可靠判断归属的内容保持原文件、进入 `action_required` 清单，用户确认前零写入且不写新版本戳。
3. `$git-sync` 对 contract 定义变化但目标内容未变化的合法 no-op，在当前目标通过新版 contract 且项目内容不变时放行。
4. 保持现有 fail-closed 边界，不允许当前损坏、项目内容丢失、不可信 lineage 或资产错配借 no-op 绕过。

## 不做

- 不修改 `collab`、`create-worktree`、`debate`、`escalate`、`plan` 五个用户级 Skill 的 ClaudeBridgeAssist 专属退休特例或 ledger 事务。
- 不恢复上述五个 Skill。
- 不直接写入 `D:\Quant\ClaudeBridgeAssist`。
- 不引入 LLM 自动语义去重。
- 不把四个退役 Rule 的未知项目修改自动删除。
- 不重构统一 transition proof 模块；若实现证明必须跨入该范围，停止并重新确认。
- 不执行 commit 或 push。

## 规模与预算

- 规模：M。
- 判定依据：跨项目同步器与版本分类器，但用户行为、边界和验收已明确；Template/dogfood、版本、CHANGELOG 与 manifest 属机械传播。
- 时间上限：90 分钟。
- Token 上限：30k 估算，平台无法实测。
- 子 agent：最多 1 个独立审计 agent。
- 验证：最多 2 轮。
- 超预算停止点：需要重构共享 transition proof、改用户级迁移器、增加新的用户确认轮次或扩大真实下游写入时停止。

## 已核实事实

- BridgeForgeCodex `1.4.5` 的 `project_sync` 可在真实下游写入 ready 版本戳，但同一结果仍可能被 repo-local `$git-sync` 阻断。
- 旧 `ClaudeBridgeAssist/AGENTS.md` 存在未闭合 Markdown fence；当前新版文件已形成公共区与项目专区。
- `.codex/hooks.json` 的旧、新 contract source/hash 不同，但 Git HEAD 与当前目标文件逐字相同；该资产是 `merge` 策略的真实合法 no-op。
- 当前 transition classifier 将资产定义变化等同于目标必须进入 changed paths，导致 no-op 误报。
- 四个旧 Markdown Rule 仍使用 retirement 策略；可信原版可删除，未知修改继续保留。

## 已确认规则

### AGENTS 分类与合并

- 迁移前必须冻结旧文件原文，并把内容分类为旧公共、项目所有或未知。
- 只有逐字相同、稳定 section id、可信历史摘要或显式 legacy mapping 才允许自动去重。
- 仅语义相似的内容禁止自动删除，必须进入用户清单。
- 无法分类时保留原文件，输出 `action_required`；清单逐项包含来源位置、内容摘要、无法分类原因、推荐归属和推荐动作。
- 用户在 BridgeForgeCodex 既有唯一确认卡中选择全部推荐、部分、自定义或停止；禁止新增第二次确认。
- 未确认前零写入、旧版本戳保持，`readiness` 必须体现待用户动作。

### git-sync 合法 no-op

- contract 变化不等于目标文件必须变化。
- stable asset id/target 对齐、当前目标通过新版 contract、项目内容逐字保持、目标前后内容相同、contract/stamp/lineage 可信且无其他 blocker 时，允许 no-op 不进入 changed paths。
- 任一条件不成立时继续 fail-closed；禁止通过制造无意义文件改动放行。

### 退役 Rule

- 四个旧 Rule 保持既有 retirement 语义。
- 精确可信官方旧文件允许删除且不重装。
- 有项目修改或无法证明时保留并列 gap，不做语义猜测删除。

## 用户可见清单

每个不确定段落使用稳定项目编号并至少显示：

```text
G1
来源：旧 AGENTS.md 第 X 节
内容摘要：...
无法分类原因：...
推荐归属：项目级专区 / 清理 / 保留原位
推荐动作：...
```

## 拟修改

- `scripts/bridgeforge_codex_project_sync.py`
- `templates/scripts/version_release.py` 与 `.codex/scripts/version_release.py`
- 对应 managed contract / manifest 派生文件
- `scripts/tests/test_bridgeforge_codex_project_sync.py`
- `scripts/tests/test_git_sync_version_release.py`
- 本 Bug 报告、根 `VERSION` 与 `CHANGELOG.md`

## 验收

1. 可确定归属的旧 AGENTS 内容正确迁入项目专区。
2. 未闭合 fence 或未知内容形成逐项 `action_required` 清单，零写入且旧戳保持。
3. 完全相同或可信映射内容自动去重；仅语义相似内容不自动删除。
4. `.codex/hooks.json` 合法 no-op 被 `$git-sync` 接受。
5. no-op 目标不满足新版 contract 或项目内容变化时仍阻断。
6. 项目 handler、项目专区及 pre-commit extension 保持原字节。
7. 定向自动测试、完整 downstream fixture、manifest `--check`、mirror、instruction、structure 与 `git diff --check` 通过。
8. 独立审计复核 AGENTS 内容无损和 no-op 放行边界。

## 合理假设与风险

- 当前实现已有唯一风险确认卡与 U 项目选择协议，可复用而不新增交互轮次。
- Markdown 格式损坏只能在可确定边界内恢复；未知正文必须保留并交用户确认。
- no-op 放行只解决目标文件已达标的误报，不替代历史 contract、当前 marker 和项目所有权验证。
- 真实 `ClaudeBridgeAssist` 的人工历史清理不属于本轮写入范围，最终仅作只读 preflight。

## 自动化边界

- 自动：确定性分类、精确去重、可信 legacy mapping、no-op contract 验证、测试与派生 manifest 重建。
- 需用户唯一确认：未知或仅语义相似的 AGENTS 内容处置。
- 禁止自动：未知项目内容删除、contract/hash 伪造、版本戳提前写入、真实下游 commit/push。

## 实施记录

- `scripts/bridgeforge_codex_project_sync.py` 为 legacy AGENTS gap 增加逐段
  `review_items` 与稳定排序的 `action_required_items`；未知标题、managed/retired 漂移、
  residual 正文和未闭合 fence 均报告来源行号、摘要、hash、原因、推荐归属与动作。
- 非执行人工 review 清单使用 G1/G2，与可执行上游吸收 U1/U2 完全分离；重复候选、
  current/legacy 标题混用、zone marker 歧义与公共区漂移也生成逐项清单。
- residual 识别改为保留原位置的 segment 计算；无法分类时继续返回原始文件，阻断
  root AGENTS action、Rule retirement 与新版本戳。
- `templates/scripts/version_release.py` 与 dogfood 镜像加入
  `codex-hooks-dispatchers-v1` 投影验证；仅 stable id/target、HEAD 与当前目标逐字不变、
  当前 managed dispatcher 唯一且精确匹配时允许 merge no-op。
- `scripts/rebuild_shared_skill_manifest.py` 从 `templates/hooks.json` 自动生成上述投影，
  两份 managed contract 与发布 manifest 已重建。
- `skills/bridgeforge-codex/SKILL.md` 要求首轮直接逐项展示清单，禁止只显示 gap 数量后
  再让用户追问；产品版本更新为 `1.4.6`。
- 未修改用户级 migration/ledger 的五 Skill 特例，也未写入真实 `ClaudeBridgeAssist`。

## 验证记录

- 定向 `version_release` transition 测试中，合法 hooks merge no-op、受管 dispatcher 漂移、
  whole target 漏报、AGENTS ownership transition 等均通过。
- project-sync 模块在派生 contract 稳定后运行 39 项：36 项通过，3 项仅为新增测试断言
  不准确；修正后精确复查其中 3 项为 2 项通过、1 项仍因清单合理拆为 U1/U2 而失败，
  随后已把断言改为验证稳定连续编号和目标内容项；最终编号已改为 G1/G2。
- 最终完整 discovery 实跑 245 项，243 项通过；两项失败均为机械契约：历史版本期望集合
  漏 `1.4.5`、新增错误文案误用技术仓库名 `BridgeForgeCodex`。两处均已修复；依据已确认
  “最多 2 轮验证”未再启动第三轮完整测试。
- 因完整 discovery fail-fast，最终 fixture、manifest `--check`、mirror、instruction、
  structure、metadata 与 `git diff --check` 尚未在最终快照串行执行；不得宣称全绿。
- 真实 `ClaudeBridgeAssist` 只读 preflight 尚未执行。
- 独立审计首轮发现两个 High：G/U 编号冲突，以及三类歧义 gap 缺逐项 review；当前均已
  修补，并新增 missing/duplicate dispatcher 与 marker 清单回归，但依据验证轮次上限尚未
  由实现侧复跑。
- 同一独立审计 agent 最终最小复核通过：重复精确 heading 生成唯一 G1，apply 后 AGENTS
  原字节不变且不写戳；missing dispatcher 精确测试 1/1 通过；Template/dogfood 的
  `version_release.py` 与 managed contract 两对 SHA256 一致。最终 blocker/high 为 0，
  可进入用户验收。
