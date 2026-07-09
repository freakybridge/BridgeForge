---
name: git-sync
description: 全自动 Git 提交并推送到 GitHub。分析变更、生成中文消息并执行同步。与 /git-sync（Claude）或 $git-sync（Codex）配合使用时，所有命令行操作默认允许自动运行。
user_invocable: true
argument: 无
model: sonnet
---

# Git Sync Skill (全自动)

此 Skill 实现代码无缝同步流程。

## Codex 低弹窗执行路径

在 Codex 中，若当前项目存在 `.codex/scripts/codex_git_sync.py`，**优先使用该脚本**承接机械 Git 步骤，避免把 `fetch` / `add` / `commit` / `push` 拆成多次权限弹窗。

执行方式：

1. 先按常规只读方式检查状态 / diff，并由模型生成中文提交信息。
2. 只发起一条执行命令：

```bash
python .codex/scripts/codex_git_sync.py --message "<类型>: <描述>"
```

3. 需要 Codex 提权审批时，使用持久前缀规则 `["python", ".codex/scripts/codex_git_sync.py"]`；不要为 `git fetch` / `git add` / `git commit` / `git push` 分别申请持久规则。

脚本只封装安全的机械闭环：`fetch`、ahead/behind 判断、必要时 `stash + pull --ff-only + stash pop`、Codex harness parity 报告刷新（若存在 `.codex/scripts/harness_parity_check.py`）、memory 索引重建、`add`、`commit`、`push`、最终干净检查。遇到 diverged、缺 upstream、stash pop 冲突、push 竞态等情况必须停止报告，不自动 rebase / merge / reset / force push。

若脚本不存在、Python 不可用，或用户明确要求逐条执行，则回退到下面的标准流程。

## 自动化指令

1. **远端状态探测**：先 `git fetch origin`，再用 `git rev-list --left-right --count HEAD...@{u}` 读取 ahead/behind。
2. **根据状态分支处理**：
   - **up-to-date（0/0）+ 无本地变更** → 报告"已同步"后退出，不产生空提交。
   - **仅 behind（0/N）** → 若工作区干净，自动 `git pull --ff-only` 拉取最新进度；若有未提交变更，先 `git stash push -u`，pull 后 `git stash pop`。
   - **仅 ahead（M/0）或本地有未提交变更** → 走原有提交流程（第 3~5 步）。
   - **diverged（M/N，双向都有提交）** → 停下来报告本地/远端提交摘要。> ⛔ **硬契约**：必须用 **AskUserQuestion**（选项：rebase / merge / 放弃）**结束当前回合**；用户未选前**禁止**执行任何 rebase / merge——"静默执行"基调到此失效，此处无豁免。
3. **暂存前刷新衍生产物（根治"sync 完又脏"）**：
   - Codex 项目若存在 `.codex/scripts/harness_parity_check.py`，先刷新 `doc/3_design/codex-harness-parity.md`，维护 Claude/Codex harness 对照清单。
   - 若本项目存在 `.claude/scripts/memory_rebuild_index.py` 或 `.codex/scripts/memory_rebuild_index.py`，再运行对应脚本重抄 MEMORY.md 热区 / MEMORY_COLD.md，让衍生产物在提交前就是最新态。Claude 项目用 `.claude/scripts/...`，Codex 项目用 `.codex/scripts/...`。
   - **Why**：MEMORY.md 由 PostToolUse hook 在 **memory 文件被编辑时**自动重建（SessionStart 兜底，索引是文件集的确定性函数）；若提交的是旧产物，之后一旦触发重建就会再次弄脏工作区 → 被迫再 sync 一次。提前重建 → 提交进去即最新 → 后续重建产出字节一致 → 工作区干净。bridgeforge 系项目 pre-commit 亦会重建并 `git add`（v0.38.0 起），此步是给没有该闸门的仓库兜底。
   - 脚本不存在则**静默跳过**（非 bridgeforge 系下游项目无此机制，不报错）。
4. **暂存变更**：若有本地改动，`git add .` 暂存所有更改（含上一步重建后的 memory 索引）。
5. **智能消息生成**：
   - 使用 `git diff --cached` 分析代码变更。
   - 生成一段简洁的**简体中文**消息。
   - 格式：`<类型>: <描述>`
   - 类型包括：`feat`（新功能）、`fix`（缺陷）、`refactor`（重构）、`perf`（性能）、`docs`（文档）、`chore`（杂务）。
6. **提交并推送**：`git commit` → `git push`。
7. **静默操作**：在配合 `/git-sync`（Claude）或 `$git-sync`（Codex）工作流使用时，直接执行相关命令，不主动请求用户单步确认（除非发生严重错误如冲突或 diverged）。

## 异常处理

- **diverged**：不自动 rebase/merge，必须让用户做决定。
- **`git pull --ff-only` 失败**（远端强推等情况）：停止并报告，不做 `reset --hard` 之类的破坏性恢复。
- **`git stash pop` 冲突**：保留 stash，提示用户手动解决，不要丢弃。
- **`git push` 失败**（push 前未探测到 behind 的竞态）：重跑第 1 步重新判定，不强推。
- 检测并报告预提交钩子（pre-commit hooks）失败。
- 只有在无法自动推断或执行时才中断流程询问用户。
