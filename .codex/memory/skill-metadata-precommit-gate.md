---
description: 通用 skill 可调用 metadata 漏标事故的制度化修复：用 pre-commit 硬闸检查 skills/*/SKILL.md。
---

# Skill Metadata Pre-commit Gate

2026-07-08，`feature-dev` 已在 `skills/feature-dev/SKILL.md` 源头存在，但当前 Codex 无法通过 skill 入口调用。根因不是流程正文，而是两层入口条件没同时满足：

- 用户级 Codex skill 货架 `~/.agents/skills/feature-dev/SKILL.md` 缺失。
- 源头 frontmatter 缺 `user_invocable: true` / `argument`，同步后也可能不可手动调用。

修复后形成产品层硬闸：

- `templates/{codex,claude}/hooks/skill_metadata_check.py` + dogfood `.codex/.claude/hooks/skill_metadata_check.py`。
- 根 `.githooks/pre-commit` 和两套模板 `.githooks/pre-commit` 均接入。
- harness `skill_metadata_health` 覆盖：源头通过、缺 `user_invocable` 的 fixture 返回 exit 2、补齐后返回 0。

后续新增通用 skill 的最低 frontmatter：

```yaml
---
name: <目录名>
description: ...
user_invocable: true
argument: ...
---
```

若 skill 无参数，写 `argument: 无`，不要省略字段；不要使用历史拼写 `user-invocable`；入口文件不能带 UTF-8 BOM。
