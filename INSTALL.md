# bridgeforge-codex 安装与迁移

bridgeforge-codex 只支持 Codex；最低清洁基线为 `1.4.31`。用户级产品入口为
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

## 旧 BridgeForge 用户

旧 `$bridgeforge` 到 `$bridgeforge-codex` 的自动迁移已经退役。当前安装器不会读取、接管
或删除旧 Codex/Claude ledger、旧 `.bridgeforge` home 或旧用户级 Skill。旧用户必须执行
上面的“新安装”流程；若正式 Skill 的目标路径已被旧安装占用，安装器会按 unmanaged
conflict 阻断，禁止借旧账本猜测 ownership。

## 项目版本戳

- 当前戳：`.codex/.bridgeforge_codex_version`
- 单一合法版本戳只按版本路由：`<1.4.31` 破坏性重建，`>=1.4.31` current-only 更新；旧戳文件名在成功事务中迁移为当前戳
- 缺戳、双戳、非法戳：在 `.venv` bootstrap 与 Planner 前零写阻断
- 旧项目：独立审计后逐项确认 rules、AGENTS 项目区、pre-commit 项目扩展，以及 `.codex/hooks/project_XXXX/` 自包含 Hook 目录；散落 Hook 必须先由独立 Agent 在临时副本或受控前置步骤中整理为这种目录，memory/Skills 自动保留并检查
- 每个可选项目资产必须明确选择保留或删除；临时保留清单不会写入项目，完成更新前即清空
- 所有写入与 validators 通过：删除旧戳并最后写入 1.4.31+ 当前戳
- 1.4.31+：`.codex/managed-skeleton.json` 只保存当前 schema 3 ownership/hash

## 已退役能力

bridgeforge-codex 不再安装或维护 `CLAUDE.md`、`.claude/`、Claude 入口、
host switch、project finalizer、setup junction 或 harness parity。项目中发现
Claude 遗留时只提示存在，不读取、不迁移、不删除。
