# Codex 迁移兼容性闭环检测报告
> 日期：2026-07-08
> 范围：从 Claude 迁到 Codex 的 hooks / rules / scripts / skills / memory / settings / 文档传播
> 结论：主要运行机制通过；检测工具和 memory 模板仍有应修项。

## 白话结论

这次不是简单问“有没有查过”，而是把厨房搬家后的几类东西分开验：

- 电线和开关：hooks / scripts，已经接上并跑通。
- 墙上的规矩：rules，数量、索引、体积检查通过。
- 操作说明书：skills，入口和封面检查通过，但还没有进入同一张 parity 对照表。
- 笔记本：memory，运行机制大体能跑，但模板和 lint 检查发现真实问题。

所以最终判断是：Codex 迁移不是空喊，核心机制能跑；但不能说“全面无问题”。下面的应修项处理完，才算兼容检测闭环真正干净。

## 总体判定

| 模块 | 判定 | 白话解释 |
|---|---|---|
| hooks | 通过，有待归类差异 | 自动按钮基本都能按 Codex 方式吃输入；差异多是 stdin JSON / CODEX_TOOL 适配。 |
| rules | 通过，有 Codex 专属差异 | 规则没有缺文件；`portability.md` 多了 Codex 模型路由等专属内容，合理但应登记为 Codex-only。 |
| scripts | 通过，有检测误报 | `bridgeforge_switch.py` 实际 Claude/Codex 字节一致；parity 报差异是替换规则误伤。 |
| skills | 部分通过 | skill 元数据和入口形态通过；但 `harness_parity_check.py` 没扫描 `skills/**` 内容。 |
| memory | 未闭环 | memory 模板没进 parity；Codex `_stats.json` 带 BOM，严格 JSON 解析失败；运行态 lint 有误报。 |
| settings | 通过 | template 用 `.venv/Scripts/python.exe`，dogfood 用 `python`，符合 BridgeForge 约定。 |
| 下游 fixture | 通过 | 20 项 fixture 全部 PASS。 |

## 20 个 parity 差异逐项判定

