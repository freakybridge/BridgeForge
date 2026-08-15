---
name: bridgeforge
description: 在 Windows 项目里铺设或更新标准化的 Claude/Codex 协作骨架（CLAUDE.md 或 AGENTS.md、rules、memory、hooks、doc 分层），并从 GitHub main 强制同步受管用户级 skill。用户提到 bridgeforge、项目骨架初始化、同步上游模板、switch claude/codex、Codex/Claude 入口 /bridgeforge 时使用。
user_invocable: true
argument: 仅支持无参数，或 switch claude|codex
model: sonnet
---

# bridgeforge — 项目协作骨架初始化 / 更新

## 定位与边界

给新项目安装或维护 Claude Code / Codex 协作骨架：入口文件、rules、memory、hooks、settings、doc 分层和用户级通用 skills。

`bridgeforge` 是用户级全局入口，必须由主对话完成共享更新、判场、用户确认和模式编排；不按下游 18-skill manifest 分派 named custom agent。

用户只需记住：

- `/bridgeforge`：先从 GitHub `main` 强制同步受管用户级 skill，再维护当前正在运行的 agent 骨架；自动判定 init、既有项目首次接入、adopt 或 update。
- `/bridgeforge switch <claude|codex>`：把另一套骨架的项目语义直接同步到当前宿主的原生骨架；两套骨架长期共存，源端保持不变。

其他参数一律停止并展示以上两种公开用法；禁止公开或接受 `/bridgeforge update`、迁移参数或脚本内部参数。

本文件只保留共享更新、判场、分流、硬红线和验证入口。命中具体模式后，只读取对应 reference；禁止为方便一次性加载全部 references。

## 渐进读取路由

| 命中条件 | 必须读取 |
|---|---|
| 显式 `switch` | [references/switch.md](references/switch.md) |
| 无参数更新收据，或当前项目存在遗留 `.agents/` | [references/user-skill-maintenance.md](references/user-skill-maintenance.md) |
| 全新项目或既有项目首次接入 | [references/init.md](references/init.md) |
| BridgeForge 衍生项目缺版本戳 | [references/adopt.md](references/adopt.md) |
| 已有 `.bridgeforge_version` | [references/update.md](references/update.md) |

`references/` 只包含本 skill 的运行手册；所有手册都由本入口直接链接。不要沿引用链加载无关手册。

## Step 0：平台、命令面与安装包路径硬闸

本 skill 仅支持 Windows。若当前平台不是 Windows，立即停止；禁止下载、创建临时目录、写入用户级目录或尝试 symlink 兼容。

只接受无参数或 `switch claude|codex`。然后按当前 agent 将 `BRIDGEFORGE_HOME` 固定为已安装的完整 command bundle：

| Agent | 用户级 skill 目录 | 项目配置 | 入口 | 项目专属 skill |
|---|---|---|---|---|
| Claude Code | `~/.claude/skills` | `.claude/` | `CLAUDE.md` | `.claude/skills/` |
| Codex | `~/.codex/skills` | `.codex/` | `AGENTS.md` | `.codex/skills/` |

Claude：

```powershell
$ENTRY_COMMAND = "/bridgeforge"
$USER_SKILLS_DIR = Join-Path $env:USERPROFILE ".claude\skills"
$BRIDGEFORGE_COMMAND_DIR = Join-Path $USER_SKILLS_DIR "bridgeforge"
$BRIDGEFORGE_HOME = $BRIDGEFORGE_COMMAND_DIR
$PROJECT_AGENT_DIR = ".claude"
$PROJECT_ENTRY_FILE = "CLAUDE.md"
$PROJECT_SKILLS_DIR = ".claude\skills"
$TEMPLATE_AGENT = "claude"
$CURRENT_HOST = "claude"
```

Codex：

```powershell
$ENTRY_COMMAND = "/bridgeforge"
$USER_SKILLS_DIR = Join-Path $env:USERPROFILE ".codex\skills"
$BRIDGEFORGE_COMMAND_DIR = Join-Path $USER_SKILLS_DIR "bridgeforge"
$BRIDGEFORGE_HOME = $BRIDGEFORGE_COMMAND_DIR
$PROJECT_AGENT_DIR = ".codex"
$PROJECT_ENTRY_FILE = "AGENTS.md"
$PROJECT_SKILLS_DIR = ".codex\skills"
$TEMPLATE_AGENT = "codex"
$CURRENT_HOST = "codex"
```

