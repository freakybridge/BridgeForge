# bridgeforge-codex 安装与迁移

bridgeforge-codex 1.4.2 只支持 Codex。用户级产品入口为
`~/.codex/skills/bridgeforge-codex/SKILL.md`，完整产品 home 为
`~/.bridgeforge-codex`，项目产品面只有
`AGENTS.md + .codex/`。

项目指令由根或嵌套 `AGENTS.md` 原生加载；根文件的公共区由 bridgeforge-codex 管理，项目约束只写入项目级专区；机器可判约束由 hook / pre-commit 执行，
操作流程由 skill 执行，长 SOP 与原理进入 `doc/`。Markdown `paths:` 不是 Codex
指令加载机制，安装过程不会建立这种自研加载器。

## 新安装

1. 克隆 `https://github.com/freakybridge/BridgeForgeCodex.git`。
2. 在仓库根运行 `scripts/install-shared-skills.ps1`。
3. 新开 Codex 会话，运行无参 `$bridgeforge-codex`。

安装器会把完整产品仓库原子安装到 `~/.bridgeforge-codex`，把薄入口与其他 Codex
skills 写入 `~/.codex/skills/`，并把
ownership 记录到 `~/.codex/bridgeforge-codex-managed.json`。项目更新由
`scripts/bridgeforge_codex_project_sync.py` 统一规划、确认、应用和回滚。

## 从旧 BridgeForge 迁移

迁移固定分两步，不能在旧入口中直接修改项目：

1. 最后一次运行旧 `$bridgeforge`。旧 updater 只消费兼容 manifest，安装并
   验证 `$bridgeforge-codex`，然后停止。
2. 新开会话运行 `$bridgeforge-codex`。新入口生成一次带 fingerprint 的风险
   清单；用户确认后，按旧 ledger 与内容 hash 删除可证明归 BridgeForge
   所有的旧 `~/.bridgeforge` home、Codex bundle、旧 ledger 和 Claude 用户级受管
   skills。旧 home 若是已核验的 junction，只删除 junction，本地实体仓库保留。

人工修改、第三方文件和 ownership 无法证明的内容一律保留并报告。迁移失败
会回滚；迁移计划变化后旧确认失效，必须重新确认。

## 项目版本戳

- 当前戳：`.codex/.bridgeforge_codex_version`
- 旧戳：`.codex/.bridgeforge_version`，仅作为 0.86.0+ 迁移输入
- 双戳、非法戳：阻断并要求人工处理
- 拒绝风险项、存在 gap 或应用失败：保留旧戳
- 所有资产验证通过：最后写入新戳，再删除旧戳

## 已退役能力

bridgeforge-codex 不再安装或维护 `CLAUDE.md`、`.claude/`、Claude 入口、
host switch、project finalizer、setup junction 或 harness parity。项目中发现
Claude 遗留时只提示存在，不读取、不迁移、不删除。
