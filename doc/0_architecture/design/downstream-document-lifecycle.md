# 下游文档生命周期设计

## 单一事实源

每个下游项目的 `doc/README.md` frontmatter 声明 `delivery_layout: flat | milestone`。所有 skill 必须读取该声明；未声明、混用或迁移中时停止并要求用户决定。

## 目录职责

- `0_architecture/`：系统边界、数据流、接口与 ADR。
- `1_delivery/`：需求确认、计划、验收和正式 debate；flat 为 `<topic>/`，milestone 为 `<M>/<topic>/`。
- `2_bugs/`：Bug 的发现、复现、根因、修复、验证与回归。
- `3_reference/`：外部资料与来源信息。
- `4_archive/`：按原交付层级保存已完成 delivery，按 `bugs/` 保存已解决 Bug。

## 迁移

新项目初始化时选择布局。已有项目升级时仅输出旧 `1_plan/`、`2_pending/`、`3_design/`、`9_reference/` 的迁移提案；必须逐项展示 `git mv` 目标并等待用户确认。
