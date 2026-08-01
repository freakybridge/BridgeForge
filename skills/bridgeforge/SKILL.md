---
name: bridgeforge
description: 在 Windows 项目里铺设或更新标准化的 Claude/Codex 协作骨架（CLAUDE.md 或 AGENTS.md、rules、memory、hooks、doc 分层），并从 GitHub main 强制同步受管用户级 skill。用户提到 bridgeforge、项目骨架初始化、同步上游模板、switch claude/codex、Codex/Claude 入口 /bridgeforge 时使用。
version: 0.80.0
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

仅无参数 `/bridgeforge` 执行本步；`switch` 不联网更新。显式运行 command bundle 内的 updater：

```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $BRIDGEFORGE_HOME "scripts\bridgeforge_shared_update.ps1")
```

- exit `0`：重新读取同一路径下更新后的 `SKILL.md`，再读取 [用户级 skill 分发收据与当前项目遗留布局](references/user-skill-maintenance.md) 的分发边界与收据章节；本轮直接从 Step 2 继续，不重复执行 updater。
- 非 `0`：报告 updater 输出并停止，不维护当前项目。
- updater 只允许修改 manifest 管理的用户级 skill 与托管账本；不得修改当前项目或其他项目。
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

## Step 2.25：项目 Python 3.11+ 一次性 preflight（写入前硬闸）

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
  解释器或使用裸 `python`。init、update、adopt 与 switch 手册继承同一个值。

## Step 2.5：当前项目遗留 `.agents/` 硬闸

工厂自检未命中后，只检查当前工作目录根部是否存在 `.agents/`。若存在，先读取 [用户级 skill 分发收据与当前项目遗留布局](references/user-skill-maintenance.md)，运行专用迁移脚本的 `--dry-run` 并展示完整计划；只有用户确认后才允许 `--apply`。

未知文件、链接或无法归类内容必须阻断。禁止调用 switch 脚本代替迁移，禁止枚举或修改其他项目。迁移未成功完成前，不得进入 switch、init、adopt 或 update。

## Step 3：显式 switch 优先

若参数以 `switch` 开头，先完成 Step 0 的宿主匹配硬闸，再读取 [switch 手册](references/switch.md) 并执行直接同步。用户命令面只有：

```text
/bridgeforge switch claude
/bridgeforge switch codex
```

主对话按当前宿主调用 command bundle 内的底层脚本，必须传入入口固定的宿主证据：

```powershell
& $HOOK_PYTHON (Join-Path $BRIDGEFORGE_HOME "templates\$TEMPLATE_AGENT\scripts\bridgeforge_switch.py") `
  $CURRENT_HOST `
  --current-host $CURRENT_HOST `
  --template-root "$BRIDGEFORGE_HOME"
```

禁止要求用户生成、编辑或传入 manifest；`--current-host`、`--template-root` 与其他脚本参数均不属于用户命令面。

switch 每次从 `.claude/`、`.codex/` 及两侧 `.bridgeforge-map.json` 的当前真实文件重新盘点，以另一套骨架为 source、当前宿主骨架为 target。source 始终保持不变，target 接收可安全表达的当前宿主原生 projection；禁止原样复制另一宿主的 hooks、settings、agent 配置、skills 或其他宿主专属资产。根 `CLAUDE.md` / `AGENTS.md` 只盘点和报告，不由 direct-sync 自动写入。

两套 live 骨架同时存在是正常状态，不得删除、归档或移动任一侧。目标 map 位于目标骨架内：`.claude/.bridgeforge-map.json` 或 `.codex/.bridgeforge-map.json`；map 只保存确定性映射、状态和 hash，不保存资产正文、命令、绝对路径或时间戳。

`untranslated`、`stale`、`forked_projection` 或 `conflict` 不阻断其他无歧义语义组同步。存在任一缺口时，switch 仍可完成，但必须明确输出 `completed_with_gaps` 与 `readiness=degraded`；禁止伪称全部等价同步。目标文件与 map 不一致、目标被人工修改、map 缺失/损坏或来源不可信时，一律保留目标并报告冲突，不覆盖、不删除、不猜测 ownership。

项目根已有旧 `.bridgeforge/` 时只提示遗留目录；switch 禁止读取、写入、迁移或删除它，也不得创建新的根 `.bridgeforge/`、archive、receipt、lineage 或 transaction journal。可捕获异常必须精确回滚本次 target/map 改动；kill、强制终止、系统崩溃或断电不承诺自动恢复，下次运行按 map/live 不一致保留并报告 `interrupted-or-modified`。

switch 完成后在当前宿主继续工作，不启动另一宿主，也不进入 init、adopt 或 update。

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
| update | 当前有 `.bridgeforge_version` | 遗留布局硬闸后读 `update.md` |
| adopt | 无戳，当前指纹 ≥2 | 遗留布局硬闸后读 `adopt.md` |
| 当前文件冲突 | 无戳，当前入口/rules 存在但指纹不足 | 遗留布局硬闸后读 `init.md`，必须先问保留补缺/备份覆盖/退出 |
| 当前缺失、另一套存在 | 当前宿主骨架不存在，另一套存在 | 停止并提示显式运行 `/bridgeforge switch $CURRENT_HOST`；禁止隐式同步 |
| 全新 init | 两套都不存在，cwd 基本为空 | 遗留布局硬闸后读 `init.md` |
| 既有项目首次接入 | 两套都不存在，但有业务文件/Git/配置 | 说明保留已有内容；遗留布局硬闸后读 `init.md`，冲突逐项问 |

普通 `/bridgeforge` 只维护当前 agent。发现另一套时保持原样；禁止把当前宿主的普通 update/adopt/init 扩大成双向同步。

判场完成后锁定本轮唯一状态：

```text
REFRESHED
  ├─ FACTORY_SELF -> STOP
  ├─ PYTHON PREFLIGHT -> `$HOOK_PYTHON` (3.11+) 或 STOP（零项目写入）
  ├─ LEGACY .agents -> dry-run -> 用户确认 -> apply 或 STOP
  ├─ EXPLICIT SWITCH -> switch 手册 -> DONE
  ├─ UPDATE -> update 手册
  ├─ ADOPT -> adopt 手册
  └─ INIT / EXISTING-ONBOARD -> init 手册
