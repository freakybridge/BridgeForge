---
name: create-worktree
description: 在 Windows 上从当前本地 Git 仓库的指定基准分支创建带 codex/ 前缀的新分支和永久 worktree，并用 Codex Desktop 打开。仅当用户显式调用 $create-worktree 并提供 worktree_name、branch_name、base_branch 三个具名参数时使用。
---

# 创建永久 Git Worktree

只执行随 skill 提供的 `scripts/create_worktree.ps1`。禁止自行拼装另一套 Git 流程，禁止访问远端，禁止清理失败成果。

## 参数硬闸

按以下顺序检查用户输入，一次只询问第一个缺失项，并在获得答案后再检查下一项：

1. `worktree_name`
2. `branch_name`
3. `base_branch`

禁止推断默认值，禁止把位置参数当成具名参数。三个参数齐全前不得运行脚本。

## 执行

确认当前工作目录就是用户要创建 worktree 的仓库内路径。然后用 Windows PowerShell 5.1 或兼容的 `powershell.exe` 执行：

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<skill-root>\scripts\create_worktree.ps1" `
  -worktree_name "<worktree_name>" `
  -branch_name "<branch_name>" `
  -base_branch "<base_branch>"
```

必须将三个值作为独立参数传递；禁止用 `Invoke-Expression` 或拼接命令字符串。脚本会完成全部只读预检，并把唯一写入 Git 的动作限制为 `git worktree add -b`。

## 结果处理

- 退出码 `0`：报告脚本输出的工作树、分支和基准提交。
- 退出码 `2`：创建前检查失败或 Git 创建失败。原样报告错误；禁止自动修复、改名、加数字后缀、清理或重试其他命令。
- 退出码 `3`：Git 成果有效，但 `codex app` 失败。明确报告“部分成功”，保留工作树和分支，并原样给出脚本输出的重试命令。
- 退出码 `4`：Git 创建后验证失败。报告诊断和已保留的成果；禁止自动删除或回滚。

禁止执行 `fetch`、`pull`、`commit`、`merge`、`push`、`prune`、`remove`、`delete`、`reset` 或任何远端、清理、迁移命令。
