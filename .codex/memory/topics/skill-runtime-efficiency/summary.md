---
category: topic
topic: skill-runtime-efficiency
status: completed
description: BridgeForge 非根 skill 已通过条件式 fast path、Git 子进程合并和 memory 索引去重降低固定运行开销，并由用户明确验收。
kind: delivery
tags:
  - bridgeforge
  - skill
  - performance
  - routing
related_paths:
  - doc/1_delivery/skill-runtime-efficiency/requirements_2026-08-15_skill-runtime-efficiency.md
  - skills/archive-scan/SKILL.md
  - skills/find-doc/SKILL.md
  - skills/find-memory/SKILL.md
  - skills/todo/SKILL.md
  - skills/debate/SKILL.md
  - skills/summary/SKILL.md
  - templates/codex/skill-routing.json
  - templates/codex/hooks/show_state.py
  - templates/codex/scripts/archive_scan.py
  - tests/harness/test_skill_runtime_efficiency.py
---

# BridgeForge skill 运行效率优化

## 已验收结论

- `archive-scan`、`find-doc`、`find-memory` 与 `todo` 的单一高置信结果留在主对话；只有歧义、多候选或递归冷检索才分派 `light-explorer`，用户确认和写入边界不变。
- `debate` 删除 A/B 之前的重复 research explorer，仍保留两个不同立场 agent、真实代码研读和审查强度。
- `summary` 与 `todo` 不再人工维护派生 memory 索引；writer 成功后复用其 rebuild 收据，禁止重复显式重建。
- `show_state.py` 用一次 `git status --porcelain=v2 --branch` 保留 branch、dirty、ahead/behind、detached 和 no-upstream 语义；Codex/Claude 模板与 dogfood 已同步。
- `archive_scan.py` 把逐候选 `git log` 合并为一次批量查询，使用 NUL 分隔和关闭路径转义保留中文路径、未跟踪文件、评分与排序语义；四份宿主镜像一致。
- 本轮未削减 `create-worktree`、`git-sync`、`collab`、L 级 `develop` 或 `escalate` 的高风险校验与独立审查。

## 验收收据

- 用户于 2026-08-15 明确执行 `$summary 同意验收`。
- 行为与安全回归 34/34 通过；分发与根入口回归 33/33 通过；中文路径边界修复后的定向回归 31/31 通过。
- shared manifest、harness parity、skill metadata、mirror drift 与 `git diff --check` 最终全部通过。
- 本机 `show_state prompt-state` 五次平均 66.4ms；同机优化前约 99-119ms。该收据只证明本机 Git 进程固定开销下降，不承诺网络、模型或平台调度的固定总耗时。

## 发布与运行时边界

- 用户在验收后同轮明确授权 `$git-sync`；最终版本、commit、push 目标与 ahead/behind 以受控同步脚本收据为准。
- named-agent 的真实平台调度耗时与下游端到端总耗时未验证，静态路由测试不替代运行时 smoke。
- Hook 模板、dogfood 与测试一致，但当前 Codex Desktop lifecycle `/hooks` trust 和新会话自动触发没有现场收据，`runtime trust 未验证`。
