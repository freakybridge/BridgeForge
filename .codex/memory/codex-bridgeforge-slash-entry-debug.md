---
description: Codex /bridgeforge slash 入口排障：旧 .codex/skills 残留、BOM frontmatter、薄 wrapper 的最终修法。
---

# Codex /bridgeforge Slash 入口排障

2026-07-07，用户在下游项目输入 `/bridgeforge` 时，slash 清单只显示 Plan/Todo/Focus 等子 skill，不显示 BridgeForge 根命令。最终确认并修复：

- 旧残留 `~/.codex/skills/bridgeforge` 是 junction，指向完整 `D:\Quant\BridgeForge`，会让 Codex 扫到仓库内子 skill，但根 `/bridgeforge` 不显示。必须迁出 `~/.codex/skills/`。
- Codex 用户级 skill 货架是 `~/.agents/skills/`。`~/.agents/skills/bridgeforge` 必须是叶子 skill 目录，不能放完整仓库。
- 根 `SKILL.md` 曾带 UTF-8 BOM，首字节不是裸 `---`；Plan/Todo 等能显示的 skill 均无 BOM。frontmatter 入口文件必须 UTF-8 no BOM。
- 最终采用薄入口：`scripts/codex_bridgeforge_entry.SKILL.md` 复制为 `~/.agents/skills/bridgeforge/SKILL.md`，只负责出现在 slash 清单并转读 `~/.agents/bridgeforge-home/SKILL.md`。

判断顺序：先确认旧扫描目录是否污染，再确认实际入口是否普通目录且只含 `SKILL.md`，再看 `SKILL.md` 首字节是否 `2D 2D 2D`，最后要求 Codex `Force Reload Skills`。
