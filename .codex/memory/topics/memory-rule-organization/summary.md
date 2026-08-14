---
category: topic
topic: memory-rule-organization
status: completed
description: BridgeForge 双 memory 架构交付完成；Codex 原生 memories 支持合法空快照收敛，并以不受 Git 换行转换影响的 opaque bytes 同步私有 GitHub 整树快照。
kind: delivery
tags:
  - codex-memory
  - project-memory
  - native-memories
  - github-sync
related_paths:
  - doc/1_delivery/memory-rule-organization/requirements_2026-08-14_memory-governance-native-sync.md
  - doc/2_bugs/BUG-codex-native-memory-empty-snapshot-reconcile.md
  - scripts/codex_memory_sync.py
  - tests/harness/test_memory_native_sync.py
  - templates/codex/scripts/memory_context.py
  - templates/codex/scripts/memory_router.py
  - templates/codex/scripts/memory_usage.py
---

# Memory 可发现性与原生 memories 同步

## 已验收结论

- BridgeForge 明确维护两套互不混合的 memory：项目 `.codex/memory/` 随项目 Git 管理；Codex 原生 `~/.codex/memories/` 由 Codex 自己生成和读取。
- 项目 memory 在 SessionStart 重建索引后，以 6000 字符预算确定性注入；UserPromptSubmit 返回 3-5 个中英文字段加权候选，成功读取正文后按 session/turn 记录 used 回执。
- Codex 项目不再依赖假想的 `~/.codex/projects/<hash>/memory/` junction；Claude junction 保持原状。
- BridgeForge 默认不擅自开启原生 memories。用户同意后，才合并三个原生开关、保留第三方用户 hooks，并准备固定私有仓库 `bridgeforge-codex-memories`。
- 原生 memories 以不透明整树快照同步：单写入设备、最新整套覆盖、单一 parentless 提交、`--force-with-lease`、最终一致；失败只告警并保留待补同步状态。
- 合法空远端快照是可收敛状态：本地目录不存在时返回 `noop`、写入同步收据并清除 pending，但不创建用户级空目录。
- memory 文件必须按 opaque bytes 同步；临时读取和发布仓库均禁止 Git attributes 或 `core.autocrlf` 改写 LF/CRLF。

## 验收收据

- 用户已明确执行 `$summary 同意验收`。
- 既有双 memory 架构已完成历史 harness 与 Codex Desktop 引用 smoke；详细历史收据保留在关联需求卡。
- BridgeForge `0.86.3` 空快照与逐字节同步修复通过 memory/shared-distribution 相关测试，真实 GitHub remote 的 6 文件快照与本地 digest 和 commit 一致；详细命令与结果见关联 Bug 文档。
- 共享发布 manifest 已重建并通过 current 检查，工作区 diff 格式检查通过。

## 未验证边界

- 用户级 Hook 仍安装 `0.86.2`；安装 `0.86.3` 后的 `/hooks` trust 与 Stop/SessionStart/SessionEnd 时序尚未重新执行运行时 smoke。
- 公开仓库转私有与新机器整树恢复仍未联调；这些外部状态不改变本次源码交付验收结论。

## 长期约束

- 禁止把项目 memory 与原生 memories 合并、junction 或逐文件拼接。
- 禁止 BridgeForge 自动创建、编辑或整理原生 memory 正文，也禁止用户拒绝开启时写入相关配置。
- 原生 memory 必须按逐字节内容计算和验证 manifest；禁止任何 Git 换行、clean/smudge 或 attributes 转换介入快照读写。
- 多设备并发写入、加密或安全擦除需求必须另开设计，不得扩张当前单写入设备模型。
