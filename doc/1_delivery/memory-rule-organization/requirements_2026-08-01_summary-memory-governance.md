---
status: confirmed
topic: memory-rule-organization
date: 2026-08-01
source: "$confirm：梳理 summary 职责、项目写入边界与 memory 颗粒度治理"
handoff: develop
recommended_handoff: develop
---

# Summary 职责收口与 Memory 颗粒度治理

## 原始需求摘要

系统梳理并修正 `$summary` 当前承担的工作：确保 BridgeForge 及下游项目都通过项目
memory writer 写入当前项目；限制 topic 与通用 memory 的记录颗粒度，防止单次事故、
子任务和日期记录持续形成碎片；明确 rule、docs、归档、用户级 memory、测试收据、
hook trust 与 Git 的自动化边界；移除 harvest 职责。对于既有碎片，`$summary` 只给出
合并候选，用户确认具体批次后再独立执行合并和删除。

## 目标

1. 将 `$summary` 收口为当前项目的知识归纳入口，自动完成高置信、非破坏性的
   memory、rule 与 docs 更新。
2. 用“一个 delivery topic 一个规范 summary、一个通用 memory 回答一个稳定问题”
   取代按日期、子任务或单次经验建文件。
3. 对既有碎片提供可审核的合并候选，不在日常总结中自动删除历史 memory。
4. 用可验证的收据区分已完成、未验证、运行时未验证与待用户验收状态。

## 不做

- 不在 `$summary` 中自动合并或删除既有 memory 碎片。
- 不把旧碎片移入 memory 内部的 archive；历史恢复由 Git 提供。
- 不自动调用 `$archive-scan`，不移动 delivery/Bug 文档，不更新归档索引。
- 不检查或写入 harvest inbox/candidate，不调用 `$harvest`；删除 harvest skill 本身
  不属于本需求。
- 不重新运行测试，不以缺失的测试、审计或运行时收据推断成功。
- 不自动写用户级 memory，不自动 `git add`、commit 或 push。
- 不给 BridgeForge 工厂伪造 `.codex/.bridgeforge_version`。

## 已核实事实

- 产品源码 `skills/summary/SKILL.md` 与当前安装的用户级 summary skill 内容一致。
- 当前 `$summary` 要求先去重和分类，但没有可执行的 memory 颗粒度门槛。
- 当前 `$summary` 以 `.codex/.bridgeforge_version` 识别受管 Codex 项目，并要求其使用
  `.codex/scripts/project_memory_writer.py`。
- BridgeForge 当前存在 `.codex/scripts/project_memory_writer.py`，但不存在
  `.codex/.bridgeforge_version`；按现有字面条件，工厂自身不会被强制走 writer。
- `D:\Quant\StratusAgent\.codex\memory` 现有 407 个 Markdown 文件，其中通用分类
  数量远高于 topic；大量文件按单次反馈、事故、决定或子任务记录。碎片问题不只存在于
  `topics/`。
- topic 内也存在按里程碑子任务或日期单独建文件的情况，不能稳定形成单一规范摘要。
- `$summary` 当前仍包含 harvest candidate/inbox 处理职责。
- 现有 `$archive-scan` 才负责在用户确认后使用 `git mv` 归档已验收 delivery topic 与
  已解决 Bug，并同步 `doc/README.md`。

## 已确认业务规则

### 1. 项目 writer 识别与写入边界

1. 当前项目存在 `.codex/scripts/project_memory_writer.py` 时，`$summary` 必须通过它
   写项目 memory，不再要求版本身份证同时存在。
2. 当前项目存在 `.codex/.bridgeforge_version` 但缺少 writer 时，必须停止写入并提示
   用户执行无参数 `/bridgeforge`；禁止回退到用户级 memory。
3. BridgeForge 工厂通过 writer 能力触发自身 dogfood，不增加虚假的受管项目版本标记。
4. 高置信、非破坏性的当前项目 memory 合并或更新可以自动执行；目标、分类或结论不确定
   时必须询问。

