---
name: git-sync
description: 分析当前 Git 变更，生成简体中文提交消息，并安全完成 fetch、必要的快进更新、commit、push 和最终同步核验；用户明确调用 /git-sync 或 $git-sync 时使用。
user_invocable: true
argument: 无
model: sonnet
---

# git-sync — 提交并推送

## 定位与边界

用户显式调用即授权本轮执行 Git 同步闭环。优先使用项目提供的确定性脚本；自动化只覆盖安全机械步骤，任何分叉、冲突、缺 upstream 或破坏性恢复都必须停止并交回主对话。

## 输入

- 当前仓库、分支、upstream、工作区与暂存区状态。
- `git diff` / `git diff --cached` 的真实变更。
- 项目内 `.codex/scripts/codex_git_sync.py` 及相关刷新脚本（存在时）。

## 核心流程

### 1. 只读判断与提交消息

1. 检查状态、diff 和当前分支，概括本轮实际变更。
2. 生成简洁的简体中文消息：`<类型>: <描述>`；类型限 `feat`、`fix`、`refactor`、`perf`、`docs`、`chore`。

### 2. Codex 确定性脚本路径

项目存在 `.codex/scripts/codex_git_sync.py` 时，必须把机械同步阶段分派给 `mechanical-sync-worker`，只运行：

```text
python .codex/scripts/codex_git_sync.py --message "<类型>: <描述>"
```

需要审批时只为该项目脚本申请合理前缀，不分别为 fetch、add、commit 和 push 申请持久规则。脚本可执行 fetch、ahead / behind 判断、安全 stash、`pull --ff-only`、衍生产物刷新、add、commit、push 和最终检查。

若首次运行在 `git fetch`、`.git/FETCH_HEAD`、`Permission denied` 或 `Access is denied` 阶段失败，机械 worker 必须把原始错误返回主对话；主对话必须立即以**完全相同的 repo-local 脚本命令**、`require_escalated` 重试。审批说明仅限：允许 Git 更新当前项目的 `.git/FETCH_HEAD` 等元数据，以完成用户已授权的同步。不得改走手工 Git 命令、修改 `.git` ACL 或扩大到无关目录。重试仍失败时保留原始错误与现场并停止；不得把网络、分叉或凭据错误伪报为权限恢复成功。

除上述确定性的权限恢复外，任何分叉、冲突或失败必须返回主对话处理。

脚本不存在、Python 不可用或用户明确要求逐条执行时，进入标准路径。

### 3. 标准路径

1. 执行 `git fetch origin`，再读取 `git rev-list --left-right --count HEAD...@{u}`。
2. 按状态处理：
   - `0/0` 且工作区干净：报告已同步并退出，不创建空提交。
   - 仅 behind：工作区干净时 `git pull --ff-only`；有未提交变更时 `git stash push -u`，快进后 `git stash pop`。
   - 仅 ahead 或存在本地变更：继续提交闭环。
   - diverged：展示双方提交摘要，以单题选择让用户决定 rebase、merge 或放弃；当前回合结束，未确认前禁止执行。
3. 暂存前刷新存在的衍生产物：
   - Codex 项目运行 `.codex/scripts/harness_parity_check.py`。
   - 运行当前 agent 的 `memory_rebuild_index.py`。
   - 脚本不存在时静默跳过。
4. 有本地变更时执行 `git add .`，再用 `git diff --cached` 复核提交范围和消息。
5. 执行 commit 和 push；预提交钩子失败时停止并报告真实输出。
6. 最后核验工作区干净，并重新报告 ahead / behind；成功收据必须包含 `0 0`。

## 输出与收据

- 当前分支、upstream、同步前后的 ahead / behind。
- 实际提交消息、commit id 和 push 目标。
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
- 禁止让非 `mechanical-sync-worker` 运行 Codex 确定性脚本。
- 禁止机械 worker 处理分叉、冲突或失败后的决策。
- 禁止只说“已同步”而不提供最终干净状态和 `0 0` 收据。

$ARGUMENTS
