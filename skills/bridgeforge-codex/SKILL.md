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
2. `.codex/.bridgeforge_codex_version` 与 `.codex/.bridgeforge_version` 中恰好一个存在且版本合法：`<1.4.31` 时 adopt 并进入 destructive rebuild，`>=1.4.31` 时 update；两个戳文件名使用同一版本规则。
3. 已有 `.codex/`、`AGENTS.md` 或 `.githooks/pre-commit` 但无可识别戳：立即阻断。
4. 否则：init。

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
- 当前策略的 `approved + enabled + hookInstalled + hookRuntimeVerified`：no-op。
- `approved + enabled + hookInstalled + !hookRuntimeVerified`：只记用户级 runtime gap；
  禁止把“已安装”描述成“健康”，禁止重复 repair 或触发 reconcile，等待下一次真实生命周期
  事件产生当前 handler revision 的运行收据。
- `approved + enabled + !hookInstalled`：把本地-only `repair-hook` 归为 safe。该 safe 来自
  用户已保存的长期授权，不是项目更新授权。
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
空项目进入 init；任一合法单戳版本 `<1.4.31` 的已识别项目进入 destructive rebuild；
`>=1.4.31` 只允许
通过已安装 current baseline 检查后常规更新。current-only 项目缺戳、双戳、非法戳、合同损坏或公共
资产漂移必须零写阻断；旧戳文件名在通过 current-only 校验后由同一事务删除，最后只写当前戳。

## 5. 整轮最多一次确认

常规 current baseline 更新无 risk 时零确认。旧项目 destructive rebuild 必须先由独立 agent
逐项审计 rules、hooks、AGENTS 项目区、memory 与 Skills，再展示完整
`PreservationManifest`；所有用户决策项必须显式选择 preserve 或 delete。用户逐项确认可
作为整轮最多一次确认的特例，但最终破坏性重装必须同时传
`--confirmed-preservation-manifest`，并且仍只接受一次 `--confirmed-risk`。

发现散落 Hook、非 canonical 命令或无法闭合的目录时，同步器必须零写阻断，禁止猜测依赖。
独立 Agent 只能先在临时副本或受控前置步骤中把它整理为
`.codex/hooks/project_XXXX/entrypoint.py` 自包含目录并闭合 `.codex/hooks.json` 注册，再重新生成
`PreservationManifest` 逐项确认。

apply 前必须重建 plan 并核对 fingerprint；漂移则零写入并重新展示。

## 6. 事务边界

apply 必须传 `--apply --plan-fingerprint <fingerprint>` 和唯一用户选择。禁止人工
copy、merge、删除或写戳。
同步器必须：

- 只修改 schema v3 current-only 合同逐资产登记的 Codex 目标；
- 常规更新保留 project-owned、未知文件和人工定制；破坏性重建对未知 `.codex/**` 结构
  零写阻断，并严格执行用户确认的 `PreservationManifest`；
- 破坏性重建必须把精确路径 `.codex/find-doc.map.md` 与 `.codex/sync-docs.map.md` 作为
  required-preserve 项目映射原样保留；禁止用 glob 扩大该所有权边界；
- Planner、Apply、`$git-sync` 与 pre-commit 必须调用同一 `current_baseline.py` 检查器；
- memory 只允许只读兼容检查和派生索引重建，禁止 organize 或移动正文；
- Skill 只允许确定性修复 frontmatter；缺少 description 或 routing 语义时必须阻断；
- 先应用并验证资产，最后写 `.codex/.bridgeforge_codex_version`；
- 任一失败必须回滚本事务全部写入，成功后不得保留 before 包；
- Claude 项目遗留只提示，不读取、不修改。

## 7. 用户结果与技术收据

必须先在本轮内部核对完整技术收据，再把用户可见结果翻译为“结论、待处理事项、下一步”三段。
默认回复只帮助用户做决定和继续操作，禁止直接倾倒原始字段、内部枚举或验证流水。

### 7.1 默认用户结果

第一段必须用一句白话说明本轮是否完成，并在成功时给出当前骨架版本。第二段只说明仍会影响
用户的未完成事项；第三段给出现在要执行的唯一动作。动作必须说明在哪里执行、执行什么，以及
完成后会得到什么结果。没有待处理事项时必须明确写“本次操作已结束，无需继续处理”。

- 升级成功且存在本轮产生、尚未提交的骨架文件时，使用以下句式；`{version}` 与 `{count}`
  必须来自本轮真实收据，禁止猜测：

  ```text
  骨架升级已完成，当前骨架版本为 {version}。
  本次升级产生的 {count} 个骨架文件尚未保存到 GitHub。
  现在请在当前 Codex 对话框运行 $git-sync，提交并推送这些文件。
  ```

- 已是最新版本且没有待处理事项时，直接说明当前版本和“无需继续处理”，禁止展示 no-op 的
  planner、validator 或 Native Memory 明细。
- 阻断或失败时，必须先说“骨架升级未完成”；再用白话说明一个最关键原因、是否发生写入或
  是否已回滚；最后只给当前能安全执行的一个动作。禁止把内部失败状态码、blocker 列表或
  traceback 当成用户结论。
- 需要用户确认 risk 时，仍必须披露做决定所必需的范围、影响、保留项和不可恢复边界；但必须
  改写成白话决策题，禁止用 safe/risk/gap、fingerprint 或 asset ID 代替影响说明。
- gap 或 advisory 只有在会影响当前结果、需要用户操作或会改变后续行为时才显示。与本轮目标
  无关且无需操作的 advisory 默认隐藏。
- Native Memory 健康且无需用户操作时默认不单列。未完成验证但无需操作时，只说明“仍在等待
  下一次正常使用完成验证”；需要用户决定或修复时，只说明影响和唯一下一步。禁止默认展示
  `hookInstalled`、`hookRuntimeVerified`、handler revision、最近运行收据或
  `remote_reconcile` 枚举。
- 工作区中无法证明由本轮产生的既有改动，禁止归为“本次升级产生”；必须明确区分本轮骨架
  文件与升级前已有改动。

### 7.2 内部技术收据

用户未追问时，以下内容只用于内部核对，禁止出现在默认回复：用户级刷新 commit、
`execution_status`、applied、preserved project asset IDs、blockers 原文、版本戳路径与终态、
rollback 字段、验证命令和逐文件工作区清单。

Native Memory 技术收据必须内部核对 `project_readiness`、`user_native_memory_readiness`、
长期授权状态、`hookInstalled`、`hookRuntimeVerified`、最近运行收据、hook 修复结果和
`remote_reconcile=applied/declined/not_requested`；禁止用项目 ready 掩盖用户级同步 gap，
也禁止把本轮未执行的 reconcile 描述成已完成。只有用户追问原因、证据或技术细节时，才按
问题范围展开对应字段，禁止一次性补发整份技术清单。
