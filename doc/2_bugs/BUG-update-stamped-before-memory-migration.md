# BUG：既有项目 memory 未迁移却提前写入骨架版本戳

> **状态**：`Resolved`（2026-08-15）

## 现象

既有项目执行 `/bridgeforge` 后，`.bridgeforge_version` 已更新为上游版本，但项目
memory 仍可能保留嵌套宿主目录、非法 topic slug、缺失 description 或同一 topic
多个文件。后续再次运行会因版本相等而误判为“已是最新”。

## 根因

1. update 手册只要求自然语言盘点，没有强制调用统一的 schema 审计器。
2. `hooks_merge.py --stamp-version` 能在 hooks 局部成功后提前写版本戳。
3. `config_health_check.py --strict` 没有把 memory schema 纳入硬失败。

## 修复

- `memory_lint.py --organize --project-root <root> --host <host>` 成为每次 update 的
  强制只读计划，校验 description、规范路径、topic 唯一 `summary.md` 和碰撞。
- apply 必须显式带 `--confirmed`；未确认或有语义冲突时零写入。
- `hooks_merge.py` 不再接受或写入版本号。
- `bridgeforge_project_finalize.py` 成为 update 唯一写戳入口；它重新运行 canonical
  memory 审计和项目严格配置体检，两者都通过后才原子写戳。

## 回归边界

双宿主测试覆盖 CausisRiskSuite 同形异常、未确认 apply、memory 审计失败、配置体检
失败、旧版本戳保留，以及合法项目最终写戳。下游项目内容不在本修复中自动改写。

## 2026-08-15 系统重构复核

- Codex `init/adopt/update` 已收敛到 `bridgeforge_project_sync.py`；旧 finalizer 不再是 Codex 第二事务入口。
- canonical memory auditor 的明确/高置信计划进入统一 risk 决策；ambiguous memory 原样保留为 gap。
- memory tree 在 apply 前纳入快照；迁移后验证或写戳失败恢复原路径和字节。
- 仅 ready 事务最后写入 `.codex/.bridgeforge_version`；gap/risk 拒绝保留旧戳或无戳，版本相同也会重新 planner，不再靠 stamp 短路资产审计。
- 双真实样本均完成故障回滚演练、正式 apply 和第二次幂等运行；所有 gap hash 保持不变，degraded 结果均保留旧 `0.90.0` 版本戳。本 Bug 的源码、fixture 与真实下游边界已闭环。
