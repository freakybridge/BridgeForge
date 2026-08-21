---
name: bridgeforge-codex-batch
description: 仅在 bridgeforge-codex 工厂仓库中，按用户本次输入的多个绝对路径串行完成下游骨架升级与 GitHub 保存；其他项目禁止调用。
user_invocable: true
argument: 每行一个下游项目绝对路径
---

# bridgeforge-codex-batch

本 Skill 只能由 bridgeforge-codex 工厂主对话执行。它负责编排，不复制骨架升级或 Git 写逻辑；
辅助脚本仅做只读预检、串行状态控制与结论式汇总。

## 调用硬闸

每次调用先把用户本次输入解析为绝对路径列表；禁止读取、推断或保存固定项目清单。然后在
当前仓库使用项目 `.venv` 运行：

```text
.venv/Scripts/python.exe -B .codex/skills/bridgeforge-codex-batch/scripts/batch_control.py factory-check --factory-root .
```

只有以下事实全部成立时才允许继续：当前 Git 根就是 bridgeforge-codex 工厂；`origin` 是
`https://github.com/freakybridge/BridgeForgeCodex.git`；分支是 `main` 且跟踪
`origin/main`；工作区干净；本地与 `origin/main` 为 `0/0`；工厂 manifest、三项 factory
witness 与 current baseline 验证通过。任一事实失败都必须拒绝分发，其他项目调用也必须
拒绝。

在 `factory-check` 前必须先执行当前仓库官方 `$git-sync`，以取得最新远端证据。若本仓库有
未提交更改，先只给变更结论，并单独确认一次是否保存；完成 `$git-sync` 且再次通过硬闸后
才能预检下游。禁止把本地 `origin/main` 缓存冒充最新 GitHub 状态。

## 一次批次确认

把全部用户输入路径放进同一次只读计划，按输入顺序重复传入 `--target`：

```text
.venv/Scripts/python.exe -B .codex/skills/bridgeforge-codex-batch/scripts/batch_control.py plan --factory-root . --target <path-1> --target <path-2>
```

`plan` 锁定工厂 HEAD、骨架指纹，以及每个目标的 HEAD、分支、upstream、骨架版本、共享
Git 仓库和已有改动摘要。路径缺失、重复或身份不清时先让用户修正，禁止写盘。默认不要向
用户展示计划指纹、绝对路径、HEAD、改动摘要或其他内部收据。

用白话展示项目清单、固定串行顺序、已有改动是否存在，以及“正常项目会升级、提交并推送”
的结果，只统一确认一次。未取得确认时禁止运行 `start`，也禁止执行任何下游写入。确认后运行：

```text
.venv/Scripts/python.exe -B .codex/skills/bridgeforge-codex-batch/scripts/batch_control.py start --factory-root . --target <path> [--target <path> ...] --plan-fingerprint <confirmed-fingerprint>
```

`start` 必须重算计划；任何状态漂移都要重新展示结论并再次确认。状态只写入
`.runtime/bridgeforge-codex-batch/<batch-id>.json`，只服务本次输入；禁止把路径写入配置、
Skill、文档或其他长期项目清单。同一个工厂同时只允许一个 active batch。

## 严格串行执行

一次只能处理一个目标，严格按输入顺序完成全部首次处理，再按原顺序重试异常项目；共享 Git
common dir 的 worktree 同样分别处理且绝不并行：

1. 运行 `begin --state <state> --target <path>`。每次 `begin` 都重新核对锁定的工厂 HEAD、
   骨架指纹、干净同步状态和目标现场；发生漂移时零下游写入。
2. 把主对话工作目录切到该目标，完整执行现有官方 `$bridgeforge-codex`。禁止调用或复制其
   内部 planner/apply 命令。
3. 骨架升级成功后，在同一目标完整执行项目自己的 `$git-sync`。只能运行该项目
   `.venv/Scripts/python.exe .codex/scripts/codex_git_sync.py`；禁止手工拆分 fetch、add、
   commit 或 push。
4. 正常流程结束后只运行 `finish ... --outcome succeeded`。辅助脚本必须亲自验证 current
   baseline、版本戳一致、工作区干净、upstream 存在且 `ahead=0`、`behind=0`，再从真实收据
   生成版本和 GitHub 保存结论；禁止由调用者传入版本或保存结果。
5. 冲突、分叉、缺 upstream、验证失败或需要用户判断时，保留全部现场并运行
   `finish ... --outcome deferred --problem-summary <一句白话原因>`；继续下一个正常项目。

用户的一次批次确认只授权正常升级和 repo-local `$git-sync`。它不授权 force push、reset、
rebase、merge、删除或丢弃改动，也不授权自动解决冲突。下游原有 dirty state 与项目定制必须
由现有两个官方流程按自身合同保留；本 Skill 不得自行 stash、改文件或归因。

## 异常与共性阻断

单项目异常不阻断其他项目。先完成其余正常目标，再留在当前对话逐个解决 deferred 项目。
人工处理导致现场变化后，先运行 `refresh-plan` 生成新计划，用白话展示变化并取得一次异常项目
确认，再运行 `reconfirm --plan-fingerprint <confirmed-fingerprint>`；随后才能 `begin` 重试并
再次走完整的 `$bridgeforge-codex` 与 `$git-sync`。禁止静默吸收漂移。

内部问题签名只能表示稳定根因类别，禁止包含项目路径、commit、逐文件差异或原始 traceback。
只有 `bridgeforge:` 命名空间的同一签名出现在两个不同目标时，状态助手才自动停止分发；普通
Git、网络或凭据问题重复出现也不得判为共性骨架问题。主对话有直接证据证明是通用骨架缺陷
时，即使只有一个目标，也只能用 `bridgeforge:` 签名确认。禁止仅凭相似话术猜测共性。

自动识别共性问题后立即停止所有下游分发，并在 bridgeforge-codex 新建或补充
`doc/2_bugs/*.md`、同步 `doc/README.md`，再运行 `link-common --bug-doc <relative-path>`；有直接
证据时使用 `confirm-common --bug-doc <relative-path>`。没有真实 Bug 文档关联不得进入可修复
阻断状态。先用结论式话术说明问题与修复影响，再单独取得修改工厂源码的确认。

完成修复、验证和本仓库 `$git-sync` 后才能运行 `restart`。它必须证明 Bug 文档已进入新的
factory HEAD、factory HEAD 与骨架 fingerprint 均相对阻断前发生变化、工厂干净且为 `0/0`；
随后重新预检全部目标、增加 generation，并把包括此前成功项目在内的全部目标从头重跑。
原 HEAD、原 fingerprint 或未提交 Bug 文档都必须拒绝重启。

## 用户结果

默认运行 `summary --state <state>`，只向用户报告：项目名称、当前骨架版本、是否已保存到
GitHub、未完成项目的最关键原因、现场是否保留，以及当前唯一下一步。不要复制辅助脚本的
JSON 收据、内部状态枚举、问题签名、Git common dir、逐文件清单或 traceback。只有用户追问
证据或技术细节时，才按其问题范围运行 `summary --technical` 并翻译相关字段。

异常说明必须是单行白话结论，禁止放入路径、traceback、内部字段或逐文件信息。同名项目使用
分支等不敏感信息区分，禁止为区分名称而展示绝对路径。批次全部成功后先展示最终摘要，再运行
`close --state <state>` 删除本次状态；完成时 active batch 必须已释放。

成功示例：`项目 A：骨架 1.4.40，已保存到 GitHub。`

失败示例：`项目 B 尚未完成，原有改动和失败现场均已保留。下一步：先决定如何处理当前冲突。`

$ARGUMENTS
