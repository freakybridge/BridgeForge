# `$summary` 将项目经验写入全局 memory 队列而非项目 memory

**状态**：source-fixed-downstream-recovery-pending
**日期**：2026-07-29  
**影响范围**：使用 BridgeForge Codex 骨架、同时存在用户级与项目级 memory 的下游项目。

## 现象

在 `D:\Quant\CausisRiskSuite` 中执行 `$summary` 后，证券黑名单爱建邮件主题变体的事故记录被写入：

```text
C:\Users\bridg\.codex\memories\extensions\ad_hoc\notes\2026-07-29-ajzq-email-subject-variant.md
```

而未更新项目受 Git 管理的：

```text
D:\Quant\CausisRiskSuite\.codex\memory\domain\security_blocklist_ajzq_email_source.md
```

该项目已存在同主题 memory，且本次内容应作为其增量经验合并。外部 note 不会自动进入项目 memory，也不会触发项目 `MEMORY.md` 索引重建。

## 已确认事实

1. BridgeForge Codex 模板将 `.codex/memory/` 定义为项目内、受 Git 管理的 memory；系统项目 memory 仅通过 junction 指向它。
2. `memory_rebuild_index.py` 只识别 `.codex/memory/**/*.md`；项目 PostToolUse hook 也只在该路径发生写入时重建 `MEMORY.md`。
3. 当前 `$summary` skill 使用“当前 agent memory”的表述，没有在 BridgeForge 下游项目中明确指定项目 memory 的优先级，也没有禁止回退到用户级 `extensions/ad_hoc/notes`。
4. 未发现从 `extensions/ad_hoc/notes` 自动消费、迁入项目 `.codex/memory/` 或重建项目索引的机制。

## 根因

这是 memory 目标解析的规约缺口：项目模板已经定义了项目 memory 的存储与索引机制，但 `$summary` 没有把“项目内调用时的唯一默认写入目标”写成可执行的硬约束。

当运行环境同时提供用户级 memory 更新队列时，agent 可将“当前 agent memory”解释为全局队列。该回退既不符合项目 summary 的预期，也没有后续同步链路，因此形成静默分叉。

## 2026-08-15 系统重构复核

- 源码：`summary` 已锁定当前宿主的 project memory writer，失败时禁止回退到用户级 `extensions/ad_hoc/notes`。
- 产品传播/dogfood：Codex template 与工厂当前骨架均使用项目内 `.codex/memory/`。
- fixture：writer、索引重建与零用户级写入已有自动化覆盖。
- 遗留/runtime：历史全局 note 是否迁回原项目仍需用户确认；真实新会话 trust 未复验，因此不标 fully closed。

本次直接写错路径是执行偏离；但骨架缺少明确目标、禁止回退和自动化验收，未能阻止这类偏离。

## 影响

- 项目经验不进入 Git，团队成员和新机器无法通过项目仓库获得该结论。
- 项目 `MEMORY.md` 保持旧内容，后续 agent 可能继续沿用过时的主题匹配约束。
- 全局队列与项目 memory 可产生重复或相互矛盾的记录。
- `$summary` 的交付状态容易被误报为“已沉淀到项目 memory”。

## 修复要求

1. 修改 `skills/summary/SKILL.md`：当当前工作目录属于已初始化的 BridgeForge 项目时，默认且只能写 `<repo>/.codex/memory/`；应优先合并已有同主题记录，而非重复新建。
2. 明确用户级 `extensions/ad_hoc/notes` 仅用于用户明确要求的跨项目 / 全局经验；它不得作为项目 `$summary` 的隐式回退路径。
3. 若项目 memory 不可写、junction 异常或分类无法确认，`$summary` 必须报告阻塞并停止对应写入；禁止改写为全局 note 以伪造完成。
4. 项目 memory 写入后必须运行或触发 `memory_rebuild_index.py`，并报告新增 / 更新文件及索引结果。
5. 为该规则增加可执行的 harness 校验：覆盖“项目 summary 写入项目 memory”“全局 memory 仅显式请求时写入”“项目 memory 写入失败不回退”三条路径。

## 验收标准

1. 在 fixture 下游项目调用 `$summary`，新增或更新的 `.md` 位于 `<repo>/.codex/memory/`，不产生 `extensions/ad_hoc/notes` 文件。
2. 同次执行后 `<repo>/.codex/memory/MEMORY.md` 包含该记录的索引条目。
3. 已存在相同 topic 的 memory 时，summary 更新该记录或按明确规则创建关联记录，不产生无依据的重复项。
4. 模拟项目 memory 拒绝写入时，summary 明确失败；全局 memory 目录保持未写入。
5. BridgeForge 的 `$summary` 文本约束与下游复制后的 skill 保持一致，并通过既有 harness / mirror 校验。

## 本次遗留迁移

`C:\Users\bridg\.codex\memories\extensions\ad_hoc\notes\2026-07-29-ajzq-email-subject-variant.md` 已存在。该文件不应被自动删除或静默搬迁；修复落地后，应在用户确认下将其中经过复核的项目经验合并到 CausisRiskSuite 的对应 project memory。
