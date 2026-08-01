# 统一 Memory schema 与 topic 生命周期治理需求

> 状态：已实现，独立审计通过，待用户验收  
> 确认日期：2026-08-02  
> 规模：L  
> 预算：90 分钟 / 约 45k 新增 token（未实测）/ 最多 3 个子 Agent / 最多 3 轮验证

## 1. 背景与目标

当前 memory 条目 schema、索引器和冷热策略继续作为单一机械底座，不分叉为两套实现。
本次补齐三类产品契约：

1. 所有项目统一使用公共/分类模块 memory 与 topic memory 的同一套大型 schema。
2. 明确模块 memory 与 topic memory 的职责边界、topic 创建门槛和生命周期管理。
3. 将 `$summary` 分为阶段性记录与明确验收两种模式，限制文档扩张。

同时在设计事实源中提供完整流程图、布局说明、判断标准和管理规则，并保持 Claude/Codex
语义等价。

## 2. Memory 模型

### 2.1 模块 memory

模块 memory 保存长期稳定、未来会重复检索的架构、接口、约束和工程结论。它回答：
“这个模块长期是怎样工作的？”

### 2.2 Topic memory

Topic memory 保存一次独立交付的目标、决策、进度、验收和交付过程。它回答：
“这次交付为什么做、做到哪里、是否已经关闭？”

完成 topic 后，只把长期稳定的模块知识提炼到模块 memory；交付过程继续留在原 topic，
并通过状态进入冷索引。禁止整份复制造成双重事实源。

## 3. 统一 schema 与布局

- 所有项目都使用公共 memory、四类模块 memory 与 `topics/<topic>/summary.md`。
- 模块分类、topic 共用同一 metadata schema、writer、索引器和冷热策略。
- 初始化只创建 `MEMORY.md`；分类目录和 topic 目录都在首次合法写入时创建，禁止预建空目录。
- 禁止按项目人数、规模、文件数或代码行数选择不同 schema，禁止新增第二套索引器或语义分类器。

## 4. `$bridgeforge` 与版本戳

- `$bridgeforge` 对所有项目铺设同一 memory schema，不执行规模判断或 profile 访谈。
- `.<host>/.bridgeforge_version` 恢复单行契约，只保存 BridgeForge 骨架版本。
- init/adopt 写入单行版本；update 替换单行版本；switch、show-state、snapshot 与 hook merge
  沿用既有单行行为。
- 禁止新增 memory schema 配置文件或在版本戳中追加第二行。

## 5. 目录创建

- 模块 memory 首次真实写入时创建对应分类目录。
- Topic 只有满足第 6 节门槛时才创建 `topics/<exact-slug>/summary.md`。
- 禁止为未来事项预建空 topic、按日期或子任务创建多个 topic memory 文件。

## 6. Topic 创建与管理

### 6.1 创建门槛

只有用户已经确认一个独立交付，且该事项同时具备独立目标、独立验收条件和可独立关闭的
生命周期时，才能创建 topic。

- 普通子任务、一次性排查、小修和里程碑子项不得创建 topic。
- 已完成主体之后出现、且有独立验收条件的后续事项应建立新 topic。
- 用户已确认独立交付即构成建 topic 授权，无需重复询问。
- 无法唯一判断时保持现状并请求确认。
- 禁止自动拆分、合并、改名或移动 topic。

### 6.2 数量控制

- 不设置历史 topic 数量上限。
- `active` topic 必须对应用户已经确认且仍在推进的独立交付。
- 创建前检查现有 active topic，禁止重复建档。
- `$summary` 时对账活跃 topic，列出疑似已完成、暂停或被替代但未更新状态的候选。
- 状态不清楚时询问用户，禁止自动关闭。
- `completed` / `superseded` topic 保留原目录并进入冷索引，不占用热区。

## 7. `$summary` 双模式

### 7.1 `$summary`

- 只更新当前工作的唯一主 memory 和自动索引。
- 当前工作属于已确认 topic 时，只更新该 `topics/<topic>/summary.md` 并保持 `active`。
- 当前工作不属于 topic 时，最多更新一个最相关的模块 memory。
- 不修改 TODO、rules、需求、设计或计划文档；只列同步候选。
- 不得把调用 `$summary` 本身解释为验收。

### 7.2 `$summary 同意验收`

