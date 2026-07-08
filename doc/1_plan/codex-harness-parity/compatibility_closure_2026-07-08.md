# Codex 迁移兼容性闭环检测报告

> 日期：2026-07-08
> 范围：从 Claude 迁到 Codex 的 hooks / rules / scripts / skills / memory / settings / 文档传播
> 结论：已闭环。P1 / P2 必修项已修完并复验通过；剩余只有不影响运行的 cleanup-only 命名残留。

## 白话结论

这轮检测做完后的结论很明确：Codex 搬家不是“看起来能用”，而是已经把自动开关、规则、脚本、说明书、记忆文件都放进同一张检查表里验过了。

用白话说：之前像搬完厨房后发现“水电能用，但盘点表漏了几个抽屉”。现在抽屉也补进盘点表了，藏在文件开头的 BOM 字符也清掉了，目录检查员误报的问题也修了。剩下的只是个别变量名还叫 `claude_*`，像标签贴旧了，但里面东西没放错。

## 总体判定

| 模块 | 当前判定 | 白话解释 |
|---|---|---|
| hooks | 通过，差异已归类 | Codex 需要 stdin JSON / `CODEX_TOOL_*` 输入适配，已逐项登记为预期差异。 |
| rules | 通过，差异已归类 | `CLAUDE.md` / `.claude` / slash skill 到 `AGENTS.md` / `.codex` / `$skill` 的差异已标清楚。 |
| scripts | 通过 | parity 脚本不再把共享脚本误报成差异。 |
| skills | 通过，已纳入检查 | `skills/*/SKILL.md` 已检查 metadata、BOM、Claude-only marker。 |
| memory | 通过，已纳入 parity | `templates/*/memory` 已进入对照；BOM 与 `memory_lint.py` orphan 误报已修。 |
| settings | 通过 | template 用 `.venv/Scripts/python.exe`，dogfood 用 `python`，符合 BridgeForge 约定。 |
| 下游 fixture | 通过 | `tests/harness/run_downstream_fixture.py` 21 项 PASS。 |

## parity 当前结果

`docs/codex-harness-parity.md` 当前状态：

- 状态：`OK`
- Claude 有但 Codex 缺失：0
- 未登记的 Codex-only 文件：0
- 归一化后仍有差异的同名文件：20
- 未分类差异：0
- skills 内容检查问题：0

这里的“仍有差异”不是坏事。它的意思是：两边确实因为 Claude / Codex 运行方式不同而有差别，但每个差别已经写明类别和原因。

## 20 个差异逐项判定

| # | 文件 | 分类 | 白话说明 |
|---:|---|---|---|
| 1 | `hooks/allow_memory_write.py` | `expected-codex-adapter` | Codex 读取工具输入的方式不同。 |
| 2 | `hooks/clarify_reminder.py` | `expected-codex-adapter` | Codex 要同时跳过 `/` 内置命令和 `$` skill。 |
| 3 | `hooks/config_health_check.py` | `codex-only` | Codex 多了模型策略检查。 |
| 4 | `hooks/context_warning.py` | `expected-codex-adapter` | Codex 的 `$snapshot` / `$resume` 这类保命 skill 要放行。 |
| 5 | `hooks/fallback_smell_check.py` | `expected-codex-adapter` | 输入来源从 Claude env 扩展到 Codex stdin / env。 |
| 6 | `hooks/find_doc_reminder.py` | `expected-codex-adapter` | Codex hook 输入适配不同。 |
| 7 | `hooks/focus_reminder.py` | `expected-codex-adapter` | Codex 提示文案和 skill 命令形态不同。 |
| 8 | `hooks/memory_lint.py` | `expected-codex-adapter` | Codex memory 路径和输入兜底不同。 |
| 9 | `hooks/mirror_drift_check.py` | `expected-codex-adapter` | dogfood 镜像路径从 `.claude` 换到 `.codex`。 |
| 10 | `hooks/requirements_check.py` | `expected-codex-adapter` | Codex 工具输入读取方式不同。 |
| 11 | `hooks/rule_index_check.py` | `cleanup-only` | 行为正确，只是局部变量名还带 `claude_md`。 |
| 12 | `hooks/rule_size_check.py` | `expected-codex-adapter` | Codex 工具输入读取方式不同。 |
| 13 | `hooks/show_state.py` | `expected-codex-adapter` | 启动提示里的 skill 和脚本路径换成 Codex 形态。 |
| 14 | `hooks/skill_sync_check.py` | `codex-path-adapter` | Codex 用户级 skill 货架是 `~/.agents/skills`。 |
| 15 | `hooks/test_receipt.py` | `expected-codex-adapter` | Codex 工具响应输入读取方式不同。 |
| 16 | `hooks/version_check.py` | `expected-codex-adapter` | Codex command payload 解析方式不同。 |
| 17 | `rules/anti_drift_hooks.md` | `expected-codex-adapter` | rule 里的路径、入口文件、skill 命令换成 Codex 形态。 |
| 18 | `rules/debugging.md` | `expected-codex-adapter` | rule 引用 `AGENTS.md` 和 `$debate`。 |
| 19 | `rules/meta_rule_design.md` | `expected-codex-adapter` | rule 路径和术语换成 Codex 形态。 |
| 20 | `rules/portability.md` | `codex-only` | Codex 专属的 config、agents、模型策略检查。 |

