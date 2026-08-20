---
status: implemented
next: user-trial-and-acceptance
scale: L
budget: 300_minutes_100k_tokens_unmeasured_3_sequential_agents_2_validation_rounds
source: user-confirmed-2026-08-20
---

# BridgeForgeCodex 1.4.28 全仓清理与干净基线需求

## 原始需求摘要

用户要求从 1.4.28 开始清理前几个版本为历史兼容累积的冗余代码，解决骨架代码与
`managed-skeleton.json` 远超预期的膨胀。旧版下游不再逐版本适配，而是直接安装最新骨架，保留经确认
的项目 rules、项目 hooks、根 `AGENTS.md` 项目区、项目 memory 与项目 Skills。1.4.28+ 恢复严格、
统一且不依赖全版本历史的常规检查，并把 1.4.28 作为长期最干净的基线。

调用来源：用户直接调用 `$confirm`，经单题访谈逐项确认。

## 目标

- 将 1.4.28 建成新的、最干净的长期基线。
- 全仓删除唯一用途是兼容 `<1.4.28` 的代码、数据、生成逻辑和测试。
- 保留当前仍在使用的 Skills、Native Memory、hooks、事务安全和用户入口，只移除其旧谱系分支。
- 旧项目不再逐版本迁移，统一使用白名单确认后的破坏性重建安装。
- 1.4.28+ 使用项目本地的当前版本单份基线，工厂不再累计全部历史版本内容。
- Planner、Apply、`$git-sync` 与 pre-commit 共用一个 current-baseline 检查器。
- 显著减少运行时代码和合同体积，并保证后续发布次数不再推动合同持续增长。

## 不做

- 不删除当前仍在使用的功能，不以减少行数为由改变现行用户行为。
- 不重写远端 Git 历史；1.4.27 保持正式有效版本。
- 不在本次产品开发中重装 CBA、Causis、主 Stratus 或 M2 四个真实项目。
- 不为 `<1.4.28` 保留逐版本增量迁移、dormant legacy 模块或历史 hash 数据库。
- 不允许 1.4.28+ 常规 update 自动吸收公共资产漂移，也不提供确认后强制覆盖。
- 不通过压缩 JSON、合并超长行或降低可读性伪造代码减量。
- 不为旧项目破坏性重装生成持久化 before 恢复包。

## 任务规模与预算

- 规模：L。
- 判定依据：全仓架构收缩、旧项目迁移范式更换、用户级与项目级运行链同时受影响，并要求临时下游与
  独立审计。
- 时间上限：300 分钟。
- Token 上限：约 100k，平台无可靠计量器，标记为未实测。
- 子 agent：最多 3 个，严格顺序使用：1 个只读调研、1 个实现、1 个最终独立审计；禁止并发修改共享文件。
- 完整验证：最多 2 轮。
- 超预算停止点：预计超过任一预算，或当前功能无法在删除旧兼容层后保持时，必须停止并由用户选择扩大
  预算或缩小范围。

## 已核实事实

- 远端 `main` 当前 HEAD 为提交 `c9b24d8`，其产品版本 1.4.27 已正式推送并由用户确认继续有效。
- 当前未提交工作区包含将 VERSION/CHANGELOG 口径退回 1.4.26 的修改，以及 CBA 1.4.26 白名单安装
  收据；实施前必须恢复 1.4.27 正式口径，同时逐项保留 CBA 验收事实和其他现有修改，禁止整批恢复。
- 当前 `scripts/bridgeforge_codex_project_sync.py` 为 5361 行。
- 当前 `templates/scripts/version_release.py` 为 3855 行。
- 当前 `templates/managed-skeleton.json` 为 7163 行。
- `scripts/tests/test_bridgeforge_codex_project_sync.py` 与
  `scripts/tests/test_git_sync_version_release.py` 当前合计 5934 行。
- 已识别主要膨胀来源包括 historical hash、schema-v1、legacy region、retirement、显式 adaptation
  proof、before snapshot 及其专用回归。
- CBA 已实证“明确放弃旧谱系、冻结项目白名单、直接安装 canonical 骨架、封存新基线”可行，但该
  现场仍待独立审计，不能直接替代 1.4.28 产品验收。

