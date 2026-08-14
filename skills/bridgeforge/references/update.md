# Update 更新模式操作手册

仅当根 `SKILL.md` 检测到 `$PROJECT_AGENT_DIR/.bridgeforge_version` 时读取。执行前必须完成 Windows 平台硬闸、无参数共享 updater、工厂自检、Python 3.11+ preflight、agent 分流和当前项目遗留 `.agents/` 检查；本手册只使用已锁定的 `$HOOK_PYTHON`。

机械半场（从已安装 command bundle 读取模板、diff、分类、呈现）由本 skill 执行；判断半场（入口/rules 选择性吸收）必须交给用户。详细边界依据是 `doc/0_architecture/design/sync-from-upstream-playbook.md`。禁止在本模式执行 `git pull` / `git clone`，也禁止从 `~/.bridgeforge`、`~/.agents` 或本地工作副本加载模板。

## U1. 计算产品增量

1. 读取项目 `$PROJECT_AGENT_DIR/.bridgeforge_version` 与 `$BRIDGEFORGE_HOME/VERSION`。
2. 判断“已是最新”前必须先执行 U2.1 的上游规范 memory dry-run；禁止仅凭版本戳
   相等跳过审计。只有该命令 exit 0、文件无差异、当前宿主 hook 承载面与 memory
   加载机制正确时，才报告“已是最新（vX.Y.Z）”并退出。审计非零、承载面或 memory
   仍待维护时，即使版本相等也必须继续 U2 的 B/D 类处理。
3. 不等：从上游 `CHANGELOG.md` 提取 `(下游版本, 上游版本]` 内全部 `[product]` 条目；过滤 `[repo]` / `[meta]`。
4. 区间没有 `[product]` 且 hook 承载面/memory 无待维护状态：不要跑全量
   diff；报告本次无下游产品变更，执行 U4 更新版本戳后退出。仍待迁移时继续
   B/D 类处理。

## U2. 按类型 diff

先给总览，再逐项处理：

### U2.0 强制退役：`stall_warning.py`

在 A-F 分类、diff 和任何用户确认前，先对项目中已存在的两套宿主目录执行
以下强制退役；缺失时静默 no-op：

1. 无条件删除 `.codex/hooks/stall_warning.py` 与
   `.claude/hooks/stall_warning.py`。不得比较 hash、展示 diff、保留备份或因
   下游人工修改而跳过。
2. 分别从 `.codex/settings.json` 和 `.claude/settings.json` 的
   `UserPromptSubmit` hook 列表移除引用对应 `stall_warning.py` 的受管注册；
   保留同一事件的所有其他 hook 与下游自定义配置。
3. 该退役不写入 host map 的资产所有权，也不等待 A/B 类覆盖确认；它是用户已确认
   的安全策略变更。收据须逐宿主报告脚本和注册各自的“已移除 / 原本不存在”。

| 类 | 文件 | 策略 |
|---|---|---|
| A | hooks、scripts；Codex `agents/*.toml`、`skill-routing.json` | 下游与旧模板一致时提议覆盖并确认；被改过时展示 diff，禁止无脑覆盖；Codex agents 与 routing 必须配套检查。BridgeForge 不管理模型或思考强度。用户级 skills 已由共享 updater 处理，不属于项目模板 diff |
| B | settings.json；Codex `hooks.json` / `config.toml`；`.githooks/pre-commit` | merge 不覆盖；Codex 先把 settings 旧 `hooks` 的第三方项迁入 `.codex/hooks.json`，再删除整个旧块；按 `command` 身份增补/替换全部受管 dispatcher，保留第三方事件、handler 与其他配置。受管内容漂移必须展示 diff 并确认；config `[hooks]` 直接阻断。Claude 注册方式不变。保留下游 permissions、additionalDirectories。项目模型选择保持用户或 Codex 平台默认 |
| C | rules、入口文件 | 只 diff；按通用增量/业务补充/上游脱敏减弱三类让用户逐段决定 |
| D | memory | 展示分类计划；Codex 校验 context/router/usage 且不建 junction；Claude junction 迁移继续按确认后 apply |
| E | `.gitignore` | 按 init 手册的 BridgeForge 机制块幂等补缺，不删项目项 |
| F | `doc/` 布局 | 检测 `doc/README.md:delivery_layout` 和旧目录；展示迁移清单，用户确认后才 `git mv`，不得静默混用 |