- 参数本身表示用户明确验收，不再重复询问。
- 已知 blocker、未满足验收条件或相互冲突的收据仍必须阻止关闭并说明原因。
- 当前工作属于已确认 topic 时，在条件满足后将其标记为 `completed`；没有 topic 时，仅在满足 topic 创建门槛后创建，否则最多更新一个模块 memory。
- 最多向一个最相关模块 memory 提炼长期稳定知识，禁止整份复制 topic。
- 结算当前交付的 TODO：完成项标记完成；验收阻塞项阻止关闭；非阻塞后续事项列为
  新 topic 或 backlog 候选，等待用户决定。
- 其他 topic 和项目级 TODO 保持不变。
- 只整理当前 topic 的 `related_paths` 或当前需求卡明确关联的需求、设计和计划文档。
- 缺少必要事实源文档时先询问，禁止自行扩张文档面。
- 只有长期稳定的“必须 / 禁止”红线可以同步到 rules。
- 重建冷热索引；不自动归档、不调用 `$archive-scan`。

## 8. 机械层边界

- 禁止引入语义自动分类器。
- 所有项目共用同一 memory 条目 schema、索引器和冷热策略。
- 机械层继续只处理字段、slug、状态、统计和索引一致性。
- 模块/topic 语义边界和知识提炼只约束 Agent 决策。

## 9. 流程图与事实源

在 memory 设计事实源中加入一张 Mermaid 流程图，完整覆盖：

```text
模块/topic 写入判断
-> summary 两种模式
-> active/completed
-> MEMORY.md / MEMORY_COLD.md
```

同一事实源同时提供：

- 所有项目统一的 memory 布局；
- 模块 memory / topic memory 判断标准；
- Topic 创建、对账、关闭和冷却规则；
- `$summary` 两种模式的文档更新范围。

## 10. 产品传播

- 产品层：Claude/Codex 模板、`bridgeforge` skill、`summary` skill。
- 元文档：本需求卡、memory 设计事实源、`doc/README.md`。
- 修改模板 hook 时必须同步对应 dogfood 镜像，并保持强制镜像契约。
- 计划版本：根 `0.81.0`、Claude `0.35.0`、Codex `0.49.0`。
- 根及双模板 CHANGELOG 使用 `[product]` 标记。
- 全部产品文案保持脱敏，不记录下游项目名、业务模块名、编号、绝对下游路径或业务术语。

## 11. 验收标准

1. Claude/Codex 模板明确且等价描述统一 schema、模块/topic 分工和 topic 生命周期。
2. 所有项目使用同一 schema；`init`、`update`、`adopt`、`switch` 和状态显示保持单行版本戳。
3. `$summary` 普通模式只更新当前 topic 或最多一个模块 memory，并重建索引。
4. `$summary 同意验收` 按当前交付范围执行 topic 关闭、知识提炼、TODO 结算、关联文档整理和冷热迁移。
5. Topic 改名后 `_stats.json.created_at` 保持，pinned 路径同步。
6. Topic 从 `active` 变为 `completed` 后从 `MEMORY.md` 进入 `MEMORY_COLD.md`。
7. Topic 目录 slug 与 frontmatter topic 不一致时，dry-run/apply 行为确定且双宿主等价。
8. 不存在第二套 schema、第二套索引器、规模配置或语义分类器。
9. 设计事实源包含完整流程图、统一布局、判断标准和管理规则。
10. 相关测试、双宿主一致性检查和独立审计通过。

## 12. 非目标与风险

### 非目标

- 不限制历史 topic 总数。
- 不自动删除、归档、合并、拆分或改名 topic。
- 不新增第二套 memory schema、规模配置或语义分类器。
- 不执行 `git add`、commit 或 push。

### 主要风险

- Topic 创建依赖 Agent 语义判断，流程图和门槛必须足够明确。
- 验收模式拥有较大文档写入面，必须严格限制在当前交付显式关联路径。
- Topic 改名必须同时维护统计记录和 pinned 路径，避免索引漂移。
- Claude/Codex 模板必须保持语义等价，避免双宿主行为分叉。

## 13. 实施与验证收据

- 已实施：所有项目统一采用单一完整 memory schema；未新增 profile、第二行版本戳、第二套
  schema/indexer 或语义分类器。
- 已实施：Claude/Codex memory 契约、`$summary` 双模式、设计事实源、版本和
  `[product]` CHANGELOG 同步完成。
- 已验证：定向回归 15 项通过；完整 harness 107 项通过；下游版本事实源 11 项通过；
  manifest、hook 镜像和 `git diff --check` 通过。
- 独立审计：无 Blocker、无 Major；现存 Minor 为双宿主契约等价和单行版本戳可增加更强的
  参数化防回归测试，不影响当前实现验收。
- Git 状态：未执行 `git add`、commit 或 push。