`BRIDGEFORGE_HOME` 必须包含本 `SKILL.md`、`references/`、`templates/` 和所需 `scripts/`。任一缺失都停止并要求重新运行 Windows 首次安装脚本；禁止回退到 `~/.bridgeforge`、`~/.agents`、其他本机 clone 或当前工作副本。

显式 `switch` 的目标参数必须等于 `$CURRENT_HOST`。Claude 中只允许 `switch claude`，Codex 中只允许 `switch codex`；不匹配时必须在读取同步输入或修改项目文件前报错。`$CURRENT_HOST` 是宿主入口固定传入底层脚本的受限证据，不得取自用户参数。

## Step 1：无参数时更新用户级受管 skill

仅无参数 `/bridgeforge` 执行本步；`switch` 不联网更新。显式运行 command bundle 内参数面
封闭的唯一用户级维护入口：

```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File `
  (Join-Path $BRIDGEFORGE_HOME "scripts\bridgeforge_user_maintenance.ps1") `
  -Action refresh
```

- exit `0`：重新读取同一路径下更新后的 `SKILL.md`，再读取 [用户级 skill 分发收据与当前项目遗留布局](references/user-skill-maintenance.md) 的分发边界与收据章节；本轮直接从 Step 2 继续，不重复执行 updater。
- 非 `0`：报告 updater 输出并停止，不维护当前项目。
- updater 只允许修改 manifest 管理的用户级 skill 与托管账本；不得修改当前项目或其他项目。
- Codex 只可为上述完整脚本路径加固定 `-Action refresh` 建议窄 `prefix_rule`；禁止放宽到
  `powershell`、解释器、其他 action、`bridgeforge_shared_update.ps1` 或任意尾参。
- 禁止用 `git pull`、`git clone`、junction、`~/.agents` 或任何本地工作副本代替 updater。

## Step 2：工厂自检（硬闸）

同时满足以下条件才是 BridgeForge 源头仓库自己：

```powershell
$factoryEntry = Join-Path "templates\$TEMPLATE_AGENT" $PROJECT_ENTRY_FILE
if ((Test-Path -LiteralPath $factoryEntry -PathType Leaf) -and
    (Select-String -LiteralPath "skills\bridgeforge\SKILL.md" -SimpleMatch "项目协作骨架初始化" -Quiet)) {
    "FACTORY_SELF"
}
```

命中 `FACTORY_SELF` 必须立即停止：源头不能 bootstrap、update、adopt 或 switch 自己；改框架应直接编辑 `skills/bridgeforge/`、`doc/0_architecture/`、`templates/` 或其他 `skills/`。

## Step 2.1：项目 Python 3.11+ 一次性 preflight（写入前硬闸）

在 `.agents/` 迁移、switch、init、adopt 或 update 的任何项目写入前，只运行一次以下
preflight，并把本轮唯一解释器锁定为 `$HOOK_PYTHON`：

```powershell
$projectVenv = Join-Path (Get-Location) ".venv"
$HOOK_PYTHON = $null
if (Test-Path -LiteralPath $projectVenv) {
    $venvPython = Join-Path $projectVenv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "BLOCKED: project .venv exists but Scripts/python.exe is missing; PATH fallback is forbidden."
    }
    & $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 2)"
    if ($LASTEXITCODE -ne 0) {
        throw "BLOCKED: project .venv must use Python 3.11+; PATH fallback is forbidden."
    }
    $HOOK_PYTHON = (Resolve-Path -LiteralPath $venvPython).Path
} else {
    foreach ($name in @("python", "python3")) {
        $candidate = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -eq $candidate) { continue }
        & $candidate.Source -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 2)"
        if ($LASTEXITCODE -eq 0) {
            $HOOK_PYTHON = $candidate.Source
            break
        }
    }
    if ($null -eq $HOOK_PYTHON) {
        throw "BLOCKED: Python 3.11+ is required before BridgeForge can modify this project."
    }
}
```

- `.venv` 一旦存在就是唯一候选；缺解释器、损坏或版本 `<3.11` 时禁止回退 PATH。
- preflight 失败后必须立即停止；禁止复制、删除、merge、迁移 `.agents/`、运行 switch
  apply 或写 `.bridgeforge_version`。
