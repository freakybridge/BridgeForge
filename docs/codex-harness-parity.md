# Codex Harness Parity Report

> 自动生成：`.codex/scripts/harness_parity_check.py`。本报告用于 git-sync 前维护 Claude/Codex harness 对照清单。

## Summary

- 状态：`REVIEW`
- Claude 有但 Codex 缺失：0
- 未登记的 Codex-only 文件：0
- 归一化后仍有差异的同名文件：21

## Inventory

| 层 | Claude 文件数 | Codex 文件数 | Codex 缺失 | Codex-only |
|---|---:|---:|---|---|
| `hooks` | 24 | 25 | - | `model_policy_check.py` |
| `rules` | 8 | 8 | - | - |
| `scripts` | 5 | 7 | - | `codex_git_sync.py`, `harness_parity_check.py` |

## Normalized Diffs

归一化规则只处理确定的壳差异：`.claude` -> `.codex`、`CLAUDE.md` -> `AGENTS.md`、普通 `$skill` 入口等。`/bridgeforge` 不归一化，因为 Codex 与 Claude 已统一使用 slash 入口。

| 文件 | diff hunk | 行变化 | 结论 |
|---|---:|---:|---|
| `hooks/allow_memory_write.py` | 3 | -3 / +9 | 待人工归类 |
| `hooks/clarify_reminder.py` | 2 | -3 / +3 | 待人工归类 |
| `hooks/config_health_check.py` | 1 | -0 / +1 | 待人工归类 |
| `hooks/context_warning.py` | 3 | -3 / +3 | 待人工归类 |
| `hooks/encoding_check.py` | 3 | -3 / +3 | 待人工归类 |
| `hooks/fallback_smell_check.py` | 3 | -4 / +5 | 待人工归类 |
| `hooks/find_doc_reminder.py` | 6 | -8 / +9 | 待人工归类 |
| `hooks/focus_reminder.py` | 2 | -2 / +2 | 待人工归类 |
| `hooks/memory_lint.py` | 2 | -4 / +5 | 待人工归类 |
| `hooks/requirements_check.py` | 2 | -4 / +5 | 待人工归类 |
| `hooks/rule_index_check.py` | 5 | -7 / +8 | 待人工归类 |
| `hooks/rule_size_check.py` | 2 | -4 / +5 | 待人工归类 |
| `hooks/skill_sync_check.py` | 4 | -4 / +4 | 待人工归类 |
| `hooks/test_receipt.py` | 3 | -3 / +4 | 待人工归类 |
| `hooks/version_check.py` | 2 | -2 / +2 | 待人工归类 |
| `rules/anti_drift_hooks.md` | 3 | -4 / +4 | 待人工归类 |
| `rules/debugging.md` | 3 | -3 / +3 | 待人工归类 |
| `rules/meta_rule_design.md` | 1 | -1 / +1 | 待人工归类 |
| `rules/portability.md` | 6 | -12 / +28 | 待人工归类 |
| `scripts/bridgeforge_switch.py` | 10 | -10 / +10 | 待人工归类 |
| `scripts/memory_search.py` | 1 | -2 / +2 | 待人工归类 |

## 使用约定

- `Codex 缺失` 默认需要补齐，除非有明确豁免原因。
- `Codex-only` 必须登记为专属能力，例如模型路由、Codex git-sync 执行器。
- `Normalized Diffs` 只提示差异，不自动判错；改动前先判断是应对齐、Codex 专属，还是文案残留。
