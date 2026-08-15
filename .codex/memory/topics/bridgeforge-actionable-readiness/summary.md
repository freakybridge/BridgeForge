---
category: topic
topic: bridgeforge-actionable-readiness
status: completed
description: BridgeForge 更新反馈已采用双状态、可执行 R/C/M/B 清单和单次 A/B/C 部分确认，并由用户明确验收。
kind: delivery
tags: bridgeforge, readiness, confirmation, transaction
related_paths:
  - doc/1_delivery/bridgeforge-actionable-readiness/requirements_2026-08-15_bridgeforge-actionable-readiness.md
  - skills/bridgeforge/SKILL.md
  - scripts/bridgeforge_project_sync.py
  - scripts/bridgeforge_switch.py
  - doc/0_architecture/design/codex-project-sync.md
  - tests/harness/test_bridgeforge_actionable_readiness.py
---

# BridgeForge 可执行就绪清单

## 已验收契约

- 更新反馈分离为 `execution_status` 与 `target_readiness`：前者只描述本轮命令是否执行完成，后者描述目标是否达到完美更新。
- safe 动作自动执行；每轮业务确认保持 0 次或 1 次。唯一确认卡提供 A 全部确认、B 按稳定 action ID 部分确认、C 本轮不再完善。
- action ID 按 R/C/M/B 分类。用户可接受推荐清单，也可在同一次回复中自定义如 `B：R1、C1`。
- 被选 action ID 与 aggregate fingerprint 绑定；确认后状态漂移必须零写入退出，事务失败必须回滚，验证完成后才写版本戳。
- 需要人工完成的 trust、restart、smoke 不得伪报完成；被 Git 忽略的 `__pycache__` / `.pyc` 仅为 advisory，不得降低目标就绪度。
- 新 receipt 字段以 additive 方式提供，保留旧 `status`、`readiness`、`confirmed-risk` 与 `decline-risk` 兼容路径。

## 验证收据

- actionable readiness、project sync、root skill：29/29 通过。
- shared skill distribution：25/25 通过。
- downstream fixture：`switch-retired-stall-warning` 与 `switch-script-mirrors` 均通过。
- manifest current、harness parity、skill metadata、mirror drift、`git diff --check` 均为 exit 0。
- 三份 switch 脚本镜像 SHA-256 一致。

## 边界

- 本轮没有真实 Codex UI A/B/C 试用、平台权限弹窗或新会话 hook/trust smoke 收据；这些运行时信任项仍为未验证。
- 用户已在同一轮授权 Git 同步；最终 commit、push、远端一致性以 `$git-sync` 收据为准。
