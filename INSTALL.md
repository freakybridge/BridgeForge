# 安装与卸载

## 安装总览

bridgeforge 现在分成三块：

```text
~/.bridgeforge/                         # 完整 BridgeForge 工厂源仓库
~/.agents/skills/bridgeforge/SKILL.md    # Codex 薄入口
~/.claude/skills/bridgeforge/SKILL.md    # Claude Code 薄入口
```

`~/.agents/skills/bridgeforge/` 和 `~/.claude/skills/bridgeforge/` 都只放一个极小 wrapper `SKILL.md`，这样 `/bridgeforge` 才会出现在各自命令清单里。完整仓库统一放在 `~/.bridgeforge/`，避免把同时包含 Claude / Codex 两套骨架的工厂误看成某个 agent 的私有目录。`~/.codex/` 是 Codex 配置和 memory 系统路径，不是用户级 skill 安装目录。

> 不要把完整 BridgeForge 仓库放在 `~/.agents/skills/bridgeforge/` 或 `~/.claude/skills/bridgeforge/`。入口货架只放 wrapper，完整工厂只放 `~/.bridgeforge/`。
> 如果旧版曾安装到 `~/.codex/skills/bridgeforge`，必须先把这个旧入口移出 `~/.codex/skills/`。否则 Codex 可能继续扫到 BridgeForge 的子 skill，却仍然不显示根 `/bridgeforge`。

## 旧完整仓库迁移到 `.bridgeforge`

如果机器上已有旧布局，先把完整仓库或 junction/symlink 移到 `~/.bridgeforge`。这一步只移动目录入口本身；如果旧路径是 junction/symlink，不会删除它指向的真实开发仓库。

### Windows

```powershell
$new = "$env:USERPROFILE\.bridgeforge"
$candidates = @(
  "$env:USERPROFILE\.agents\bridgeforge-home",
  "$env:USERPROFILE\.claude\skills\bridgeforge"
)

if (!(Test-Path $new)) {
  foreach ($old in $candidates) {
    if ((Test-Path "$old\SKILL.md") -and (Test-Path "$old\templates")) {
      Move-Item -LiteralPath $old -Destination $new
      break
    }
  }
}
```

然后重建两个 agent 的薄入口：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills\bridgeforge" | Out-Null
Copy-Item "$env:USERPROFILE\.bridgeforge\scripts\codex_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.agents\skills\bridgeforge\SKILL.md"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills\bridgeforge" | Out-Null
Copy-Item "$env:USERPROFILE\.bridgeforge\scripts\claude_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.claude\skills\bridgeforge\SKILL.md"
```

### macOS / Linux

```bash
if [ ! -e ~/.bridgeforge ]; then
  for old in ~/.agents/bridgeforge-home ~/.claude/skills/bridgeforge; do
    if [ -f "$old/SKILL.md" ] && [ -d "$old/templates" ]; then
      mv "$old" ~/.bridgeforge
      break
    fi
  done
fi
```

然后重建两个 agent 的薄入口：

```bash
mkdir -p ~/.agents/skills/bridgeforge ~/.claude/skills/bridgeforge
cp ~/.bridgeforge/scripts/codex_bridgeforge_entry.SKILL.md ~/.agents/skills/bridgeforge/SKILL.md
cp ~/.bridgeforge/scripts/claude_bridgeforge_entry.SKILL.md ~/.claude/skills/bridgeforge/SKILL.md
```

## 安装到 Codex

### Windows

```powershell
git clone https://github.com/<你的用户名>/BridgeForge.git "$env:USERPROFILE\.bridgeforge"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills\bridgeforge" | Out-Null
Copy-Item "$env:USERPROFILE\.bridgeforge\scripts\codex_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.agents\skills\bridgeforge\SKILL.md"
```

旧安装迁移（只移动链接/旧入口，不删除真实仓库）：

```powershell
$old = "$env:USERPROFILE\.codex\skills\bridgeforge"
if (Test-Path $old) {
  $backup = "$env:USERPROFILE\.codex\backups\bridgeforge-codex-skills-legacy-$(Get-Date -Format yyyyMMdd-HHmmss)"
  New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\backups" | Out-Null
  Move-Item -LiteralPath $old -Destination $backup
}
```

### macOS / Linux

```bash
git clone https://github.com/<你的用户名>/BridgeForge.git ~/.bridgeforge
mkdir -p ~/.agents/skills/bridgeforge
cp ~/.bridgeforge/scripts/codex_bridgeforge_entry.SKILL.md ~/.agents/skills/bridgeforge/SKILL.md
```

旧安装迁移：

```bash
if [ -e ~/.codex/skills/bridgeforge ]; then
  mkdir -p ~/.codex/backups
  mv ~/.codex/skills/bridgeforge ~/.codex/backups/bridgeforge-codex-skills-legacy-$(date +%Y%m%d-%H%M%S)
