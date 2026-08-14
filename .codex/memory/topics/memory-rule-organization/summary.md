---
category: topic
topic: memory-rule-organization
status: completed
description: BridgeForge 双 memory 架构交付完成：项目 memory 可确定性加载和召回，Codex 原生 memories 可经可选用户级 hook 与私有 GitHub 最新整树快照同步。
kind: delivery
tags:
  - codex-memory
  - project-memory
  - native-memories
  - github-sync
related_paths:
  - doc/1_delivery/memory-rule-organization/requirements_2026-08-14_memory-governance-native-sync.md
  - scripts/codex_memory_sync.py
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

## 验收收据

- 用户已明确执行 `$summary 同意验收`。
- 相关 harness 历史完整回归为 103 项通过、0 失败；回滚界面实验后重新验收 69/69 通过，其中 memory/Hook/junction 51 项、共享分发 18 项。
- `.codex/hooks/mirror_drift_check.py` 退出 0；`rebuild_shared_skill_manifest.py --check` 报告 manifest current；`git diff --check` 退出 0。
- Codex Desktop 新任务已实际命中一条原生 memory，客户端“引用的记忆”悬浮框显示对应 M2-47 引用；临时 Hook 文案实验已完全回滚。

## 未验证边界

- 真实用户级同步 hook 的 `/hooks` trust、SessionStart/Stop/SessionEnd 时序未做运行时 smoke。
- 真实 GitHub 建仓、公开转私有、网络 `force-with-lease` 和换机恢复未联调。
- 上述外部状态不阻止本次代码交付验收，但后续启用时必须如实保留为上线验证项；不得以隔离测试替代。

## 长期约束

- 禁止把项目 memory 与原生 memories 合并、junction 或逐文件拼接。
- 禁止 BridgeForge 自动创建、编辑或整理原生 memory 正文，也禁止用户拒绝开启时写入相关配置。
- 多设备并发写入、加密或安全擦除需求必须另开设计，不得扩张当前单写入设备模型。
