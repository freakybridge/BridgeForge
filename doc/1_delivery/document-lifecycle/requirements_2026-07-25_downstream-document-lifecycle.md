# 下游文档生命周期重构确认卡

> 状态：confirmed
> 日期：2026-07-25

## 目标

让所有 BridgeForge 下游项目使用统一、可归档的文档生命周期：系统架构、需求交付、Bug 修复和外部资料各有唯一位置。

## 已确认规则

- `doc/` 固定为 `0_architecture/`、`1_delivery/`、`2_bugs/`、`3_reference/`、`4_archive/`。
- `1_delivery/` 支持 `flat` 与 `milestone` 两种布局，由 `doc/README.md` 的 `delivery_layout` 明确声明；禁止混用。
- `$confirm` 的确认卡承担需求论证，不新增 `decision.md`；正式 debate 跟随所属 delivery topic。
- 已完成 delivery 与已解决 Bug 经用户确认后归档；既有下游升级必须展示迁移清单，禁止静默移动。

## 验收

- 两套模板、共享 skill、init/update 手册和相关归档/快照 hook 不再依赖旧文档路径。
- 下游可根据 `delivery_layout` 解析确认卡与讨论记录路径。
