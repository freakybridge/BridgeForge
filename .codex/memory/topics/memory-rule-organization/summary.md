---
category: topic
topic: memory-rule-organization
status: completed
description: BridgeForge 双 memory 架构与 Native Memory 私有云同步已完成验收；Windows Codex App 生命周期 hook 通过独立 cmd wrapper、运行收据和远端 commit 实机闭环。
kind: delivery
tags:
  - codex-memory
  - project-memory
  - native-memories
  - github-sync
related_paths:
  - doc/1_delivery/memory-rule-organization/requirements_2026-08-14_memory-governance-native-sync.md
  - doc/2_bugs/BUG-codex-native-memory-empty-snapshot-reconcile.md
  - doc/2_bugs/BUG-codex-desktop-native-memory-powershell-hook-not-entering-python.md
  - scripts/codex_memory_sync.py
  - scripts/codex_memory_sync_hook.cmd
  - scripts/tests/test_memory_native_sync.py
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
- Windows 生命周期 hook 的 `commandWindows` 必须调用受管 `cmd.exe` wrapper，再由 wrapper 动态解析当前 Git 根和项目 `.venv`；禁止把内联 PowerShell 命令存在视为 runtime 健康。
- 健康状态必须同时满足 `hookInstalled=true` 与当前 handler revision 的 `hookRuntimeVerified=true`。升级只替换内容完全匹配的官方旧 handler，人工漂移继续 fail closed。

## 验收收据

- 用户已明确执行 `$summary 同意验收`。
- 既有双 memory 架构已完成历史 harness 与 Codex Desktop 引用 smoke；详细历史收据保留在关联需求卡。
- BridgeForge `0.86.3` 空快照与逐字节同步修复通过 memory/shared-distribution 相关测试，真实 GitHub remote 的 6 文件快照与本地 digest 和 commit 一致；详细命令与结果见关联 Bug 文档。
- Windows wrapper 修复通过 60 项定向测试、266 项全量测试和 3/3 下游 fixture；manifest、项目结构与 diff 检查通过。
- BridgeForge `1.4.37` 的正式用户 hook 已重新信任。Codex App 自动触发 `SessionStart` / `Stop` 后生成 `wrapper-start`、`python-exit-0` 和 `hookRuntimeVerified=true` 收据，pending 不存在。
- Native Memory 同步从 revision 11 推进到 12；本地收据与 GitHub `main` 均为 commit `5d568f3b5e93859b5b6040f5be38c77688781644`，未运行手动 reconcile。
- 修复源码由 BridgeForge commit `9012df51fafdfd6511574d78342e0040c3b8d1f2` 发布到 `origin/main`。

## 未验证边界

- 公开仓库转私有与新机器整树恢复仍未联调；这些外部状态不改变本次 Windows 自动同步修复的验收结论。

## 长期约束

- 禁止把项目 memory 与原生 memories 合并、junction 或逐文件拼接。
- 禁止 BridgeForge 自动创建、编辑或整理原生 memory 正文，也禁止用户拒绝开启时写入相关配置。
- 原生 memory 必须按逐字节内容计算和验证 manifest；禁止任何 Git 换行、clean/smudge 或 attributes 转换介入快照读写。
- Windows hook 是否健康必须由当前 handler revision 的实际运行收据证明；静态配置、安装状态或 `/hooks` 展示不能代替 runtime 证据。
- 多设备并发写入、加密或安全擦除需求必须另开设计，不得扩张当前单写入设备模型。
