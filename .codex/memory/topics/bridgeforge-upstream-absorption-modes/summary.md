---
category: topic
topic: bridgeforge-upstream-absorption-modes
status: completed
description: BridgeForge 逐受管区块的 A 激进、B 温和、C 保守上游吸收模式已实现，并完成末尾空行回归修复与用户验收。
kind: delivery
tags: bridgeforge, upstream-absorption, managed-blocks, confirmation, transaction
related_paths:
  - doc/1_delivery/bridgeforge-upstream-absorption-modes/requirements_2026-08-15_bridgeforge-upstream-absorption-modes.md
  - scripts/bridgeforge_project_sync.py
  - templates/codex/managed-skeleton.json
  - shared-skill-manifest.json
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
- `confirmation.options` 是不可改写的显示契约；冲突必须逐 U 展示完整项目相对路径、区块、上游效果、本地影响与可恢复性，禁止压缩为编号范围或 basename。

## 0.94.0 下游格式回归修复

- 根因是缺失受管区块追加到文件末尾时复用了模板中间区块的分隔空行，导致 `AGENTS.md` 和 `workflow.md` 产生第二个末尾换行；旧比较逻辑又会归一化该边界，因此无法自愈。
- 受管区块改为按目标位置渲染：非末尾区块保留标题分隔空行，末尾区块只保留一个终止换行。既有 0.94.0 多余末尾空行被分类为 safe 边界修复，无需再次确认吸收。
- 写版本戳前对本轮受管路径执行 `git diff --check HEAD -- <targets>`；失败进入原事务回滚，禁止留下新版本戳。

## 独立审计与验证

- 上游吸收模式首轮独立审计发现的 B 自定义执行、managed-block ownership 和 receipt 对账三个阻断均已修复；独立复审通过。
- 本次格式回归修复已有 35 项相关 unittest、真实 CLI absorption-card fixture、manifest `--check` 与 `git diff --check` 通过收据。
- 用户于 2026-08-15 明确调用 `$summary 同意验收`，本次回归修复验收成立，topic 保持 completed。

## 边界

- 真实下游 `ClaudeBridgeAssist` 的本次版本试用由用户后续执行，当前未验证。
- 当前会话未取得 Codex `/hooks` review/trust 或新会话 smoke 收据，runtime trust 未验证。
- VERSION、CHANGELOG、commit、push 和远端同步收据由紧随其后的受控 `$git-sync` 生成。
