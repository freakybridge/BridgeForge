---
status: implemented
topic: codex-harness-parity
source: user-confirmed version-domain decision
---

# 下游业务版本与骨架版本分离确认卡

## 已确认规则

- 下游业务版本与 BridgeForge 骨架版本是两个独立生命周期，禁止互相推导或覆盖。
- 根 `VERSION`、原生 manifest 与其他业务版本来源均由下游项目维护；BridgeForge 禁止创建、改写、展示或检查它们。
- 当前宿主 `.<host>/.bridgeforge_version` 是唯一骨架版本戳，仅由 `/bridgeforge init` 与 `/bridgeforge update` 写为上游 `$BRIDGEFORGE_HOME/VERSION`。
- 下游业务提交和本地骨架定制不得要求 bump 骨架版本戳。
- BridgeForge 工厂自身的根 `VERSION` 仍表示上游产品版本；仅产品层 `templates/**` 或 `skills/**` 改动提交时必须同次更新它。

## 验收

1. init / update 后，`.bridgeforge_version` 等于上游版本，已有业务版本文件逐字不变。
2. 下游业务提交不因根 `VERSION` 或业务 manifest 未暂存而被 BridgeForge 阻断。
3. BridgeForge 工厂暂存产品层但未暂存根 `VERSION` 时，factory gate 返回 `exit 2`。
4. Codex / Claude 模板、dogfood 副本与 downstream fixture 对版本域语义一致。
