# Update 更新模式操作手册

仅当根 `SKILL.md` 检测到 `$PROJECT_AGENT_DIR/.bridgeforge_version` 时读取。执行前必须完成 Windows 平台硬闸、无参数共享 updater、工厂自检、agent 分流和当前项目遗留 `.agents/` 检查。

机械半场（从已安装 command bundle 读取模板、diff、分类、呈现）由本 skill 执行；判断半场（入口/rules 选择性吸收）必须交给用户。详细边界依据是 `doc/0_architecture/design/sync-from-upstream-playbook.md`。禁止在本模式执行 `git pull` / `git clone`，也禁止从 `~/.bridgeforge`、`~/.agents` 或本地工作副本加载模板。

## U1. 计算产品增量

1. 读取项目 `$PROJECT_AGENT_DIR/.bridgeforge_version` 与 `$BRIDGEFORGE_HOME/VERSION`。
2. 相等且文件无差异、当前宿主 hook 承载面正确且 memory junction 无待迁移
   状态：报告“已是最新（vX.Y.Z）”并退出。承载面或 junction 仍待迁移时，即使
   版本相等也必须继续 U2 的 B/D 类处理。
3. 不等：从上游 `CHANGELOG.md` 提取 `(下游版本, 上游版本]` 内全部 `[product]` 条目；过滤 `[repo]` / `[meta]`。
4. 区间没有 `[product]` 且 hook 承载面/junction 无待迁移状态：不要跑全量
   diff；报告本次无下游产品变更，执行 U4 更新版本戳后退出。仍待迁移时继续
   B/D 类处理。

## U2. 按类型 diff

先给总览，再逐项处理：

| 类 | 文件 | 策略 |
|---|---|---|
| A | hooks、scripts；Codex `agents/*.toml`（`implementation-worker` 的模型字段除外）、`skill-routing.json` | 下游与旧模板一致时提议覆盖并确认；被改过时展示 diff，禁止无脑覆盖；Codex agents 与 routing 必须配套检查。用户级 skills 已由共享 updater 处理，不属于项目模板 diff |
| B | settings.json；Codex `hooks.json` / `subscription-tier.toml` / `config.toml` / `implementation-worker.toml` 的模型字段；`.githooks/pre-commit` | merge 不覆盖；Codex 按 `command` 身份在 `.codex/hooks.json` 增补/替换受管 `memory_junction_check`，保留第三方事件与 hook，并从 `.codex/settings.json` 移除旧 junction 注册；Claude 保持 `.claude/settings.json` 承载并保留第三方 hook；订阅 marker 是项目状态，禁止用模板高档 marker 覆盖；保留下游 permissions、additionalDirectories；主对话与 implementation 的模型/effort 字段以 marker 对应档位为准 |
| C | rules、入口文件 | 只 diff；按通用增量/业务补充/上游脱敏减弱三类让用户逐段决定 |
| D | memory | 分别展示分类计划与 junction 迁移计划；低置信 `category` / `topic` 由用户补齐；任何含复制/删除的 junction 迁移必须明确确认后才 apply |
| E | `.gitignore` | 按 init 手册的 BridgeForge 机制块幂等补缺，不删项目项 |
| F | `doc/` 布局 | 检测 `doc/README.md:delivery_layout` 和旧目录；展示迁移清单，用户确认后才 `git mv`，不得静默混用 |

类 C 判据：

- 上游新增通用增量：建议吸收。
- 下游业务专属补充：保留。
- 上游脱敏版比下游弱：保留下游。

任何类 C 修改都要展示具体 diff 并等用户决定。禁止跨多个项目批量同步。

### U2.1 Memory 迁移计划

更新既有项目时先递归盘点当前 agent 的 `memory/**/*.md`；跳过自动生成的
`MEMORY.md`、`MEMORY_COLD.md`，只输出计划，不写 frontmatter、不创建目录、
不移动文件：

1. 对合法 `category` 直接给出目标：`architecture`、`engineering`、
   `domain`、`operations` 进入 `memory/<category>/`；`topic` 必须同时有
   `topic: <exact-slug>`，进入 `memory/topics/<exact-slug>/`。
