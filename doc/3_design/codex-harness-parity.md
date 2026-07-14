# Codex Harness Parity Report

> 自动生成：`.codex/scripts/harness_parity_check.py`。本报告用于 git-sync 前维护 Claude/Codex harness 对照清单。

## Summary

- 状态：`OK`
- Claude 有但 Codex 缺失：0
- 未登记的 Codex-only 文件：0
- 归一化后仍有差异的同名文件：24（未分类：0）
- skills 内容检查问题：0

## Inventory

| 层 | Claude 文件数 | Codex 文件数 | Codex 缺失 | Codex-only |
|---|---:|---:|---|---|
| `hooks` | 29 | 31 | - | `model_policy_check.py`, `user_config_write_guard.py` |
| `rules` | 8 | 8 | - | - |
| `scripts` | 5 | 7 | - | `codex_git_sync.py`, `harness_parity_check.py` |
| `memory` | 2 | 2 | - | - |
| `skills` | 18 | 18 | - | 共享单一源 |

## Normalized Diffs

归一化规则只处理确定的壳差异：`.claude` -> `.codex`、`CLAUDE.md` -> `AGENTS.md`、独立 `/skill` 命令 -> `$skill`。路径片段里的 `/focus` / `/find-doc` 不会被替换，避免误报。`/bridgeforge` 不归一化，因为 Codex 与 Claude 已统一使用 slash 入口。

| 文件 | diff hunk | 行变化 | 分类 | 说明 |
|---|---:|---:|---|---|
| `hooks/allow_memory_write.py` | 3 | -3 / +9 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_* fallback |
| `hooks/cargo_default_run_check.py` | 4 | -6 / +6 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_INPUT fallback |
| `hooks/clarify_reminder.py` | 2 | -3 / +3 | `expected-codex-adapter` | Codex must skip both / commands and $ skills |
| `hooks/config_health_check.py` | 1 | -0 / +1 | `codex-only` | Codex registers model_policy_check health signal |
| `hooks/context_warning.py` | 11 | -15 / +30 | `expected-codex-adapter` | Codex skill calls use $ and must bypass ctx warning |
| `hooks/enforce_no_effortlevel.py` | 1 | -2 / +2 | `expected-codex-adapter` | Codex removes only the legacy project effortLevel while leaving user config read-only |
| `hooks/fallback_smell_check.py` | 3 | -4 / +5 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_INPUT fallback |
| `hooks/find_doc_reminder.py` | 4 | -6 / +7 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_* fallback |
| `hooks/focus_reminder.py` | 1 | -1 / +1 | `expected-codex-adapter` | Codex text and skill command surface differ |
| `hooks/git_add_all_guard.py` | 10 | -30 / +54 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_INPUT fallback and broader git flag parsing |
| `hooks/memory_dup_check.py` | 11 | -17 / +45 | `expected-codex-adapter` | Codex memory path plus hyphen/underscore topic splitting |
| `hooks/memory_lint.py` | 4 | -6 / +7 | `expected-codex-adapter` | Codex memory path and CODEX_TOOL_INPUT fallback |
| `hooks/mirror_drift_check.py` | 1 | -1 / +1 | `expected-codex-adapter` | Codex dogfood paths and AGENTS.md wording differ |
| `hooks/requirements_check.py` | 2 | -4 / +5 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_INPUT fallback |
| `hooks/rule_index_check.py` | 2 | -4 / +5 | `cleanup-only` | behavior OK; local variable naming still carries claude_md |
| `hooks/rule_size_check.py` | 2 | -4 / +5 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_INPUT fallback |
| `hooks/show_state.py` | 2 | -2 / +2 | `expected-codex-adapter` | Codex startup hints use $ skills and .codex scripts |
| `hooks/skill_sync_check.py` | 4 | -4 / +4 | `codex-path-adapter` | Codex user skill shelf is ~/.agents/skills |
| `hooks/test_receipt.py` | 3 | -3 / +4 | `expected-codex-adapter` | Codex stdin JSON + CODEX_TOOL_INPUT fallback |
| `hooks/version_check.py` | 3 | -4 / +4 | `expected-codex-adapter` | Codex command payload fallback differs |
| `rules/anti_drift_hooks.md` | 3 | -3 / +5 | `expected-codex-adapter` | Codex rule paths, AGENTS.md refs, and $ skills differ |
| `rules/debugging.md` | 2 | -2 / +2 | `expected-codex-adapter` | Codex rule text references AGENTS.md and $debate |
| `rules/meta_rule_design.md` | 2 | -2 / +2 | `expected-codex-adapter` | Codex rule paths and AGENTS.md terminology differ |
| `rules/portability.md` | 6 | -10 / +28 | `codex-only` | Codex config.toml, custom agents, and model_policy_check policy |

## Shared Skills Checks

- 共享 `skills/*/SKILL.md` metadata / BOM / Claude-only marker 检查通过。

## 使用约定

- `Codex 缺失` 默认需要补齐，除非有明确豁免原因。
- `Codex-only` 必须登记为专属能力，例如模型路由、Codex git-sync 执行器。
- `expected-codex-adapter` / `codex-only` / `codex-path-adapter` / `cleanup-only` 是已归类差异，不阻止状态为 OK。
- `needs-review` 才表示新差异还没人工判定。
