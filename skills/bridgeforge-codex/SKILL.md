---
name: bridgeforge-codex
description: 在 Windows Codex 项目中初始化或事务更新 bridgeforge-codex 协作骨架，并维护受管用户级 skills。用户提到 bridgeforge-codex、Codex 骨架初始化或同步上游模板时使用。
user_invocable: true
argument: 仅支持无参数
---

# bridgeforge-codex

bridgeforge-codex 是 Codex-only 骨架维护入口。只接受无参数
`/bridgeforge-codex`；旧 `/bridgeforge`、`switch`、Claude 项目维护和任意内部参数
都不属于公开命令面。本 skill 必须由主对话编排。

## 1. 平台、薄入口与产品 home 硬闸

仅支持 Windows。非 Windows 必须在下载或写入前停止。

```powershell
$BRIDGEFORGE_CODEX_ENTRY = Join-Path $env:USERPROFILE ".codex\skills\bridgeforge-codex"
$BRIDGEFORGE_CODEX_HOME = Join-Path $env:USERPROFILE ".bridgeforge-codex"
$PROJECT_AGENT_DIR = ".codex"
$PROJECT_ENTRY_FILE = "AGENTS.md"
```

`$BRIDGEFORGE_CODEX_ENTRY` 只是 Codex 可发现的薄入口，只允许包含 `SKILL.md`、
`references/` 与 bootstrap updater。每轮开始先从薄入口运行一次 updater：

```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File `
  (Join-Path $BRIDGEFORGE_CODEX_ENTRY "scripts\bridgeforge_codex_shared_update.ps1")
```

成功收据必须包含 `BRIDGEFORGE_CODEX_SHARED_UPDATE_RECEIPT`。随后重新读取
`$BRIDGEFORGE_CODEX_HOME\skills\bridgeforge-codex\SKILL.md` 并以新版本继续；本轮禁止再次
刷新。`$BRIDGEFORGE_CODEX_HOME` 必须是普通、干净且 origin 指向官方仓库的完整产品 home，
并包含 `templates/`、`scripts/bridgeforge_codex_project_sync.py`、
`scripts/bridgeforge_codex_user_migrate.py`。禁止从旧用户目录、本地 clone、当前项目或其他
工作副本补文件。

## 2. Python preflight

在运行任何 Python planner 或 apply 前锁定本轮唯一解释器。项目存在 `.venv` 时只能使用
`.venv/Scripts/python.exe`；缺失、损坏或低于 Python 3.11 必须阻断，禁止回退 PATH。
没有 `.venv` 时才可从 PATH 选择一个 Python 3.11+。锁定为 `$HOOK_PYTHON` 后，本轮所有
Python 命令必须使用 `& $HOOK_PYTHON`，禁止裸 `python` 或中途切换解释器。

## 3. 一次性用户级迁移 planner

每轮在刷新成功后运行一次；它同时检查旧 home、旧 Codex ledger 和 Claude managed
ledger。无旧资产时计划为空，不触发确认：

```powershell
$USER_MIGRATION = & $HOOK_PYTHON `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\bridgeforge_codex_user_migrate.py") `
  --user-profile $env:USERPROFILE --source-root $BRIDGEFORGE_CODEX_HOME | Out-String
```

planner 只能退休 ledger/hash 证明受管的旧 Codex bundle 与 Claude skills；第三方、人工
修改、reparse 或 ownership 不明内容必须保留并报告。项目内 `.claude/` 和 `CLAUDE.md`
只检查是否存在并提示“已停止支持”，禁止读取、迁移、删除或阻止 Codex 更新。

把迁移动作并入本轮唯一风险卡。获准后必须传回原 fingerprint：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\bridgeforge_codex_user_migrate.py") `
  --user-profile $env:USERPROFILE --source-root $BRIDGEFORGE_CODEX_HOME `
  --apply --confirmed --plan-fingerprint $USER_MIGRATION_FINGERPRINT
```

失败或 fingerprint 漂移必须停止，禁止手工补删。

## 4. Codex 原生 memories planner

