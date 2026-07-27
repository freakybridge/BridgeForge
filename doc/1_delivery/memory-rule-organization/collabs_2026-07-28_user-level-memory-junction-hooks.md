---
status: superseded
topic: memory-rule-organization
created: 2026-07-28
confirmation_card: requirements_2026-07-28_user-level-memory-junction-hooks.md
debate: debates/2026-07-28_user-level-memory-junction-hooks.md
superseded_by: requirements_2026-07-28_project-level-memory-junction-hooks.md
---

# Collab：用户级双宿主 memory junction hook

## 目标与硬约束

实现已确认的用户级双宿主 junction runtime：新 clone 的空系统路径自动恢复；已有系统路径仅由确认式 `/bridgeforge` 迁移；现有 shared updater 继续 skill-only；runtime 更新不可绕过宿主 trust。

## 接口契约

- runtime：`memory_junction.py --host codex|claude`，从 stdin hook payload 读取 `cwd`；只允许在系统 memory 路径不存在时建 junction；其余状态诊断并 exit 0。
- reconciler：`bridgeforge_user_runtime.ps1` 是唯一管理用户级 runtime、hook 配置与 ownership ledger 的入口；支持 plan/apply/recover，配置 handler 直接引用 content-addressed runtime。
- cutover：项目内 host-specific marker 最后写；legacy 注册或脚本任一存在时 runtime no-op。

## 拆分计划

| 组 | 负责人 | 文件边界 | 依赖 |
|---|---|---|---|
| 1A | implementation-worker | 新 runtime Python、其专属测试 | 无；按接口契约实现 |
| 1B | implementation-worker | 独立 PowerShell reconciler、初装入口、受管资产 manifest | 无；消费固定 runtime CLI |
| 2A | implementation-worker | Codex/Claude 模板与本仓 dogfood 镜像：移除 legacy junction 脚本/注册，接入 cutover 迁移入口 | 依赖 1A/1B 的路径和 marker 契约 |
| 2B | implementation-worker | BridgeForge 手册、迁移说明、版本与 CHANGELOG | 依赖最终文件/命令名 |
| 3 | main + review-auditor | 串联、回归测试、独立审计与修复 | 依赖 1/2 完成 |

## 验收

- runtime 单测覆盖 marker/legacy/路径/ledger/正确与错误 junction；reconciler 覆盖两侧配置 merge、回滚与 trust-pending。
- 模板/狗粮镜像及版本 CHANGELOG 完整；现有 shared updater 回归不越权。
- 独立审计验证最终 `git diff`、接口衔接和遗漏风险。
