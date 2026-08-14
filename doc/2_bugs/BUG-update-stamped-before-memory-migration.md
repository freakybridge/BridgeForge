# BUG：既有项目 memory 未迁移却提前写入骨架版本戳

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
