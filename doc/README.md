# BridgeForge Documents

This `doc/` tree is the only documentation system for BridgeForge. It tracks active feature work, long-lived design and playbook material, pending investigations, archived records, and reference examples.

## Index

### Active Plans

| Path | Status | Purpose |
|------|--------|---------|
| `1_plan/bridgeforge-command-clarity/requirements_2026-07-08_bridgeforge-command-clarity.md` | trial | Clarify BridgeForge's user-facing command model around `bridgeforge` and `bridgeforge switch <agent>`. |
| `1_plan/bridgeforge-home-layout/requirements_2026-07-08_bridgeforge-home-layout.md` | trial | Move the user-level BridgeForge factory home from `.agents/bridgeforge-home` to neutral `.bridgeforge`. |
| `1_plan/codex-harness-parity/requirements_2026-07-08_codex-harness-parity.md` | trial | Align Codex harness with Claude harness, fix migration residue, and add a parity report before git-sync. |
| `1_plan/codex-harness-parity/compatibility_closure_2026-07-08.md` | review | Closed-loop compatibility audit for Claude-to-Codex hooks, rules, scripts, skills, and memory migration. |
| `1_plan/codex-model-routing/requirements_2026-07-08_codex-model-routing.md` | trial | Add Codex model / reasoning-effort routing with config defaults, custom agents, and hook drift checks. |
| `1_plan/codex-model-routing-56/requirements_2026-07-10_codex-model-routing-56.md` | trial | Upgrade Codex model / reasoning-effort routing defaults from GPT-5.5 to GPT-5.6. |
| `1_plan/codex-cost-routing/requirements_2026-07-10_codex-cost-routing.md` | implementing | Route Codex models by task cost while keeping user-level model configuration read-only to the skeleton. |
| `1_plan/codex-subscription-routing/requirements_2026-07-23_codex-subscription-routing.md` | confirmed | Ask once during `/bridgeforge` and persist a Codex model-routing tier selected from the user's subscription. |
| `1_plan/codex-skill-routing-dispatch/requirements_2026-07-15_codex-skill-routing-dispatch.md` | trial | Bind all 18 common skills' stages to Codex custom agents, with explicit quality and token-efficiency evidence. |
| `1_plan/confirm-workflow/requirements_2026-07-14_confirm-workflow.md` | trial | Add the shared confirm skill and require develop, debate, and collab to consume its confirmed requirement card. |
| `1_plan/cross-project-write-guard/requirements_2026-07-10_cross-project-write-guard.md` | implementing | Add Claude/Codex hook protection against accidental cross-project writes and dangerous external git operations. |
| `1_plan/ctx-management/requirements_2026-07-09_codex-ctx-budget.md` | implementing | Adapt Codex ctx-budget warnings from the Claude-proven mechanism without assuming a 1M Codex context window. |
| `1_plan/doc-unification/requirements_2026-07-09_doc-unification.md` | implementing | Unify the repository documentation tree under `doc/` and remove the legacy root `docs` tree. |
| `1_plan/non-ascii-shell-guard/requirements_2026-07-10_non-ascii-shell-guard.md` | trial | Add Claude/Codex hook protection against non-ASCII shell transit corruption and scan existing skeleton text. |
| `1_plan/token-context-optimization/requirements_2026-07-15_token-context-optimization.md` | implementing | Reduce Codex startup and long-thread token cost, and standardize all 19 BridgeForge product skills. |
| `1_plan/token-context-optimization/collabs_2026-07-15_implementation.md` | implementing | Track parallel skill standardization and shared token/memory integration work. |

### Pending