### 2. Topic memory 单一规范文件

1. 每个 delivery topic 只能维护一个规范文件：
   `.codex/memory/topics/<topic>/summary.md`。
2. 后续总结必须更新该文件，禁止按日期、单次对话、里程碑子项或子任务新增 topic
   memory 文件。
3. topic 状态只有在全部验收条件满足、用户已试用或明确验收、且不存在未解决 blocker
   时才能标记为 `completed`。
4. 只有代码、测试、审计或 Git 收据时，不得代替用户验收。

### 3. 通用 memory 的稳定问题门槛

1. 一个通用 memory 必须回答一个长期稳定、后续会重复检索的问题，例如交互契约、
   身份规则或网关可靠性模式。
2. 单次事故、小修复、测试数字、实施流水和孤立经验不得各自成为 memory 文件。
3. memory 只保留当前有效结论、原因、适用范围、例外和权威代码/设计文档链接。
4. 事故经过、过程证据、长示例和测试数字留在 delivery 或 Bug 文档。
5. 写入前必须优先检索并更新已有规范 memory；只有确实出现新的稳定问题时才允许新建。

### 4. 既有碎片的合并边界

1. `$summary` 只列出旧 memory 合并候选，不执行合并或删除。
2. 每个候选簇必须列明：建议的规范目标文件、来源文件、重复结论、冲突或疑似过时结论、
   建议保留内容和建议删除文件。
3. 用户确认具体批次后，才由独立整理任务合并到规范文件并删除已被吸收的旧碎片。
4. 合并不得机械拼接；冲突或无法判断的新旧结论必须单独请求用户裁决。
5. 合并后的固定校验顺序为 `memory_rebuild_index → memory_lint`，并检查失效链接、
   重复主题与 Git diff。
6. 已删除旧文件的恢复渠道是 Git 历史；禁止在 memory 树内保留仍会参与加载和检索的
   archive 副本。

### 5. Rule 与 docs 同步

1. `$summary` 可以自动更新高置信且确有必要的当前项目 rule 与文档。
2. 只有长期稳定的“必须/禁止”红线才能进入 rule；事故经过、方案对比与长示例必须留在
   memory/doc。
3. rule 最多用一行 `Why` 指向对应 memory；按路径加载的 rule 必须具备机器可解析的
   `paths` frontmatter。
4. 分类、约束强度或文档归属不确定时必须询问，不得自动扩张规则范围。

### 6. Archive Scan 与 Harvest

1. `$summary` 只列出已完成 delivery topic 与已解决 Bug 的归档候选，并提示用户另行
   调用 `$archive-scan`。
2. `$summary` 不自动调用 `$archive-scan`，不执行 `git mv`，不更新归档索引。
3. `$summary` 完全移除 harvest candidate/inbox 检查、写入与 `$harvest` 调用。

### 7. 测试、hook trust 与 Git 收据

1. `$summary` 不重新运行测试；只读取本轮已经产生的真实测试、审计和 Git 收据。
2. 缺少证据的事项必须明确标记“未验证”。
3. `/hooks` review/trust 或新会话 smoke 未完成时，收据必须注明
   `runtime trust 未验证`，不得宣称 lifecycle hook 已生效。
4. `$summary` 报告 `git status` 和相关变更文件，但禁止自动暂存、commit 或 push；发布
   继续由 `$git-sync` 负责。

### 8. 用户级 memory

1. 默认只写当前项目。
2. agent 判断某项知识具有跨项目价值时，只能列出“用户级 memory 候选”及理由。
3. 只有用户明确批准后才能写入用户级 memory；项目写入失败不得触发用户级回退。

## 数据与行为映射

