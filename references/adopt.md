# Adopt 收编模式操作手册

仅当根 `SKILL.md` 判定“当前 agent 无 `.bridgeforge_version`，但 BridgeForge 衍生指纹至少命中 2 项”时读取。执行前必须完成根入口规定的公共用户级 skill 维护。

## 核心语义

收编只登记同步基线，绝不覆盖已有文件。典型对象是 v0.14.0 以前的无版本戳安装，或手动复制过 BridgeForge 模板的项目。

Codex 例外仅限根入口 Step 4.5：无订阅档位 marker 时，先由用户选择，再由订阅路由脚本只写 marker、`config.toml` 的主模型字段和 `implementation-worker.toml` 的模型字段。这是独立的用户授权配置，不等于允许 adopt 覆盖其他既有内容；已有 marker 时不重复询问或改写。

## 默认流程

1. 列出实际命中的指纹项。
2. 告诉用户：“检测到项目像是 BridgeForge 铺过但缺版本戳；建议收编。收编只登记纳管，不改已有文件。”
3. 用户确认后写当前上游版本：

```bash
cp "$BRIDGEFORGE_HOME/VERSION" "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

版本戳等于声明“以当前项目现状为最新同步基线”。首次收编默认不补历史增量；从下次运行起，才按 `(此版, 新版]` 处理 `[product]` 更新。

## 可选：补历史差量

仅用户明确要求时执行：

1. 写戳前询问用户记得的旧安装版本。
2. 记得则把该版本作为临时基线；记不得时可建议保守基线 `0.1.0`，但必须由用户确认。
3. 回根入口读取其直接链接的 `references/update.md`，按类 C diff 让用户逐段吸收。
4. 拿不准基线就不补；宁可漏历史增量，也不冒覆盖业务内容的风险。

## 禁止与收据

- 禁止覆盖任何入口文件、rules 或 settings，即使先备份也不行。
- 禁止改 memory 或 `doc/`。
- 禁止未经用户确认写版本戳。
- 禁止在 Codex 无有效订阅档位 marker 时完成收编。
- 禁止把“像 BridgeForge”当成“允许 fresh init 覆盖”。

结束时报告命中的指纹、用户是否确认、写入的基线版本，以及是否跳过历史增量。