## 已确认业务规则

### 旧项目版本分流

- 已识别项目的骨架戳 `<1.4.28` 时，自动进入一次性破坏性重装。
- 骨架戳 `>=1.4.28` 时，进入常规 current-baseline 更新。
- 缺戳、双戳或无法识别的项目必须零写停止，禁止擅自按旧项目重装。

### 旧项目确认次数特例

- 先由独立 agent 只读审计旧项目资产，对每个候选给出保留/删除建议和证据。
- 用户在一轮汇总清单中逐项确认项目 rules、项目 hooks 和根 `AGENTS.md` 项目区。
- 该白名单确认是“更新最多一次普通确认”的额外特例。
- 白名单确认后仍允许一次正常更新风险确认，总计最多两轮确认。

### 破坏性重建

- 旧项目使用最新 Template 生成全新公共 `.codex`，再放回已确认保留的项目资产。
- 未进入保留范围的旧骨架内容不得进入新目录。
- 不维护历史旧文件名清单，不以覆盖同名文件的方式留下退役资产。
- 不保留长期 before 包；安装期间必须使用临时事务副本，失败立即恢复，成功立即删除临时副本。
- 禁止任一可捕获失败留下半新半旧状态。

### 1.4.28+ current baseline

- `.codex/managed-skeleton.json` 是 Git 跟踪的当前版本单份基线。
- 该文件只保存当前安装版本的公共资产、ownership 和 hash，禁止保存历史版本集合。
- 公共资产与本地基线一致时才允许常规更新。
- 公共资产漂移、基线缺失、基线损坏或身份不一致时必须整轮零写停止。
- 有效项目定制必须迁入项目 rules、项目 hooks、根 `AGENTS.md` 项目区、项目 memory 或项目 Skills。
- 常规 update 禁止自动吸收公共资产漂移，禁止通过一次风险确认强制覆盖漂移。

### 统一检查入口

- Planner、Apply、`$git-sync` 与 pre-commit 必须直接共用同一个 current-baseline 检查器。
- 禁止各入口维护近似实现或不同放行标准。
- Apply 必须复核 Planner 的真实基线与 fingerprint；写后必须复核真实磁盘状态并最后写版本戳。

## 数据与资产映射

| 旧项目资产 | 1.4.28 处置 |
|---|---|
| 根 `AGENTS.md` 项目区 | 逐字保留 |
| 项目 rules | 独立审计后由用户逐项确认 |
| 项目 hooks 及项目扩展 | 保留业务正文，按 1.4.28 检查注册与 runtime |
| 项目 memory 正文与有效配置 | 保留；允许重建派生索引 |
| 项目 Skills 业务正文 | 保留；允许机械补齐 frontmatter 与 routing |
| 公共 scripts、agents、config、hooks | 使用最新 Template 重建 |
| 未确认的旧骨架内容 | 删除，不保留历史兼容 |
| 旧 managed contract | 替换为 1.4.28 current-only baseline |
| 旧版本戳 | 在全部验证通过后最后替换为 1.4.28 戳 |

### 自动修复边界

- 允许重建 `MEMORY.md`、`MEMORY_COLD.md` 等派生索引。
- 允许补齐 Skill 标准 frontmatter 并同步项目 Skill routing。
- 禁止修改 memory 正文语义。
- 禁止修改 Skill 业务流程、参数或外部副作用。
- 语义冲突、未知格式或无法证明的项目资产必须停止，不得猜测修复。

## 拟修改范围

核心范围包括但不限于：

- `scripts/bridgeforge_codex_project_sync.py`
- `templates/scripts/version_release.py` 及 `.codex/` dogfood 镜像
- `templates/managed-skeleton.json` 及 `.codex/` dogfood 镜像
- `scripts/rebuild_shared_skill_manifest.py`
- `templates/scripts/codex_git_sync.py` 及 dogfood 镜像
- hooks ownership/merge 与相关用户级 lifecycle/setup/repair 代码
- 用户级 Skills 分发与兼容入口
- Native Memory 中明确依赖旧骨架谱系的分支
- 对应模板、manifest、fixture、测试、Skill 流程、VERSION、CHANGELOG 与文档

