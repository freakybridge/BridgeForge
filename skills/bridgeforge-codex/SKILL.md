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

1. 新 `.codex/.bridgeforge_codex_version` 或旧 `.codex/.bridgeforge_version` 存在：update。
2. `.codex/` 或 `AGENTS.md` 存在：adopt。
3. 否则：init。

双戳、异常值或旧版本低于 `0.86.0` 时必须在创建 `.venv` 前阻断且零写入。每个项目必须使用
自己的 CPython 3.11+ `.venv/Scripts/python.exe`。`.venv` 已存在时只能把它锁定为
`$HOOK_PYTHON`；缺失时只有 init/adopt 可以从 PATH 选择一次经验证的 CPython 3.11+，并且
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
- `consent=null + enabled`：健康时视为 `legacy_enabled`；不健康时保留并记 gap，禁止
  擅自 repair。
- 旧字符串 `approved`：只有本地 `remote.txt` 仍指向原
  `bridgeforge-codex-memories` 仓库时，才允许无感迁移为当前长期授权；目标不一致时记
  用户级 gap 并重新进入唯一 risk 卡。

首次 risk 卡必须明确披露：同步整个用户级 `~/.codex/memories/**`、本地较新自动上传、
远端较新自动恢复、生命周期 hook 会持续自动同步、目标必须是指定 private 仓库。确认后
形成长期授权；目录、远端、可见性或协议未变化时，日常同步和 hook 修复不得重复询问。

`repair-hook/setup/decline` 都必须传 `--project-root .`，并属于本轮统一 safe/risk/gap accumulator；
禁止提前执行或另问
一次。`repair-hook` 只能修改用户 hooks 并验证解释器，禁止访问 GitHub、Git、读取 Memory
或调用 `reconcile`。项目骨架更新禁止顺手执行完整 `reconcile`；实际同步只由已授权的
生命周期 hook 独立触发，且每次同步前必须验证长期授权、远端身份与 private 状态。用户级
hook 必须通过当前 Git 根动态调用当前项目 `.venv`；禁止持久化任一项目的绝对 Python 路径。

## 4. 当前项目遗留 `.agents/` planner

只检查 cwd 根部 `.agents/`，禁止枚举其他项目。存在时先运行：

```powershell
& $HOOK_PYTHON `
  (Join-Path $BRIDGEFORGE_CODEX_HOME "scripts\bridgeforge_codex_migrate_layout.py") `
  --project-root . --dry-run
```

已知公共副本删除、无冲突项目私有 skill 移动进入本轮 risk；未知内容、目标冲突或归属不明
内容保留为 gap。apply 必须使用同一计划的 `--plan-fingerprint` 与唯一确认；链接、路径逃逸
或 planner 失败必须阻断。禁止用人工移动代替事务脚本。

## 5. 模式与只读计划

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

plan 必须零写入，并输出 fingerprint、safe、risk、absorption、gap、blocker 与
`action_required_items`。当旧 `AGENTS.md` 无法可靠分类时，必须把
`action_required_items` 按 G1、G2……逐项完整展示：来源行号、内容摘要、无法分类原因、
推荐归属和推荐动作；禁止只显示 gap 数量后让用户再次追问。该清单只提供处置建议，
原文件必须保持不写，且不得为它新增第二次确认。G 项是非执行 review 清单，不得与
可执行的上游吸收 U 项混用；用户选 B 时，只有 U/R/P 等可执行 ID 可直接进入 apply。

## 6. 整轮最多一次确认

把 native memories、`.agents` 布局迁移、版本戳迁移、上游 absorption 和其他项目 risk 汇总成一张清单。无 risk
时零确认；有 risk 时整轮最多确认一次。必须一次展示全部冲突文件，并提供：

- A：执行全部推荐项，包括吸收全部上游受管变更。
- B：只执行用户列出的 ID，也接受自定义区块指令；强提示未选项会留下 gap。
- C：不再执行风险动作；只应用无依赖 safe。

apply 前必须重建 plan 并核对 fingerprint；漂移则零写入并重新展示。

## 7. 事务边界

apply 必须传紧邻计划的 fingerprint 和唯一用户选择。禁止人工 copy、merge、删除或写戳。
同步器必须：

- 只修改 schema v2 逐资产登记的 Codex 目标；
- 保留 project-owned、未知文件和人工定制；
- Planner 必须先用产品侧可信 `version_release.py::evaluate_release_transition()` 检查内存中的
  prospective snapshot；只有通过才允许报告 `ready`；
- Apply 与后续 `$git-sync` 的骨架 transition 必须直接调用同一个 evaluator，分别检查真实
  工作区和提交前快照；禁止另建近似判断；
- 先应用并验证资产，再用同一 evaluator 复核 Git 实际 changed paths，最后写
  `.codex/.bridgeforge_codex_version`；
- 旧戳只有在确认、无 gap 且验证成功时才事务删除；
- release preflight 或其他验证失败时回滚本轮全部写入，并保留旧戳；
- 当前骨架戳已等于目标版本但本轮修改了受管资产时，仍必须按真实 changed paths 运行 preflight；
  禁止虚构 stamp 变化放行同版本修复；
- Claude 项目遗留只提示，不读取、不修改。

## 8. 收据

必须报告用户级刷新 commit、execution_status 与 target_readiness、applied/declined、
gaps、`action_required_items`、blockers、版本戳终态、rollback、验证命令和工作区状态。
项目同步计划与收据必须报告 `release_preflight_status`、ownership classification 与耗时；模拟
预检阻断时必须在首次 plan 按 stable asset id/target/reason 显示 `G*` 清单，禁止先报告
`ready` 或只返回聚合报错。
Native Memory 必须另外报告 `project_readiness`、`user_native_memory_readiness`、长期授权
状态、hook 修复结果和 `remote_reconcile=applied/declined/not_requested`；禁止用项目 ready
掩盖用户级同步 gap，也禁止把本轮未执行的 reconcile 描述成已完成。
`action_required_items` 必须使用上述逐项清单格式，不得折叠为一句“请人工处理”。不得把
`completed_with_gaps` 描述成完美更新；应给出达到 ready 的剩余清单。