fi
```

## 安装到 Claude Code

Claude Code 也使用薄入口。完整 BridgeForge 工厂仍在 `~/.bridgeforge/`，`~/.claude/skills/bridgeforge/` 只放 wrapper。

### Windows

```powershell
# PowerShell
# 若已安装 Codex 且 $env:USERPROFILE\.bridgeforge 已存在，跳过 clone
git clone https://github.com/<你的用户名>/BridgeForge.git "$env:USERPROFILE\.bridgeforge"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills\bridgeforge" | Out-Null
Copy-Item "$env:USERPROFILE\.bridgeforge\scripts\claude_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.claude\skills\bridgeforge\SKILL.md"
```

或 Git Bash：
```bash
# 若已安装 Codex 且 ~/.bridgeforge 已存在，跳过 clone
git clone https://github.com/<你的用户名>/BridgeForge.git ~/.bridgeforge
mkdir -p ~/.claude/skills/bridgeforge
cp ~/.bridgeforge/scripts/claude_bridgeforge_entry.SKILL.md ~/.claude/skills/bridgeforge/SKILL.md
```

### macOS / Linux

```bash
# 若已安装 Codex 且 ~/.bridgeforge 已存在，跳过 clone
git clone https://github.com/<你的用户名>/BridgeForge.git ~/.bridgeforge
mkdir -p ~/.claude/skills/bridgeforge
cp ~/.bridgeforge/scripts/claude_bridgeforge_entry.SKILL.md ~/.claude/skills/bridgeforge/SKILL.md
```

### 开发者模式：完整工厂用 junction，两个 agent 都用叶子入口

上面的直接 clone 适合**只用不改**的人——它在 `~/.bridgeforge` 下放一份真实副本。

如果你**既要用、又要维护 bridgeforge 本体**（改 `templates/` / `skills/`、做下游反哺 harvest），让 `~/.bridgeforge` 指向开发仓库；Codex 和 Claude Code 的用户级 skill 目录都只放 wrapper。

```powershell
# Windows：开发仓库放哪自己定，例 D:\Quant\BridgeForge
git clone https://github.com/<你的用户名>/BridgeForge.git D:\Quant\BridgeForge
# 完整 BridgeForge 工厂指向开发仓库
New-Item -ItemType Junction -Path "$env:USERPROFILE\.bridgeforge" -Target "D:\Quant\BridgeForge"
# Codex slash 发现目录只放 wrapper
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills\bridgeforge" | Out-Null
Copy-Item "D:\Quant\BridgeForge\scripts\codex_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.agents\skills\bridgeforge\SKILL.md"
# Claude Code skill 发现目录也只放 wrapper
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills\bridgeforge" | Out-Null
Copy-Item "D:\Quant\BridgeForge\scripts\claude_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.claude\skills\bridgeforge\SKILL.md"
```

```bash
# macOS / Linux：用 symlink
git clone https://github.com/<你的用户名>/BridgeForge.git ~/dev/BridgeForge
# 完整 BridgeForge 工厂指向开发仓库
ln -s ~/dev/BridgeForge ~/.bridgeforge
# Codex slash 发现目录只放 wrapper
mkdir -p ~/.agents/skills/bridgeforge
cp ~/dev/BridgeForge/scripts/codex_bridgeforge_entry.SKILL.md ~/.agents/skills/bridgeforge/SKILL.md
# Claude Code slash 发现目录也只放 wrapper
mkdir -p ~/.claude/skills/bridgeforge
cp ~/dev/BridgeForge/scripts/claude_bridgeforge_entry.SKILL.md ~/.claude/skills/bridgeforge/SKILL.md
```

**单一真相源 = 你的开发仓库**。所有编辑、版本 bump、下游 harvest 都只改开发仓库；`~/.bridgeforge` 指向它。Codex 的 `~/.agents/skills/bridgeforge` 和 Claude Code 的 `~/.claude/skills/bridgeforge` 都只是叶子入口 wrapper，模板和脚本读取 `$HOME/.bridgeforge`。

> **验真 & 防骗**：`Get-Item "$env:USERPROFILE\.bridgeforge" -Force` 才是完整仓库或 junction；`Get-Item "$env:USERPROFILE\.agents\skills\bridgeforge" -Force` 和 `Get-Item "$env:USERPROFILE\.claude\skills\bridgeforge" -Force` 应是普通目录，里面只需要 `SKILL.md`。

## 验证安装

打开任意项目，启动 Codex 或 Claude Code，输入：

```
# Codex
/bridgeforge