Codex B 类必须用 command bundle 内的确定性工具先只读输出完整 diff；只有用户确认后
才 apply，禁止手工拼接 JSON 或把 `--confirmed` 当成自动授权：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "templates\codex\scripts\hooks_merge.py") `
  --project-root . --template-hooks (Join-Path $BRIDGEFORGE_HOME "templates\codex\hooks.json")
# 用户确认完整 diff 后才追加：--apply --confirmed
```

`.githooks/pre-commit` 的 B 类 merge 必须改用当前宿主模板内的
`scripts/precommit_merge.py`。它只替换 `BRIDGEFORGE_MANAGED` 区块，并输出
`PROJECT_EXTENSION` 的 SHA-256 作为保留收据。仅当无标记旧 hook 同时含历史
`Step 2: VERSION bump`、`scripts/bump_version.py`、末尾 `git add VERSION`，且此前缀
SHA-256 逐字匹配冻结的 0.81 Codex / Claude 模板时，允许一次性转换为边界格式并逐字保留该段；其余缺标记、
前缀改动、损坏标记、区块外项目代码或 apply 前漂移都必须 exit 2 且零写入。严禁把模板
pre-commit 整份复制到下游：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "templates\$TEMPLATE_AGENT\scripts\precommit_merge.py") `
  --project-root . --template-precommit (Join-Path $BRIDGEFORGE_HOME "templates\$TEMPLATE_AGENT\.githooks\pre-commit")
# 用户确认完整 diff 后才追加：--apply --confirmed
```

类 C 判据：

- 上游新增通用增量：建议吸收。
- 下游业务专属补充：保留。
- 上游脱敏版比下游弱：保留下游。

任何类 C 修改都要展示具体 diff 并等用户决定。禁止跨多个项目批量同步。

### U2.1 Memory 迁移计划

每次更新既有项目都必须先调用上游 bundle 内的规范审计器；版本戳相等也不得跳过：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "templates\$TEMPLATE_AGENT\hooks\memory_lint.py") `
  --organize --project-root . --host $CURRENT_HOST
```

该命令递归盘点当前 agent 的 `memory/**/*.md`，跳过自动生成的 `MEMORY.md`、
`MEMORY_COLD.md`，只输出完整计划，不写 frontmatter、不创建目录、不移动文件：

1. 对合法 `category` 直接给出目标：`architecture`、`engineering`、
   `domain`、`operations` 进入 `memory/<category>/`；`topic` 必须同时有
   `topic: <exact-slug>`，且唯一规范文件是
   `memory/topics/<exact-slug>/summary.md`。
2. 缺失或非法 `category` 时展示候选。低置信项必须由用户逐项选择
   `category`；选择 `topic` 时还必须确认 exact slug。未决项阻断 apply。
3. 每个 memory 必须有非空单行 `description`。计划必须列出每个文件的原路径、
   目标路径、拟补写的 `category` / `topic` / `status` / `description`，以及会新建的
   非空目录；嵌套的 `memory/.codex/memory/` 或 `memory/.claude/memory/`、非法 slug、
   同一 topic 多文件竞争 `summary.md`、目标已存在均必须明确报告并阻断 apply。
4. dry-run 非零时必须把完整输出展示给用户。只有用户明确确认整份计划后，才允许
   使用同一上游审计器附加 `--apply --confirmed`，并为需人工判断的单文件附加明确的
   `--category` / `--topic` / `--status` / `--description`；补写 metadata、创建实际需要
   的目录、移动文件后再重建索引。禁止预建未使用的分类目录，禁止把
   `--confirmed` 当作未取得的用户确认。
5. `status` 只允许 `active`、`completed`、`superseded`，缺省按
   `active`。`completed` / `superseded` topic 仍保留在原
   `memory/topics/<topic>/`，只由索引降温；禁止创建或使用
   `memory/_archive/`。
6. 原始需求、讨论、计划和验收仍保留在 `doc/1_delivery/<topic>/`；
   topic memory 只提供可独立阅读的恢复摘要，禁止用它替代或删除 delivery 证据。

用户拒绝或未确认迁移时，保持 memory 逐字不变并继续报告为未迁移；不得把
“展示了计划”写成“已迁移”。

### U2.2 项目 memory 运行机制

只处理当前宿主：

| 宿主 | 系统 memory | 项目唯一事实源 | SessionStart 承载 |
|---|---|---|---|
| Codex | 无系统 junction；与原生 memories 分离 | `.codex/memory/` | `.codex/hooks.json` 的 context/router |
| Claude Code | `~/.claude/projects/<project-hash>/memory/` | `.claude/memory/` | `.claude/settings.json` |

