---
description: Codex 迁移兼容闭环验收：parity 覆盖 memory/skills，20 个差异必须归类，报告状态以未分类为 0 才算 OK。
---

# Codex Harness Parity Closure

2026-07-08，围绕 Claude 骨架迁移到 Codex 的 rule / skill / memory / hooks 兼容性，用户要求“分配 agents 检测、逐项判定 20 个差异、最后全面闭环”。

最终闭环口径：

- `docs/codex-harness-parity.md` 是长期机器报告，状态必须能表达 `OK` / `REVIEW`。
- `harness_parity_check.py` 不只对比 hooks/rules/scripts，还要覆盖 `templates/*/memory`。
- 共享 `skills/*/SKILL.md` 不需要按 Claude/Codex 分两份，但必须检查 metadata、BOM、以及是否存在只有 Claude 没有 Codex 分支的高风险描述。
- 20 个 Claude/Codex 差异不能只写“待人工归类”；每项必须落到机器可读分类：`expected-codex-adapter`、`codex-only`、`codex-path-adapter`、`cleanup-only` 或 `needs-review`。
- `needs-review` 数量必须为 0 才能把 parity 报告状态判为 `OK`。
- slash skill 归一化只能替换独立 `/skill` 命令，不能替换路径片段里的 `/focus`、`/find-doc`、`/debates_*`。
- 如果 Claude/Codex 原文件字节完全一致，parity 脚本要直接判无差异，避免单边归一化把共享脚本造出假 diff。

本次已修复的真实问题：

- Codex memory 模板 BOM 由 `encoding_check.py` 双层防线兜住：PostToolUse 早提醒，pre-commit 硬拦。
- `memory_lint.py` 支持带连字符 / 点号的 memory 文件名，并排除生成索引 `MEMORY_COLD.md`，避免把正常 memory 文件误报 orphan。
- parity 报告最终达到：Claude 缺失 0、未登记 Codex-only 0、20 个差异未分类 0、skills 问题 0。

保留项：

- `rule_index_check.py` 的 `claude_md`、`memory_search.py` 的 `claude_dir` 属于 `cleanup-only` 命名残留，不影响运行，可后续单独清理。

验证收据：

- `python .codex\scripts\harness_parity_check.py --check`
- `python templates\codex\scripts\harness_parity_check.py --check`
- `python .codex\hooks\encoding_check.py --pre-commit`
- `python .claude\hooks\encoding_check.py --pre-commit`
- `python .codex\hooks\skill_metadata_check.py --pre-commit`
- `python .codex\hooks\version_check.py --pre-commit`
- `python tests\harness\run_downstream_fixture.py`：21 项 PASS。