## 已关闭的问题

| 优先级 | 问题 | 当前处理 |
|---|---|---|
| P1 | `templates/codex/memory/MEMORY.md` / `_stats.json` 带 BOM | 已修；严格 JSON 解析通过，encoding hook 可防回归。 |
| P1 | `memory_lint.py` 把正常 memory 文件误报 orphan | 已修；支持连字符 / 点号文件名，并排除 `MEMORY_COLD.md`。 |
| P2 | parity 没覆盖 `memory` | 已修；`templates/*/memory` 已纳入 `COMPARE_DIRS`。 |
| P2 | slash skill 归一化误伤路径 | 已修；只替换独立 `/skill` 命令，路径里的 `/focus` / `/find-doc` 不再动。 |
| P2 | 20 个差异缺机器可读结论 | 已修；全部登记分类，未分类为 0。 |
| P3 | `skills/**` 未纳入兼容审计 | 已修；新增共享 skill metadata / BOM / Claude-only marker 检查。 |
| P3 | Codex 文件里局部变量名残留 | 未改，保留为 `cleanup-only`；不影响运行，只影响可读性。 |

## 验证收据

本轮复验实际跑过：

```powershell
python .codex\scripts\harness_parity_check.py --check
python templates\codex\scripts\harness_parity_check.py --check
python .codex\hooks\encoding_check.py --pre-commit
python .claude\hooks\encoding_check.py --pre-commit
'{"tool_input":{"file_path":".codex/memory/MEMORY.md"}}' | python .codex\hooks\memory_lint.py
'{"tool_input":{"file_path":".claude/memory/MEMORY.md"}}' | python .claude\hooks\memory_lint.py
python -m json.tool templates\codex\memory\_stats.json
python .codex\hooks\skill_metadata_check.py --pre-commit
python -m py_compile .codex\hooks\memory_lint.py templates\codex\hooks\memory_lint.py .claude\hooks\memory_lint.py templates\claude\hooks\memory_lint.py .codex\scripts\harness_parity_check.py templates\codex\scripts\harness_parity_check.py .codex\hooks\encoding_check.py .claude\hooks\encoding_check.py templates\codex\hooks\encoding_check.py templates\claude\hooks\encoding_check.py
python .codex\hooks\version_check.py --pre-commit
python tests\harness\run_downstream_fixture.py
```

关键结果：

- parity 两套入口均通过，报告状态 `OK`。
- memory lint 运行态无 orphan 误报。
- `templates/codex/memory/_stats.json` 可被严格 JSON 工具解析。
- skill metadata 检查通过。
- py_compile 通过。
- version_check 通过。
- 下游 fixture 21 项 PASS。

## 最终结论

兼容性检测已闭环。现在可以说：Codex 骨架主链路、检测表、memory、skills 都已经纳入自动验证；没有剩余 P1/P2 阻断项。

剩余的 `cleanup-only` 命名残留可以后续单独做一次小清理，不影响这次迁移验收。
