---
name: create-worktree
description: 在 Windows 上从当前本地 Git 仓库创建带 codex/ 前缀的新分支和永久 worktree，并用 Codex Desktop 打开。用户调用 /create-worktree 或 $create-worktree 并依次传入工作树名、分支名和可选基准分支时使用。
user_invocable: true
argument: 两个必填位置参数，可选第三个基准分支
---

# 创建永久 Git Worktree

只执行随 skill 提供的 `scripts/create_worktree.ps1`。禁止自行拼装另一套 Git 流程，禁止访问远端，禁止清理失败成果。脚本通过 Windows 注册的 `codex://` 协议激活 Codex Desktop，禁止解析或直接执行 `WindowsApps` 内的 `codex.exe`。

## 调用格式

只接受按顺序排列的位置参数：

```text
/create-worktree <工作树名> <分支名> [基准分支]
$create-worktree <工作树名> <分支名> [基准分支]
```

第一个参数是目标工作树的单层目录名，第二个是新分支名。两者均必填；缺失时一次只询问第一个缺失项。禁止要求用户输入 `worktree_name=`、`branch_name=` 或 `base_branch=` 这类变量名。

第三个参数可选。未提供时，脚本优先使用本地 `main`；本地 `main` 不存在时使用本地 `master`；两者都不存在时必须停止并请用户补充第三个参数。

## 权限硬闸

运行脚本前必须使用当前宿主的提升权限机制，为整条脚本命令申请沙箱外执行。原因必须说明为：需要在当前工作区之外的 `desktop.git-worktree-root` 持久创建目录，并启动 Codex Desktop。

禁止先在默认沙箱运行再提升重试；这会造成源仓库的 Git worktree 登记已持久写入，而仓库外目标目录未持久保留的半创建状态。用户不批准提升权限时必须零写入停止。

## 执行

确认当前工作目录就是用户要创建 worktree 的仓库内路径。然后用 Windows PowerShell 5.1 或兼容的 `powershell.exe` 执行：

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<skill-root>\scripts\create_worktree.ps1" `
  -worktree_name "<worktree_name>" `
  -branch_name "<branch_name>"

# 只在用户提供第三个位置参数时改用：
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<skill-root>\scripts\create_worktree.ps1" `
  -worktree_name "<worktree_name>" `
  -branch_name "<branch_name>" `
  -base_branch "<base_branch>"
```

必须将已提供的值作为独立参数传递；第三个值缺失时省略 `-base_branch`。禁止用 `Invoke-Expression` 或拼接命令字符串。脚本会完成全部只读预检，并把唯一写入 Git 的动作限制为 `git worktree add -b`。

## 结果处理

- 退出码 `0`：报告脚本输出的工作树、分支和基准提交。
- 退出码 `2`：创建前检查失败或 Git 创建失败。原样报告错误；禁止自动修复、改名、加数字后缀、清理或重试其他命令。
- 退出码 `3`：Git 成果有效，但 Codex Desktop 协议激活失败。明确报告“部分成功”，保留工作树和分支，并原样给出脚本输出的重试命令。
- 退出码 `4`：Git 创建后验证失败。报告诊断和已保留的成果；禁止自动删除或回滚。

禁止执行 `fetch`、`pull`、`commit`、`merge`、`push`、`prune`、`remove`、`delete`、`reset` 或任何远端、清理、迁移命令。
