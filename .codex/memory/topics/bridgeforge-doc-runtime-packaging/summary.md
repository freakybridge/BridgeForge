---
description: BridgeForge 的运行手册统一位于 doc/0_playbook；只有该编号子树随 bridgeforge command bundle 分发，其余 doc 只留在工厂仓库。
category: topic
topic: bridgeforge-doc-runtime-packaging
status: superseded
---

# BridgeForge Runtime Documentation Packaging

2026-07-25，根 `references/` 的五份 BridgeForge 运行手册合并至 `doc/0_playbook/`：`init.md`、`adopt.md`、`update.md`、`switch.md`、`user-skill-maintenance.md`。

## 稳定边界

- `doc/0_playbook/` 是 `bridgeforge` command bundle 唯一需要携带的 `doc/` 子树；`shared-skill-manifest.json` 必须只枚举该编号子树，不得把需求卡、设计记录、pending 或 archive 打进用户级安装包。
- 根 `SKILL.md` 与 Claude/Codex 入口包装统一链接和检查 `doc/0_playbook/`；用户入口仍只有 `/bridgeforge` 与 `/bridgeforge switch <agent>`。
- `skills/*/references/` 是各 skill 的局部按需资料，不属于根 BridgeForge 运行手册迁移范围。
- 目录移动后，分发 inventory/hash 与下游 fixture 必须同时更新；运行 `test_shared_skill_distribution.py` 验证安装包没有遗漏或缓存文件。

## 验证收据

- `tests/harness/test_shared_skill_distribution.py`：13/13 通过。
- `tests/harness/run_downstream_fixture.py`：完整下游 harness 通过。
- 根版本从 `0.65.0` 升至 `0.65.1`，CHANGELOG 记录 `[product][meta]` 目录重组。

## 注意

`codex_directory_layout_report_2026-07-25.md` 已由用户明确授权删除；不再作为运行手册目录重组的测试副作用处理。
