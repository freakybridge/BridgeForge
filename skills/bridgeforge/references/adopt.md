# Adopt 收编模式操作手册

进入本手册前必须已通过根入口 Python 3.11+ preflight，并锁定本轮唯一
`$HOOK_PYTHON`。preflight 失败时禁止 merge、复制、删除或写版本戳。

仅当根 `SKILL.md` 判定“当前 agent 无 `.bridgeforge_version`，但 BridgeForge 衍生指纹至少命中 2 项”时读取。执行前必须完成根入口规定的公共用户级 skill 维护。

## 核心语义

收编只登记同步基线，绝不覆盖已有文件。典型对象是 v0.14.0 以前的无版本戳安装，或手动复制过 BridgeForge 模板的项目。

Codex 例外仅限根入口 Step 4.5：无订阅档位 marker 时，先由用户选择，再由订阅路由脚本只写 marker、`config.toml` 的主模型字段和 `implementation-worker.toml` 的模型字段。这是独立的用户授权配置，不等于允许 adopt 覆盖其他既有内容；已有 marker 时不重复询问或改写。

## 默认流程

1. 列出实际命中的指纹项。
2. 告诉用户：“检测到项目像是 BridgeForge 铺过但缺版本戳；建议收编。收编只登记纳管，不改已有文件。”
3. 用户确认后先执行 Codex hook 承载迁移，再写当前上游版本：

```bash
cp "$BRIDGEFORGE_HOME/VERSION" "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

版本戳等于声明“以当前项目现状为最新同步基线”。首次收编默认不补历史增量；从下次运行起，才按 `(此版, 新版]` 处理 `[product]` 更新。

写戳前审计当前宿主的项目级 hook 承载面与 memory 加载机制：

- Codex lifecycle hook 的唯一承载面必须是 `.codex/hooks.json`；先把 settings 旧
  `hooks` 的第三方项合并进去，再删除整个 settings `hooks` 块，按 `command` 身份
  增补/替换全部受管 dispatcher，并保留 hooks.json 第三方项。Claude Code 保持
  `.claude/settings.json`。
- 受管 hook 已被修改时必须展示 diff 并取得覆盖确认；拒绝或冲突时保持全部文件不变。
- `.codex/config.toml` 含 `[hooks]`、严格健康检查失败或 hook merge 未完成时，
  **禁止写版本戳**，转入待维护状态。
- Codex merge 必须先运行 command bundle 内
  `& $HOOK_PYTHON templates/codex/scripts/hooks_merge.py --project-root . --template-hooks <模板 hooks.json>`
  展示 diff；用户确认后才追加 `--apply --confirmed`。禁止手工拼接 JSON。
- `.githooks/pre-commit` 存在时，必须先用当前宿主模板的
  `scripts/precommit_merge.py --project-root . --template-precommit <模板 pre-commit>`
  做只读预览。仅 `BRIDGEFORGE_MANAGED` 可更新；`PROJECT_EXTENSION` 必须逐字保留。
  仅当历史 `Step 2: VERSION bump`、`scripts/bump_version.py`、末尾 `git add VERSION`
  均存在，且其前缀 SHA-256 逐字匹配冻结的 0.81 Codex / Claude 模板时，无标记旧 hook 才可转换；
  其他缺标记、前缀改动、标记损坏或区块外自定义代码一律阻断版本戳，禁止整份覆盖；用户确认 diff 后才允许
  追加 `--apply --confirmed`。
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

1. 写戳前询问用户记得的旧安装版本。
2. 记得则把该版本作为临时基线；记不得时可建议保守基线 `0.1.0`，但必须由用户确认。
3. 回根入口读取其直接链接的 `references/update.md`，按类 C diff 让用户逐段吸收。
4. 拿不准基线就不补；宁可漏历史增量，也不冒覆盖业务内容的风险。

## 禁止与收据

- 禁止覆盖任何入口文件、rules 或 settings，即使先备份也不行。
- 禁止静默覆盖 hook；允许按上述确认式 merge 承载面。禁止改 memory 或 `doc/`。
- 禁止未经用户确认写版本戳。
- 禁止在 Codex 无有效订阅档位 marker 时完成收编。
- 禁止把“像 BridgeForge”当成“允许 fresh init 覆盖”。

结束时报告命中的指纹、用户是否确认、写入的基线版本、是否跳过历史增量，以及
当前宿主 hook/memory 审计结果、trust 验证状态与是否需要运行
无参数 `/bridgeforge`。