实施前必须先做全仓兼容入口审计并形成删除映射；不得因本清单未写出某个文件名而漏掉真实 legacy 分支，
也不得把名称含 legacy/compat 但服务当前功能的代码直接删除。

## 量化验收

- `managed-skeleton.json` 相比当前 7163 行至少减少 70%。
- `project_sync.py + version_release.py` 相比当前合计 9216 行至少减少 25%。
- 连续增加发布版本时，合同体积不得随历史版本数量增长。
- Template 与 dogfood 镜像必须一致。
- 产品运行时代码不得保留唯一用途是服务 `<1.4.28` 的历史映射、旧 schema、retirement 或
  adaptation proof。
- 禁止通过压缩格式、超长行或降低可读性达到数量闸。

## 功能验收

- `<1.4.28` 已识别项目能进入破坏性重建；缺戳、双戳和无法识别项目零写阻断。
- 独立审计与用户白名单确认能精确保留项目 rules、hooks、AGENTS 项目区、memory 和 Skills。
- memory/Skill 只发生批准的机械兼容，业务正文保持。
- 临时事务在失败时恢复全部本轮写入，成功后不保留 before 包。
- 1.4.28+ 项目能按 current-only baseline 正常更新。
- 公共资产漂移、基线缺失或损坏时，Planner、Apply、`$git-sync`、pre-commit 一致阻断。
- 版本戳只在所有验证通过后最后写入；终态 no-op replan 全零。
- 当前仍在使用的 Skills、Native Memory、hooks 和用户入口保持功能等价。

## 验证方式

- 定向单元测试。
- 完整 factory `unittest`。
- downstream fixture。
- manifest、mirror、project structure、instruction source、Skill metadata、encoding 和 `git diff --check`。
- 临时旧版下游执行一次白名单破坏性重建。
- 临时 1.4.28+ 下游执行常规升级、漂移阻断和损坏基线阻断。
- 自动验证量化行数与“发布版本增加但合同不增长”。
- 一个独立 agent 完成最终审计。
- 最多两轮完整验证；修复后重新执行同一完整验收集才计入第二轮。

## 真实下游边界

- 本需求只交付 1.4.28 产品、fixture、临时下游和独立审计。
- CBA、Causis、主 Stratus 和 M2 不在本交付中执行重装。
- 产品验收后，每个真实项目分别重新执行独立审计、白名单逐项确认和一次风险确认。
- 各真实项目之间保持 Git 与 Native Memory 串行约束。

## 合理假设与风险

- “清理得越干净越好”不授权删除当前仍在使用的功能。
- 当前 dirty 工作区混有 1.4.27/1.4.26 口径调整和 CBA 收据；实施前必须精确拆分并保留用户现有修改。
- 全仓审计可能发现当前功能仍依赖某段旧结构；无法在保持现行行为时删除必须停止重新确认。
- 旧项目成功破坏性重装后，旧骨架不能通过安装器恢复；用户只保留 Git 自身能力和另行存在的外部备份。
- 量化目标若与完整现行功能冲突，优先保功能并停止重新确认，禁止为达标删除有效能力。
- 当前 CBA 收据记录的验证不能替代 1.4.28 新架构的 fixture、临时下游和独立审计。

## 自动化边界

- 本需求确认不授权修改四个真实下游项目。
- 不授权 commit、push、force push、reset、clean、stash 或历史重写。
- 破坏性重装只能在本卡定义的白名单确认与风险确认后执行。
- 任何预算升档、现行功能删除、真实下游写入或回滚边界变化都必须重新取得用户确认。

## 后续交接目标

- 需求卡落盘后由用户选择 `$develop`、`$debate` 或 `$collab`。
- `$develop` 负责实现、验证、试用和独立审计闭环。
- 如先进入 `$debate`，只讨论 current-only baseline 与全仓删除边界，不修改代码。
- 如进入 `$collab`，必须先按文件 ownership 切分且不得并发修改共享 manifest/Template/dogfood 对。

## 实施记录占位

- 实施状态：已进入 `$develop`，尚未修改产品代码。
- 预算调整：用户于 2026-08-20 确认将 agent 预算从 1 个独立审计 agent 扩大为最多 3 个顺序 agent，
  以满足 L 级只读调研、实现和最终独立审计的角色独立性；时间、token 与验证轮次预算不变。
