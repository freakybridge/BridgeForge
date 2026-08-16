# Codex 骨架更新

仅在根 skill 判定为 `update` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode update` 生成计划。
2. 新版本戳是当前状态；旧 `.bridgeforge_version` 仅作为 `0.86.0+` 迁移输入。
3. 双戳、异常值或低于基线必须阻断；旧戳迁移属于 risk。
4. 拒绝、gap 或验证失败时保留旧戳。
5. 上游 Markdown 按 heading/key 合并；项目独有行和 project-owned 区块不得整段覆盖。
6. apply 前重建 plan 并核对 fingerprint；失败回滚。
7. 只有无 gap、无拒绝且验证通过时，才删除旧戳并最后写新戳。

不得调用已退役的 switch、finalizer 或 parity 工具，不得手工写戳或整套重装项目骨架。
