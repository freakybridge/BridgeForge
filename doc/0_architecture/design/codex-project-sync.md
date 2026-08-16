# BridgeForgeCodex 项目同步事务

> 状态：implemented（BridgeForgeCodex 1.2.0）
> 入口：`scripts/bridgeforge_codex_project_sync.py`

BridgeForgeCodex 只维护 `AGENTS.md + .codex/`。项目资产 ownership 的唯一事实源是
`templates/managed-skeleton.json` schema v2；每个目标都必须逐资产登记，禁止 glob
ownership 和未知内容覆盖。

`AGENTS.md` 是区域 ownership 的特例：`BRIDGEFORGE:PUBLIC` 公共区只有命中当前或历史发布 hash 才可更新，`BRIDGEFORGE:PROJECT` 项目专区在计划、apply、验证和回滚中保持原始字节。marker 缺失、重复、倒序、嵌套、公共区漂移或专区必需标题损坏均产生 gap；只要 `root.agents` 有 gap，旧 Markdown rule 退休与新骨架版本戳继续被阻断。无 marker 的 0.86.0+ 项目只通过保留的 `section_layout` 迁移一次，禁止走 whole historical replace 覆盖项目内容。

## 流程

```text
detect init/adopt/update
  -> validate current or legacy stamp
  -> build safe/risk/gap/blocker plan + fingerprint
  -> at most one risk confirmation
  -> immediate replan/fingerprint check
  -> transactional apply
  -> validate assets, Markdown, memory and git diff
  -> write .codex/.bridgeforge_codex_version last
```

旧 `.codex/.bridgeforge_version` 仅作为 `0.86.0+` 迁移输入。旧戳迁移属于 risk；双戳、
非法戳和低于最低 lineage 的版本阻断且零写入。拒绝风险项、存在 gap 或验证失败时保留
旧戳；只有全部验证通过才在同一事务删除旧戳并最后写新戳。

## 退役边界

Claude 项目资产只做 existence probe 并提示停止支持，禁止读取、迁移或删除。switch、
project finalizer 与 harness parity 不再是活跃执行步骤；其已发布 Codex 文件 hash 只保留在
schema retirement lineage，用于安全识别和删除仍保持原样的旧受管副本。