2. 缺失或非法 `category` 时展示候选。低置信项必须由用户逐项选择
   `category`；选择 `topic` 时还必须确认 exact slug。未决项阻断 apply。
3. 计划必须列出每个文件的原路径、目标路径、拟补写的
   `category` / `topic` / `status`，以及会新建的非空目录。
4. 只有用户明确确认整份计划后才 apply：补写 metadata、创建实际需要的目录、
   移动文件并重建索引。禁止预建未使用的分类目录。
5. `status` 只允许 `active`、`completed`、`superseded`，缺省按
   `active`。`completed` / `superseded` topic 仍保留在原
   `memory/topics/<topic>/`，只由索引降温；禁止创建或使用
   `memory/_archive/`。
6. 原始需求、讨论、计划和验收仍保留在 `doc/1_delivery/<topic>/`；
   topic memory 只提供可独立阅读的恢复摘要，禁止用它替代或删除 delivery 证据。

用户拒绝或未确认迁移时，保持 memory 逐字不变并继续报告为未迁移；不得把
“展示了计划”写成“已迁移”。

### U2.2 Memory junction 迁移计划

只处理当前宿主：

| 宿主 | 系统 memory | 项目唯一事实源 | SessionStart 承载 |
|---|---|---|---|
| Codex | `~/.codex/projects/<project-hash>/memory/` | `.codex/memory/` | `.codex/hooks.json` |
| Claude Code | `~/.claude/projects/<project-hash>/memory/` | `.claude/memory/` | `.claude/settings.json` |

先只读盘点并展示状态：

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
python "$PROJECT_AGENT_DIR/hooks/memory_junction_check.py" --mode migrate --confirmed
```

`SessionStart` 禁止执行上述含复制、合并或删除的迁移。它只允许对正确 junction
no-op，或在系统 memory 不存在且项目 memory 已存在时建链；遇到实目录必须
fail-closed 并提示运行 `/bridgeforge update`。实目录迁移只能在本 update 流程中，
取得用户确认后执行 `--mode migrate --confirmed`。

## U3. 路径适配

更新进入的 hook 命令若引用 `.venv`，而项目没有 `.venv`，改为裸 `python`；
有 conda/项目解释器则用明确路径。Codex 命令来自 `.codex/hooks.json`，Claude
命令来自 `.claude/settings.json`。若新模板已动态读取模型上下文窗口，不再修改
历史静态 `WINDOW` 常量。

## U4. 验证与收尾

1. 对更新过的 hook 运行实际 smoke test：

```bash
python "$PROJECT_AGENT_DIR/hooks/<hook>.py"
```

2. settings / hooks / routing 有变更时验证 JSON 可解析，`config.toml` / agents TOML 可解析，routing 引用的 named agent 全部存在，且下游自定义字段与自定义 hook 仍存在；Codex 还必须确认 `.codex/hooks.json` 已含受管 junction 注册，`.codex/settings.json` 已无旧 junction 注册。
3. Codex 新增或变更 `.codex/hooks.json` 后，必须让用户执行 `/hooks`，逐项 review
   并 trust，再开启新会话，以实际 `SessionStart` 行为做 smoke。无法在当前流程
   完成新会话 smoke 时，收据只能写“trust 未验证”，禁止把 JSON 可解析或脚本直跑
   当成已信任。Claude hook 配置变更保持对应的配置 review / trust 与新会话 smoke
   流程；未完成时同样报告“trust 未验证”。
4. Codex 验证 `.codex/subscription-tier.toml` 存在，`model_policy_check.py --pre-commit` 按 marker 对应档位通过；无 marker 时必须先回根入口 Step 4.5 询问并写入，禁止静默套用模板高档。
5. `.githooks/pre-commit` 有变更时确认原有项目检查仍在，并实际运行一次无暂存改动的 no-op 路径。
6. 将 `$PROJECT_AGENT_DIR/.bridgeforge_version` 写为上游当前 `VERSION`。
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
- 禁止跨多个项目批量同步。
- 禁止自动 commit / push。
- 类 A-D 任一项存在未决冲突时，禁止先更新版本戳。
