# bridgeforge-codex 上游更新 Playbook

> **定位**：把 bridgeforge-codex 的 Codex 骨架安全更新到当前项目。唯一产品入口是 `$bridgeforge-codex`；禁止手工复制模板或串联旧脚本。

## 1. 更新对象

- 用户级产品仓库：`~/.bridgeforge-codex`。
- 用户级薄入口：`~/.codex/skills/bridgeforge-codex`。
- 项目骨架：`AGENTS.md`、`.codex/`、`.githooks/pre-commit` 与 `doc/README.md`。
- 项目版本戳：`.codex/.bridgeforge_codex_version`。

Claude 骨架已经退役。遗留 `.claude/` 只报告存在，不读取正文、不迁移、不删除；旧用户级 Claude 资产仅由已确认的用户迁移计划按 ledger 与实际 hash 处理。

## 2. 唯一流程

1. 在目标项目运行 `$bridgeforge-codex`。
2. 入口先刷新并验证 `~/.bridgeforge-codex`，再以同一个 Python 3.11+ 解释器生成：用户级旧资产迁移、原生 memories、项目 `.agents` 旧布局和项目 schema v2 更新计划。
3. 计划把动作分成：
   - `safe`：受管资产的可信升级或缺失资产补齐；
   - `risk`：删除、移动、旧戳迁移、首次外部授权；
   - `U`：可由用户选择吸收的上游受管 Markdown 变动；
   - `gap`：所有权不明、解析歧义或本地定制，保持原样并阻止写新版本戳。
4. 没有 risk/U 时零确认；存在时整轮最多一次确认。A 全部执行，B 只执行列明项并接受逐项自定义，C 不再改动。
5. apply 前重算聚合 fingerprint。任何漂移、验证失败或运行错误都必须零写入或事务回滚。
6. 所有写入和验证完成后才最后写新版本戳；存在 gap 时保留旧戳。

## 3. 所有权边界

- `whole` 资产只在当前内容命中可信发布谱系时替换。
- `managed_blocks` 只处理明确标记的受管区块；区块外内容归项目。
- `keyed_table` 按稳定键合并，禁止整表覆盖；损坏或歧义行 fail-closed。
- `seed` 只在缺失时创建，既有内容归项目。
- `.codex/memory/`、业务文档和未登记文件默认归项目；禁止凭版本戳推断所有权。

## 4. 验收收据

完成更新至少核对：

- `status` 与 `readiness` 分开报告；
- safe/risk/U/gap 清单与实际执行逐项对账；
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
