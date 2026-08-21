# bridgeforge-codex 上游更新 Playbook

> **定位**：把 bridgeforge-codex 的 Codex 骨架安全更新到当前项目。唯一产品入口是 `$bridgeforge-codex`；禁止手工复制模板或串联旧脚本。

## 1. 更新对象

- 用户级产品仓库：`~/.bridgeforge-codex`。
- 用户级薄入口：`~/.codex/skills/bridgeforge-codex`。
- 项目骨架：`AGENTS.md`、`.codex/`、`.githooks/pre-commit` 与 `doc/README.md`。
- 项目版本戳：`.codex/.bridgeforge_codex_version`。

Claude 骨架已经退役。遗留 `.claude/` 只报告存在，不读取正文、不迁移、不删除；旧用户级 Claude 资产、旧 ledger 与旧产品 home 不再由当前产品接管或清理。

## 2. 唯一流程

1. 在目标项目运行 `$bridgeforge-codex`。
2. 入口在 `.venv` bootstrap 前验证版本戳：缺戳、双戳、非法戳立即零写停止。
3. 恰好一个合法版本戳且版本 `<1.4.31` 时进入独立审计；用户逐项确认 rules、AGENTS 项目区、pre-commit 项目扩展与 `.codex/hooks/project_XXXX/` Hook 目录的保留或删除后，再做一次破坏性重建风险确认。
4. `>=1.4.31` 先由 schema 3 current baseline 验证真实公共资产；任一漂移或合同损坏阻断，禁止吸收或强制覆盖。旧文件名验证通过后在同一事务迁移为当前戳。
5. apply 前重算聚合 fingerprint。任何漂移、验证失败或运行错误都必须零写入或事务回滚。
6. validators 与真实磁盘 current baseline 全部通过后，最后写新版本戳；旧项目成功时同事务删除旧戳。

## 3. 所有权边界

- `whole`、`merge`、`managed_blocks`、`region` 均只接受 schema 3 当前 hash/projection。
- 旧项目不解析旧 managed contract，也不复用常规 merge；每个可选项目资产必须明确保留或删除，只把已确认保留项注入 fresh canonical。
- 项目 Hook 以 `.codex/hooks/project_XXXX/` 自包含 Python 目录为原子所有权单位，目录与 `.codex/hooks.json` 注册必须成对。
- 散落 Hook 先阻断；独立 Agent 只能在临时副本或受控前置步骤中完成目录正规化，随后重新生成 `PreservationManifest`。
- `seed` 只在缺失时创建，既有内容归项目。
- `.codex/memory/` 与 `.codex/skills/` 自动保留正文并执行当前兼容检查；其他未登记旧内容阻断，不得静默删除。

## 4. 验收收据

完成更新至少核对：

- `status` 与 `readiness` 分开报告；
- actions/`PreservationManifest`/blocker 清单与实际执行逐项对账；
- `stamp_written_last=true` 只在完整验证后出现；
- 再次 plan 为 no-op；
- `git diff --check`、manifest/schema、memory 与 hook 验证通过；
- 遗留 Claude 内容未被读取或改写。

有 gap 时，结果不是“完美更新”。收据必须给出用户还需处理的文件、原因和可执行选择，不得只显示 `completed_with_gaps`。

## 5. 禁止事项

- 禁止手工 `copy`/`cp` 覆盖下游骨架。
- 禁止用旧 `bridgeforge_project_finalize.py` 或多脚本串联写戳。
- 禁止自动覆盖项目自定义 rules、AGENTS 区块、memory 或 doc。
- 禁止在同一轮重复索要确认。
- 禁止把 Claude 遗留目录当作 Codex 模板来源。

反方向的通用经验回灌见 [reverse-sync-playbook.md](reverse-sync-playbook.md)。
