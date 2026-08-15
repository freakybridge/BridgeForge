---
category: topic
topic: bridgeforge-upstream-absorption-modes
status: completed
description: BridgeForge 逐受管区块的 A 激进、B 温和、C 保守上游吸收模式已实现、获用户验收并通过独立发布复审。
kind: delivery
tags: bridgeforge, upstream-absorption, managed-blocks, confirmation, transaction
related_paths:
  - doc/1_delivery/bridgeforge-upstream-absorption-modes/requirements_2026-08-15_bridgeforge-upstream-absorption-modes.md
  - scripts/bridgeforge_project_sync.py
  - templates/codex/managed-skeleton.json
  - skills/bridgeforge/SKILL.md
  - doc/0_architecture/design/codex-project-sync.md
  - tests/harness/test_bridgeforge_project_sync.py
  - tests/harness/test_git_sync_version_release.py
  - tests/harness/run_downstream_fixture.py
---

# BridgeForge 上游吸收模式

## 已验收契约

- 唯一业务确认卡提供 A 激进、B 温和、C 保守三种模式；每轮整体业务确认仍为 0 次或 1 次。
- A 在强风险提示和完整冲突清单后，一次确认执行全部推荐风险项并默认吸收所有可信上游受管区块；禁止整文件覆盖项目自有内容。
- B 支持稳定 `R/U` 编号及逐 U 自定义指令。每条指令必须确定表达 `absorb` 或 `preserve`；两种意图并存、缺少意图或试图在一个 U 内继续细分时零写入拒绝。
- C 保留已经完成的 safe 核心更新，不执行本轮进一步完善，也不保存永久拒绝偏好。
- 每个 `U` 对应一个显式登记的 Markdown 受管区块；同一文件选择多个区块时合并为一次事务写入。无可信边界的变化只进入 manual/blocker。
- `.codex/memory/MEMORY.md` 使用 `seed` 策略；version-release 将 seed 和受管标题区块之外的内容视为项目所有。
- apply 受 aggregate fingerprint、事务快照、失败回滚和 stamp-last 保护；receipt 回显完整冲突卡及逐 U 的吸收/保留效果。

## 独立审计与验证

- 首轮独立审计发现三个发布阻断：B 自定义文字未参与执行、version-release 把 managed_blocks 误判为整文件 ownership、apply receipt 缺少冲突及效果字段；三项均已修复。
- 修复后独立复审重新实测真实 CLI preserve / ambiguous / absorb 路径，四份 version-release ownership 和 receipt 对账，结论为独立发布审计通过。
- 相关回归 43/43、完整 downstream fixture 37/37 通过。
- manifest `--check`、harness parity、mirror drift、skill metadata、schema dogfood 与 `git diff --check` 全部通过。

## 边界

- 用户于 2026-08-15 明确调用 `$summary 同意验收`，产品行为验收成立，topic 已完成。
- 真实下游 Codex UI、runtime trust 和新会话 smoke 未验证；属于非阻塞运行时边界。
- VERSION、CHANGELOG、commit、push 和远端同步收据由紧随其后的受控 `$git-sync` 生成。
