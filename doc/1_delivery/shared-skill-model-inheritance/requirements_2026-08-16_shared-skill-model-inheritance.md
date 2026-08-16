---
status: implemented-awaiting-user-acceptance
topic: shared-skill-model-inheritance
date: 2026-08-16
source: "$confirm"
scale: M
---

# Shared Skill 模型继承与执行分工精简需求卡

## 原始需求摘要

用户认为 `templates/codex/AGENTS.md` 现有 `#4.5` 与 `#4.6` 难以理解且包含过时、重复的模型路由说明，要求：

1. 删除“`SKILL.md` 中的 `model:` 不作为 BridgeForge 的自动模型路由依据”。
2. 删除 BridgeForge 受管 shared skill 与两份全局入口 SKILL 中的全部 `model:` 字段。
3. Codex 与 Claude 统一继承用户当前会话模型。
4. 将 `#4.5` 与 `#4.6` 合并成一段容易理解的模型选择与执行分工说明。

## 目标

- BridgeForge 不替用户固定 skill 或子 agent 的模型与 effort。
- Codex 与 Claude 的受管 shared skill 统一继承用户当前会话模型。
- 保留必要的子 agent 分工红线，删除平台事实、兼容性解释和重复表述。
- 产品源发布后，通过正常 BridgeForge 同步更新用户级副本。

## 不做

