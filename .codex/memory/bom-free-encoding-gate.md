---
description: BridgeForge 全 repo 文本统一 UTF-8 without BOM，并用编辑后 / pre-commit / shell 中转 hook 防编码污染。
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

## 2026-07-10 非 ASCII shell 中转防护

下游报告补齐了另一类编码污染：非 ASCII 正文（中文、CJK、emoji 等）被塞进 shell 命令字符串，再经管道、重定向、here-string、`python -`、`python -c`、`node -e`、`Set-Content`、`Out-File`、`tee` 等路径写文件或动态执行时，可能在 shell / 终端 / 解释器编码边界损坏。污染写入后只剩三连问号或 `U+FFFD`，原文不可恢复。

落地：
- 新增 `non_ascii_shell_guard.py` 到 `templates/claude/hooks/`、`templates/codex/hooks/`、`.claude/hooks/`、`.codex/hooks/`，并接入两套 settings 的 `PreToolUse(Bash)`。
- 阻断条件收窄为三要素同时命中：命令含非 ASCII、存在 shell 中转边界、存在写入或动态执行入口；`Write-Output "中文"` 和 ASCII 管道放行。
- `encoding_check.py` 扩展为三层：BOM 硬拦、编辑后扫描当前文件、pre-commit 只扫 staged 文本中的三连问号 / `U+FFFD`，避免历史 archive 样本反复告警。
- portability rule 增加红线：禁止非 ASCII 正文经 shell 中转写入 / 动态执行；必须改用 `apply_patch`、Edit/Write/MultiEdit、复制已存在 UTF-8 文件，或脚本源码保持 ASCII 并显式读取 UTF-8 输入文件。

版本记录：
- 根版本升到 `0.58.0`。
- `templates/codex/VERSION` 升到 `0.29.0`。
- `templates/claude/VERSION` 升到 `0.22.0`。

验证要点：
- `python tests\harness\run_downstream_fixture.py` 全量通过。
- `encoding_check --scan-garble` 扫描两套模板骨架和 dogfood hooks/settings exit 0。
- 独立 review-auditor 复核通过；第一次指出三连问号漏检后，阈值从五连问号收紧到三连问号，并把测试改为运行时拼接样本，避免源码自报。
