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
