# bridgeforge-codex 项目同步事务

> 状态：implemented（bridgeforge-codex 1.4.12）
> 入口：`scripts/bridgeforge_codex_project_sync.py`

bridgeforge-codex 只维护 `AGENTS.md + .codex/`。项目资产 ownership 的唯一事实源是
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
  -> run the trusted release transition preflight with the prospective stamp
  -> write .codex/.bridgeforge_codex_version last
```

旧 `.codex/.bridgeforge_version` 仅作为 `0.86.0+` 迁移输入。旧戳迁移属于 risk；双戳、
非法戳和低于最低 lineage 的版本阻断且零写入。拒绝风险项、存在 gap 或验证失败时保留
旧戳；只有全部验证通过才在同一事务删除旧戳并最后写新戳。

## 提交前迁移证明

项目同步器在准备报告 ready 且本轮实际修改受管资产时，从产品 Template 加载受 contract 哈希保护的
`version_release.py`，用 Git 工作树真实的 unstaged、staged、untracked 路径和计划中的新骨架
版本执行只读 transition preflight。该预检与 `$git-sync` 共用同一 ownership classifier：hooks
只比较受管 dispatcher 投影，managed Markdown 只比较受管标题与 keyed rows，region 只比较受管
区块，AGENTS 继续比较公共区与可信 legacy mapping；项目内容分别保留并归类为 project change。

需要写新戳时预检使用 prospective stamp；当前戳已是目标版本时，预检严格使用真实 changed
paths，不虚构 stamp 变化。预检不得 stage、修改业务版本、commit、push 或生成 bytecode cache。
预检失败会回滚本轮项目同步写入，保留旧骨架
戳，并按 stable asset id/target/reason 输出 `G*` action-required 清单。收据中的
`release_preflight_status=passed` 是受管变更报告 ready 的前置条件；无 Git HEAD 的首次初始化明确记为
`not_applicable`，存在 gap 或拒绝执行项而本就不写戳时记为 `not_required`。

## 退役边界

Claude 项目资产只做 existence probe 并提示停止支持，禁止读取、迁移或删除。switch、
project finalizer 与 harness parity 不再是活跃执行步骤；其已发布 Codex 文件 hash 只保留在
schema retirement lineage，用于安全识别和删除仍保持原样的旧受管副本。
