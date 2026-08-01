---
name: summary
description: 总结当前对话的关键决策、稳定经验、完成项与遗留问题，默认归入当前项目的规范 memory，并按价值同步 rules 或 docs；用户调用 /summary、$summary 或要求沉淀本轮成果时使用。
user_invocable: true
argument: 可选的本次总结重点提示
model: sonnet
---

# summary — 沉淀当前项目成果

## 定位与边界

默认只整理和写入**当前项目**。保留值得跨对话重复检索的当前有效结论；事故经过、实施
流水、长示例和测试数字留在 delivery 或 Bug 文档。会话只把 `MEMORY.md` 当作热区，其他
正文按需读取。命中旧碎片整理、rule-memory 对账或归档候选时，只读取
[`references/deep-steps.md`](references/deep-steps.md) 的对应章节。

## 项目 memory 写入路由（先宿主、再能力、后身份）

先确定当前执行 `$summary` 的宿主，再只检查该宿主一行；禁止因为另一宿主的 writer 或
marker 存在而切换路径：

| 当前宿主 | marker | writer | memory 根 | rebuild | lint |
|---|---|---|---|---|---|
| Codex | `.codex/.bridgeforge_version` | `.codex/scripts/project_memory_writer.py` | `.codex/memory/` | `.codex/scripts/memory_rebuild_index.py` | `.codex/hooks/memory_lint.py` |
| Claude | `.claude/.bridgeforge_version` | `.claude/scripts/project_memory_writer.py` | `.claude/memory/` | `.claude/scripts/memory_rebuild_index.py` | `.claude/hooks/memory_lint.py` |

对当前宿主按以下顺序处理：

1. 当前宿主 writer 存在时，必须把最终正文交给它；无论当前宿主 marker 是否存在，都禁止
   直接 Write/Edit 当前宿主 memory 正文或自动索引。writer 能力本身授权受限的项目内
   写入；检查收据中的 `host`、目标路径、SHA-256 与索引结果。
2. 当前宿主 writer 不存在但 marker 存在时，必须 **fail closed**：停止全部项目 memory
   写入，提示用户执行无参数 `/bridgeforge`。禁止回退到用户级 memory，也禁止跨宿主
   fallback、伪造或补写 marker。
3. 当前宿主的 writer 与 marker 都不存在时，只能使用该宿主已经提供、且能确认目标属于
   当前项目的 memory 机制；无法确认项目目标、分类、路径或可写性时，标记“未验证”并
   停止对应写入。另一宿主的 writer 不构成当前宿主能力。

项目写入失败、路径不确定或 writer 收据失败，都不得触发用户级回退。配置文件存在也不
等于 lifecycle hook 已在运行时生效；缺少 `/hooks` review/trust 或新会话 smoke 收据时，
必须写明 `runtime trust 未验证`。

## 输入与证据

- 当前对话中的已确认事实、决策及原因、遗留问题和用户反馈。
- `$ARGUMENTS`：用户指定的总结重点。
- 当前项目已有 memory、rules、设计/delivery/Bug 文档及索引。
- 本轮**已经产生**的测试、审计和 Git 收据；只读这些收据，不重新运行测试、build、审计
  或 smoke。允许读取实际 `git status` 和相关 diff 以报告工作树状态。

缺少收据时必须标记“未验证”，禁止用代码存在、静态配置、测试缺失或推断替代成功证据。

## Memory 颗粒度门槛

### 分类与 metadata

- 通用长期知识的 `category` 只能是 `architecture`、`engineering`、`domain`、
  `operations`，目标是当前项目 memory 根下的同名分类目录。
- delivery topic 的 `category` 必须是 `topic`，并写入 `topic: <exact-slug>`；目标是当前
  项目 memory 根下的 `topics/<exact-slug>/summary.md`。
- `status` 只能是 `active`、`completed`、`superseded`，缺省为 `active`；`description`
  必填，`kind`、`tags`、`related_paths` 按需填写。
- 分类或 metadata 不能确认时，只展示候选并用一个单题请求用户裁决；确认前禁止写入、
  创建目录或移动文件。

### Delivery topic

- 每个 topic 只维护一个规范文件：
  `<project-memory-root>/topics/<topic>/summary.md`。Codex 对应
  `.codex/memory/topics/<topic>/summary.md`，Claude 对应
  `.claude/memory/topics/<topic>/summary.md`。
