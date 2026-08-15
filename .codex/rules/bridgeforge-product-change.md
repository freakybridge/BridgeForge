---
paths:
  - "templates/*/**"
  - "skills/*/**"
  - "scripts/bridgeforge_*.py"
  - "shared-skill-manifest.json"
  - ".codex/hooks/**"
  - ".codex/scripts/**"
  - ".codex/rules/**"
  - ".codex/managed-skeleton.json"
  - ".codex/skill-routing.json"
  - "AGENTS.md"
  - "VERSION"
  - "CHANGELOG.md"
---

# BridgeForge 产品改动红线

- 通用能力 **必须**进入 `templates/` 或共享 `skills/`；工厂专属约束 **禁止**下沉污染模板。
- 产品层改动 **必须** bump 根 `VERSION`，并在 `CHANGELOG.md` 标记 `[product]`。
- Codex hook/settings 产品改动 **必须**同步 `.codex/` dogfood；缺镜像禁止提交。
- 受管资产 **必须**使用显式 target、稳定 asset id、可验证历史 hash 和单一 ownership strategy；禁止 glob ownership。
- safe/risk/gap 计划 **必须**在 apply 前重算 aggregate fingerprint；漂移时禁止任何写入。
- gap **必须**原样保留并降级收据；禁止把未知 ownership 转成覆盖授权。
- 任一可捕获失败 **必须**回滚本事务写入；版本戳只允许在 ready 时最后写，degraded 必须保留旧戳或无戳。
- 用户级 skill 分发集合 **必须**与 Codex routing 集合一致；global entry 必须同时出现在两份 `AGENTS.md`。
- `--check` / `--dry-run` **必须**零写入。
- 未执行真实下游时 **禁止**写“真实下游已验收”；未执行 runtime smoke 时 **禁止**写“runtime 已验证”。