| 当前情况 | 目标行为 |
|---|---|
| 有 writer，无 `.bridgeforge_version` | 通过能力检测强制使用 writer |
| 有 `.bridgeforge_version`，无 writer | 阻断并提示 `/bridgeforge` |
| 同一 topic 的日期/子任务文件 | 后续统一更新 `topics/<topic>/summary.md` |
| 单次事故或小经验 | 留在 delivery/Bug 文档，不新建通用 memory |
| 多个文件回答同一稳定问题 | 列为合并候选簇，待用户确认后独立整理 |
| 高置信当前项目结论 | 自动合并或更新规范 memory |
| 疑似跨项目经验 | 只列用户级候选，等待批准 |
| 已完成 delivery/Bug | 只列归档候选，交给 `$archive-scan` |
| 已有测试/审计/Git 收据 | 读取并据实总结，不重新执行 |

## 拟修改范围

### 产品层

- `skills/summary/SKILL.md`
- `skills/summary/references/deep-steps.md`
- summary skill 的分发 manifest、元数据或路由资产（仅在现有机制要求时更新）

### 测试

- writer 能力检测与缺失阻断
- topic 单一 `summary.md` 与通用 memory 新建门槛
- 旧碎片只报告候选、零自动删除
- harvest 职责移除
- archive、用户级 memory、测试收据、Git 与 runtime trust 边界

### 传播与 dogfood

- 产品层变更对应的根版本与 skill 分发版本
- `CHANGELOG.md` 的 `[product]` 条目
- 当前安装的 summary skill 与 BridgeForge dogfood 所需资产同步
- 必要的设计文档和 `doc/README.md`

## 验收标准

1. BridgeForge 在没有 `.bridgeforge_version` 时仍因 writer 存在而走确定性项目写入。
2. 受管项目缺少 writer 时 fail closed，且不产生用户级 memory。
3. 同一 topic 的后续 summary 只更新唯一 `summary.md`，不新增日期或子任务文件。
4. 通用 memory 新建前必须通过“新的稳定问题”门槛；单次事故/小修复被拒绝为独立文件。
5. `$summary` 对旧碎片只输出结构化合并候选，未获确认时文件零删除、零移动。
6. 独立合并流程明确执行 `memory_rebuild_index → memory_lint`，重建失败时不得继续 lint。
7. `$summary` 不产生 harvest candidate/inbox，不调用 `$harvest`。
8. 归档候选不被自动移动，且明确交给 `$archive-scan`。
9. 用户级 memory 在未获明确批准时零写入。
10. 缺失测试或运行时 trust 收据时准确标记“未验证”，不做成功推断。
11. `$summary` 不重新运行测试，不暂存、commit 或 push。
12. 产品版本、`[product]` CHANGELOG、分发 manifest、安装态 skill 与测试收据完整，
    并通过独立审计。

## 合理假设与风险

- “稳定问题”需要以可重复检索的工程问题为判断单位，不能只依赖文件名相似度；实现必须
  给出正反例和 fail-closed 规则。
- 既有 memory 可能包含相互冲突或时间语义不同的结论，自动相似度只能生成候选，不能
  自动决定权威结论。
- 删除旧碎片虽然可由 Git 恢复，仍属于破坏性操作，必须按候选批次取得用户确认。
- 已有 memory 数量较大，本需求不承诺在 `$summary` 改造交付中一次性整理完成。
- 当前 hook 迁移只有静态验证收据，真实 `/hooks` trust 与新会话 smoke 仍需用户环境验证。

## 自动化边界

- 可自动：当前项目高置信 memory 合并/更新、必要 rule/docs 更新、读取既有收据、生成
  旧 memory 合并候选与文档归档候选。
- 必须确认：结论冲突、分类不确定、既有 memory 合并删除、用户级 memory 写入。
- 禁止自动：重新运行测试、调用 `$archive-scan`/`$harvest`、删除旧 memory、Git 发布。

## 后续交接目标

- 推荐 `$develop`：该需求涉及产品 skill、颗粒度策略、writer 路由、分发版本、测试与
  dogfood，属于跨模块完整交付。
