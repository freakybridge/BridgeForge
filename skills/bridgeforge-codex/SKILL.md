---
name: bridgeforge-codex
description: 在 Windows Codex 项目中初始化或事务更新 bridgeforge-codex 协作骨架，并维护受管用户级 skills。用户提到 bridgeforge-codex、Codex 骨架初始化或同步上游模板时使用。
user_invocable: true
argument: 仅支持无参数
---

# bridgeforge-codex

bridgeforge-codex 是 Codex-only 骨架维护入口。只接受无参数
`$bridgeforge-codex`；旧 `$bridgeforge`、`switch`、Claude 项目维护和任意内部参数
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
`scripts/codex_memory_sync.py`。禁止从旧用户目录、本地 clone、当前项目或其他工作副本补文件。
旧 `$bridgeforge`、旧 ledger、旧 Claude Skill 与旧 `.bridgeforge` home 不再支持自动迁移或
清理；发现时只说明需要重新安装当前产品，禁止读取正文或代为删除。

## 2. Python preflight

在运行任何 Python planner、status 或 apply 前，先按以下顺序只读判定并锁定 `$MODE`：

1. current/obsolete 双戳：立即阻断。
2. `.codex/.bridgeforge_codex_version` 是合法版本：update。
3. `.codex/.bridgeforge_version` 是合法 `<1.4.28` 版本：adopt，并进入 destructive rebuild。
4. 已有 `.codex/`、`AGENTS.md` 或 `.githooks/pre-commit` 但无可识别戳：立即阻断。
5. 否则：init。

双戳、缺戳或异常值必须在创建 `.venv` 前阻断且零写入；禁止根据旧合同、目录或文件内容
推断旧项目身份。每个项目必须使用
自己的 CPython 3.11+ `.venv/Scripts/python.exe`。`.venv` 已存在时只能把它锁定为
`$HOOK_PYTHON`；缺失时只有空白 init 或已识别旧戳的 adopt 可以从 PATH 选择一次经验证的
CPython 3.11+，并且
该解释器只能执行：

```powershell
& $BOOTSTRAP_PYTHON `
  -B `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "templates\scripts\project_runtime.py") `
  bootstrap --project-root . --mode $MODE --bootstrap-executable $BOOTSTRAP_PYTHON
```

创建成功后立即把 `.venv/Scripts/python.exe` 锁定为 `$HOOK_PYTHON`，再运行同一模块的
`validate --project-root . --executable $HOOK_PYTHON`。update 缺失 `.venv`，或者现有 `.venv`
损坏、低于 3.11、不是 CPython、路径逃逸时必须阻断，禁止重建或回退 PATH。锁定后本轮所有
Python 命令只能使用 `& $HOOK_PYTHON`，禁止裸 `python` 或中途切换解释器。

## 3. Codex 原生 memories planner

仅无参数入口执行。先读取新 Codex ledger 的 `consents.native_memories`，再用同一
`$HOOK_PYTHON` 运行只读状态检查：

```powershell
& $HOOK_PYTHON `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\codex_memory_sync.py") `
  status --project-root .
