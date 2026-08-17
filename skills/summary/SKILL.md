---
name: summary
description: 总结当前工作的阶段性进展，或在用户明确传入“同意验收”时结算当前交付；用户调用 /summary、$summary 或要求沉淀本轮成果时使用。
user_invocable: true
argument: 无参数，或精确参数“同意验收”
---

# summary — 沉淀当前项目成果

## 定位与边界

默认只整理和写入**当前项目**。无参数是阶段性记录，不代表验收；精确参数
`同意验收` 才表示用户明确验收当前交付。其他参数必须停止并展示这两种用法，禁止把参数
当自由文本重点提示。事故经过、实施流水、长示例和测试数字留在当前交付事实源。

## 模式硬闸

| 调用 | 模式 | 写入面 |
|---|---|---|
| `$summary` | 普通模式 | 一个当前主 memory + 自动索引 |
| `$summary 同意验收` | 验收模式 | 当前交付 memory、至多一个模块 memory、当前交付 TODO 与显式关联文档、必要 rule、自动索引 |

调用 `$summary` 本身禁止解释为用户验收。`同意验收` 参数已构成明确验收授权，不重复询问；
但已知 blocker、未满足验收条件或相互冲突的收据仍必须阻止关闭并列出原因。

## 项目 memory 写入路由（先宿主、再能力、后身份）

bridgeforge-codex 只支持 Codex，固定使用下列项目内路径：

| 宿主 | marker | writer | memory 根 | rebuild | lint |
|---|---|---|---|---|---|
| Codex | `.codex/.bridgeforge_codex_version` | `.codex/scripts/project_memory_writer.py` | `.codex/memory/` | `.codex/scripts/memory_rebuild_index.py` | `.codex/hooks/memory_lint.py` |

向 writer 交付最终正文时，必须先用当前宿主的非 shell 文件编辑工具创建项目 `.runtime/`
下的无 BOM UTF-8 临时内容文件，再把显式文件路径传给 `--content-file`；writer 调用结束后
必须删除临时文件，只有成功收据才允许继续。禁止传 `--content-file -`，也禁止用 stdin、
here-string、管道或命令行内嵌非 ASCII 正文中转。writer 拒绝 stdin、BOM 或非法 UTF-8
时必须停止，禁止改走直接写入。

对当前宿主按以下顺序处理：

1. 当前宿主 writer 存在时，必须把最终正文交给它；无论 marker 是否存在，都禁止直接 Write/Edit 当前宿主 memory
   正文或自动索引。writer 能力本身授权受限的项目内写入；检查收据中的 `host`、目标路径、
   SHA-256、`rebuild_command` 与索引结果。该 writer 已负责本次唯一一次索引重建；成功后
   禁止再次单独运行 `memory_rebuild_index.py`。
2. 当前宿主 writer 不存在但 marker 存在时，必须 **fail closed**：停止全部项目 memory
   写入，提示用户执行无参数 `$bridgeforge-codex`。禁止回退到用户级 memory，也禁止
   fallback、伪造或补写 marker。writer 与 marker 都不存在时，只能使用当前宿主已提供且
   能确认属于当前项目的既有 memory 机制；目标或写入能力不确定时停止对应写入。

项目写入失败、路径不确定或 writer 收据失败，都不得触发用户级回退。配置文件存在也不
等于 lifecycle hook 已在运行时生效；缺少 `/hooks` review/trust 或新会话 smoke 收据时，
必须写明 `runtime trust 未验证`。

## 输入与证据

- 当前对话中的已确认事实、决策及原因、遗留问题和用户反馈。
- `$ARGUMENTS`：只能为空或精确等于 `同意验收`，用于锁定本轮模式。
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
  `.codex/memory/topics/<topic>/summary.md`。
- 后续总结只更新该 `summary.md`；禁止按日期、单次对话、里程碑子项或子任务新增 topic
  memory 文件。
- `status` 只能是 `active`、`completed`、`superseded`。只有全部验收条件满足、用户已
  试用或明确验收、且没有未解决 blocker 时，才能标记 `completed`。代码、测试、审计或
  Git 收据不能代替用户验收。

### Topic 创建与管理门槛

- 所有项目共用同一 metadata schema、writer、索引器与冷热策略，并允许在满足门槛时写
  `topics/<topic>/summary.md`；禁止新增第二套实现或语义分类器。
- 只有用户已确认的事项同时具备独立目标、独立验收条件和可独立关闭生命周期时，才能在
  首次合法写入创建 topic。普通子任务、一次性排查、小修和里程碑子项不得建 topic。
- 创建前对账现有 active topic，禁止重复建档。状态不清楚时列出疑似已完成、暂停或被
  替代的候选并用一个问题请求裁决；禁止自动拆分、合并、改名、移动或关闭 topic。
