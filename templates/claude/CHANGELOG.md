# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本规则见 `.claude/rules/workflow.md §9`（Milestone-bound SemVer，详细版）。

**小项目退化版**（无 Milestone 节奏时可用）：
- **major (X)** — 破坏性变更 / 范式重写
- **minor (Y)** — 新功能（用户多了一件能干的事）
- **patch (Z)** — bug 修复 / 文档调整 / refactor

---

## 版本号 SoT（单一事实源）

本项目版本号写在**根目录的 `VERSION` 文件**，所有其他位置（CLI `--version` / 关于对话框 / build 产物）通过读取或编译时嵌入获取。

<!-- BridgeForge 管理的下游项目始终以根目录 `VERSION` 为骨架版本 SoT；业务 manifest 不参与该版本口径。 -->

---

## [Unreleased]

<!-- 新改动先记在这里；下次 commit 时挪到对应版本号 section 下 -->

### Changed

- [product] **Breaking baseline**：所有 hooks 最低要求 Python 3.11；项目 `.venv` 存在时是唯一解释器，低版本或损坏环境禁止 PATH 回退，pre-commit 在运行任何检查前硬拦。

## [0.32.0] - 2026-07-30

### Changed

- [product] 移除 `stall_warning.py` 及其 hook 注册和 `[stall]` 入口契约；下游更新会强制退役项目级遗留脚本。
- [product] 下游骨架版本唯一取根 `VERSION`，由 BridgeForge 根版本同步；版本 hook 与状态展示忽略业务 manifest。

## [0.31.0] - 2026-07-29

### Added

- [product] `rule_index_check.py` 新增只读 `--audit-all`，供 CI / 人工在不使用 `[skip-rule-size]` 豁免的情况下复核规则索引完整性。

### Fixed

- [product] 规则索引仅解析 `CLAUDE.md` 的“规则文件索引”章节，示例和其他章节中的 `rules/*.md` 不再误计入索引。
- [product] direct switch 仅报告显式 portable Rule 的迁移候选，不再把 Rule 误作可自动投影资产；目标 Rule 和入口索引保持不变。

## [0.30.1] - 2026-07-29

### Changed

- [product] memory junction 迁移统一由无参数 `/bridgeforge` 的既有项目维护分支展示计划并经用户确认后执行；不再向下游暴露不存在的 `/bridgeforge update`。

## [0.30.0] - 2026-07-28

### Added
- [product] memory junction hook 新增 `check` / `plan` / `migrate --confirmed` 项目级状态机：新 clone 可直接建链；已存在的系统 memory 与项目 memory 仅合并各自独有文件，同路径同内容跳过、内容冲突即阻断；完整性校验通过后删除系统目录并建立、验证 junction。

### Changed
- [product] Claude Code 继续由 `.claude/settings.json` 的 `SessionStart` 注册 junction hook；启动阶段只做无损幂等检查，已有系统 memory 的合并与删除收紧到无参数 `/bridgeforge` 的既有项目维护分支展示计划并经用户确认后执行。错误或断裂 junction、异常路径及校验失败均 fail-closed，不再创建 `memory.premigrate.bak`。

## [0.29.0] - 2026-07-25

### Added
- [product] memory 支持按需创建的分类目录与 `topics/<topic>/`：递归索引、检索、重复检测和显式整理均支持嵌套记录；`completed` / `superseded` topic 自动冷却而不搬入 archive。新项目仅创建 `memory/MEMORY.md`，旧项目迁移必须先展示计划并等待用户确认。

## [0.28.0] - 2026-07-25

### Changed
- [product] 下游文档体系改为 architecture / delivery / bugs / reference / archive；`doc/README.md` 的 `delivery_layout` 显式选择 flat 或 milestone 交付路径，确认卡、正式 debate、归档扫描与会话摘要均按新生命周期处理。旧项目升级只提出经用户确认的迁移。

## [0.27.0] - 2026-07-25

### Changed
- [product] `/bridgeforge switch claude` 改为将 Codex 项目资产直接同步至长期保留的 `.claude/`；目标内 `.bridgeforge-map.json` 记录可验证映射，源 `.codex/` 不移动、不归档。宿主专属文件不原样复制；未转译或冲突项以 degraded 状态明确报告。旧项目根 `.bridgeforge/` 仅提示，不读写删。

## [0.26.0] - 2026-07-25

### Added
- [product] `/bridgeforge switch <claude|codex>` 新增逐项 schema v2 语义迁移 manifest：发现旧 live 或 target archive 时只生成提案并 exit `2`，用户逐项确认后才受控执行；成功 receipt 固定写入 `.bridgeforge/migrations/<migration_id>/receipt.json`。

