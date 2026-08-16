# 用户级受管 skill 维护

- 活跃目录：`~/.codex/skills/`。
- 活跃账本：`~/.codex/bridgeforge-codex-managed.json`。
- 完整产品 home：`~/.bridgeforge-codex/`。
- Codex 薄入口：`~/.codex/skills/bridgeforge-codex/`，只含入口、references 与 bootstrap updater。
- 唯一刷新入口：Codex 薄入口内的 `scripts/bridgeforge_codex_shared_update.ps1`；每轮最多运行一次。
- 新 updater 只处理 `bridgeforge-codex-manifest.json` 登记的 Codex skills；第三方目录不得修改。`shared-skill-manifest.json` 只供旧 updater 一次性交接，禁止作为新产品分发源。
- source 必须来自 GitHub `freakybridge/BridgeForgeCodex` 的 `main` 并逐文件验 hash。
- 产品 home、skill stage/swap、ledger 和崩溃恢复必须处于同一可恢复事务。

旧 Codex/Claude ledger 只由 `bridgeforge_codex_user_migrate.py` 处理。它必须先给出精确
计划与 fingerprint，经唯一确认后，才可退休 hash 匹配的旧资产。漂移内容原样保留，
不得根据名称或 glob 猜测 ownership。
