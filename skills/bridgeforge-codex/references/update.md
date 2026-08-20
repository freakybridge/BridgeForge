# Codex 骨架更新

仅在根 skill 判定为 `update` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode update` 生成计划。
2. 缺戳、双戳、废弃 `.bridgeforge_version` 或异常值必须零写阻断。
3. current 版本戳 `<1.4.28` 时进入 `PreservationManifest` destructive rebuild；`>=1.4.28` 时先校验已安装 baseline。
4. 重建前独立审计 AGENTS 项目区、rules、hooks、memory 与 Skills，对所有用户决策项逐项确认 preserve 或 delete。
5. apply 前重建 plan 并核对 fingerprint；失败回滚。
6. 所有资产验证通过后最后写 current 版本戳。

不得调用已退役的 switch、finalizer、parity 或布局迁移工具，不得手工写戳。