- preflight 成功后，本轮所有 Python 命令统一用 `& $HOOK_PYTHON`；禁止重新探测、切换
  解释器或使用裸 `python`。原生 memories、init、update、adopt 与 switch 流程继承同一个值。

## Step 2.2：Codex 原生 memories 只读 planner

仅无参数且当前宿主为 Codex 时执行，并复用 Step 2.1 锁定的 `$HOOK_PYTHON` 运行
`scripts/codex_memory_sync.py`；项目 `.venv` 只负责本轮 setup，脚本必须把该 venv 对应的
Python 3.11+ 基础解释器写入用户级 hook，禁止把任何项目 `.venv` 路径持久化到
`~/.codex/hooks.json`。基础解释器不存在或不稳定时只报告本次原生 memories 配置未完成，
继续项目骨架维护，禁止安装依赖项目目录的用户级 hook。

先读取 Codex `bridgeforge-managed.json` schema v1 的
`consents.native_memories`，再运行只读 `status`；status 分类完成前禁止 setup 或其他写入。
分类完成后也只有下述 `approved + enabled + drift` 分支允许运行 `maintain`：

- `declined`：只记录 gap“用户已选择不启用”，禁止调用 `gh`、修改 config/hooks 或再次询问。
- `approved` 且已启用：先直接只读检查 config、三个精确受管 hook、remote 与 pending/last-sync
  收据。全部健康时不运行用户级 Python，同步由既有 SessionStart / SessionEnd / Stop hook
  幂等补齐；有漂移或配置不完整时，把 command bundle 的
  `codex_memory_sync.py maintain` 归为 safe 幂等修复并 reconcile，不新增业务确认。该动作写
  用户目录且可能访问 GitHub，只能使用窄的非持久平台审批，禁止加入 refresh 的持久规则。
- `approved` 但用户后来关闭任一开关：视为 `disabled_by_user` gap；禁止重复询问、擅自重开
  开关、调用 setup 或 reconcile。只有用户明确要求重新开启时才生成新的 risk。
- 未记录 consent 且未启用：把首次 enable、private 仓库创建与用户级 hook 安装合并为一项
  risk；不得在此处单独询问。
- 未记录 consent 但已启用：健康时视为旧版安装的既有授权，禁止重复询问并只读报告
  `legacy_enabled`；hook/remote 不完整时保留现状并记 gap，禁止冒充健康或擅自运行 maintain。
  用户明确要求关闭或重开时再改变状态。
- 同名 public 仓库：把 public→private 并入同一 risk，禁止另取第二次确认。

唯一风险卡必须提前写明：若用户拒绝首次 enable，BridgeForge 会在既有 ledger 记录
`declined` 以免后续重复询问。用户拒绝后，以非持久平台审批运行
`codex_memory_sync.py decline --confirmed`，仅在既有 Codex ledger 写入 `declined`；明确要求
重新开启时才允许重新生成 risk 计划。用户确认 enable 后才允许执行 setup，并在成功后写
`approved`。Claude ledger 禁止出现 `consents`。

SessionEnd 最多 3 秒内落待同步标记并启动脱离会话的后台 reconciliation，不等待
GitHub 成功回执；最终一致仍由 Stop、下次 SessionStart 或本步骤补齐。关闭任一开关后
已有仓库/hook 保留且 hook no-op。

## Step 2.5：当前项目遗留 `.agents/` 只读 planner

工厂自检未命中后，只检查当前 cwd 根部 `.agents/`。存在时运行专用脚本 `--dry-run`：
已知公共副本删除与无冲突私有 skill 移动进入 risk accumulator；未知、人工修改、目标冲突
或归属不明内容原样保留并进入 gap accumulator，不再硬阻断其他模式。链接、路径逃逸或
planner 自身失败仍是 blocked，且全部项目写入为零。

apply 必须同时传 `--confirmed --plan-fingerprint <dry-run 收据>`；脚本会紧邻重建计划，
fingerprint 漂移则零写入。禁止调用 switch 代替迁移，禁止枚举或修改其他项目。

## Step 3：显式 switch planner 优先

若参数以 `switch` 开头，先完成 Step 0 的宿主匹配硬闸，再读取 [switch 手册](references/switch.md) 并执行直接同步。用户命令面只有：

```text
/bridgeforge switch claude
/bridgeforge switch codex
```

