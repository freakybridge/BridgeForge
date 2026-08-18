# 用户级受管 skill 维护

- 活跃目录：`~/.codex/skills/`。
- 活跃账本：`~/.codex/bridgeforge-codex-managed.json`。
- 完整产品 home：`~/.bridgeforge-codex/`。
- Codex 薄入口：`~/.codex/skills/bridgeforge-codex/`，只含入口、references 与 bootstrap updater。
- 唯一刷新入口：Codex 薄入口内的 `scripts/bridgeforge_codex_shared_update.ps1`；每轮最多运行一次。
- updater 只处理 `bridgeforge-codex-manifest.json` 登记的 Codex skills；第三方目录不得修改。
- source 必须来自 GitHub `freakybridge/BridgeForgeCodex` 的 `main` 并逐文件验 hash。
- 产品 home、skill stage/swap、ledger 和崩溃恢复必须处于同一可恢复事务。

旧 `$bridgeforge`、旧 Codex/Claude ledger、旧 `.bridgeforge` home 与旧 Claude Skill 均不再
受支持。产品不得读取、接管或删除这些遗留资产；旧用户必须按当前安装说明重新安装
`$bridgeforge-codex`。正式 Skill 的存在性、hash 与 ledger 一致性只由当前 updater 维护。
