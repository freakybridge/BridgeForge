# 安装与卸载

## 安装到 Claude Code

setup_agent 是一个 Claude Code **用户级 skill**，clone 到 `~/.claude/skills/setup_agent/` 即可被所有项目调用。

### Windows

```powershell
# PowerShell
git clone https://github.com/<你的用户名>/setup_agent.git "$env:USERPROFILE\.claude\skills\setup_agent"
```

或 Git Bash：
```bash
git clone https://github.com/<你的用户名>/setup_agent.git ~/.claude/skills/setup_agent
```

### macOS / Linux

```bash
git clone https://github.com/<你的用户名>/setup_agent.git ~/.claude/skills/setup_agent
```

## 验证安装

打开任意项目，启动 Claude Code，输入：

```
/setup_agent
```

如果 skill 列表里能看到 `setup_agent`（描述是"在新项目里铺设标准化的..."），说明安装成功。

## 升级

```bash
cd ~/.claude/skills/setup_agent
git pull
```

模板更新后**不会自动重铺**已有项目——已铺设的项目保持原样，新项目调用 skill 才会拿到新模板。

如果想把更新同步到已有项目，手动 diff `~/.claude/skills/setup_agent/templates/` 与 `<已有项目>/.claude/rules/` 对比。

## 卸载

```bash
rm -rf ~/.claude/skills/setup_agent
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
1. 路径必须是 `~/.claude/skills/setup_agent/SKILL.md`（不是 `~/.claude/skills/setup_agent/setup_agent/SKILL.md`，clone 时不要嵌套）
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

可以。模板是普通 markdown 文件，直接 clone 仓库后手动复制 `templates/` 内容到目标项目即可，自己手动替换占位符 + 跑 junction 脚本。
