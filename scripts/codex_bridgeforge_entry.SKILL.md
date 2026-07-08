---
name: bridgeforge
description: 在新项目里铺设或更新标准化的 Claude/Codex 协作骨架；用户输入 /bridgeforge、bridgeforge、switch claude/codex 时使用。
version: 0.55.4
user_invocable: true
user-invocable: true
argument: 可选：switch claude|codex [--dry-run|--interactive] [--skip-settings-migration] [--migrate-setting KEY] [--memory-conflict REL=ACTION]；不带参数则维护当前 agent 骨架，发现另一套骨架时先确认再 switch
model: sonnet
---

# BridgeForge Codex Slash Entry

这是 Codex 专用的薄入口，只负责让 `/bridgeforge` 出现在 slash 命令清单里。

执行顺序硬闸：读取完整 BridgeForge skill 前，必须先刷新用户级骨架库。

- Windows: `%USERPROFILE%\.bridgeforge\SKILL.md`
- macOS / Linux: `~/.bridgeforge/SKILL.md`

先定位完整仓库目录（优先 `%USERPROFILE%\.bridgeforge` / `~/.bridgeforge`）。若该目录是 git repo，先执行：

```bash
git -C "$BRIDGEFORGE_HOME" pull --ff-only
```

- pull 成功后，读取刷新后的 `$BRIDGEFORGE_HOME/SKILL.md`。
- pull 失败（冲突 / 网络 / 权限）→ 停下报告，不继续用旧 skill 执行；让用户处理后重跑 `/bridgeforge`。
- 完整仓库不是 git repo（手动拷贝）→ 跳过 pull，但必须提示"建议改用 git clone 到 ~/.bridgeforge，后续 /bridgeforge 才能自动刷新"。

读取后按完整 skill 的说明执行，并把 `/bridgeforge` 后面的用户参数原样当作 `ARGUMENTS` 处理。

兼容提示：如果新路径不存在，但旧路径 `%USERPROFILE%\.agents\bridgeforge-home\SKILL.md` / `~/.agents/bridgeforge-home/SKILL.md` 存在，说明本机还是旧安装布局。不要静默迁移；提示用户按 INSTALL.md 把完整仓库移到 `.bridgeforge`，再保留本叶子入口。

如果完整 skill 文件不存在，说明 BridgeForge 尚未安装或路径错了。此时不要继续猜测，直接提示用户先安装：

```text
完整 BridgeForge 工厂放在 ~/.bridgeforge；Codex 入口放在 ~/.agents/skills/bridgeforge/SKILL.md。
```