主对话先给底层脚本追加 `--dry-run` 生成只读计划；完成统一累计后才按 Step 4.5 决定
是否去掉 `--dry-run` apply。必须传入入口固定的宿主证据：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "templates\$TEMPLATE_AGENT\scripts\bridgeforge_switch.py") `
  $CURRENT_HOST `
  --current-host $CURRENT_HOST `
  --template-root "$BRIDGEFORGE_HOME" `
  --dry-run
```

禁止要求用户生成、编辑或传入 manifest；`--current-host`、`--template-root` 与其他脚本参数均不属于用户命令面。

switch 每次从 `.claude/`、`.codex/` 及两侧 `.bridgeforge-map.json` 的当前真实文件重新盘点，以另一套骨架为 source、当前宿主骨架为 target。source 始终保持不变，target 接收可安全表达的当前宿主原生 projection；禁止原样复制另一宿主的 hooks、settings、agent 配置、skills 或其他宿主专属资产。根 `CLAUDE.md` / `AGENTS.md` 只盘点和报告，不由 direct-sync 自动写入。

两套 live 骨架同时存在是正常状态，不得删除、归档或移动任一侧。目标 map 位于目标骨架内：`.claude/.bridgeforge-map.json` 或 `.codex/.bridgeforge-map.json`；map 只保存确定性映射、状态和 hash，不保存资产正文、命令、绝对路径或时间戳。

`untranslated`、`stale`、`forked_projection` 或 `conflict` 不阻断其他无歧义语义组同步。存在任一缺口时，switch 仍可完成，但必须明确输出 `completed_with_gaps` 与 `readiness=degraded`；禁止伪称全部等价同步。目标文件与 map 不一致、目标被人工修改、map 缺失/损坏或来源不可信时，一律保留目标并报告冲突，不覆盖、不删除、不猜测 ownership。

项目根已有旧 `.bridgeforge/` 时只提示遗留目录；switch 禁止读取、写入、迁移或删除它，也不得创建新的根 `.bridgeforge/`、archive、receipt、lineage 或 transaction journal。可捕获异常必须精确回滚本次 target/map 改动；kill、强制终止、系统崩溃或断电不承诺自动恢复，下次运行按 map/live 不一致保留并报告 `interrupted-or-modified`。

switch planner 完成后进入 Step 4.8；apply 完成后留在当前宿主，不启动另一宿主，也不进入
init、adopt 或 update。

## Step 4：识别 live 骨架与模式

当前/另一套骨架路径：

| 当前 agent | 当前宿主骨架 | 另一套骨架 |
|---|---|---|
| Claude | `CLAUDE.md` 或 `.claude/` | `AGENTS.md` 或 `.codex/` |
| Codex | `AGENTS.md` 或 `.codex/` | `CLAUDE.md` 或 `.claude/` |

先检查当前版本戳：

```powershell
$versionFile = Join-Path $PROJECT_AGENT_DIR ".bridgeforge_version"
if (Test-Path -LiteralPath $versionFile -PathType Leaf) {
    Get-Content -LiteralPath $versionFile
}
```

无版本戳时检查 BridgeForge 衍生指纹；至少命中 2 项才算衍生：

```powershell
Select-String -LiteralPath $PROJECT_ENTRY_FILE -SimpleMatch "鬼打墙" -Quiet
Select-String -LiteralPath $PROJECT_ENTRY_FILE -SimpleMatch "ctx-budget" -Quiet
Get-ChildItem -LiteralPath (Join-Path $PROJECT_AGENT_DIR "rules") -File -Recurse |
    Select-String -SimpleMatch "OPTIONAL_BEGIN" -Quiet
