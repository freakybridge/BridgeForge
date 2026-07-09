# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本规则见 `.claude/rules/workflow.md §9`（Milestone-bound SemVer，详细版）。

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