- 不建立 Codex、Claude 两套不同的 skill 源文件或派生元数据。
- 不开发新的模型自动选择器。
- 不修改 Codex 系统 skill、插件 skill 或第三方 skill。
- 本轮不直接修改 `C:\Users\bridg\.codex\skills\` 等当前用户级副本。
- 不批量改写历史需求卡和归档文档中的历史记录。
- 未经用户后续明确调用，不执行 commit 或 push。

## 任务规模与预算

- **规模：M**。
- **判定依据**：逻辑规则单一，但同时影响双宿主 shared skill 元数据、Codex 模板、相关规则、manifest 和下游传播验证。
- **时间预算**：45 分钟。
- **Token 预算**：20k 新增 token（估算，平台无可靠计量器，未实测）。
- **Agent 预算**：最多 1 个子 agent。
- **验证预算**：最多 2 轮。
- **超预算停止点**：预计超过时间、token、agent 或验证轮次任一预算时停止，由用户选择扩大预算或缩小范围。

## 已核实事实

1. BridgeForge 仓库中有 15 个受管 SKILL 包含 `model:`：`skills/**/SKILL.md` 13 处，两份 `scripts/*_bridgeforge_entry.SKILL.md` 入口各 1 处。
2. 当前用户级 Codex skills 中存在对应的 13 份 shared skill 副本；两份入口由各宿主入口传播链管理。
3. Codex 不依赖该字段完成 BridgeForge 模型切换。
4. Claude Code 会使用 `model:` 作为 per-skill 模型覆盖；删除后 Claude 也将继承当前会话模型。
5. `templates/codex/AGENTS.md` 当前把模型选择与 skill 分段路由拆成 `#4.5` 和 `#4.6`。
6. `doc/README.md` 声明 `delivery_layout: flat`。

## 已确认规则

1. 删除全部 13 个 BridgeForge 受管 shared skill 的 `model:` 字段。
2. Codex 与 Claude 均继承用户当前会话的 model 和 effort。
3. 不保留 Claude 专用的 `sonnet/haiku` 元数据，不增加双宿主分叉。
4. 删除 Codex 模板及直接关联规则中关于“skill frontmatter `model:` 不是自动路由依据”的现行说明。
5. 本轮保留 `#4.5` 与 `#4.6` 的现有标题，只精简两个区域的正文；标题合并或改名由用户后续另行整理。
6. 默认由主对话执行任务；只有 `.codex/skill-routing.json` 明确要求独立阶段时才启动对应子 agent。
7. 用户沟通、确认、授权和最终汇总始终由主对话负责。
8. `$bridgeforge`、`$create-worktree` 与 `$git-sync` 始终由主对话执行；`$git-sync` 只运行当前项目自带同步脚本。
9. 产品源先修改并发布，用户级副本以后通过正常 BridgeForge 同步更新；本轮不直接写当前全局目录。

## 本轮目标文案

```markdown
## 4.5 Codex 模型 / effort（平台默认）

BridgeForge 不替用户选择模型。所有 skill 和子 agent 默认沿用用户当前会话的 model 和 effort；项目模板不得擅自锁定模型或思考强度。xhigh、max、pro 等高成本模式，只能由用户当次明确选择。

### 4.6 Skill 分段路由（强制）

任务默认由当前主对话完成。只有 `.codex/skill-routing.json` 明确要求独立调研、实现或审计时，主对话才启动对应的子 agent。

- 主对话负责与用户沟通、取得确认、处理授权并汇总最终结果。
- 子 agent 只执行分配给自己的阶段，不代替用户决策，也不重复已经完成的工作。
- `$bridgeforge`、`$create-worktree` 和 `$git-sync` 始终由主对话执行。
- `$git-sync` 只能运行当前项目自带的同步脚本，禁止拆成手工 Git 命令。
```

## 数据与传播映射

| 来源 | 派生或目标 | 规则 |
|---|---|---|
| 15 份受管 SKILL 中的 `model:` | shared skill manifest hashes 与全局入口 | 删除字段后由官方重建器更新和传播 |
| `templates/codex/AGENTS.md` | 新建或升级后的 Codex 下游 | 保留标题并精简两个区域正文后随产品同步 |
| BridgeForge 已发布产品源 | 用户级 shared skill 副本 | 仅通过正常 BridgeForge 受控同步传播 |

## 拟修改范围

- 13 个带 `model:` 的 `skills/**/SKILL.md` 与两份 `scripts/*_bridgeforge_entry.SKILL.md`。
- `templates/codex/AGENTS.md`。
- 与旧 `model:` 说明直接重复的 Codex portability 规则及必要 dogfood 镜像。
- 受影响的测试断言。
- `shared-skill-manifest.json` 与其他必要机械派生资产。
- VERSION 与 CHANGELOG 产品发布记录。
- 本需求卡与 `doc/README.md` 索引。

## 验收标准

1. BridgeForge 15 份受管 SKILL 中 `model:` 命中数为 0。
2. `templates/codex/AGENTS.md` 保留现有 `#4.5/#4.6` 标题，两个区域正文均替换为确认后的精简文案。
3. 产品模板和直接关联规则不再出现被删除的旧句。
4. skill metadata 检查通过。
5. 根与模板两份 `skill-routing.json` 结构一致，既有分工语义未被削弱。
6. manifest `--check`、mirror drift、harness parity 全部通过。
7. 完整 downstream fixture 通过。
8. 临时下游受控同步后，受管 shared skill 不含 `model:`。
9. 当前用户级 skill 副本没有被直接修改。
10. `git diff --check` 通过。

## 合理假设与风险

- 删除字段后，Claude 不再为简单 skill 自动选择 Haiku，也不再为其他 skill 自动选择 Sonnet；实际成本与能力取决于用户当前会话模型。这是已确认的预期行为。
- Codex 系统 skill、插件 skill 和第三方 skill 不属于 BridgeForge 产品源，必须保持原样。
- 历史需求卡、归档文档和 memory 中的 `model:` 记录属于历史事实，不作为现行产品残留。
- 只删除模型覆盖元数据，不改变 skill 的职责、输入、停止条件和用户调用方式。

## 自动化边界

- 允许修改仓库内产品源、模板、测试、manifest、版本和文档。
- 允许使用仓库官方重建器及下游 fixture 验证传播结果。
- 禁止在实现阶段直接写当前用户级 skill 目录。
- 禁止未经明确调用执行 commit 或 push。

## 后续交接目标

建议交给 `$develop` 按 M 级交付流程完成实现、验证和用户试用闭环。

## 实施记录

- 2026-08-16：用户明确暂缓标题调整；本轮只修改 `#4.5/#4.6` 正文。
- 2026-08-16：删除 13 份 shared skill 与两份 BridgeForge 兼容入口中的全部 `model:` 字段。
- 2026-08-16：精简 `templates/codex/AGENTS.md` 的 `#4.5/#4.6` 正文，保留既有标题与受管区块标识。
- 2026-08-16：删除现行 portability rule 中重复的 skill frontmatter 模型路由说明。
- 2026-08-16：补充源码与双用户货架的无模型覆盖断言，重建 managed schema 和 shared-skill manifest。
- 2026-08-16：未直接修改当前 `C:\Users\bridg\.codex\skills\`；产品发布后由正常 BridgeForge 同步传播。
- 2026-08-16：VERSION/CHANGELOG 尚未结算；仓库 `$git-sync` 会在用户明确调用时自动完成版本提升、CHANGELOG、parity 刷新、manifest 重建、commit 与 push。

## 验证记录

- `.venv\Scripts\python.exe -B -m unittest tests.harness.test_bridgeforge_root_skill tests.harness.test_skill_metadata_budget tests.harness.test_bridgeforge_project_sync`：49/49 通过；覆盖 SKILL frontmatter、模板正文、portability 规则、schema v2 与项目同步回归。
- `.venv\Scripts\python.exe -B tests\harness\run_downstream_fixture.py`：39/39 通过；`user_skill_distribution` 明确验证 Claude/Codex 两个测试用户货架收到的 skill 均不含模型覆盖，同时 ledger 漂移检测保持有效。
- `.venv\Scripts\python.exe -B scripts\rebuild_shared_skill_manifest.py --check`：exit 0，manifest 与 managed schema 已是当前状态。
- `.venv\Scripts\python.exe -B .codex\scripts\harness_parity_check.py --check`：exit 0；parity 报告已随 portability 行数变化刷新。
- `.venv\Scripts\python.exe -B .codex\hooks\mirror_drift_check.py`：exit 0。
- `.venv\Scripts\python.exe -B .codex\hooks\skill_metadata_check.py --pre-commit`：exit 0。
- `git diff --check`：exit 0。
- `rg -n "^model\s*:" skills scripts`：零命中；当前用户级目录仍命中原 13 项，证明本轮未直接写全局副本。
- 独立 `review-auditor`：实现审计通过；未发现代码、模板、双宿主分发、manifest、schema 或测试阻断。发布前仍须通过 `$git-sync` 自动完成版本与 CHANGELOG 结算。