- 只读 discovery：已完成。确认核心删除面为历史合同字段、14 个 retirement 资产、schema-v1、
  historical projection/hash、显式 adaptation proof/receipt、旧 stamp 增量迁移、`.agents` 布局迁移和
  Native Memory legacy consent/handler 分支；现行 ownership、`.venv`、事务回滚、validators、
  stamp-last、当前用户级 Skill 与 Native Memory 功能必须保留。
- 实现级保守解释：项目 Skill 只允许修复可确定性推导的现有 frontmatter；缺失 `description` 或 routing
  语义时阻断，禁止编造。项目 memory 取消自动 organize/移动正文，只允许只读校验与派生索引重建。
- current-only 单一来源：新增 Template/dogfood 镜像检查器，供 Planner、Apply、`$git-sync` 与
  pre-commit 直接复用；旧项目重建保持独立路径。
- 实际修改：发布 1.4.28 schema 3 current-only 合同；新增共用 `current_baseline.py`、Git HEAD
  前态锚点与 worktree/index 双视图检查；重写 project sync 为 current update + 旧项目 fresh canonical
  白名单重建；保留事务回滚、config health、文本卫生、业务版本与 Native Memory 当前功能。
- 删除映射：删除 historical/schema-v1/retirement/adaptation proof/before snapshot、旧 `.agents` 布局
  迁移器、兼容 hooks merge/precommit merge、rule wrapper 及其历史专用测试；无活跃源码命中这些机制。
- 白名单闭合：旧项目只允许用户选择的 AGENTS 项目区、第三方 hook 注册、project hook 文件与
  依赖、pre-commit project extension、项目 rules 回灌；memory/Skills 自动保留并按当前规则检查，
  其他旧内容从 fresh canonical 终态删除。
- Template/dogfood 传播：current checker、version release、git-sync、hooks ownership、config health、
  Skill metadata、pre-commit 与 schema 3 合同均完成 Template/dogfood 镜像；manifest `--check` 通过。
- 活跃说明同步：README、INSTALL、项目同步架构、上游同步与反向回灌 playbook 已改为 1.4.28
  current-only / destructive rebuild 口径；1.4.27 CHANGELOG 正式条目逐字保留。
- 预算使用与停止点：顺序使用 discovery、implementation、review-auditor 3 个 agent；执行 2 轮完整
  验证，未扩大真实下游范围，未触发时间/token 停止点。

## 验证记录占位

- 定向测试：current baseline/project sync/release/Skill metadata 共 33 项通过；覆盖 current
  projection、HEAD anchor、worktree/index、精确白名单、未知 managed hook、duplicate JSON、
  schema 损坏、memory 派生回滚、原生 manifest/lock 版本同步。
- 完整 factory 测试：第 2 轮
  `.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`，212 项，
  93.896 秒，`OK`。
- downstream fixture：真实临时项目 `.venv` + project-sync CLI planner/apply；3/3 通过。
- 临时旧版重装：合法 1.4.27 旧戳经确认白名单与风险参数重建成功；项目 hook/Skill 保留，旧戳
  删除，current baseline 通过，终态 CLI replan no-op。
- 临时 1.4.28+ 更新：init/current replan no-op 通过；公共 hook 漂移时 CLI 返回阻断且目标字节
  不变。
- 数量闸与无增长闸：合同 692 行，较 7163 减少 90.34%；project sync 1924 行 + version release
  466 行 = 2390 行，较 9216 减少 74.07%；1.4.28 -> 1.4.29 -> 1.4.30 合同字段与行数恒定测试通过。
- 发布硬闸：manifest `--check`、current baseline 1.4.28、instruction source、project structure、
  mirror drift、Skill metadata、encoding 与 `git diff --check` 均通过；project structure 仅报告既有
  archive advisory。
- 独立审计：review-auditor 完成；发现的 baseline 自证、projection skip、白名单泄漏、validators、
  Skill 检查、回滚、文档与测试证据问题已修复并纳入第 2 轮验证。
- 真实下游：不在本需求交付范围。
