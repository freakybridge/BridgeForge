---
name: project-target-cleanup-design
description: target_cleanup.py 的核心设计决策（体积而非 atime、自门控、全深度扫描）
metadata:
  node_type: memory
  type: project
  originSessionId: f7e75bfc-a44e-46b9-b1db-f78d0947b7b9
---

`templates/hooks/target_cleanup.py` 三个关键设计选择：

1. **体积而非 atime**：Windows 上 Defender 实时扫描会刷新 atime，`cargo-sweep --time N` 对陈年缓存无效（实测对 200GB+ 只清几百 KiB）。改用 `incremental/` 体积超 `THRESHOLD_GB`(30) 才清。

2. **自门控 no-op**：`find_workspace()` 找不到 Cargo.toml 直接返回 None，对非 Rust 项目静默跳过。因此 `templates/settings.json` 可无条件挂 SessionStart，不需要在 setup 时按主语言裁剪——项目后来新增 Rust crate 也自动激活。

3. **全深度扫描 `**/incremental`**：普通编译缓存在 `target/{debug,release}/incremental`（一层），交叉编译缓存在 `target/<triple>/debug/incremental`（多一层）。用 `**/incremental` 递归到底，两种都覆盖。v0.19.0 最初用 `*/incremental` 只有一层，当次对话修正。

[[feedback-dogfood-hook-gap]]