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

## [0.31.2] - 2026-07-11

### Changed
- [product] Codex 模型选择范围收窄到 GPT-5.6 家族：默认主对话改为 `gpt-5.6-terra + medium`，轻量探索改为 `gpt-5.6-luna + low`，实现 / 复核 / xhigh 继续使用 GPT-5.6 Terra/Sol 分层；模型策略机检和说明同步更新。

## [0.31.1] - 2026-07-11

### Changed
- [product] 大需求交付入口从 `$delivery-flow` 简化为 `$develop`，同步入口文件、workflow rule 示例和 harness parity 共享 skill 清单。

## [0.31.0] - 2026-07-10

### Changed
- [product] Codex 成本路由调整为默认主对话 `gpt-5.5 + medium`、轻量检索 `gpt-5.5 + low`、明确开发/跨文件判断 `gpt-5.6-terra + high`、高风险实现与独立审查 `gpt-5.6-sol + high`；`xhigh` 继续只由用户当次选择。新增 `user_config_write_guard.py` 并接入 PreToolUse，禁止骨架写入用户级 `~/.codex/config.toml`；模型策略机检与 fixture 同步覆盖绝对、环境变量与波浪路径保护。

## [0.30.1] - 2026-07-10

### Changed
- [product] Codex `context_warning.py` 默认窗口按当前 `/status` 观察从 `258_000` 重新校准为 `353_000`，保留 `BRIDGEFORGE_CODEX_CTX_WINDOW` 覆盖能力；`[ctx-budget]` 仍输出 `surface=codex`、`token_source`、`window_source` 便于后续继续校准。

## [0.30.0] - 2026-07-10

### Changed
- [product] Codex 模型 / effort 路由升级到 GPT-5.6 代际：`.codex/config.toml` 默认主对话改为 `gpt-5.6-terra + medium`；`.codex/agents/` 四档 agent 改为 `light-explorer`（`gpt-5.6-luna + low`）、`implementation-worker`（`gpt-5.6-sol + high`）、`review-auditor`（`gpt-5.6-sol + high`）和需用户确认的 `xhigh-auditor`（`gpt-5.6-sol + xhigh`）；`model_policy_check.py` 同步硬拦新策略漂移，`xhigh` 用户确认门槛不变。

## [0.29.0] - 2026-07-10

### Added
- [product] 新增 `.codex/hooks/non_ascii_shell_guard.py` 并接入 `PreToolUse(Bash)`：阻断含非 ASCII 文本且经 shell 写入或动态执行路径的高风险命令，避免中文、CJK、emoji 等正文在 shell / 终端 / 解释器编码边界被污染；`encoding_check.py` 扩展可疑连续问号 / `U+FFFD` 扫描，编辑后提示、pre-commit 检查 staged 文本。
- [product] 新增 `.codex/hooks/cross_project_write_guard.py` 并接入 `PreToolUse(Bash|PowerShell|Write|Edit|MultiEdit)`：阻断当前项目根外的显式写入、删除、移动和危险外部 git 操作，避免 A 项目对话框静默修改 B 项目代码。

## [0.28.3] - 2026-07-09

### Fixed
- [product] 修复 Codex `context_warning.py` 照抄 Claude 1M 上下文窗口导致预警静默失效的问题：Codex 侧保留 Claude 成熟的 transcript usage 读取和 `$snapshot` / `$resume` 豁免机制，但默认按 `/status` 实测约 `258K` 的 `258_000` 有效窗口计算，并支持 `BRIDGEFORGE_CODEX_CTX_WINDOW` 覆盖；`[ctx-budget]` 输出新增 `surface=codex`、`token_source`、`window_source` 便于后续校准。

## [0.28.2] - 2026-07-09

### Changed
- [product] 模板内文档指针统一改向 `doc/` 体系：`harness_parity_check.py` 的报告目标改为 `doc/3_design/codex-harness-parity.md`，`skill_sync_check.py` 的设计文档引用改为 `doc/3_design/skill-distribution-gaps.md`，`encoding_check.py` 不再扫描已退役的根 `docs` 目录。

## [0.28.1] - 2026-07-09

