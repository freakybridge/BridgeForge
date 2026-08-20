# bridgeforge-codex 项目同步事务

> 状态：implemented（bridgeforge-codex 1.4.28）
> 入口：`scripts/bridgeforge_codex_project_sync.py`

bridgeforge-codex 只维护 Codex 当前产品面。公共资产 ownership 的唯一产品来源是
`templates/managed-skeleton.json` schema 3；合同只保存当前版本的稳定 asset id、显式
source/target、ownership strategy 和当前 hash/projection，禁止历史版本集合、retirement、
adaptation proof 与 glob ownership。

## 版本分流

```text
空白骨架身份 + init
  -> 安装当前 Template

合法 .codex/.bridgeforge_version < 1.4.28
  -> 独立只读审计
  -> 用户逐项确认项目 rules/hooks/AGENTS 项目区
  -> 一次破坏性重建风险确认
  -> fresh canonical Template + 精确白名单 + memory/Skills

合法 .codex/.bridgeforge_codex_version >= 1.4.28
  -> current-baseline 常规 update

缺戳 / 双戳 / 非法戳 / 身份不一致
  -> 零写阻断
```

破坏性重建不会复用常规 merge。它先生成 fresh canonical，再只放回确认的 AGENTS 项目区、
项目 hook 注册与文件、pre-commit 项目扩展、项目 rules，以及自动保留并通过当前检查的
`.codex/memory/**` 和 `.codex/skills/**`。未进入白名单的旧骨架内容删除；不生成持久 before 包。

## Current-only 事务

```text
verify real baseline + trusted Git HEAD anchor
  -> build deterministic actions + aggregate fingerprint
  -> immediate replan/fingerprint check
  -> temporary transaction snapshot
  -> apply current assets / selected preserved assets
  -> rebuild memory derived indexes
  -> verify actions + preserved knowledge
  -> config health + text hygiene validators
  -> verify current baseline on real disk
  -> delete obsolete stamp if applicable
  -> write .codex/.bridgeforge_codex_version last
```

任一可捕获失败必须恢复本事务写入及 memory 派生产物。Planner、Apply、`$git-sync` 与
pre-commit 直接复用 `current_baseline.py`；pre-commit 同时检查 worktree 与 Git index，防止
暂存/未暂存视图不一致。公共资产漂移、合同损坏或同版本合同自证修改不能通过风险确认覆盖。

## 项目资产边界

- 根 `AGENTS.md` 公共区由产品管理；项目区只有进入旧项目白名单才逐字保留。
- `.codex/hooks.json` 只允许 canonical managed handler 与明确保留的第三方 handler；未知
  managed ID 阻断。
- schema 3 merge/Markdown/region/AGENTS 都携带当前可验证 projection；真实下游不存在
  `templates/**` 时也不得跳过。
- 项目 memory/Skills 正文不得语义改写；只允许派生索引重建和 current metadata 校验。
- Claude、switch、project finalizer 与 harness parity 不属于当前产品面，也不保留识别谱系。