- 后续总结只更新该 `summary.md`；禁止按日期、单次对话、里程碑子项或子任务新增 topic
  memory 文件。
- `status` 只能是 `active`、`completed`、`superseded`。只有全部验收条件满足、用户已
  试用或明确验收、且没有未解决 blocker 时，才能标记 `completed`。代码、测试、审计或
  Git 收据不能代替用户验收。

### 通用 memory：新的稳定问题门槛

一个通用 memory 必须回答**一个长期稳定、未来会重复检索的工程问题**。写入前先检索并
更新已有规范 memory；只有确实出现新的稳定问题时才能新建。

- 正例：“网关重连时怎样恢复订阅并避免重复订单？”、“项目身份与 writer 的选择规则是
  什么？”、“交互流程在哪些状态必须停下来请求确认？”
- 反例：“今天的断线事故经过”、“修复某一行参数的小补丁”、“本次 37 项测试数字”、
  “某个子任务的实施流水”或一条尚未复现的孤立经验。这些不得各自新建通用 memory，
  应留在对应 delivery 或 Bug 文档。
- 规范正文只保留当前有效结论、原因、适用范围、例外，以及权威代码/设计文档链接。

不能确定它是否是新问题、是否长期稳定、应更新哪个规范文件，或新旧结论是否冲突时，
必须停止写入并用一个单题请求用户裁决；禁止为了完成总结而新建文件。

## 核心流程

1. 回顾本轮，分开记录已确认事实、推断、已完成、未验证和待用户验收事项。
2. 执行 writer 能力检测；读取项目 `MEMORY.md` 与候选同主题正文，先查重再确定唯一目标。
3. 按既有四类通用知识或 `topic` 完成首次归类；对 delivery topic 更新唯一
   `topics/<topic>/summary.md`，对通用知识执行“新的稳定问题”门槛并优先更新已有规范
   memory。
4. 高置信、非破坏性的当前项目规范 memory 更新可自动执行；目标、分类、结论或冲突任一
   不确定时停止并询问。首次实际写入时才创建目标目录，禁止预建空目录。
5. 只有长期稳定的“必须 / 禁止”红线才能进入 rule；事故与案例留在 memory，方案比较与
   长示例留在 doc。按路径加载的 rule 必须有机器可解析的 `paths` frontmatter，最多用
   一行 `Why` 指向支撑 memory。高置信、非破坏且确有必要的 rule 更新自动执行；分类或
   约束强度不确定时停止并询问。
6. 发现旧 memory 碎片时，只读取深档的“旧碎片候选”节并输出结构化候选簇。`$summary`
   禁止自动合并、删除或移动旧碎片；用户确认具体批次后，交给独立整理任务。
7. 发现已完成 delivery topic 或已解决 Bug 时，只读取深档的“归档候选”节列清单，并
   提示用户另行调用 `$archive-scan`。本 skill 不调用它、不执行 `git mv`、不更新归档索引。
8. 高置信、非破坏且确有必要的 docs 同步自动执行；映射或归属不确定时停止并询问。读取
   实际 `git status` 和相关变更文件，但不发布。

## 用户级 memory

默认零写入用户级 memory。判断某项知识可能跨项目复用时，只列“用户级 memory 候选”及
理由；只有用户明确批准后才能写入，并在收据中明确标为用户级。项目写入失败不得视为批准。

## 输出与收据

列出：

- 新增或更新的当前项目 memory 路径、`category` / `topic` / `status` 和一句话结论；使用
  writer 时附目标路径、SHA-256 与索引收据。
- 修改的 rules、docs 和索引；未修改也明确说明。
- 旧碎片的结构化合并候选、delivery/Bug 归档候选及用户级 memory 候选；候选不等于已执行。
- 已有测试、审计、Git 和 runtime trust 收据；缺失项分别标记“未验证”或
  `runtime trust 未验证`。
- `git status` 与相关变更文件，并明确“未暂存、未 commit、未 push”；发布由
  `$git-sync` 负责。

## 禁止事项

- 禁止把推断、缺失收据或静态配置写成已验证事实。
- 禁止重新运行测试、build、审计或 runtime smoke。
- 禁止为旧碎片自动合并、删除、移动或创建 memory 内部 archive 副本。
- 禁止自动调用 `$archive-scan`、执行 `git mv` 或更新归档索引。
- 禁止未经用户批准写用户级 memory，或在项目写入失败后回退到用户级 memory。
- 禁止自动 `git add`、commit 或 push。

$ARGUMENTS
