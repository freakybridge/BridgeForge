# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本按 `templates/rules/workflow.md §9` **简版**（小项目退化版）：

- **major (X)** — 破坏性变更 / 范式重写
- **minor (Y)** — 新功能（新 hook / 新 skill / 新 rule / 新模板）
- **patch (Z)** — bug 修复 / 文档调整 / refactor

> **追溯说明**：v0.1.0 - v0.7.0 基于 git log 历史回溯标记，**git tag 仅从 v0.8.0 开始打**。早期未启用版本号管理是 setup_agent 自打脸问题（要求下游用但自己没用），v0.8.0 修补。

---

## [Unreleased]

## [0.10.0] - 2026-05-29

### Added
- `templates/settings.json` 新增 `permissions` 块，下沉「少弹框」黄金组合到所有下游项目：
  - `defaultMode: acceptEdits` — 文件编辑（Write/Edit）默认放行，不再逐个弹框
  - `allow` allowlist — 只读工具（Read/Grep/Glob）+ git 看状态类（status/diff/log/show/branch/fetch）+ ls/cat/pwd
  - `deny` 安全闸口 — 挡不可逆操作（`rm -rf` / `git push --force` / `git reset --hard` / `git clean -f`）+ 敏感文件读取（`.env` / `secrets/**` / `*.key` / `*.pem`），deny 优先级最高，bypass 模式下仍生效
- `SKILL.md` Step 1：settings.json merge 逻辑扩展——除 hooks 外，新增 `permissions.allow/deny` 数组追加去重 + `defaultMode` 仅在用户未设时才写（不覆盖用户已有偏好）
- `SKILL.md` 模板速查表：`settings.json` 行补充 permissions 块说明

### Note
- 下游已有项目不自动获得（permissions 只随**新** `/setup_agent` 安装下沉）；存量项目需手动 merge 或重跑 skill 的 settings 合并步骤
- 白名单设计为「精选起步 + 留白」——常用但因人而异的命令交给权限弹框的「别再问」选项自增长，或 `/fewer-permission-prompts` skill 批量补齐

## [0.9.1] - 2026-05-29

### Changed
- 4 个写文档/轻量类 skill 的 `SKILL.md` frontmatter 加 `model:` 字段（利用官方机制 skill 激活期间临时切模型，结束自动恢复）：
  - `sync-docs` / `summary` → `sonnet`（写文档为主，能力够用速度更快）
  - `todo` / `archive-scan` → `haiku`（轻量追加 / 批量 git mv，无需推理）

### Fixed
- 版本号自打脸 v3：v0.9.0 commit (`4aa57c2`) 写了 CHANGELOG 但漏打 git tag → 本次补打 `v0.9.0` tag；`50edbac` 改 skill 配置时也漏走版本号流程 → 本版补齐

## [0.9.0] - 2026-05-24

### Added
- `templates/VERSION`（初始 `0.1.0`，下游项目无原生版本源时用）
- `templates/CHANGELOG.md`（通用骨架，引用 `rules/workflow.md §9` SemVer 语义，所有下游项目无条件复制）
- `SKILL.md` Step 3：新增"版本号 SoT 条件复制"段（检测 `package.json` / `Cargo.toml` / `pyproject.toml` → 跳过 VERSION 避免双 SoT；CHANGELOG.md 仍统一复制）
- `SKILL.md` Step 3 复制清单 + 模板速查表：新增 VERSION / CHANGELOG.md 两行
- `README.md` 新增"未反哺的上游 hook（为什么不在 templates 里）"段，明列 `cargo_check.py` 等语言/业务专属 hook 不反哺的判断标准
- `docs/reverse-sync-playbook.md` 新增 §3.1 实战记录（v0.6.0 / v0.7.0 / v0.8.0 三次反哺的 checklist 实例化）+ §3.2 元规则（含"禁止虚构踩坑故事"红线）

### Fixed
- 自打脸 v2：v0.8.0 给 setup_agent 自己装了版本号但**没下沉到 templates**，下游项目装完 `/setup_agent` 仍然没有版本号机制 → 本版闭环

## [0.8.0] - 2026-05-24

