---
name: bridgeforge
description: 在新项目里铺设或更新标准化的 Claude/Codex 协作骨架；用户输入 /bridgeforge、bridgeforge、switch claude/codex 时使用。
version: 0.52.0
user_invocable: true
user-invocable: true
argument: 可选：switch claude|codex [--dry-run|--interactive] [--skip-settings-migration] [--migrate-setting KEY] [--memory-conflict REL=ACTION]；不带参数则初始化或更新当前项目骨架
model: sonnet
---

# BridgeForge Claude Slash Entry

这是 Claude Code 专用的薄入口，只负责让 `/bridgeforge` 出现在 skill 命令清单里。

执行时必须立刻读取完整 BridgeForge skill：

- Windows: `%USERPROFILE%\.bridgeforge\SKILL.md`
- macOS / Linux: `~/.bridgeforge/SKILL.md`

读取后按完整 skill 的说明执行，并把 `/bridgeforge` 后面的用户参数原样当作 `ARGUMENTS` 处理。

兼容提示：如果新路径不存在，但旧路径 `%USERPROFILE%\.claude\skills\bridgeforge\SKILL.md` / `~/.claude/skills/bridgeforge/SKILL.md` 是完整 BridgeForge 仓库，说明本机还是旧安装布局。不要静默迁移；提示用户按 INSTALL.md 把完整仓库移到 `.bridgeforge`，再保留本叶子入口。

如果完整 skill 文件不存在，说明 BridgeForge 尚未安装或路径错了。此时不要继续猜测，直接提示用户先安装：

```text
完整 BridgeForge 工厂放在 ~/.bridgeforge；Claude 入口放在 ~/.claude/skills/bridgeforge/SKILL.md。
```
