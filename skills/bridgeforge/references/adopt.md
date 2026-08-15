# Adopt 收编模式操作手册

进入本手册前必须已通过根入口 Python 3.11+ preflight，并锁定本轮唯一
`$HOOK_PYTHON`。preflight 失败时禁止 merge、复制、删除或写版本戳。

仅当根 `SKILL.md` 判定“当前 agent 无 `.bridgeforge_version`，但 BridgeForge 衍生指纹至少命中 2 项”时读取。执行前必须完成根入口规定的公共用户级 skill 维护。

## Codex 项目事务唯一入口

当 `$CURRENT_HOST = "codex"` 时，本手册后续的逐文件步骤全部跳过；只能调用：

```powershell
$PROJECT_SYNC = Join-Path $BRIDGEFORGE_HOME "scripts\bridgeforge_project_sync.py"
$PLAN_JSON = (& $HOOK_PYTHON $PROJECT_SYNC --project-root . `
  --template-root $BRIDGEFORGE_HOME --mode adopt | Out-String)
if ($LASTEXITCODE -ne 0) { throw $PLAN_JSON }
$PLAN = $PLAN_JSON | ConvertFrom-Json
$PLAN_JSON
```

将 `MODE` 替换为本手册对应的 `init`、`adopt` 或 `update`。读取 plan 的
`required_actions / optional_actions / manual_steps / blocker_items / recommended_selection`，按根
契约只展示一张 A/B/C 卡。没有 R/C 时立即以
`--apply --plan-fingerprint $PLAN.aggregate_fingerprint` 执行；A 追加 `--confirmed-risk`；
B 为同一回复中的每个合法 R 编号追加 `--selected-risk <Rn>`；C 追加 `--decline-risk`。
执行器会紧邻 replan；fingerprint 漂移零写入，任何失败回滚。仅
`target_readiness=ready|ready_with_advisories` 且验证通过时最后写版本戳；存在必要 gap、
人工步骤或拒绝 risk 时保留旧戳/无戳，并同时输出双状态与兼容 JSON receipt。

Codex 禁止再单独调用 `hooks_merge.py`、`precommit_merge.py`、
`bridgeforge_project_finalize.py`，也禁止手工复制、删除或写
`.codex/.bridgeforge_version`。以下旧步骤只服务 Claude 兼容路径，不适用于 Codex。


## 核心语义

收编只登记同步基线，绝不覆盖已有文件。典型对象是 v0.14.0 以前的无版本戳安装，或手动复制过 BridgeForge 模板的项目。

Codex 使用平台默认调度；adopt 禁止创建、读取或要求任何订阅档位 marker，也不写模型或
reasoning effort 字段。

## 默认流程

1. 列出实际命中的指纹项。
2. 只读说明“检测到 BridgeForge 衍生骨架；收编只登记纳管，不改已有 whole-file”。
3. 先完成 safe hook 承载 merge；无风险且无阻断 gap 时直接写当前上游版本，不单独确认：

```bash
cp "$BRIDGEFORGE_HOME/VERSION" "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

版本戳等于声明“以当前项目现状为最新同步基线”。首次收编默认不补历史增量；从下次运行起，才按 `(此版, 新版]` 处理 `[product]` 更新。

写戳前审计当前宿主的项目级 hook 承载面与 memory 加载机制：

- Codex lifecycle hook 的唯一承载面必须是 `.codex/hooks.json`；先把 settings 旧
  `hooks` 的第三方项合并进去，再删除整个 settings `hooks` 块，按 `command` 身份
  增补/替换全部受管 dispatcher，并保留 hooks.json 第三方项。Claude Code 保持
  `.claude/settings.json`。
- 受管 hook 已被修改时展示 diff、保留原样并记 gap；禁止另行询问覆盖。
- `.codex/config.toml` 含 `[hooks]`、严格健康检查失败或 hook merge 未完成时，
  **禁止写版本戳**，转入待维护状态。
- Codex merge 必须先运行 command bundle 内
  `& $HOOK_PYTHON templates/codex/scripts/hooks_merge.py --project-root . --template-hooks <模板 hooks.json>`
  展示 diff；只有稳定身份 merge 才可作为 safe 追加 `--apply --confirmed`，其中
  `--confirmed` 表示本轮 accumulator 已复核，不是新增业务询问。禁止手工拼接 JSON。
- `.githooks/pre-commit` 存在时，必须先用当前宿主模板的
  `scripts/precommit_merge.py --project-root . --template-precommit <模板 pre-commit>`
  做只读预览。仅 `BRIDGEFORGE_MANAGED` 可更新；`PROJECT_EXTENSION` 必须逐字保留。
  仅当历史 `Step 2: VERSION bump`、`scripts/bump_version.py`、末尾 `git add VERSION`
  均存在，且其前缀 SHA-256 逐字匹配冻结的 0.81 Codex / Claude 模板时，无标记旧 hook 才可转换；
  其他缺标记、前缀改动、标记损坏或区块外自定义代码一律保留为 gap，禁止整份覆盖；
  只有可证明的 managed 区块 merge 才允许追加 `--apply --confirmed`。
- adopt 不复制、合并或删除 memory；Codex 不建项目 memory junction，Claude 保持既有规则。
- Codex context/router 未安装，或 Claude junction 不是已验证的正确目标时记录为“待维护”；hook 承载必须先完成，不能以
  “收编只登记”为由把无效 hooks 注册盖上新版本戳。
- Claude 错误/断裂 junction、路径异常或系统 memory 实目录只报告状态；禁止在
  `SessionStart` 或 adopt 中自动迁移。
- Codex 若审计发现 `.codex/hooks.json` 新增或变更后没有 trust 与新会话 smoke
  证据，必须提示用户执行 `/hooks`，逐项 review 并 trust，再开启新会话 smoke。
  adopt 不改 hook；当前流程无法完成时只能记录“trust 未验证”。Claude 保持其
  对应的配置 review / trust 与新会话 smoke 流程。

## 可选：补历史差量

仅用户明确要求时执行：

1. 只接受用户本轮主动提供或项目事实能证明的旧安装版本。
2. 无可靠基线时跳过历史差量并记 gap；禁止为此新增询问或猜测 `0.1.0`。
3. 回根入口读取其直接链接的 `references/update.md`，按类 C 只展示 diff；无历史 hash 或人工修改时保留原文件并记 gap，不再逐段询问。
4. 拿不准基线就不补；宁可漏历史增量，也不冒覆盖业务内容的风险。

## 禁止与收据

- 禁止覆盖任何入口文件、rules 或 settings，即使先备份也不行。
- 禁止静默覆盖 hook；只允许按稳定身份 safe merge 承载面。禁止改 memory 或 `doc/`。
- 禁止在存在未解决的 hook/config 归属 gap 时写版本戳。
- 禁止把“像 BridgeForge”当成“允许 fresh init 覆盖”。

结束时报告命中的指纹、业务确认次数（0 或 1）、写入的基线版本、是否跳过历史增量，以及
当前宿主 hook/memory 审计结果、trust 验证状态与是否需要运行
无参数 `/bridgeforge`。