Test-Path -LiteralPath (Join-Path $PROJECT_AGENT_DIR "rules\meta_rule_design.md") -PathType Leaf
Test-Path -LiteralPath (Join-Path $PROJECT_AGENT_DIR "rules\workflow.md") -PathType Leaf
```

无参数 `/bridgeforge` 只维护当前宿主骨架；另一套骨架存在是长期共存的正常状态，不是冲突，也不会触发隐式 switch。按顺序判定，首个命中即停止继续判场：

| 场景 | 判据 | 路由 |
|---|---|---|
| update | 当前有 `.bridgeforge_version` | `.agents` planner 后读 `update.md`，统一累计 |
| adopt | 无戳，当前指纹 ≥2 | `.agents` planner 后读 `adopt.md`，统一累计 |
| 当前文件冲突 | 无戳，当前入口/rules 存在但指纹不足 | 读 `init.md`；补缺为 safe，whole-file 差异保留 gap |
| 当前缺失、另一套存在 | 当前宿主骨架不存在，另一套存在 | 停止并提示显式运行 `/bridgeforge switch $CURRENT_HOST`；禁止隐式同步 |
| 全新 init | 两套都不存在，cwd 基本为空 | `.agents` planner 后读 `init.md`，统一累计 |
| 既有项目首次接入 | 两套都不存在，但有业务文件/Git/配置 | 保留已有内容；冲突进入 gap，不逐项问 |

普通 `/bridgeforge` 只维护当前 agent。发现另一套时保持原样；禁止把当前宿主的普通 update/adopt/init 扩大成双向同步。

判场完成后锁定本轮唯一状态：

```text
REFRESHED
  ├─ FACTORY_SELF -> STOP
  ├─ PYTHON PREFLIGHT -> `$HOOK_PYTHON` (3.11+) 或 STOP（零项目写入）
  ├─ CODEX NATIVE MEMORIES -> consent/status planner（仅无参数 Codex）
  ├─ LEGACY .agents -> dry-run -> risk / gap accumulator
  ├─ EXPLICIT SWITCH -> switch dry-run -> accumulator
  ├─ UPDATE -> update 手册
  ├─ ADOPT -> adopt 手册
  └─ INIT / EXISTING-ONBOARD -> init 手册
