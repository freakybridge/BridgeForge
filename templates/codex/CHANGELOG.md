# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本规则见 `.codex/rules/workflow.md §9`（Milestone-bound SemVer，详细版）。

**小项目退化版**（无 Milestone 节奏时可用）：
- **major (X)** — 破坏性变更 / 范式重写
- **minor (Y)** — 新功能（用户多了一件能干的事）
- **patch (Z)** — bug 修复 / 文档调整 / refactor

---

## 版本号 SoT（单一事实源）

本项目版本号写在**根目录的 `VERSION` 文件**，所有其他位置（CLI `--version` / 关于对话框 / build 产物）通过读取或编译时嵌入获取。

<!-- TODO: 若本项目有原生版本源（`package.json` / `Cargo.toml` / `pyproject.toml` 等），可删除根目录 `VERSION` 文件，改用原生源。本 CHANGELOG.md 仍保留。 -->

---

## [Unreleased]

<!-- 新改动先记在这里；下次 commit 时挪到对应版本号 section 下 -->

## [0.24.0] - 2026-07-08

### Added
- [product] 新增 `skill_metadata_check.py` 并接入 `.githooks/pre-commit`：当项目包含 BridgeForge 工厂源头 `skills/<name>/SKILL.md` 时，提交前硬拦缺 `name` / `description` / `user_invocable: true` / `argument` 或 BOM/旧拼写的通用 skill frontmatter；普通下游项目没有根 `skills/` 时自门控 no-op。

## [0.23.0] - 2026-07-08

### Changed
- [product] 用户级 BridgeForge 工厂源头改为 `~/.bridgeforge`：Codex 的 `~/.agents/skills/bridgeforge/SKILL.md` 仍是叶子薄入口，但完整仓库不再推荐放在 `~/.agents/bridgeforge-home`。`skill_sync_check.py` 改为从 `~/.bridgeforge/skills` 比对通用 skill 源，`bridgeforge_switch.py` 优先识别 `~/.bridgeforge` 并保留旧路径 fallback。

## [0.22.0] - 2026-07-08

### Added
- [product] `AGENTS.md` 的 `[clarify]` 响应新增 `$feature-dev` 触发指针：需要落盘需求 / 验收清单 / 用户试用闭环的大需求，转交通用 `feature-dev` skill 承接需求文档、自动拆解、开发、独立验证和反馈修复。同时将入口文件压缩为常驻红线 + 信号路由 + rule 索引，长解释回落到 `rules/*`。`rules/workflow.md` 的 doc/ 依赖说明同步加入 `$feature-dev`，并去掉过时固定 skill 计数。

## [0.21.0] - 2026-07-08

### Changed
- [product] 较大需求主动澄清改为“低用户负担收敛到可靠开发路线”：agent 先给当前理解、可选路线、推荐路线和理由，再逐轮追问高质量问题；问题数量动态调整，每 3 问强制总结，超过 6 问转 PRD / 验收草案 / 设计讨论稿；禁止询问高置信可推断信息，并同步 `[clarify]` settings 注释。

## [0.20.0] - 2026-07-07

### Changed
- `/bridgeforge switch` 改为归档恢复模型：跨 agent 切换会把旧 agent 骨架归档到当前项目 `.bridgeforge/archive/<agent>/<timestamp>/`，每个 agent 只保留最新归档；目标 agent 优先从当前项目归档恢复，没有归档才从上游模板安装。memory 合并到目标 agent，settings 逐项确认，hooks / skills / rules / 入口文件只归档不自动迁移；目标 live path 已存在时停止。

## [0.19.0] - 2026-07-07

### Added
- `/bridgeforge switch` 强保护逐项决策：dirty / untracked 的 agent 骨架文件触发 blocked 时，默认不改任何文件；新增 `--interactive` 逐项确认，以及 `--apply-blocked PATH` / `--keep-blocked PATH` / `--delete-unknown PATH` 三个非交互回放参数，让 agent 可按用户逐项选择继续执行。

## [0.18.0] - 2026-07-07