Codex 更新必须退役 `memory_junction_check.py`，安装 index/context/router/search/usage，
并验证 6000 字符预算、3-5 候选和成功 Read 后 used。禁止读取或迁移旧
`~/.codex/projects/**`；其清理由用户另行授权。

以下迁移仅适用于 Claude Code。先只读盘点并展示状态：

1. 正确 junction 必须解析并验证最终目标等于当前项目 memory，然后 no-op。
2. 系统 memory 不存在且项目 memory 存在时，可直接建 junction并验证。
3. 系统 memory 是实目录时，计划必须逐文件列出：仅系统存在则复制；两侧同路径
   且内容相同则跳过；同路径内容不同则标记冲突并阻断整次迁移。路径异常、错误
   junction、断裂 junction或其他无法归类状态同样阻断且零写入。
4. 计划必须明确最后会删除系统 memory 实目录、不会创建备份，并列出建链与验证
   动作。只有用户明确确认整份计划后才允许 apply。
5. apply 时只复制系统独有文件并跳过同内容文件；复制后必须重新校验项目 memory
   包含系统 memory 的全部文件且内容逐一相同。只有校验通过后才允许删除系统
   memory、建立 junction，并验证最终目标。
6. 禁止创建 `.bak`、`memory.premigrate.bak` 或其他迁移备份；冲突或校验失败时
   禁止删除系统 memory。

用户确认后调用当前宿主脚本的显式迁移模式；`--confirmed` 只能表达已经取得的
用户确认，禁止用它绕过计划展示：

```bash
& $HOOK_PYTHON ".claude/hooks/memory_junction_check.py" --mode migrate --confirmed
```

Claude `SessionStart` 禁止执行上述含复制、合并或删除的迁移。它只允许对正确 junction
no-op，或在系统 memory 不存在且项目 memory 已存在时建链；遇到实目录必须
fail-closed 并提示无参数运行 `/bridgeforge`。实目录迁移只能在本既有项目维护流程中，
取得用户确认后执行 `--mode migrate --confirmed`。

### U2.3 Codex 用户级遗留 note 恢复与空孤儿目录清理

仅当前宿主为 Codex 且类 A 已确认安装 `project_memory_writer.py` 与
`project_memory_recovery.py` 时执行。本节不扫描、复制、移动或删除
`~/.codex/memories` 的其他内容；它只读取
`~/.codex/memories/extensions/ad_hoc/notes/`。

1. 先运行 `project_memory_recovery.py notes-plan`，传入当前项目根和该固定 notes
   路径。候选必须在 note 正文中包含严格的 `项目：<绝对路径>`，规范化后完全等于
   当前项目，且当前项目有 `.codex/.bridgeforge_version`。标题、关键词或模型推断
   一律不是归属证据。
2. 计划必须逐项展示 source、SHA-256、候选项目和建议的项目 memory 目标。没有候选
   时零写入；不符合格式或属于其他项目的 note 必须原样保留。
3. 用户明确确认后，先由主对话生成同主题的最终合并正文，再以 source 路径、计划
   SHA-256、项目内相对目标和最终正文调用 `notes-apply --confirmed`。脚本必须通过
   项目写入器完成写入、索引重建和索引引用验证后，才允许删除原 note。任一 hash
   变化、路径异常、链接、写入器失败或索引验证失败都必须零删除。
4. 另对 `~/.codex/memory` 运行 `orphan-plan`。只有它是非 junction 普通目录，且
   内容严格为 `MEMORY.md`、`MEMORY_COLD.md`、`_stats.json` 并且 `_stats.json` 的
   `files` 为空时，才能展示为清理候选。用户确认后才允许以计划 fingerprint 调用
   `orphan-apply --confirmed`；重新校验不通过时必须保留目录。
5. `~/.codex/memories` 是用户级 Codex memory 存储，禁止整体迁移、删除或把它当作
   项目 `$summary` 的默认目标。

本节所有复制/删除都属于用户级外部路径操作：没有明确确认不得 apply。用户级 memory
写入仅在用户明确要求跨项目 / 全局经验时允许，并且输出必须标为用户级收据。

## U3. 路径适配

更新进入的所有受管 hook 命令必须投影为根入口 preflight 已锁定的
`$HOOK_PYTHON`。项目 `.venv` 存在时只能引用它，禁止因损坏或 `<3.11` 回退 PATH；
项目无 `.venv` 时才使用已锁定的 PATH 解释器。Codex 命令来自
`.codex/hooks.json`，Claude 命令来自 `.claude/settings.json`。若新模板已动态读取
模型上下文窗口，不再修改历史静态 `WINDOW` 常量。

