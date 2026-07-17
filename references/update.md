# Update 更新模式操作手册

仅当根 `SKILL.md` 检测到 `$PROJECT_AGENT_DIR/.bridgeforge_version` 时读取。执行前必须完成刷新、工厂自检、agent 分流和公共用户级 skill 维护。

机械半场（拉取、diff、分类、呈现）由本 skill 执行；判断半场（入口/rules 选择性吸收）必须交给用户。详细边界依据是 `doc/3_design/sync-from-upstream-playbook.md`。

## U1. 计算产品增量

1. 读取项目 `$PROJECT_AGENT_DIR/.bridgeforge_version` 与 `$BRIDGEFORGE_HOME/VERSION`。
2. 相等且文件无差异：报告“已是最新（vX.Y.Z）”并退出。
3. 不等：从上游 `CHANGELOG.md` 提取 `(下游版本, 上游版本]` 内全部 `[product]` 条目；过滤 `[repo]` / `[meta]`。
4. 区间没有 `[product]`：不要跑全量 diff；报告本次无下游产品变更，执行 U4 更新版本戳后退出。

## U2. 按类型 diff

先给总览，再逐项处理：

| 类 | 文件 | 策略 |
|---|---|---|
| A | hooks、scripts、用户级 skills；Codex `agents/*.toml`、`skill-routing.json` | 下游与旧模板一致时提议覆盖并确认；被改过时展示 diff，禁止无脑覆盖；Codex agents 与 routing 必须配套检查 |
| B | settings.json；Codex `config.toml`；`.githooks/pre-commit` | merge 不覆盖；加入上游通用 hooks / 配置 / 检查段，保留下游 permissions、additionalDirectories、模型覆盖和自定义注册 |
| C | rules、入口文件 | 只 diff；按通用增量/业务补充/上游脱敏减弱三类让用户逐段决定 |
| D | memory、`doc/` | 绝对不碰 |
| E | `.gitignore` | 按 init 手册的 BridgeForge 机制块幂等补缺，不删项目项 |

类 C 判据：

- 上游新增通用增量：建议吸收。
- 下游业务专属补充：保留。
- 上游脱敏版比下游弱：保留下游。

任何类 C 修改都要展示具体 diff 并等用户决定。禁止跨多个项目批量同步。

## U3. 路径适配

更新进入的 settings hook 命令若引用 `.venv`，而项目没有 `.venv`，改为裸 `python`；有 conda/项目解释器则用明确路径。若新模板已动态读取模型上下文窗口，不再修改历史静态 `WINDOW` 常量。

## U4. 验证与收尾

1. 对更新过的 hook 运行实际 smoke test：

```bash
python "$PROJECT_AGENT_DIR/hooks/<hook>.py"
```

2. settings / routing 有变更时验证 JSON 可解析，`config.toml` / agents TOML 可解析，routing 引用的 named agent 全部存在，且下游自定义字段仍存在。
3. `.githooks/pre-commit` 有变更时确认原有项目检查仍在，并实际运行一次无暂存改动的 no-op 路径。
4. 将 `$PROJECT_AGENT_DIR/.bridgeforge_version` 写为上游当前 `VERSION`。
5. 输出 `git status` 与 `git diff` 供用户 review。
6. 不自动 commit / push。

结束时给出收据：版本区间、命中的 `[product]` 条目、A-E 各类实际处理、测试命令与退出码、新版本戳。

## 禁止

- 禁止自动覆盖 rules 或入口文件。
- 禁止修改 memory 或 `doc/`。
- 禁止跨多个项目批量同步。
- 禁止自动 commit / push。
- 类 A/B/C 任一项存在未决冲突时，禁止先更新版本戳。