- `completed` / `superseded` topic 保留原目录，由同一索引器进入 `MEMORY_COLD.md`；
  禁止物理归档或创建 memory 内部 archive。

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

## 普通模式：`$summary`

1. 回顾当前工作，分开记录已确认事实、推断、已完成、未验证和待验收事项；只读取已有
   收据，不重新运行测试、build、审计或 smoke。
2. 读取 `MEMORY.md` 与唯一候选正文并查重。当前工作属于已确认 topic 时只更新当前
   `topics/<topic>/summary.md` 且保持 `status: active`；否则最多更新一个最相关模块
   memory。目标不唯一时先问一个问题，确认前零写入。
3. 通过当前宿主 writer 写入唯一主 memory，并采用其内置的单次机械索引收据；禁止在
   writer 成功后再次运行索引器。普通模式禁止修改
   TODO、rules、需求、设计、计划或其他 docs；需要同步的内容只列候选。
4. 对账 active topic，但只列疑似状态漂移候选；禁止自动关闭。禁止为保存本次会话而新建
   topic，也禁止自动归档或调用 `$archive-scan`。

## 验收模式：`$summary 同意验收`

1. 先核对当前交付验收条件、blocker 与已有收据。任一 blocker、未满足条件或冲突收据
   都阻止 `completed`，保持现状并说明原因。
2. 更新当前唯一 topic；条件全部满足时改为 `status: completed`。若当前交付尚无 topic，
   只有同时满足 topic 创建门槛时才允许首次合法写入；否则只更新一个最相关模块 memory。
3. 只把长期稳定、未来会重复检索的知识提炼到至多一个最相关模块 memory；禁止整份复制
   topic 造成双重事实源。没有符合门槛的模块知识时不创建文件。
4. 只结算当前交付 TODO：完成项标记完成；验收阻塞项已在第 1 步阻止关闭；非阻塞后续
   事项仅列为新 topic 或 backlog 候选，等待用户决定。其他 topic 与项目级 TODO 不变。
5. 只整理当前 topic `related_paths` 或当前需求卡明确关联的需求、设计和计划文档。缺少必要
   事实源或路径映射不唯一时先问一个问题，禁止自行创建文档、扩大目录或顺带同步其他主题。
6. 只有长期稳定的“必须 / 禁止”红线可同步到 rule；按路径加载的 rule 必须带机器可解析
   `paths` frontmatter，并最多用一行 `Why` 指向 memory。事故、案例和方案比较禁止进 rule。
7. 写入完成后检查 writer 已生成的冷热索引收据；仅无 writer、无 marker 且既有项目机制
   未自带 rebuild 时，才显式运行一次同宿主索引器。`completed` / `superseded` topic 必须进入
   `MEMORY_COLD.md`；不移动 topic 目录、不自动归档、不调用 `$archive-scan`。

## 用户级 memory

默认零写入用户级 memory。判断某项知识可能跨项目复用时，只列“用户级 memory 候选”及
理由；只有用户明确批准后才能写入，并在收据中明确标为用户级。项目写入失败不得视为批准。

旧 memory 碎片只报告结构化候选，禁止自动合并、删除或移动；用户确认具体批次后交给独立整理任务。
已完成 delivery topic 或已解决 Bug 也只列归档候选，本 skill 不执行归档。

## 输出与收据

列出：

- 新增或更新的当前项目 memory 路径、`category` / `topic` / `status` 和一句话结论；使用
  writer 时附目标路径、SHA-256 与索引收据。
- 当前模式、修改的 TODO/AGENTS/docs 和索引；普通模式必须明确后三类均
  未修改，验收模式必须证明每个改动都属于当前交付显式范围。
- 旧碎片的结构化合并候选、delivery/Bug 归档候选及用户级 memory 候选；候选不等于已执行。
- 已有测试、审计、Git 和 runtime trust 收据；缺失项分别标记“未验证”或
  `runtime trust 未验证`。
- `git status` 与相关变更文件，并明确“未暂存、未 commit、未 push”；发布由
  `$git-sync` 负责。

## 禁止事项

- 禁止把推断、缺失收据或静态配置写成已验证事实。
- 禁止重新运行测试、build、审计或 runtime smoke。
- 禁止普通模式修改 TODO、rules、需求、设计、计划或其他 docs。
- 禁止验收模式扩张到当前交付未显式关联的文档、其他 topic 或项目级 TODO。
- 禁止为旧碎片自动合并、删除、移动或创建 memory 内部 archive 副本。
- 禁止自动调用 `$archive-scan`、执行 `git mv` 或更新归档索引。
- 禁止未经用户批准写用户级 memory，或在项目写入失败后回退到用户级 memory。
- 禁止自动 `git add`、commit 或 push。

$ARGUMENTS