Codex 每个受管 handler 的 `command` 与 `commandWindows` 都必须从
`git rev-parse --show-toplevel` 定位项目根。禁止把模板命令改回依赖 cwd 的相对路径。

## U4. 验证与收尾

1. 对更新过的 hook 运行实际 smoke test：

```bash
& $HOOK_PYTHON "$PROJECT_AGENT_DIR/hooks/<hook>.py"
```

2. settings / hooks / routing 有变更时验证 JSON 可解析，`config.toml` / agents TOML 可解析，routing 引用的 named agent 全部存在，且下游自定义字段与第三方 hook 仍存在；Codex 还必须确认 `.codex/hooks.json` 已含全部受管 dispatcher，`.codex/settings.json` 已无 `hooks`，`.codex/config.toml` 已无 `[hooks]`。
3. Codex 新增或变更 `.codex/hooks.json` 后，必须让用户执行 `/hooks`，逐项 review
   并 trust，再开启新会话，以实际 `SessionStart` 行为做 smoke。无法在当前流程
   完成新会话 smoke 时，收据只能写“trust 未验证”，禁止把 JSON 可解析或脚本直跑
   当成已信任。Claude hook 配置变更保持对应的配置 review / trust 与新会话 smoke
   流程；未完成时同样报告“trust 未验证”。
4. Codex 验证项目 `.codex/config.toml` 和 `.codex/agents/*.toml` 未被 BridgeForge 写入模型或思考强度字段；若下游自行固定过这些字段，展示差异并由用户决定是否保留。
5. `.githooks/pre-commit` 有变更时确认 `PROJECT_EXTENSION` hash 与 merge 前一致，并实际运行一次无暂存改动的 no-op 路径。
6. 禁止任何 merge 脚本或人工命令直接写 `$PROJECT_AGENT_DIR/.bridgeforge_version`。
   所有 A-D 冲突解决、受管 hook 覆盖确认后，只能调用唯一 finalizer；它会重新运行
   上游规范 memory 审计与项目 `config_health_check.py --strict`，两者均 exit 0 后才
   原子写入版本戳：

```powershell
$UPSTREAM_VERSION = (Get-Content -LiteralPath (Join-Path $BRIDGEFORGE_HOME "VERSION") -Raw).Trim()
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "scripts\bridgeforge_project_finalize.py") `
  --project-root . --template-root $BRIDGEFORGE_HOME --host $CURRENT_HOST `
  --version $UPSTREAM_VERSION --confirmed
```

   finalizer 非零时必须报告 `completed_with_gaps` 并保留旧戳；只有其输出包含
   `FINALIZED`、`memory_schema=clean`、`config_health=clean` 才能报告升级完成。
   根 `VERSION`、项目 `CHANGELOG.md`、`package.json`、`pyproject.toml`、
   `Cargo.toml` 均属于业务版本域，必须逐字保持不变；`managed-skeleton.json`
   属于受管骨架，随上游更新。
7. 输出 `git status` 与 `git diff` 供用户 review。
8. 不自动 commit / push。
9. 确认本模式未修改用户级 skill、其他项目或当前项目之外的路径。
10. 类 D 已 apply 时，重新生成 migration receipt：确认递归检索仍能命中
   分类 memory 与 topic memory，且未创建 `memory/_archive/`；junction 迁移还要
   确认系统路径已成为指向当前项目 memory 的 junction、项目内容校验通过，且未
   创建任何迁移备份。

结束时给出收据：版本区间、命中的 `[product]` 条目、A-F 各类实际处理、
memory 分类计划与 junction 计划 / 用户选择 / apply 状态、测试命令与退出码、
hook trust / 新会话 smoke 状态、新版本戳。

## 禁止

- 禁止自动覆盖 rules 或入口文件。
- 禁止在用户确认类 D 迁移计划前修改 memory；系统 memory 不存在时直接建链除外。
  `doc/` 仅可按类 F 经用户确认迁移。
- 禁止由 `SessionStart` 复制、合并或删除系统 memory。
- 禁止为 junction 迁移创建备份；校验完成前禁止删除系统 memory。
- 禁止把完成的 topic memory 移入 archive，或创建 `memory/_archive/`。
- 禁止绕过 `bridgeforge_project_finalize.py` 手工写 `.bridgeforge_version`。
- 禁止跨多个项目批量同步。
- 禁止自动 commit / push。
- 类 A-D 任一项存在未决冲突时，禁止先更新版本戳。