# Claude Code
/bridgeforge
```

如果 skill 列表里能看到 `bridgeforge`（描述是"在新项目里铺设或更新标准化的..."），说明安装成功。

## 升级

```bash
# Codex
cd ~/.bridgeforge
git pull

# Claude Code
cd ~/.bridgeforge
git pull
```

模板更新后**不会自动重铺**已有项目——已铺设的项目保持原样，新项目调用 skill 才会拿到新模板。

如果想把更新同步到已有项目，Codex 项目对比 `~/.bridgeforge/templates/codex/` 与 `<已有项目>/.codex/`；Claude 项目对比 `~/.bridgeforge/templates/claude/` 与 `<已有项目>/.claude/`。切换目标 agent 时优先用 `/bridgeforge switch <claude|codex> --dry-run` 预览完整计划：旧 agent 会归档到当前项目 `.bridgeforge/archive/<agent>/<timestamp>/`，目标 agent 优先从当前项目归档恢复、否则从上游模板安装；memory 合并到目标 agent，settings 逐项确认，hooks / skills / rules / 入口文件只归档不自动迁移。若目标 live path 已存在，switch 会停止，不覆盖。

> 开发者模式（junction / symlink，见上）下你自己就是上游，不需要在 home 目录 `git pull`；直接在开发仓库改并提交即可。

## 卸载

```bash
# Codex
rm -rf ~/.agents/skills/bridgeforge

# Claude Code
rm -rf ~/.claude/skills/bridgeforge

# 完整 BridgeForge 工厂
rm -rf ~/.bridgeforge
```

**注意**：卸载 skill 不会影响已经用 skill 铺过骨架的项目——它们的 CLAUDE.md / rules / memory 都在项目自己的 git 里。

## 前置依赖

- **Git**：clone 用
- **Bash 或 PowerShell**：跑 junction 脚本用
- **Codex 或 Claude Code CLI**

可选：
- 项目主语言对应的工具链（不影响 skill 本身，只影响后续填快速命令时的命令是否能跑通）

## 常见问题

### Q：skill 不出现在列表里

检查：
1. 完整仓库必须在 `~/.bridgeforge/SKILL.md`；Codex 路径必须是 `~/.agents/skills/bridgeforge/SKILL.md`；Claude Code 路径必须是 `~/.claude/skills/bridgeforge/SKILL.md`
2. `SKILL.md` frontmatter 必须有 `name: bridgeforge` 和 `description:`
3. 重启当前 agent 让它重新扫描 skill 目录

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
