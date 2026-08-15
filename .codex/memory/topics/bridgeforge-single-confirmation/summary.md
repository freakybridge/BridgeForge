---
description: BridgeForge 四种维护模式统一为常规零确认、风险最多一次汇总确认；人工差异保留为 gap，用户级权限仅开放封闭入口。
category: topic
topic: bridgeforge-single-confirmation
status: completed
---

# BridgeForge Single Confirmation

2026-08-15，用户验收 BridgeForge 单次确认与零确认更新协议。

最终行为：

- `init`、`adopt`、`update`、`switch` 共用 safe / risk / gap accumulator。常规安全路径不产生 BridgeForge 业务确认；确定性风险动作只生成一张聚合卡。
- apply 前必须重跑 planner 并核对 aggregate fingerprint；输入漂移时零风险写入。人工修改、未知 ownership 和低置信项原样保留为 gap，不再逐项追问。
- Codex native memories consent 复用 schema-v1 managed ledger。`declined` 后不重复询问；旧版已启用但无 consent 的健康安装报告 `legacy_enabled`，不完整安装只记 gap。
- `approved + enabled` 仅在只读健康检查发现漂移时，经非持久平台审批执行 `codex_memory_sync.py maintain`；它拒绝自动 public-to-private，并在 legacy、disabled 或非法 ledger 状态下 fail-closed。
- 可持久授权的用户级入口只有 `bridgeforge_user_maintenance.ps1 -Action refresh`。wrapper 不接受 source、payload、尾参或 native action，也不从用户 hooks 配置执行 Python。
- 普通 whole-file 差异缺少可信历史 hash 时禁止自动覆盖；仅缺失文件、受管 block、稳定 identity merge 和 switch map ownership 可自动推进。

验收收据：相关 unittest 69 项通过，完整下游 fixture 37 项通过，metadata 7 项通过；manifest、mirror drift、`git diff --check` 和五份 switch 脚本镜像一致性通过。独立审计提出的 P1 均已修正。

未现场验证边界：真实 Codex Desktop `prefix_rule` 持久时序及 `/hooks` review/trust、新会话 smoke。静态配置或脚本直跑不得冒充 runtime trust 收据。

权威交付文档：`doc/1_delivery/bridgeforge-single-confirmation/requirements_2026-08-15_bridgeforge-single-confirmation.md`。