### Fixed
- [product] 修复 `/bridgeforge switch <agent>` 在目标 agent 已完整存在但旧 agent live 骨架仍残留时的处理：`bridgeforge_switch.py` 进入 cleanup-only，只归档/删除旧 agent 并合并 memory/settings，不覆盖目标 agent；目标只存在一部分时仍阻断。

## [0.28.0] - 2026-07-08

### Added
- [product] 新增 `.codex/hooks/git_add_all_guard.py`、`.codex/hooks/memory_dup_check.py`、`.codex/hooks/cargo_default_run_check.py` 并接入 settings：阻断高风险 bulk git add，新建 Codex memory 前提示同主题碎片化，编辑多 `[[bin]]` 的 `Cargo.toml` 后提示缺少 `default-run`；同步登记 `harness_parity_check.py` 差异分类。

## [0.27.4] - 2026-07-08

### Changed
- [product] `.codex/scripts/harness_parity_check.py` 扩展覆盖 `memory`，新增共享 `skills/*/SKILL.md` metadata / BOM / Claude-only marker 检查；20 个 Claude/Codex harness 差异全部带机器可读分类，报告在无缺失、无未分类差异、无 skill 问题时输出 `OK`。同时只替换独立 `/skill` 命令，并对原文件一致的共享脚本直接判无差异，避免路径片段和共享脚本误报。

## [0.27.3] - 2026-07-08

### Fixed
- [product] 修复 `.codex/hooks/memory_lint.py` 运行态误报：MEMORY.md 链接解析支持带连字符 / 点号的 memory 文件名，并排除生成索引 `MEMORY_COLD.md`，避免正常 memory 文件被报成 orphan。

## [0.27.2] - 2026-07-08

### Changed
- [product] `.codex/hooks/encoding_check.py` 接入 `PostToolUse(Edit|Write|MultiEdit)`：编辑后立即扫描受管文本文件是否带 UTF-8 BOM，作为 pre-commit 前的早期防线。

## [0.27.1] - 2026-07-08

### Fixed
- [product] 统一 Codex 骨架文本文件为 UTF-8 无 BOM，修复 `memory/_stats.json` 被普通 JSON 解析器拒绝的问题；新增 `.codex/hooks/encoding_check.py` 并接入 `.githooks/pre-commit`，提交前硬拦模板、入口、脚本、rule、JSON、memory 等文本文件继续混入 BOM。

## [0.27.0] - 2026-07-08

### Added
- [product] 新增 `.codex/scripts/harness_parity_check.py`，用于刷新 `doc/3_design/codex-harness-parity.md`，长期维护 Claude/Codex harness 对照清单；Codex git-sync 执行器会在暂存前刷新该报告。

### Changed
- [product] Codex hook 的兼容环境变量回退改为优先读取 `CODEX_TOOL_INPUT` / `CODEX_TOOL_NAME`，再兼容旧导入配置里的 `CLAUDE_TOOL_INPUT` / `CLAUDE_TOOL_NAME`；用户入口文案统一为 `/bridgeforge`，与 Claude 保持一致。

## [0.26.0] - 2026-07-08

### Added
- [product] 新增 Codex 模型 / effort 分层路由：`.codex/config.toml` 默认主对话 `gpt-5.5 + medium`；`.codex/agents/` 预置 `light-explorer`（`gpt-5.4-mini + low`）、`implementation-worker`（`gpt-5.5 + high`）、`review-auditor`（`gpt-5.5 + high`）和需用户确认的 `xhigh-auditor`（`gpt-5.5 + xhigh`）；新增 `model_policy_check.py`，SessionStart 只读提示漂移，pre-commit 硬拦配置漂移。同步更新 AGENTS、portability rule、settings 注册和 harness；`settings.json` 统一为 UTF-8 无 BOM。

## [0.25.0] - 2026-07-08

### Added
- [product] 新增 `.codex/scripts/codex_git_sync.py` 低弹窗同步执行器：Codex 运行 `$git-sync` 时可优先用一条 `python .codex/scripts/codex_git_sync.py --message "<提交信息>"` 承接 `fetch` / ahead-behind 判断 / memory 索引重建 / `add` / `commit` / `push` / 最终干净检查，并通过持久前缀规则减少多次权限弹窗；脚本遇到 diverged、缺 upstream、stash 冲突、push 竞态时停止报告，不自动 rebase / merge / reset / force push。

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
