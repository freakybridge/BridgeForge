# Codex 骨架更新

仅在根 skill 判定为 `update` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode update` 生成计划。
2. 缺戳、双戳或异常值必须零写阻断；恰好一个合法戳时只按版本路由，不按文件名路由。
3. 版本 `<1.4.31` 时进入 `PreservationManifest` destructive rebuild；`>=1.4.31` 时先校验已安装 baseline，旧文件名在同一事务中迁移为 current stamp。
4. 重建前独立审计 AGENTS 项目区、rules、hooks、memory 与 Skills，对所有用户决策项逐项确认 preserve 或 delete。
5. 散落 Hook 或非 canonical 注册必须阻断；由独立 Agent 在临时副本或受控前置步骤中整理为 `.codex/hooks/project_XXXX/entrypoint.py` 自包含目录后重新规划。
6. apply 前重建 plan 并核对 fingerprint；失败回滚。
7. 所有资产验证通过后最后写 current 版本戳。

不得调用已退役的 switch、finalizer、parity 或布局迁移工具，不得手工写戳。