| # | 文件 | 判定 | 说明 |
|---:|---|---|---|
| 1 | `hooks/allow_memory_write.py` | 通过 | Codex 改为 stdin JSON 优先，`CODEX_TOOL_*` 次之，`CLAUDE_TOOL_*` 仅兼容旧配置。 |
| 2 | `hooks/clarify_reminder.py` | 通过 | Codex 需要同时跳过 `/` 内置命令和 `$` skill 调用。 |
| 3 | `hooks/config_health_check.py` | 通过 | Codex 多登记 `model_policy_check.py`，属于 Codex 专属健康项。 |
| 4 | `hooks/context_warning.py` | 通过 | Codex 需要对 `$snapshot` / `$resume` 这类 skill 放行，避免保命命令也被上下文预警挡住。 |
| 5 | `hooks/fallback_smell_check.py` | 通过 | 输入兼容路径从旧 env-only 改为 stdin JSON + `CODEX_TOOL_INPUT`。 |
| 6 | `hooks/find_doc_reminder.py` | 通过 + 检测误报 | 代码适配正确；parity 把 `.runtime/find-doc-stats.log` 里的 `/find-doc` 误替换成 `$find-doc`，这是检测脚本误报。 |
| 7 | `hooks/focus_reminder.py` | 通过 + 检测误报 | `.runtime/focus/anchor.json` 是路径，不该被 slash skill 替换规则影响。 |
| 8 | `hooks/memory_lint.py` | 通过但另有运行态问题 | Codex 输入适配正确；但运行态 lint 会把 `MEMORY_COLD.md` 和带连字符的 memory 文件误报成 orphan，见应修项。 |
| 9 | `hooks/requirements_check.py` | 通过 | 输入兼容路径正确。 |
| 10 | `hooks/rule_index_check.py` | 通过，建议清理命名 | 行为正确；Codex 文件里局部变量仍叫 `claude_md`，只是命名残留，不影响执行。 |
| 11 | `hooks/rule_size_check.py` | 通过 | 输入兼容路径正确。 |
| 12 | `hooks/skill_sync_check.py` | 通过，有运行态提示 | Codex 用户级 skill 目录改为 `~/.agents/skills` 是正确的；当前本机提示 `git-sync` 用户级副本与上游不一致。 |
| 13 | `hooks/test_receipt.py` | 通过 | stdin JSON 优先，env 只兜底；没有 tool_response 时不强行模拟。 |
| 14 | `hooks/version_check.py` | 通过 | Bash command 提取逻辑适配 Codex 输入。 |
| 15 | `rules/anti_drift_hooks.md` | 检测误报 | `.codex/hooks/focus_reminder.py`、`.runtime/focus/anchor.json` 是路径；parity 的 `/focus -> $focus` 替换误伤。 |
| 16 | `rules/debugging.md` | 通过 + 检测误报 | `AGENTS.md` 引用是正确 Codex 化；`doc/2_pending/debates_*` 的路径差异是替换误伤。 |
| 17 | `rules/meta_rule_design.md` | 检测误报 | `doc/2_pending/debates_*` 是路径，不是 skill 调用。 |
| 18 | `rules/portability.md` | 接受为 Codex 专属 | `.agents/skills`、`.codex/config.toml`、custom agents、`model_policy_check.py` 都是 Codex 专属语义，应在 parity 报告里标为 Codex-only rationale。 |
| 19 | `scripts/bridgeforge_switch.py` | 检测误报 | Claude/Codex 两份脚本 SHA256 一致；差异来自 parity 把 Claude 文本替换成 Codex 后制造了“Codex and Codex”。 |
| 20 | `scripts/memory_search.py` | 通过，建议清理命名 | Codex 文案和命令已适配；局部变量仍叫 `claude_dir`，只是命名残留，不影响执行。 |

## skills 闭环检测

已验证：

- `python .codex/hooks/skill_metadata_check.py --pre-commit`：通过。
- 所有 `skills/*/SKILL.md` 都有 frontmatter、`user_invocable: true`、`argument`，未发现 BOM。
- 命中 `Claude` 的 skill 均有 Codex 对应说明或 `$` 调用形态；没有发现“只有 Claude，没有 Codex”的 skill。

发现：

- `harness_parity_check.py` 没有扫描 `skills/**`，所以 skill 内容兼容性还不在自动 parity 报告里。
- `python .codex/hooks/skill_sync_check.py` 当前提示：用户级 `git-sync` skill 与上游不一致。这是本机用户级货架的同步状态问题，不是上游源文件 metadata 失败。

白话解释：说明书都有封面、标题、可上架，也基本写了 Codex 用法；但还没纳入“Claude/Codex 对照盘点表”，所以后续新 skill 仍可能只靠人工发现内容漂移。

## memory 闭环检测

已验证：

- `.codex/settings.json` 和 `templates/codex/settings.json` 都注册了 `memory_rebuild_index.py --from-hook` 与 `memory_lint.py`。
- `python .codex/scripts/memory_rebuild_index.py` 可运行。
- `python .codex/hooks/memory_lint.py --pre-commit` 当前无阻断输出。

发现：

1. `templates/codex/memory/_stats.json` 带 UTF-8 BOM。
   - `python -m json.tool templates\codex\memory\_stats.json` 报错：`Unexpected UTF-8 BOM`。
   - 这会让严格 JSON 工具读失败；`memory_rebuild_index.py` 当前会吞掉异常并退回默认 stats，属于静默降级。

2. `templates/codex/memory/MEMORY.md` 也带 BOM。
   - Markdown 不一定立刻坏，但 BridgeForge 已多次遇到 BOM 影响 frontmatter / shell shebang / JSON 解析的问题，不应继续把 BOM 放进模板。