- 也可先用 `$debate` 专门论证“稳定问题”机器判据，或用 `$collab` 在需求已稳定时分治
  skill、测试与审计；实际交接目标由用户在需求卡落盘后选择。

## 实施与验证记录

- 实施计划：重写 summary 主契约与低频深档步骤；新增静态契约测试；更新共享分发哈希与
  根产品版本；运行定向测试、分发回归、fixture、manifest/parity 和独立交付审计。
- 已实施：
  - `skills/summary/SKILL.md` 已改为先按 writer 能力路由；有版本戳但缺 writer 时
    fail closed。保留四类通用 memory 与 metadata 契约，并把 topic 固定为当前项目
    memory 根下唯一 `topics/<topic>/summary.md`。
  - 通用 memory 新增“稳定问题”正反例和不确定时停止门槛；高置信、非破坏的当前项目
    memory/rule/docs 更新可自动执行。
  - `deep-steps.md` 已把旧碎片收口为只读候选簇，把归档交给 `$archive-scan`；独立整理
    明确 `memory_rebuild_index → memory_lint` 串行及失败短路。
  - summary 已移除 harvest 捕捉、测试重跑、自动归档和 Git 发布职责；用户级 memory
    必须先列候选并取得批准。
  - 项目 memory writer 已改为 Codex/Claude 宿主无关实现，四份模板/dogfood 正文一致；
    writer 按自身位置锁定 `.codex` 或 `.claude`，不依赖版本戳即可安全写当前项目，
    但仍严格校验宿主目录、writer、memory、rebuild、目标边界、原子写入和索引收据。
  - `$harvest` 的过时反向声明已修正：候选只来自用户显式参数或既有 inbox，不再假设
    `$summary` 生产候选。
  - 新增 `tests/harness/test_summary_skill.py` 并扩展 writer/shared distribution 测试；根
    版本升至 `0.76.0`，Codex/Claude 模板分别升至 `0.45.0`/`0.33.0`，更新三份
    CHANGELOG、双平台 shared-skill manifest 与 harness parity 报告。
- 测试收据：
  - `.venv\\Scripts\\python.exe -m unittest tests.harness.test_summary_skill
    tests.harness.test_project_memory_recovery tests.harness.test_shared_skill_distribution
    tests.harness.test_skill_metadata_budget tests.harness.test_bridgeforge_root_skill
    tests.harness.test_downstream_version_sot -v` → exit 0，47 tests；覆盖 summary 双宿主
    路由、topic 单文件、稳定问题、分类 metadata、候选边界、rebuild/lint 短路、归档/
    用户级/Git/runtime trust、rule/docs 自动更新、harvest 接口、Codex/Claude markerless
    安全写入、逃逸阻断、四份 writer parity、分发 inventory 与版本链。
  - `.venv\\Scripts\\python.exe tests\\harness\\run_downstream_fixture.py --case
    skill-metadata --case skill-refs --case user-skill-distribution` → exit 0，3 cases。
  - `rebuild_shared_skill_manifest.py --check`、`harness_parity_check.py --check`、
    `git diff --check` → exit 0。
- 独立审计：首次 review-auditor 发现 Claude 缺少确定性 writer、deep steps 硬编码 Codex、
  harvest 反向声明和测试未覆盖跨宿主，判定 blocker；上述问题修复后由同一 auditor 复核。
  复核结果：四项 finding 全部 closed，无新 blocker，允许进入用户
  试用；四份 writer SHA-256 均为
  `90b78027b0276d42a905671467b91ed2cfdbf84b483a03e78e7a03fc0f6389d2`。
- 安装态：未直接从未发布工作副本覆盖用户级 skill；发布后由无参数 `/bridgeforge` 通过
  GitHub `main` manifest 同步。当前安装态为待同步，运行时试用未验证。
- 用户试用/验收：未开始。
