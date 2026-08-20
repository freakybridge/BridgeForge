---
name: git-sync
description: 分析当前 Git 变更，生成简体中文提交消息与代码变动效果摘要，并安全完成 fetch、必要的快进更新、commit、push 和最终同步核验；用户明确调用 /git-sync 或 $git-sync 时使用。
user_invocable: true
argument: 无
---

# git-sync — 提交并推送

## 定位与边界

用户显式调用即授权本轮执行 Git 同步闭环。优先使用项目提供的确定性脚本；自动化只覆盖安全机械步骤，任何分叉、冲突、缺 upstream 或破坏性恢复都必须停止并交回主对话。

## 输入

- 当前仓库、分支、upstream、工作区与暂存区状态。
- `git diff` / `git diff --cached` 的真实变更。
- 当前宿主目录内 `.<host>/scripts/codex_git_sync.py` 及相关刷新脚本（存在时）。

## 核心流程

### 1. 只读判断、效果摘要与提交消息

1. 检查状态、diff 和当前分支，概括本轮实际变更。
2. 在运行同步脚本前，根据真实 diff 固化 1-3 条“代码变动效果”：说明增加的功能、修复的问题或改变的系统行为，以及它们带来的实际结果；禁止只罗列文件名、提交类型或“更新了代码”等空话。无法可靠判断时明确标记“未能从 diff 可靠判定”，禁止猜测。
3. 生成简洁的简体中文消息：`<类型>: <描述>`；类型限 `feat`、`fix`、`refactor`、`perf`、`docs`、`chore`。

### 2. 当前宿主确定性脚本路径

Codex 项目使用 `.codex/scripts/codex_git_sync.py`。脚本存在时，主 agent 完成只读范围审查和提交消息决策后，必须直接且只运行该脚本：

```text
.venv/Scripts/python.exe .codex/scripts/codex_git_sync.py --message "<类型>: <描述>"
```

需要审批时只为该项目脚本申请合理前缀，不分别为 fetch、add、commit 和 push 申请持久规则。脚本可执行 fetch、ahead / behind 判断、安全 stash、`pull --ff-only`、自动版本升级与原生版本同步、CHANGELOG 和衍生产物刷新、add、commit、push 和最终检查。它只在创建新提交时升级版本；纯 `$bridgeforge-codex` 骨架更新不升级项目版本。

若首次运行在 `git fetch`、`.git/FETCH_HEAD`、`Permission denied` 或 `Access is denied` 阶段失败，主 agent 必须立即以**完全相同的 repo-local 脚本命令**、`require_escalated` 重试。审批说明仅限：允许 Git 更新当前项目的 `.git/FETCH_HEAD` 等元数据，以完成用户已授权的同步。不得改走手工 Git 命令、修改 `.git` ACL 或扩大到无关目录。重试仍失败时保留原始错误与现场并停止；不得把网络、分叉或凭据错误伪报为权限恢复成功。

除上述确定性的权限恢复外，任何分叉、冲突或失败必须返回主对话处理。

脚本不存在、项目 `.venv` 不可用或当前解释器不属于该项目 `.venv` 时必须停止并报告；禁止回退
PATH Python。即使用户要求逐条执行，也不得退化为手工 fetch、add、commit 或 push。

## 输出与收据

- 当前分支、upstream、同步前后的 ahead / behind。
- 实际提交消息、commit id 和 push 目标。
- 同步成功后输出此前固化的“代码变动效果”，最多 3 条；若本轮无本地变更，则写“本轮没有代码变动，仅确认本地与远端已同步”。
- 工作区最终状态；只有状态干净且 ahead / behind 为 `0 0` 才报告同步完成。
- 失败时给出原始错误阶段和保留的现场状态。

## 停止条件

- diverged、缺 upstream 或无法可靠判定远端状态时，停止并由主对话决定。
- `pull --ff-only` 失败时停止，不改变历史。
- `stash pop` 冲突时保留 stash 和冲突现场，交给用户处理。
- push 失败时重新 fetch 并判定一次；若出现竞态或分叉，停止，不强推。
- pre-commit 或衍生产物刷新失败时停止，不绕过检查。

## 禁止事项

- 禁止自动 rebase、merge、`reset --hard`、force push 或丢弃 stash。
- 禁止在 `0/0` 且无变更时创建空提交。
- repo-local 确定性脚本存在时，禁止主 agent 把 fetch、add、commit、push 拆成手工 Git 命令，或把脚本执行再次委派给其他 agent。
- 禁止脚本或其他 agent 处理分叉、冲突或失败后的决策；这些决策始终留在主对话。
- 禁止用文件清单代替代码变动效果，或因提交后 diff 已清空而省略成功收据中的效果摘要。
- 禁止只说“已同步”而不提供最终干净状态和 `0 0` 收据。

$ARGUMENTS
