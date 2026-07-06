# 安装与卸载

## 安装到 Claude Code

bridgeforge 是一个 Claude Code **用户级 skill**，clone 到 `~/.claude/skills/bridgeforge/` 即可被所有项目调用。

### Windows

```powershell
# PowerShell
git clone https://github.com/<你的用户名>/BridgeForge.git "$env:USERPROFILE\.claude\skills\bridgeforge"
```

或 Git Bash：
```bash
git clone https://github.com/<你的用户名>/BridgeForge.git ~/.claude/skills/bridgeforge
```

### macOS / Linux

```bash
git clone https://github.com/<你的用户名>/BridgeForge.git ~/.claude/skills/bridgeforge
```

### 开发者模式：junction 指向开发仓库（要改 bridgeforge 本体时用这个）

上面的直接 clone 适合**只用不改**的人——它在 `~/.claude/skills/` 下放一份真实副本。

但如果你**既要用、又要维护 bridgeforge 本体**（改 `templates/` / `skills/`、做下游反哺 harvest），别用直接 clone，否则会出现"开发仓库一份 + skill 目录一份"两处副本、改了一边忘同步另一边。正确姿势是把开发仓库放在你自己的工作区，再让 skill 发现目录 **junction 指过去**，物理只留一份：

```powershell
# Windows：开发仓库放哪自己定，例 D:\Quant\BridgeForge
git clone https://github.com/<你的用户名>/BridgeForge.git D:\Quant\BridgeForge
# skill 发现目录 junction 指向开发仓库（NTFS junction，无需管理员）
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\bridgeforge" -Target "D:\Quant\BridgeForge"
```

```bash
# macOS / Linux：用 symlink
git clone https://github.com/<你的用户名>/BridgeForge.git ~/dev/BridgeForge
ln -s ~/dev/BridgeForge ~/.claude/skills/bridgeforge
```

**单一真相源 = 你的开发仓库**。所有编辑、版本 bump、下游 harvest 都只改开发仓库；`~/.claude/skills/bridgeforge` 只是 Claude Code 发现 skill 的透明入口，会实时看到改动，无需任何同步。以后所有操作（含 git）都在开发仓库里做，别去 `~/.claude/skills/` 那个路径操作。

> **验真 & 防骗**：`Get-Item "$env:USERPROFILE\.claude\skills\bridgeforge" -Force` 看到 `LinkType: Junction`、`Target` 指向开发仓库，就是同一份。注意 **Glob / 文件列举会穿透 junction**，把两个路径列成一模一样的内容（连 `.git/objects` 哈希都对应）——那不是两份副本，是同一份。

## 验证安装

打开任意项目，启动 Claude Code，输入：

```
/bridgeforge
```

如果 skill 列表里能看到 `bridgeforge`（描述是"在新项目里铺设标准化的..."），说明安装成功。

## 升级

```bash
cd ~/.claude/skills/bridgeforge
git pull
```

模板更新后**不会自动重铺**已有项目——已铺设的项目保持原样，新项目调用 skill 才会拿到新模板。

如果想把更新同步到已有 Claude 项目，手动 diff `~/.claude/skills/bridgeforge/templates/claude/` 与 `<已有项目>/.claude/` 对比；Codex 项目则对比 `templates/codex/` 与 `<已有项目>/.codex/`。切换目标 agent 时优先用 `/bridgeforge switch <claude|codex> --dry-run` 预览。

> 开发者模式（junction，见上）下你自己就是上游，不需要 `git pull`——直接在开发仓库改并提交即可，`~/.claude/skills/bridgeforge` 会实时反映。

## 卸载

```bash
rm -rf ~/.claude/skills/bridgeforge
```

**注意**：卸载 skill 不会影响已经用 skill 铺过骨架的项目——它们的 CLAUDE.md / rules / memory 都在项目自己的 git 里。

## 前置依赖

- **Git**：clone 用
- **Bash 或 PowerShell**：跑 junction 脚本用
- **Claude Code CLI**：[安装文档](https://docs.claude.com/claude-code)

可选：
- 项目主语言对应的工具链（不影响 skill 本身，只影响后续填快速命令时的命令是否能跑通）

## 常见问题

### Q：skill 不出现在 Claude Code 列表里

检查：
1. 路径必须是 `~/.claude/skills/bridgeforge/SKILL.md`（不是 `~/.claude/skills/bridgeforge/bridgeforge/SKILL.md`，clone 时不要嵌套）
2. SKILL.md 第一行的 frontmatter `description:` 必须存在
3. 重启 Claude Code 让它重新扫描 skill 目录

### Q：Windows 下 junction 脚本说"权限不足"

Windows 创建 junction 通常**不需要**管理员权限（这是 junction 与 symlink 的区别），但需要：
- PowerShell 的脚本执行策略允许：`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
- 目标目录所在卷支持 NTFS（FAT32 不支持）

如果跑的是 `setup-junction.sh` 创建 symlink，那需要 Windows 10+ 开发者模式或管理员权限。

### Q：已经手动建过 CLAUDE.md / rules，能跑 skill 吗

能。skill 检测到已有文件会问你是 (A) 跳过 (B) 备份覆盖 (C) 退出，由你拍板。

### Q：可以只用模板不用 skill 吗

可以。模板是普通文件，直接 clone 仓库后按目标 agent 手动复制：
- Claude：以 `templates/claude/` 为源，生成 `CLAUDE.md` + `.claude/`
- Codex：以 `templates/codex/` 为源，生成 `AGENTS.md` + `.codex/`

不要整包复制 `templates/`，它现在只是两套 agent 骨架的容器目录。手动模式下仍需自己替换占位符 + 跑 junction 脚本。
