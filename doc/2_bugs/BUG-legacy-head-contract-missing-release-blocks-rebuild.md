# BUG：旧 HEAD 合同缺少发布版本时重建事务被误拦

## 状态

- 发现日期：2026-08-21
- 发现项目：`D:\Quant\causis_risk_suite`
- 影响版本：BridgeForgeCodex 1.4.34 及之前
- 修复版本：1.4.35（源码、传播与自动测试已完成；尚未 commit / push / 发布）

## 现象

CausisRiskSuite 从 1.4.26 进入 destructive rebuild。Planner 为 `ready`，
PreservationManifest 已独立审计并逐项确认，但 Apply 在末端校验失败并完整回滚：

```text
HEAD release is not MAJOR.MINOR.PATCH: None
```

回滚后骨架版本戳仍为 1.4.26，Git HEAD、dirty 业务改动与三个 stash 均未改变。

## 根因

旧 schema-v2 `HEAD:.codex/managed-skeleton.json` 没有 `release_version`，但 HEAD
保存了合法的旧 Codex 骨架版本戳。检查器只读取合同发布版本，没有把旧戳作为这种旧合同
的前向迁移锚，因此无法证明 1.4.26 -> 1.4.34 是合法前进。

## 修复

- 只有 HEAD 合同缺少 `release_version` 且新旧合同确实不同时，才读取 HEAD 中
  `.codex/.bridgeforge_codex_version` 或 `.codex/.bridgeforge_version`。
- 只接受唯一且符合 `MAJOR.MINOR.PATCH` 的 Codex HEAD 版本戳。
- 新合同必须严格高于可信旧戳；同版本自证继续 fail-closed。
- 两个旧戳冲突、旧戳非法或缺失时继续 fail-closed。
- HEAD 合同已有有效发布版本时，残留旧戳不参与判断。
- Template 与 factory dogfood 的检查器同轮同步，合同哈希由官方 manifest 重建器生成。

## 验证证据

- Causis 现场回归与 4 类信任边界测试：5 项通过。
- current-baseline / project-sync 组合测试：56 项通过（首次审计前基线）。
- 全仓自动测试：257 项通过（最终修订后完整重跑）。
- downstream fixture：init 幂等、旧项目确认重建、当前漂移零写入均通过。
- manifest `--check`、project structure、Skill metadata、instruction source 均通过。
- 首轮独立审计发现并阻断了无条件读取 HEAD stamp 的 High；第二轮发现两个
  Medium；全部修订后第三轮独立复审未发现 Blocker / High / Medium。

## 真实下游终态

尚未完成。官方 Skill 禁止从本地开发工作树或未发布 clone 给真实项目补文件；需在用户
明确授权 BridgeForge 产品 commit / push 后刷新官方 product home，再重新执行
CausisRiskSuite 的 plan -> apply -> validators -> stamp-last -> no-op replan。
