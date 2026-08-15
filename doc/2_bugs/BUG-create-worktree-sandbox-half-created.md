# BUG：create-worktree 默认沙箱留下半创建状态

> 日期：2026-08-15
> 状态：核心 Git 事务已验收；Desktop 成功打开现场 smoke 待补

## 现象

在 `D:\Quant\BridgeForge` 调用 `/create-worktree aaa aaa` 时，Git 登记了 `D:\Quant\CodexWorktree\aaa` 与 `codex/aaa`，但命令结束后目标目录不存在；紧接着 `codex.exe` 启动报 `Access is denied`，脚本意外返回 `1` 而非部分成功码 `3`。

## 根因

- Skill 没有在调用前强制为整条脚本申请沙箱外执行。源仓库 Git 元数据可持久写入，但配置的 worktree 根目录位于当前工作区外，目标目录未持久保留。
- `codex app` 来自 WindowsApps，在受限沙箱中启动被系统拒绝。
- PowerShell 调用异常发生在取得 `$LASTEXITCODE` 之前，原逻辑只处理“进程已启动但返回非零”，没有处理“进程根本无法启动”。

## 修复

- `SKILL.md` 强制整条脚本在首次执行时申请提升权限；未批准时零写入停止，禁止先在默认沙箱试跑。
- PowerShell 脚本捕获 `codex.exe` 启动异常，保留 Git 成果、输出原始错误和重试命令，统一返回 `3`。
- 回归测试覆盖 Codex 进程返回非零与启动阶段抛异常两条路径。

## 清理收据

- 清理前 `git worktree prune --dry-run --verbose --expire now` 只报告 `worktrees/aaa`，原因为 `gitdir file points to non-existent location`。
- 确认 `codex/aaa` 是 `main` 的 ancestor 后，执行 `git worktree prune --verbose --expire now` 和 `git branch -d codex/aaa`；分支删除时指向 `4051fd0`。
- 清理后 `git worktree list --porcelain` 只剩主工作树，`refs/heads/codex/aaa`、`.git/worktrees/aaa` 与 `D:\Quant\CodexWorktree\aaa` 均不存在。
- 2026-08-15，用户明确执行 `$summary 同意验收`，本 Bug 关闭。

## 验收后补充修复

- 后续调用 `/create-worktree aaa bbb` 时，worktree 与 `codex/bbb` 已正确创建，但提升后的执行器仍无法直接执行 WindowsApps 中的 `codex.exe`，因此对话显示失败。
- 启动方式已从 `codex app <PATH>` 改为通过 Windows Shell 打开 `codex://threads/new?path=<encoded-path>`；该协议由 Codex Desktop 注册，不再解析或直接执行 WindowsApps 物理路径。
- 回归测试使用可控 `Start-Process` 替身验证路径编码、协议调用、启动异常时退出码 `3` 以及 Git 成果保留。
- 用户确认删除试用产生且无独有改动的 `D:\Quant\CodexWorktree\aaa` 与 `codex/bbb`；清理后只剩主工作树，并再次执行 `$summary 同意验收`。

## 2026-08-15 系统重构复核

- `create-worktree` 已登记为第二个 Codex `global_entries` 主对话入口，并由 skill metadata hook 机检分发/routing/AGENTS 三方一致。
- 零写入预检、整条脚本提升、Git 成功/Desktop 失败 exit 3、Unicode/reparse/路径冲突均有自动化。
- 自动化只能证明 deep-link 构造与 `Start-Process` 调用，不能证明 Codex Desktop 实际显示了目标项目；该现场项保持未验证。
