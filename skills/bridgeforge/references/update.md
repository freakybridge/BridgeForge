# Update 更新模式操作手册

仅当根 `SKILL.md` 检测到 `$PROJECT_AGENT_DIR/.bridgeforge_version` 时读取。执行前必须完成 Windows 平台硬闸、无参数共享 updater、工厂自检、agent 分流和当前项目遗留 `.agents/` 检查。

机械半场（从已安装 command bundle 读取模板、diff、分类、呈现）由本 skill 执行；判断半场（入口/rules 选择性吸收）必须交给用户。详细边界依据是 `doc/0_architecture/design/sync-from-upstream-playbook.md`。禁止在本模式执行 `git pull` / `git clone`，也禁止从 `~/.bridgeforge`、`~/.agents` 或本地工作副本加载模板。

## U1. 计算产品增量

1. 读取项目 `$PROJECT_AGENT_DIR/.bridgeforge_version` 与 `$BRIDGEFORGE_HOME/VERSION`。
2. 相等且文件无差异：报告“已是最新（vX.Y.Z）”并退出。
3. 不等：从上游 `CHANGELOG.md` 提取 `(下游版本, 上游版本]` 内全部 `[product]` 条目；过滤 `[repo]` / `[meta]`。
4. 区间没有 `[product]`：不要跑全量 diff；报告本次无下游产品变更，执行 U4 更新版本戳后退出。

## U2. 按类型 diff

先给总览，再逐项处理：

| 类 | 文件 | 策略 |
|---|---|---|
| A | hooks、scripts；Codex `agents/*.toml`（`implementation-worker` 的模型字段除外）、`skill-routing.json` | 下游与旧模板一致时提议覆盖并确认；被改过时展示 diff，禁止无脑覆盖；Codex agents 与 routing 必须配套检查。用户级 skills 已由共享 updater 处理，不属于项目模板 diff |
| B | settings.json；Codex `subscription-tier.toml` / `config.toml` / `implementation-worker.toml` 的模型字段；`.githooks/pre-commit` | merge 不覆盖；订阅 marker 是项目状态，禁止用模板高档 marker 覆盖；加入上游通用 hooks / 配置 / 检查段，保留下游 permissions、additionalDirectories 和自定义注册；主对话与 implementation 的模型/effort 字段以 marker 对应档位为准 |
| C | rules、入口文件 | 只 diff；按通用增量/业务补充/上游脱敏减弱三类让用户逐段决定 |
| D | memory | 先展示迁移计划；用户逐项补齐低置信 `category` / `topic` 并明确确认后才 apply |
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

## U3. 路径适配

更新进入的 settings hook 命令若引用 `.venv`，而项目没有 `.venv`，改为裸 `python`；有 conda/项目解释器则用明确路径。若新模板已动态读取模型上下文窗口，不再修改历史静态 `WINDOW` 常量。

## U4. 验证与收尾

1. 对更新过的 hook 运行实际 smoke test：

```bash
python "$PROJECT_AGENT_DIR/hooks/<hook>.py"
```

2. settings / routing 有变更时验证 JSON 可解析，`config.toml` / agents TOML 可解析，routing 引用的 named agent 全部存在，且下游自定义字段仍存在。
3. Codex 验证 `.codex/subscription-tier.toml` 存在，`model_policy_check.py --pre-commit` 按 marker 对应档位通过；无 marker 时必须先回根入口 Step 4.5 询问并写入，禁止静默套用模板高档。
4. `.githooks/pre-commit` 有变更时确认原有项目检查仍在，并实际运行一次无暂存改动的 no-op 路径。
5. 将 `$PROJECT_AGENT_DIR/.bridgeforge_version` 写为上游当前 `VERSION`。
6. 输出 `git status` 与 `git diff` 供用户 review。
7. 不自动 commit / push。
8. 确认本模式未修改用户级 skill、其他项目或当前项目之外的路径。
9. 类 D 已 apply 时，重新生成 migration receipt：确认递归检索仍能命中
   分类 memory 与 topic memory，且未创建 `memory/_archive/`。

结束时给出收据：版本区间、命中的 `[product]` 条目、A-F 各类实际处理、
memory plan / 用户选择 / apply 状态、测试命令与退出码、新版本戳。

## 禁止

- 禁止自动覆盖 rules 或入口文件。
- 禁止在用户确认类 D 迁移计划前修改 memory；`doc/` 仅可按类 F 经用户确认迁移。
- 禁止把完成的 topic memory 移入 archive，或创建 `memory/_archive/`。
- 禁止跨多个项目批量同步。
- 禁止自动 commit / push。
- 类 A/B/C 任一项存在未决冲突时，禁止先更新版本戳。