| Path | Status | Purpose |
|------|--------|---------|
| `2_pending/2026-07-09_switch_codex_left_claude_live_dir_report.md` | pending | Investigation report for leftover Claude live directory behavior after switching to Codex. |
| `2_pending/2026-07-10_non_ascii_shell_pipe_hook_proposal.md` | pending | Proposal for Claude/Codex hook protection against non-ASCII shell transit corruption. |
| `2_pending/2026-07-10_cross_project_write_guard_proposal.md` | pending | Proposal for Claude/Codex hook protection against accidental cross-project writes. |
| `2_pending/debates_2026-07-15_codex-skill-routing-dispatch.md` | pending | Debate on binding Codex skill stages to named custom agents without eroding quality. |
| `2_pending/2026-07-14_develop-demand-discovery-gap-report.md` | pending | 调查 `develop` 在既有业务载体重构需求中确认过早的缺口，并提出事实核验与需求发现闸门。 |
| `2_pending/debates_2026-07-14_develop-single-question-interview.md` | pending | 审查 `develop` 的单题选择式需求访谈是否符合预期，并记录双 Agent 辩论。 |
| `2_pending/2026-07-17_git-sync-sandbox-permission-report.md` | pending | 下游实机验证 git-sync 的 `.git/FETCH_HEAD` 沙箱权限失败，并提出骨架恢复规则。 |

### Design And Playbooks

| Path | Purpose |
|------|---------|
| `3_design/antifabrication-framework.md` | Anti-fabrication framework and reference hook design. |
| `3_design/codex-harness-parity.md` | Generated Claude/Codex harness parity report. |
| `3_design/design-rationale.md` | BridgeForge architecture and design rationale. |
| `3_design/harness-engineering-design.md` | Harness engineering design. |
| `3_design/harness-impl-plan.md` | Harness implementation plan. |
| `3_design/memory-scoring-design.md` | Memory scoring and deterministic indexing design. |
| `3_design/reverse-sync-playbook.md` | Downstream-to-upstream harvest playbook. |
| `3_design/skill-distribution-gaps.md` | Skill distribution and drift design notes. |
| `3_design/sync-from-upstream-playbook.md` | Upstream-to-downstream sync playbook. |

### Archive

| Path | Purpose |
|------|---------|
| `4_archive/audit_handoff_2026-06-27_debate-collab-rewrite.md` | Historical audit handoff for debate/collab rewrite. |
| `4_archive/codex_agents_dir_cleanup_investigation_2026-07-06.md` | Historical investigation for Codex `.agents` cleanup behavior. |
| `4_archive/debates_2026-06-25_encoding-fix-scope.md` | Historical debate on encoding fix scope. |
| `4_archive/debates_2026-06-25_harness-drift.md` | Historical debate on harness drift. |
| `4_archive/debates_2026-06-25_redline-placement.md` | Historical debate on redline placement. |
| `4_archive/debates_2026-06-27_memory-untrack.md` | Historical debate on memory tracking and deterministic indexing. |
| `4_archive/handoff_2026-06-30_antifabrication-playbook.md` | Historical anti-fabrication playbook handoff. |
| `4_archive/handoff_2026-06-30_antifabrication-playbook_addendum.md` | Historical anti-fabrication playbook addendum. |
| `4_archive/handoff_2026-06-30_antifabrication-playbook_consensus.md` | Historical anti-fabrication playbook consensus. |
| `4_archive/handoff_2026-06-30_stall-vs-fabrication.md` | Historical stall-versus-fabrication handoff. |
| `4_archive/调查报告_AB对话_空转与幻觉_2026-07-01.md` | Historical investigation report for idle-loop and fabrication behavior. |
| `4_archive/调查报告_BOM-no-BOM统一策略与模板污染修复_2026-07-08.md` | Historical investigation report for BOM/no-BOM policy and template contamination. |
| `4_archive/调查报告_bridgeforge-switch-codex-强保护无交互确认_2026-07-07.md` | Historical investigation report for switch-codex strong protection without interactive confirmation. |
| `4_archive/调查报告_codex-bridgeforge-slash入口不可见_2026-07-07.md` | Historical investigation report for invisible Codex slash entry. |
| `4_archive/调查报告_codex-pre-commit-BOM导致spawn失败_2026-07-07.md` | Historical investigation report for Codex pre-commit BOM spawn failure. |
| `4_archive/调查报告_rule-index-check-HTML注释误判_2026-07-02.md` | Historical investigation report for rule-index HTML comment false positive. |

### Reference

| Path | Purpose |
|------|---------|
| `9_reference/examples/antifab-deny-hook.py` | Reference implementation for the anti-fabrication deny hook. |