### Changed
- [product] 目标基线固定为含 `.bridgeforge_version` 的当前模板；只有 schema v2 receipt 可作 provenance，archive 仅机械 replay proven `user-owned`，`constraint-generated` 无注册 adapter 时阻断。`source_owner` / `target_owner` 分离，旧 receipt、legacy archive、hard constraint 未满足、Windows 路径碰撞及 link/junction 均 fail-closed。
- [product] 执行采用 approved source-state backup/restore、临时 stage、detached/stage/live/archive exact-tree、target move journal 和完整回滚；archive destination 排他 claim，rollback 只删除本事务 owned archive，并保留预建的空 archive agent 父目录。当前没有 trusted sandbox runner，任何 manifest `evidence.command` 都禁止执行；`contract-smoke` / `native-host` 以 `sandbox-unavailable` 阻断，因此本版本只支持完成纯文本约束迁移。
- [product] schema v2 receipt 与 archive 按 canonical Windows 路径、双向 inventory 和逐文件 hash 完全对账；三跳 lineage duplicate 仅 stable constraint ID 相同者可跳过。不再使用旧 memory/settings 参数、cleanup-only 或整包 archive 恢复。
- [product] 下游同步到 `0.26.0` 后继续使用原 `/bridgeforge switch <agent>`；manifest 是 agent 与用户审核产物，不是新的用户 CLI 或需用户直接调用的脚本参数。

## [0.25.0] - 2026-07-25

### Added
- [product] 新增 Windows-only 共享 skill 分发契约：Claude 用户级目录继续使用 `~/.claude/skills/`，以平台托管账本、manifest 哈希和可恢复更新日志保证仅覆盖 BridgeForge 托管内容并保留第三方 skill。

### Changed
- [product] `/bridgeforge` 改为运行已安装 command bundle 的共享 updater；存量项目 `.agents/` 仅在当前项目 dry-run 与用户确认后迁移。

## [0.22.2] - 2026-07-11

### Changed
- [product] 大需求交付入口从 `/delivery-flow` 简化为 `/develop`，同步入口文件和 workflow rule 示例。

## [0.22.0] - 2026-07-10

### Added
- [product] 新增 `.claude/hooks/non_ascii_shell_guard.py` 并接入 `PreToolUse(Bash)`：阻断含非 ASCII 文本且经 shell 写入或动态执行路径的高风险命令，避免中文、CJK、emoji 等正文在 shell / 终端 / 解释器编码边界被污染；`encoding_check.py` 扩展可疑连续问号 / `U+FFFD` 扫描，编辑后提示、pre-commit 检查 staged 文本。
- [product] 新增 `.claude/hooks/cross_project_write_guard.py` 并接入 `PreToolUse(Bash|PowerShell|Write|Edit|MultiEdit)`：阻断当前项目根外的显式写入、删除、移动和危险外部 git 操作，避免 A 项目对话框静默修改 B 项目代码。

## [0.21.2] - 2026-07-09

### Changed
- [product] 模板内文档指针统一改向 `doc/` 体系：`skill_sync_check.py` 的设计文档引用改为 `doc/3_design/skill-distribution-gaps.md`，`encoding_check.py` 不再扫描已退役的根 `docs` 目录。

## [0.21.1] - 2026-07-09

### Fixed
- [product] 修复 `/bridgeforge switch <agent>` 在目标 agent 已完整存在但旧 agent live 骨架仍残留时的处理：`bridgeforge_switch.py` 进入 cleanup-only，只归档/删除旧 agent 并合并 memory/settings，不覆盖目标 agent；目标只存在一部分时仍阻断。

## [0.21.0] - 2026-07-08

### Added
- [product] 新增 `.claude/hooks/git_add_all_guard.py`、`.claude/hooks/memory_dup_check.py`、`.claude/hooks/cargo_default_run_check.py` 并接入 settings：阻断高风险 bulk git add，新建 memory 前提示同主题碎片化，编辑多 `[[bin]]` 的 `Cargo.toml` 后提示缺少 `default-run`。
## [0.20.3] - 2026-07-08

### Fixed
- [product] 修复 `.claude/hooks/memory_lint.py` 运行态误报：MEMORY.md 链接解析支持带连字符 / 点号的 memory 文件名，并排除生成索引 `MEMORY_COLD.md`，避免正常 memory 文件被报成 orphan。

## [0.20.2] - 2026-07-08

### Changed
- [product] `.claude/hooks/encoding_check.py` 接入 `PostToolUse(Edit|Write|MultiEdit)`：编辑后立即扫描受管文本文件是否带 UTF-8 BOM，作为 pre-commit 前的早期防线。

## [0.20.1] - 2026-07-08

### Fixed
- [product] 明确 Claude 骨架同样执行 UTF-8 无 BOM 规则；新增 `.claude/hooks/encoding_check.py` 并接入 `.githooks/pre-commit`，防止模板、入口、脚本、rule、JSON、memory 等文本文件混入 BOM。

