---
name: bridgeforge
description: 在新项目里铺设或更新标准化的 Claude/Codex 协作骨架；用户输入 /bridgeforge、bridgeforge、switch claude/codex 时使用。
version: 0.48.0
user_invocable: true
user-invocable: true
argument: 可选：switch claude|codex [--dry-run|--interactive] [--apply-blocked PATH] [--keep-blocked PATH] [--delete-unknown PATH]；不带参数则初始化或更新当前项目骨架
model: sonnet
---

# BridgeForge Codex Slash Entry

这是 Codex 专用的薄入口，只负责让 `/bridgeforge` 出现在 slash 命令清单里。

执行时必须立刻读取完整 BridgeForge skill：

- Windows: `%USERPROFILE%\.agents\bridgeforge-home\SKILL.md`
- macOS / Linux: `~/.agents/bridgeforge-home/SKILL.md`

读取后按完整 skill 的说明执行，并把 `/bridgeforge` 后面的用户参数原样当作 `ARGUMENTS` 处理。

如果完整 skill 文件不存在，说明 BridgeForge home 尚未安装或路径错了。此时不要继续猜测，直接提示用户先安装：

```text
Codex: ~/.agents/bridgeforge-home 存完整仓库，~/.agents/skills/bridgeforge/SKILL.md 存本薄入口。
```
