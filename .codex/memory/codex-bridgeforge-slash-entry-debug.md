---
description: Codex /bridgeforge slash 入口排障：旧 .codex/skills 残留、BOM frontmatter、~/.bridgeforge 完整工厂与薄 wrapper 的最终布局。
---

# Codex /bridgeforge Slash 入口排障

2026-07-07，用户在下游项目输入 `/bridgeforge` 时，slash 清单只显示 Plan/Todo/Focus 等子 skill，不显示 BridgeForge 根命令。最终确认并修复：

- 旧残留 `~/.codex/skills/bridgeforge` 是 junction，指向完整 `D:\Quant\BridgeForge`，会让 Codex 扫到仓库内子 skill，但根 `/bridgeforge` 不显示。必须迁出 `~/.codex/skills/`。
- Codex 用户级 skill 货架是 `~/.agents/skills/`。`~/.agents/skills/bridgeforge` 必须是叶子 skill 目录，不能放完整仓库。
- 根 `SKILL.md` 曾带 UTF-8 BOM，首字节不是裸 `---`；Plan/Todo 等能显示的 skill 均无 BOM。frontmatter 入口文件必须 UTF-8 no BOM。
- 最终采用薄入口：`scripts/codex_bridgeforge_entry.SKILL.md` 复制为 `~/.agents/skills/bridgeforge/SKILL.md`，只负责出现在 slash 清单并转读 `~/.bridgeforge/SKILL.md`。

判断顺序：先确认旧扫描目录是否污染，再确认实际入口是否普通目录且只含 `SKILL.md`，再看 `SKILL.md` 首字节是否 `2D 2D 2D`，最后要求 Codex `Force Reload Skills`。

2026-07-08 本机迁移验真：

- `C:\Users\bridg\.bridgeforge` 应是 junction，目标为 `D:\Quant\BridgeForge`。
- `C:\Users\bridg\.agents\skills\bridgeforge` 和 `C:\Users\bridg\.claude\skills\bridgeforge` 都应是普通目录，只放对应 wrapper；不能是指向完整仓库的 junction。
- 旧完整工厂入口 `C:\Users\bridg\.agents\bridgeforge-home` 应不存在。
- 如果误把 wrapper 写进完整仓库根 `SKILL.md`，先用 `git diff` / blob hash 确认并恢复根 skill，再处理旧 junction；不要把完整仓库 clone/junction 留在 agent 的 skill 货架里。

2026-07-14 版本一致性补充：

- 薄入口虽然会拉取并读取完整 `~/.bridgeforge/SKILL.md`，功能实际跟随根版本，但其 frontmatter `version:` 仍决定菜单 / 入口显示。
- 每次根 `VERSION` 升级时，同时核对根 `SKILL.md`、`scripts/codex_bridgeforge_entry.SKILL.md`、`scripts/claude_bridgeforge_entry.SKILL.md` 的版本；再复制两份 wrapper 到用户级入口并做内容哈希校验。