仅无参数入口执行。先读取新 Codex ledger 的 `consents.native_memories`，再用同一
`$HOOK_PYTHON` 运行只读状态检查：

```powershell
& $HOOK_PYTHON `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\codex_memory_sync.py") status
```

- `declined`：只记 gap，禁止再次询问或改配置。
- `approved + enabled + healthy`：no-op；有漂移时把 `maintain` 归为 safe。
- `approved + disabled_by_user`：保留现状并记 gap，禁止擅自重开。
- `consent=null + disabled`：把首次 `setup` 与 private 仓库、用户 hook 安装合并为本轮
  唯一 risk；拒绝后才运行 `decline --confirmed`，同意后才运行
  `setup --confirmed-enable`。
- `consent=null + enabled`：健康时视为 `legacy_enabled`；不健康时保留并记 gap，禁止
  擅自 maintain。

`maintain/setup/decline` 都属于本轮统一 safe/risk/gap accumulator；禁止提前执行或另问
一次。用户级 hook 必须使用稳定基础解释器，禁止持久化项目 `.venv` 路径。

## 5. 当前项目遗留 `.agents/` planner

只检查 cwd 根部 `.agents/`，禁止枚举其他项目。存在时先运行：

```powershell
& $HOOK_PYTHON `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\bridgeforge_codex_migrate_layout.py") `
  --project-root . --dry-run
```

已知公共副本删除、无冲突项目私有 skill 移动进入本轮 risk；未知内容、目标冲突或归属不明
内容保留为 gap。apply 必须使用同一计划的 `--plan-fingerprint` 与唯一确认；链接、路径逃逸
或 planner 失败必须阻断。禁止用人工移动代替事务脚本。

## 6. 模式与只读计划

按以下顺序唯一判定：

1. 新 `.codex/.bridgeforge_codex_version` 或旧 `.codex/.bridgeforge_version` 存在：update。
2. `.codex/` 或 `AGENTS.md` 存在：adopt。
3. 否则：init。

双戳、异常值或旧版本低于 `0.86.0` 时阻断且零写入。按模式只读取一个手册：

| 模式 | 手册 |
|---|---|
| init | [references/init.md](references/init.md) |
| adopt | [references/adopt.md](references/adopt.md) |
| update | [references/update.md](references/update.md) |

三个模式只能调用：

```powershell
& $HOOK_PYTHON `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\bridgeforge_codex_project_sync.py") `
  --project-root . --template-root $BRIDGEFORGE_CODEX_HOME --mode $MODE
```

plan 必须零写入，并输出 fingerprint、safe、risk、absorption、gap 与 blocker。

## 7. 整轮最多一次确认

把用户级迁移、native memories、`.agents` 布局迁移、版本戳迁移、上游 absorption 和其他项目 risk 汇总成一张清单。无 risk
时零确认；有 risk 时整轮最多确认一次。必须一次展示全部冲突文件，并提供：

- A：执行全部推荐项，包括吸收全部上游受管变更。
- B：只执行用户列出的 ID，也接受自定义区块指令；强提示未选项会留下 gap。
- C：不再执行风险动作；只应用无依赖 safe。

apply 前必须重建 plan 并核对 fingerprint；漂移则零写入并重新展示。

## 8. 事务边界

apply 必须传紧邻计划的 fingerprint 和唯一用户选择。禁止人工 copy、merge、删除或写戳。
同步器必须：

- 只修改 schema v2 逐资产登记的 Codex 目标；
- 保留 project-owned、未知文件和人工定制；
- 先应用并验证资产，最后写 `.codex/.bridgeforge_codex_version`；
- 旧戳只有在确认、无 gap 且验证成功时才事务删除；
- 失败时回滚本轮全部写入；
- Claude 项目遗留只提示，不读取、不修改。

## 9. 收据

必须报告用户级迁移/刷新 commit、execution_status 与 target_readiness、applied/declined、
gaps、blockers、版本戳终态、rollback、验证命令和工作区状态。不得把
`completed_with_gaps` 描述成完美更新；应给出达到 ready 的剩余清单。
