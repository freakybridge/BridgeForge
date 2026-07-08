---
description: BridgeForge 全 repo 文本统一 UTF-8 without BOM，并用编辑后 hook + pre-commit 双层防线防模板污染。
---

# BOM-Free Encoding Gate

2026-07-08 用户追问 BOM 是否有价值，并明确要求“每次编辑 md/json 等文件后就检查一次”，认为这比只靠 pre-commit 更可靠。结论落地为 BridgeForge 全 repo 文本文件统一 UTF-8 without BOM。

原因：
- 对 BridgeForge 没有实际收益：现代 UTF-8 工具不需要 BOM。
- 对关键入口有风险：JSON 解析、skill frontmatter、shell shebang 都可能要求第 0 字节就是 `{` / `---` / `#!`。
- 骨架工厂会把模板复制给下游，模板层 BOM 会放大成多项目污染。

落地机制：
- `encoding_check.py` 同步进入 `templates/claude/hooks/`、`templates/codex/hooks/`、`.claude/hooks/`、`.codex/hooks/`。
- 三份 `.githooks/pre-commit` 接入 `encoding_check.py --pre-commit`，作为提交前硬拦。
- Claude/Codex 模板和 dogfood settings 的 `PostToolUse(Edit|Write|MultiEdit)` 接入 `encoding_check.py`，编辑后提前提示 `[encoding]`。
- harness 增加 `encoding-no-bom`，并把 `encoding_check.py` 纳入 settings matcher / root precommit 覆盖。

版本记录：
- 根版本升到 `0.55.2`。
- `templates/codex/VERSION` 升到 `0.27.2`。
- `templates/claude/VERSION` 升到 `0.20.2`。

验证要点：
- 全 repo 文本扫描 `bom_count 0`。
- `python -m json.tool templates\codex\memory\_stats.json` 通过。
- `python tests\harness\run_downstream_fixture.py --case encoding-no-bom --case settings-matchers --case root-precommit` 通过。
