# bridgeforge 重复更新中断导致 Codex command bundle 残缺

**状态**：Resolved  
**发现日期**：2026-08-12  
**修复日期**：2026-08-12  
**影响范围**：Codex 用户级 `~/.codex/skills/bridgeforge/`；Claude 安装结果未受损

## 2026-08-15 系统重构复核

- `shared-skill-manifest.json` 继续显式分发全部 references、canonical 执行器与模板资产。
- updater 的 mutex、目录 hash、backup/restore 与账本事务保持为用户级分发唯一入口。
- manifest 重建器现同时维护 Codex asset contract lineage，且 `--check` 零写入；本 Bug 保持 `Resolved`。

## 现象

下游项目 `D:\Quant\ClaudeBridgeAssist` 运行无参 `/bridgeforge` 后，Codex 安装目录
`C:\Users\bridg\.codex\skills\bridgeforge\` 最终仅剩：

- `SKILL.md`
- `VERSION`
- `CHANGELOG.md`

完整 command bundle 应有 139 个 manifest 文件；现场缺失 136 个，包括 5 个 `references/*.md`、
3 个 `scripts/*` 和 128 个 `templates/*`。入口无法读取
`references/user-skill-maintenance.md`，因此必须停止项目骨架维护。

## 已验证证据

| 断言 | 收据 |
| --- | --- |
| 第一次更新已经成功 | Codex 与 Claude 账本均记录 `source_commit=9e5f38de39b8b99c2d73ab095e922c99813a8d6a`，安装时间约为 `14:31:03Z` |
| 随后发生第二次更新 | 残留 `.bridgeforge-shared-update.json` 的 `started_at` 为 `14:31:08Z`，同一提交，`committed=false` |
| 中断点位于 Codex 自更新 | Codex 其他 18 个 skill action 为 `complete`，`bridgeforge` 为 `pending`；Claude 全部 action 仍为 `pending` |
| Claude 包完整 | Claude 的 `references/`、`scripts/` 与 `templates/` 均存在，不能归类为双平台漏装 |
| 发布源完整 | manifest 包含 139 个 bridgeforge 文件，仓库源文件全部存在 |
| 账本不能证明实际目录完整 | 账本保留第一次成功记录，但第二次未提交事务已经改变了 Codex 实际目录 |

## 根因判断

已确认：**同一提交被再次执行更新，第二次事务在 Codex `bridgeforge` 自替换阶段中断，留下未提交事务与残缺实际目录。**

原实现存在三项系统缺口：

1. 没有单实例互斥，无法阻止同一用户并发执行 updater。
2. 同一 commit 且目录完整时仍会再次替换所有 skill，扩大了无收益的自更新窗口。
3. 恢复逻辑未记录并验证原目录 hash，损坏或空 backup 可能覆盖当前目标。

尚未确认：第二次调用由哪个进程或入口触发，以及该进程为何在自替换阶段中断。没有保留对应进程日志，因此不能把文件锁、Codex 自动同步或人工重复调用写成既定触发原因。

## 修复内容

1. updater 使用按用户命名的 mutex；第二实例在事务写入前退出非零。
2. 账本 commit、账本 content hash 和实际目录 hash 三者一致时跳过换包；任一不一致则重装。
3. stage、swap 后目标和全平台最终目录均按 manifest 的完整文件集合与 hash 验证。
4. 事务日志记录原目录 hash；恢复时只接受 hash 完全一致的 backup，损坏或缺失时保留当前目标并停止。
5. 测试 fixture 包含真实的 5 份嵌套 references，并覆盖相同提交重跑、并发调用、crash 恢复、损坏 backup 和跨平台回滚。

## 临时处置

已将残缺包和未完成事务现场隔离到：

`C:\Users\bridg\.bridgeforge-recovery\20260812-225426-ffd5b8100d0a4ec7814d656e0b084049`

随后运行官方首次安装器，从 canonical `main` 恢复用户级包。实测 Codex command bundle 为 139/139 个文件，
manifest hash 异常为 0，`references/`、`scripts/`、`templates/` 均可读取，未登记 skill 前后摘要一致。

## 验证

- `.venv\Scripts\python.exe tests\harness\test_shared_skill_distribution.py`
- 断言：18 项全部通过；覆盖完整嵌套 bundle、相同提交幂等重跑、并发拒绝、真实 crash 恢复、损坏 backup fail closed、Codex/Claude 跨平台事务回滚。