3. `memory_lint.py` 的 PostToolUse 运行态提醒有误报。
   - 命令：`'{"tool_input":{"file_path":".codex/memory/MEMORY.md"}}' | python .codex\hooks\memory_lint.py`
   - 输出：`未索引 orphans（5）: MEMORY_COLD.md, bridgeforge-command-model.md, codex-bridgeforge-slash-entry-debug.md, codex-model-routing-policy.md, skill-metadata-precommit-gate.md`
   - 原因：`MEMORY_COLD.md` 本应排除；正则 `([a-z0-9_]+\.md)` 不支持连字符文件名。

白话解释：笔记本能用，但目录检查员眼神有问题，会把带短横线的笔记看成“没登记”；另外模板里的 JSON 文件开头有隐藏字符，严格工具会读不进去。

## 验证收据

本次亲自运行过：

```powershell
python .codex\scripts\harness_parity_check.py --check
python templates\codex\scripts\harness_parity_check.py --check
python .codex\hooks\rule_index_check.py --pre-commit
python .codex\hooks\skill_metadata_check.py --pre-commit
python .codex\hooks\mirror_drift_check.py
python .codex\hooks\skill_sync_check.py
python .codex\scripts\memory_rebuild_index.py
python .codex\hooks\memory_lint.py --pre-commit
python tests\harness\run_downstream_fixture.py
python -m json.tool templates\codex\memory\_stats.json
```

关键结果：

- parity `--check`：通过，但报告仍是 `REVIEW`。
- rule index / skill metadata / mirror drift：通过。
- fixture：20 项全部 PASS。
- skill sync：提示本机用户级 `git-sync` divergent。
- Codex memory `_stats.json`：严格 JSON 解析失败，原因是 BOM。

## 应修项

| 优先级 | 项 | 处理建议 |
|---|---|---|
| P1 | 去掉 `templates/codex/memory/MEMORY.md` 和 `_stats.json` 的 BOM | 模板文件应统一 UTF-8 no BOM；`_stats.json` 必须能被严格 JSON 工具解析。 |
| P1 | 修 `memory_lint.py` orphan 检测 | 排除 `MEMORY_COLD.md`；链接正则支持连字符文件名，如 `([A-Za-z0-9_-]+\.md)`。需要同步 template + dogfood。 |
| P2 | 扩展 `harness_parity_check.py` 覆盖 `memory` | 至少把 `templates/*/memory` 纳入报告，并登记合理差异。 |
| P2 | 改进 parity slash skill 归一化 | 只替换独立命令 token，不替换路径里的 `/focus`、`/find-doc`、`/debates_*`。 |
| P2 | 给 20 个差异写入机器可读结论 | 例如 `expected-codex-adapter` / `codex-only` / `normalizer-false-positive` / `cleanup-only`。 |
| P3 | 将 `skills/**` 纳入兼容审计 | 不一定进同一个 parity 脚本，但至少要有 skill 内容扫描：Claude-only 命令、缺 Codex 分支、旧路径、BOM/frontmatter。 |
| P3 | 清理 Codex 文件中的变量名残留 | 如 `rule_index_check.py` 的 `claude_md`、`memory_search.py` 的 `claude_dir`，不影响运行但影响可读性。 |

## 最终结论

闭环检测已经完成，结论不是“全绿”，而是：

1. 迁移主链路能跑：hooks / rules / scripts / settings / fixture 通过。
2. 20 个 parity 差异已逐项判定，没有发现会立刻阻断 Codex 运行的 hooks/scripts 差异。
3. 真正需要修的是检测与 memory 相关边界：BOM、memory lint 误报、parity 覆盖范围、slash 归一化误伤。

白话收口：电线能通电，开关也能用；但盘点表漏了说明书和笔记本，笔记本目录还有两个明显小毛病。先修 P1，再补 P2，才算这套 Codex 搬家验收单真正干净。