## [0.20.0] - 2026-07-08

### Added
- [product] 新增 `skill_metadata_check.py` 并接入 `.githooks/pre-commit`：当项目包含 BridgeForge 工厂源头 `skills/<name>/SKILL.md` 时，提交前硬拦缺 `name` / `description` / `user_invocable: true` / `argument` 或 BOM/旧拼写的通用 skill frontmatter；普通下游项目没有根 `skills/` 时自门控 no-op。

## [0.19.0] - 2026-07-08

### Changed
- [product] 用户级 BridgeForge 工厂源头改为 `~/.bridgeforge`：Claude Code 的 `~/.claude/skills/bridgeforge/SKILL.md` 改为叶子薄入口，完整仓库不再推荐放在 `~/.claude/skills/bridgeforge`。`skill_sync_check.py` 改为从 `~/.bridgeforge/skills` 比对通用 skill 源，`bridgeforge_switch.py` 优先识别 `~/.bridgeforge` 并保留旧路径 fallback。

## [0.18.0] - 2026-07-08

### Added
- [product] `CLAUDE.md` 的 `[clarify]` 响应新增 `/feature-dev` 触发指针：需要落盘需求 / 验收清单 / 用户试用闭环的大需求，转交通用 `feature-dev` skill 承接需求文档、自动拆解、开发、独立验证和反馈修复。同时将入口文件压缩为常驻红线 + 信号路由 + rule 索引，长解释回落到 `rules/*`。`rules/workflow.md` 的 doc/ 依赖说明同步加入 `/feature-dev`，并去掉过时固定 skill 计数。

## [0.17.0] - 2026-07-08

### Changed
- [product] 较大需求主动澄清改为“低用户负担收敛到可靠开发路线”：agent 先给当前理解、可选路线、推荐路线和理由，再逐轮追问高质量问题；问题数量动态调整，每 3 问强制总结，超过 6 问转 PRD / 验收草案 / 设计讨论稿；禁止询问高置信可推断信息，并同步 `[clarify]` settings 注释。

## [0.16.0] - 2026-07-07

### Changed
- `/bridgeforge switch` 改为归档恢复模型：跨 agent 切换会把旧 agent 骨架归档到当前项目 `.bridgeforge/archive/<agent>/<timestamp>/`，每个 agent 只保留最新归档；目标 agent 优先从当前项目归档恢复，没有归档才从上游模板安装。memory 合并到目标 agent，settings 逐项确认，hooks / skills / rules / 入口文件只归档不自动迁移；目标 live path 已存在时停止。

## [0.15.0] - 2026-07-07

### Added
- `/bridgeforge switch` 强保护逐项决策：dirty / untracked 的 agent 骨架文件触发 blocked 时，默认不改任何文件；新增 `--interactive` 逐项确认，以及 `--apply-blocked PATH` / `--keep-blocked PATH` / `--delete-unknown PATH` 三个非交互回放参数，让 agent 可按用户逐项选择继续执行。

## [0.14.0] - 2026-07-06

### Added
- `CLAUDE.md` 新增"验证通过三件套"红线：凡交付中写「验证通过 / 测试通过 / 已验证」，必须同时列出实际命令或 test receipt 指纹、具体验证断言、覆盖路径 / 场景；缺任一项只能标「已运行但验证有效性未确认」或「未验证」。

### Fixed
- `rules/portability.md` dogfood 镜像路径改为 `templates/claude/hooks ↔ .claude/hooks`；`settings.json` 中 rule size 注释改指 `templates/claude/rules/meta_rule_design.md`，避免拆目录后继续引用旧 `templates/hooks` / `templates/rules` 路径。
- `scripts/archive_scan.py` 补 `from __future__ import annotations`，避免默认 Python 低于 3.10 时因 `int | None` 类型注解运行时求值直接崩溃。

## [0.13.0] - 2026-07-06

### Added
- `CLAUDE.md` 新增"自改审计必须独立"常驻红线：当审计对象包含本轮 agent 自己刚做的改动，且用户要求审计 / 复核 / 找遗漏时，必须启动独立 agent 做二次审计。

## [0.12.0] - 2026-07-06

### Changed
- BridgeForge 上游模板迁入 `templates/claude/`，为后续 Claude/Codex 双骨架切换做目录分离。
- 新增 `scripts/bridgeforge_switch.py`，作为 `/bridgeforge switch <agent>` 的核心执行脚本；支持 dry-run、Git 强保护和切换后验证。

## [0.1.0] - {{TODAY}}

### Added
- 项目初始化（通过 `/bridgeforge` 铺设骨架）

<!-- TODO: 后续每次 bump 版本号时在上方追加新 section，格式：

## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Removed
- ...
-->