```

禁止在同一轮把 init、adopt、update 混着执行。模式执行中若新证据改变判定，先停止并重新报告判场依据；不得凭惯性继续原分支。

## Step 4.5：统一 safe / risk / gap accumulator

读取本轮唯一模式手册并完成所有只读 planner 后，必须把全部结果归入一个 accumulator：

- `safe`：当前项目内可证明确定、幂等且无需业务判断的补缺、known-hash fast-forward、
  稳定身份 merge、manifest 受管 refresh、无冲突 map projection、验证与 finalization。
- `risk`：有精确 source/target/hash/影响/回滚边界的移动、删除、首次 native memories enable、
  public→private 或无法从项目事实确定且会改变结果的 init/adopt 参数。
- `gap`：人工修改、whole-file 无历史 hash、低置信分类、目标冲突、map 损坏、来源不可信。
  gap 必须保留原样，不得进入 risk，也不得再次询问。

对所有 planner 输出做确定性排序与 canonical JSON 序列化，计算单一
`aggregate_fingerprint=sha256:<64hex>`。没有 risk 时直接执行 safe，业务确认次数为 0。
存在 risk 时只展示一张卡，逐项列路径、动作、影响、可恢复性、fingerprint 与推荐处理，
并且只问一次：`我要执行 [汇总风险动作]，这可能导致 [列明影响]，是否继续?`

用户确认后必须紧邻重跑全部 planner 并重算 aggregate fingerprint；不一致时风险项零写入
并停止，禁止沿用旧授权。用户拒绝时 risk 跳过，safe 继续，gap 与拒绝项合并到收据；
禁止第二轮逐项确认。每个底层 apply 仍须传自己的 confirmed/fingerprint/recheck 参数。
switch dry-run 输出 `risk_fingerprint` 时，真实 apply 必须去掉 `--dry-run` 并精确追加
`--confirmed-risk-fingerprint <本轮值>`；缺失、旧值或不同值必须在任何写入前失败。
所有模式统一输出 `status=completed|completed_with_gaps|failed`、
`readiness=ready|degraded|blocked` 与逐项 gaps。

## Step 4.6：Codex 平台默认调度（仅 init / adopt / update）

Claude 跳过本节。BridgeForge 不再创建、读取或修改项目级模型、reasoning effort 或订阅档位配置；新项目和更新后的受管配置均让 Codex 平台自行按任务选择。若用户要固定模型或思考强度，必须在项目骨架之外自行明确配置，且该选择不属于 BridgeForge 管理范围。

## Step 5：执行唯一模式

用户级 skill 已由 Step 1 的固定入口处理；本步执行 Step 4.5 已授权的 safe/risk 动作，
并保留所有 gaps。本步不得再次复制、覆盖或删除用户级 skill。

只读取本轮模式手册：

- init / 既有项目首次接入：`references/init.md`
- adopt：`references/adopt.md`
- update：`references/update.md`

显式 switch 不执行这三条路线，完成后直接留在当前宿主继续工作。不存在隐式 switch，也不因 target 已存在而回到普通维护模式。

## 传播与数据边界红线

BridgeForge 下沉时按业务专属性分层：

| 内容 | 允许动作 |
|---|---|
| 上游项目 hooks/scripts | 与已知旧模板一致时 safe fast-forward；人工修改或无历史 hash 时保留为 gap |
| manifest 管理的用户级 skill | 只由共享 updater 强制同步；不在项目模式中比对或写入 |
| settings / hooks | merge，不覆盖；Codex hook 只进 `.codex/hooks.json`，settings 移除 hooks；Claude 注册不变；保留 permissions/env/additionalDirectories/第三方 hook |
| rules、入口文件 | 只 diff；人工差异或无历史 hash 时原样保留为 gap |
| memory | init 只创建 `MEMORY.md`；update 每次先运行上游规范审计并展示完整分类计划；Codex 项目 memory 不建用户级 junction |
| `doc/` | 新项目按事实推导布局；已有项目迁移清单进入唯一 risk 卡 |
| 项目专属 skill | 不属于通用去重范围，绝对不动 |

项目骨架通用改进的运行时来源必须是 `$BRIDGEFORGE_HOME/templates/`；用户级 skill 的上游来源必须是 updater 校验的 GitHub `main` manifest。下游副本只是消费者。一次只维护当前 cwd，禁止 AI 自动跨多个项目同步。

## 通用危险红线

- 禁止静默覆盖已有入口文件、rules、settings 或同名定制 skill。
- 禁止静默删除人工修改内容；确定性删除只能进入唯一 risk 卡，未知项保留为 gap。
- 禁止代编架构红线、快速命令和项目结构。
- 禁止跳过 doc 分层、Python 硬依赖或项目 memory 的 context/router；Claude junction 规则保持不变。
- 禁止在 BridgeForge 源头仓库自身运行 bootstrap/update/adopt/switch。
- 禁止自动 `git commit` / `git push`；真实 switch 同样只改工作区。
- 禁止在未解决冲突、未完成验证时写新版本戳；update 只能由
  `bridgeforge_project_finalize.py` 在 memory schema 与严格配置体检均通过后写戳。
- 禁止预建空 memory 分类目录；禁止创建 `memory/_archive/`，完成的 topic
  memory 只由索引降温并保留原路径。
- 禁止把 Claude 与 Codex 的用户级目录、memory 机制或 settings 混用。
- 禁止从账户、账单或用户级 Codex 配置推断订阅档位；只接受用户在 `/bridgeforge` 主对话中的明确声明。

## 验证与输出

只有列出真实命令、断言和覆盖场景，才能说“验证通过”。按模式至少提供：

| 模式 | 最低收据 |
|---|---|
| switch | 脚本真实调用与退出码；target/current-host 匹配；source hash 前后不变；目标 map 路径与确定性内容；目标原生 projection；未原样复制宿主专属资产；`status` / `readiness` / gaps / conflicts；旧根 `.bridgeforge/` 未读写删；可捕获异常回滚或硬中断后的保守冲突 |
| init | 复制/merge 清单；memory 初始仅含 `MEMORY.md`；OPTIONAL 残留检查；snapshot smoke test；Codex context/router 或 Claude junction；版本戳 |
| adopt | 命中指纹、用户确认、写入基线；确认未改既有内容 |
| update | 版本区间与 `[product]`；A-F 分类；上游规范 memory plan / 用户确认 / apply 状态；hook smoke test；finalizer 收据或保留旧戳的 gaps；git diff |
| 用户级 skill 更新 | updater 退出码；目标 commit；Codex/Claude 托管账本结果；第三方 skill 未触碰 |
| `.agents` 迁移 | 当前项目 dry-run、plan fingerprint、唯一卡决定、apply 退出码、未知内容保留 gap |
| 统一确认 | safe/risk/gap 数量；aggregate fingerprint；业务确认次数 0 或 1；`status` / `readiness` / gaps |

最终输出遵循“已做什么 / 验证了什么 / 还剩什么风险”。任何停止条件命中时，说明缺少的证据或用户决定，不得伪称完成。