```

- `declined`：只记用户级 gap，禁止再次询问或改配置。
- 当前策略的 `approved + enabled + healthy`：no-op；hook 有漂移时把本地-only
  `repair-hook` 归为 safe。该 safe 来自用户已保存的长期授权，不是项目更新授权。
- `approved + disabled_by_user`：保留现状并记 gap，禁止擅自重开。
- `consent=null + disabled`：把首次 `setup` 与 private 仓库、用户 hook 安装合并为本轮
  唯一 risk；拒绝后才运行 `decline --confirmed`，同意后才运行
  `setup --confirmed-enable`。
- `consent=null + enabled`：授权状态损坏，保留现场并阻断；禁止猜测修复或补写授权。

首次 risk 卡必须明确披露：同步整个用户级 `~/.codex/memories/**`、本地较新自动上传、
远端较新自动恢复、生命周期 hook 会持续自动同步、目标必须是指定 private 仓库。确认后
形成长期授权；目录、远端、可见性或协议未变化时，日常同步和 hook 修复不得重复询问。

`repair-hook/setup/decline` 都必须传 `--project-root .`，并属于本轮统一 safe/risk/gap accumulator；
禁止提前执行或另问
一次。`repair-hook` 只能修改用户 hooks 并验证解释器，禁止访问 GitHub、Git、读取 Memory
或调用 `reconcile`。项目骨架更新禁止顺手执行完整 `reconcile`；实际同步只由已授权的
生命周期 hook 独立触发，且每次同步前必须验证长期授权、远端身份与 private 状态。用户级
hook 必须通过当前 Git 根动态调用当前项目 `.venv`；禁止持久化任一项目的绝对 Python 路径。

## 4. 模式与只读计划

继续使用 Python preflight 已锁定的唯一 `$MODE` 和 `$HOOK_PYTHON`，禁止重新判定模式或切换
解释器。按模式只读取一个手册：

| 模式 | 手册 |
|---|---|
| init | [references/init.md](references/init.md) |
| adopt | [references/adopt.md](references/adopt.md) |
| update | [references/update.md](references/update.md) |

三个模式只能调用：

```powershell
& $HOOK_PYTHON `
  -B `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\bridgeforge_codex_project_sync.py") `
  --project-root . --template-root $BRIDGEFORGE_CODEX_HOME --mode $MODE
```

plan 必须零写入，并输出 fingerprint、safe、risk、gap、blocker 与一次性
`PreservationManifest`。
空项目进入 init；旧 `.codex/.bridgeforge_version` 或 current 版本戳 `<1.4.28` 的已识别项目
进入 destructive rebuild；`>=1.4.28` 只允许
通过已安装 current baseline 检查后常规更新。current-only 项目缺戳、双戳、非法戳、合同损坏或公共
资产漂移必须零写阻断；已识别旧戳只用于路由 destructive rebuild，不做增量迁移。

## 5. 整轮最多一次确认

常规 current baseline 更新无 risk 时零确认。旧项目 destructive rebuild 必须先由独立 agent
逐项审计 rules、hooks、AGENTS 项目区、memory 与 Skills，再展示完整
`PreservationManifest`；所有用户决策项必须显式选择 preserve 或 delete。用户逐项确认可
作为整轮最多一次确认的特例，但最终破坏性重装必须同时传
`--confirmed-preservation-manifest`，并且仍只接受一次 `--confirmed-risk`。

apply 前必须重建 plan 并核对 fingerprint；漂移则零写入并重新展示。

## 6. 事务边界

apply 必须传 `--apply --plan-fingerprint <fingerprint>` 和唯一用户选择。禁止人工
copy、merge、删除或写戳。
同步器必须：

- 只修改 schema v3 current-only 合同逐资产登记的 Codex 目标；
- 常规更新保留 project-owned、未知文件和人工定制；破坏性重建严格执行用户确认的
  `PreservationManifest`；
- Planner、Apply、`$git-sync` 与 pre-commit 必须调用同一 `current_baseline.py` 检查器；
- memory 只允许只读兼容检查和派生索引重建，禁止 organize 或移动正文；
- Skill 只允许确定性修复 frontmatter；缺少 description 或 routing 语义时必须阻断；
- 先应用并验证资产，最后写 `.codex/.bridgeforge_codex_version`；
- 任一失败必须回滚本事务全部写入，成功后不得保留 before 包；
- Claude 项目遗留只提示，不读取、不修改。

## 7. 收据

必须报告用户级刷新 commit、execution_status、applied、preserved project asset IDs、
blockers、版本戳终态、rollback、验证命令和工作区状态。
Native Memory 必须另外报告 `project_readiness`、`user_native_memory_readiness`、长期授权
状态、hook 修复结果和 `remote_reconcile=applied/declined/not_requested`；禁止用项目 ready
掩盖用户级同步 gap，也禁止把本轮未执行的 reconcile 描述成已完成。