```

禁止在同一轮把 init、adopt、update 混着执行。模式执行中若新证据改变判定，先停止并重新报告判场依据；不得凭惯性继续原分支。

## Step 4.5：Codex 平台默认调度（仅 init / adopt / update）

Claude 跳过本节。BridgeForge 不再创建、读取或修改项目级模型、reasoning effort 或订阅档位配置；新项目和更新后的受管配置均让 Codex 平台自行按任务选择。若用户要固定模型或思考强度，必须在项目骨架之外自行明确配置，且该选择不属于 BridgeForge 管理范围。

## Step 5：执行唯一模式

用户级 skill 已由 Step 1 的 updater 处理，当前项目遗留 `.agents/` 已由 Step 2.5 阻断或迁移。本步不得再次复制、覆盖或删除用户级 skill。

只读取本轮模式手册：

- init / 既有项目首次接入：`references/init.md`
- adopt：`references/adopt.md`
- update：`references/update.md`

显式 switch 不执行这三条路线，完成后直接留在当前宿主继续工作。不存在隐式 switch，也不因 target 已存在而回到普通维护模式。

## 传播与数据边界红线

BridgeForge 下沉时按业务专属性分层：

| 内容 | 允许动作 |
|---|---|
| 上游项目 hooks/scripts | 比对后覆盖；存在差异先展示并确认 |
| manifest 管理的用户级 skill | 只由共享 updater 强制同步；不在项目模式中比对或写入 |
| settings / hooks | merge，不覆盖；Codex hook 只进 `.codex/hooks.json`，settings 移除 hooks；Claude 注册不变；保留 permissions/env/additionalDirectories/第三方 hook |
| rules、入口文件 | 只 diff，用户逐段决定 |
| memory | init 只创建 `MEMORY.md`；update 先展示迁移计划，用户补齐低置信分类并明确确认后才 apply |
| `doc/` | 新项目按模板创建；已有项目仅按 `references/update.md` 展示迁移清单并经用户确认后移动 |
| 项目专属 skill | 不属于通用去重范围，绝对不动 |

项目骨架通用改进的运行时来源必须是 `$BRIDGEFORGE_HOME/templates/`；用户级 skill 的上游来源必须是 updater 校验的 GitHub `main` manifest。下游副本只是消费者。一次只维护当前 cwd，禁止 AI 自动跨多个项目同步。

## 通用危险红线

- 禁止静默覆盖已有入口文件、rules、settings 或同名定制 skill。
- 禁止批量/静默删除项目级重复 skill、用户级扁平 shadow 或退役 skill；每项单独确认。
- 禁止代编架构红线、快速命令和项目结构。
- 禁止跳过 doc 分层、Python 硬依赖或 memory junction。
- 禁止在 BridgeForge 源头仓库自身运行 bootstrap/update/adopt/switch。
- 禁止自动 `git commit` / `git push`；真实 switch 同样只改工作区。
- 禁止在未解决冲突、未完成验证时写新版本戳。
- 禁止预建空 memory 分类目录；禁止创建 `memory/_archive/`，完成的 topic
  memory 只由索引降温并保留原路径。
- 禁止把 Claude 与 Codex 的用户级目录、memory 机制或 settings 混用。
- 禁止从账户、账单或用户级 Codex 配置推断订阅档位；只接受用户在 `/bridgeforge` 主对话中的明确声明。

## 验证与输出

只有列出真实命令、断言和覆盖场景，才能说“验证通过”。按模式至少提供：

| 模式 | 最低收据 |
|---|---|
| switch | 脚本真实调用与退出码；target/current-host 匹配；source hash 前后不变；目标 map 路径与确定性内容；目标原生 projection；未原样复制宿主专属资产；`status` / `readiness` / gaps / conflicts；旧根 `.bridgeforge/` 未读写删；可捕获异常回滚或硬中断后的保守冲突 |
| init | 复制/merge 清单；memory 初始仅含 `MEMORY.md`；OPTIONAL 残留检查；snapshot smoke test；memory junction；版本戳 |
| adopt | 命中指纹、用户确认、写入基线；确认未改既有内容 |
| update | 版本区间与 `[product]`；A-F 分类；memory plan / 用户确认 / apply 状态；hook smoke test；新版本戳；git diff |
| 用户级 skill 更新 | updater 退出码；目标 commit；Codex/Claude 托管账本结果；第三方 skill 未触碰 |
| `.agents` 迁移 | 当前项目 dry-run 清单；用户确认；apply 退出码；未知内容阻断结果 |
| Codex 订阅档位 | marker 的 `tier`；脚本退出码；config/implementation 实际模型与 effort；用户级配置未触碰 |

最终输出遵循“已做什么 / 验证了什么 / 还剩什么风险”。任何停止条件命中时，说明缺少的证据或用户决定，不得伪称完成。