### Added
- `VERSION` 文件（单一事实源，符合 workflow.md §9.1）
- `CHANGELOG.md` 本文件
- `SKILL.md` frontmatter `version: 0.8.0` 字段
- `skills/resume/SKILL.md` **Step 5**：用户确认接续后主动建议对话框重命名（避免 `/resume` 默认 session 名 "resume" 无指导性，多 session 并发时无法区分内容）

### Fixed
- 自打脸：setup_agent 之前要求下游用版本号但自己没用 → 本版补齐版本号机制

## [0.7.0] - 2026-05-24（追溯，commit 4b976da）

### Added
- 反哺 5 个通用 hook：`memory_lint.py` / `rule_index_check.py` / `rule_size_check.py` / `find_doc_reminder.py` / `show_state.py`（脱敏简化版）
- `templates/settings.json` 扩展到 6 类 hook 注册段（PreToolUse / PostToolUse / PostCompact / Stop / UserPromptSubmit / SessionStart）
- `templates/rules/modules.md §3.1 §3.2` 从 causis_risk_suite 反哺（协调中枢三块分层 + 提炼共享常量三件套）
- `docs/sync-from-upstream-playbook.md`（与 reverse-sync-playbook 互为镜像，按业务专属程度分 4 层决定覆盖策略）

### Changed
- `SKILL.md` Step 3 改造：加 Python hook 体系条件复制（基于 Q2 主语言）+ 无 `.venv` fallback + 非 Python 项目跳过说明
- `docs/reverse-sync-playbook.md §7` 改为引用新 sync-from-upstream playbook 的精简版

## [0.6.0] - 2026-05-24（追溯，commit 9cfa7ae）

### Added
- `templates/hooks/session_snapshot.py`（脱敏简化版 ~150 行，去 tag 逻辑 + 通用版本检测）
- `templates/scripts/archive_scan.py`（通用版直接 cp）
- `templates/settings.json` 加 PostCompact + Stop hook 注册
- `README.md` "Python 依赖（agent 安装前必读）"段
- `docs/reverse-sync-playbook.md §4` 白名单扩展（加 `templates/hooks/` + `templates/scripts/`）
- `skills/find-doc` + `skills/sync-docs` SKILL.md 末尾加 placeholder 检测与提醒段

## [0.5.0] - 2026-05-24（追溯，commit d73ea5a）

### Added
- 反哺 StratusAgent + causis_risk_suite 经验：
  - `templates/rules/portability.md §4.3-§4.5` 多项可移植性约束
  - `templates/rules/workflow.md §9` 拆细为 §9.1-§9.7（Milestone-bound SemVer 详细版）
  - `templates/rules/meta_rule_design.md`（新建，元规则）
- `README.md` "适合/不适合"诚实段
- OPTIONAL 段落物理裁剪机制（`<!-- OPTIONAL_BEGIN PLATFORM/LANG/SCENARIO -->`）
- `templates/CLAUDE.md §11` doc/ 红线化

### Removed
- `session-tag` skill（过度设计，整目录删 + snapshot/resume 里的 tag 引用清理）

## [0.4.0] - 2026-05-23（追溯，commit fa8c75f）

### Added
- 13 个通用协作 skill：`archive-scan` / `collab` / `debate` / `escalate` / `find-doc` / `git-sync` / `plan` / `resume` / `session-tag` / `snapshot` / `summary` / `sync-docs` / `todo`（**`session-tag` 后于 v0.5.0 删除**）
- setup_agent SKILL.md 加 skill 自检流程

## [0.3.0] - 2026-05-09（追溯，commit 88db438）

### Added
- `templates/hooks/context_warning.py`（ctx-budget 红线 hook — 跨 75/85/95% 阈值预警）
- `templates/CLAUDE.md §10` ctx-budget 信号响应红线

## [0.2.0] - 2026-05-08（追溯，commit 2ed5df2）

### Added
- doc/ 分层引入 acceptance + TODO-INDEX 二分语义（短期 vs 远期 backlog）

## [0.1.0] - 2026-05-01（追溯，commit 7f30c9a）

### Added
- setup_agent skill 骨架初始化（CLAUDE.md / rules / memory junction / doc 基础模板）