### Fixed
- Codex 侧 bridgeforge 日常入口改回 `/bridgeforge`：slash 命令清单应显示 `bridgeforge`，`skill_sync_check.py` 的提示语同步改为 `/bridgeforge`。
- Codex 安装改为叶子入口结构：完整 BridgeForge 仓库放在 `~/.agents/bridgeforge-home`，`~/.agents/skills/bridgeforge/SKILL.md` 只放极小 wrapper（源文件 `scripts/codex_bridgeforge_entry.SKILL.md`）。完整仓库不能直接放在 `~/.agents/skills/bridgeforge`，否则 Codex 会加载子 skill，但不显示仓库根 `/bridgeforge`。旧安装残留 `~/.codex/skills/bridgeforge` 也必须迁出技能扫描目录，否则会继续污染 slash 列表。

## [0.17.0] - 2026-07-07

### Fixed
- 用户级通用 skill 路径从旧 `~/.codex/skills/` 修正为 Codex 规范路径 `~/.agents/skills/`，项目专属 skill 路径从 `.codex/skills/` 修正为 `.agents/skills/`：覆盖 `AGENTS.md` 技能目录说明、`rules/portability.md` 单一源约定、`skill_sync_check.py` 漂移检测路径和 settings 注释。
- `skill_sync_check.py` 提示语改为 `$bridgeforge`，避免 Codex 用户继续按 Claude Code slash command 入口操作。
- Codex 模板内的用户可见 skill 调用统一改为 `$skill`，并让 `clarify_reminder.py` / `context_warning.py` 同时豁免 `/` 与 `$` 开头的命令，避免 `$snapshot` / `$resume` 被上下文或澄清 hook 干扰。
- 通用 skill 的历史 `user-invocable` 元数据统一改为 `user_invocable`。
- 退役空 `.agents/` 清理 hook：`.agents/skills/` 是 Codex 官方 repo skill 路径，不再把项目根 `.agents/` 视为必须自动清除的异常；删除 `legacy_agents_cleanup.py` 及其 `PostToolUse` / `SessionStart` 注册。

## [0.16.1] - 2026-07-06

### Fixed
- `legacy_agents_cleanup.py` 追加到文件编辑后的 `PostToolUse`：覆盖 `Edit` / `Write` / `MultiEdit` / Codex `apply_patch`，修复编辑工具链在运行期重新留下项目根空 `.agents/` 时，单靠 `SessionStart` 清理覆盖不到的问题。

## [0.16.0] - 2026-07-06

### Added
- `legacy_agents_cleanup.py` SessionStart hook：清理运行时兼容探测留下的项目根空 `.agents/`，仅删除普通空目录；非空、symlink、junction 或异常均静默 no-op。

## [0.15.0] - 2026-07-06

### Added
- `AGENTS.md` 新增"验证通过三件套"红线：凡交付中写「验证通过 / 测试通过 / 已验证」，必须同时列出实际命令或 test receipt 指纹、具体验证断言、覆盖路径 / 场景；缺任一项只能标「已运行但验证有效性未确认」或「未验证」。

### Fixed
- `settings.json` 中 rule size 注释改指 `templates/codex/rules/meta_rule_design.md`，避免拆目录后继续引用旧 `templates/rules` 路径。
- `scripts/archive_scan.py` 补 `from __future__ import annotations`，避免默认 Python 低于 3.10 时因 `int | None` 类型注解运行时求值直接崩溃。

## [0.14.0] - 2026-07-06

### Added
- `AGENTS.md` 新增"专业表达风格"常驻段：Codex 默认先给结论再给依据，减少空泛安抚和弱判断；新增"默认工作姿态"，明确执行目标时默认读上下文、判断风险、动手、验证并交付；新增"高价值场景输出结构"，要求代码审查先问题、排障先根因、架构判断先推荐结论。

## [0.13.0] - 2026-07-06

### Added
- `AGENTS.md` 新增"自改审计必须独立"常驻红线：当审计对象包含本轮 agent 自己刚做的改动，且用户要求审计 / 复核 / 找遗漏时，必须启动独立 agent 做二次审计。

## [0.12.0] - 2026-07-06

### Changed
- BridgeForge 上游复制 Codex 骨架作为 Codex 初始骨架，并将入口文件改为 `AGENTS.md`；后续版本继续清理 Codex 专属假设。
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
