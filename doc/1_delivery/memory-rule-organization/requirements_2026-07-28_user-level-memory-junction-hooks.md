---
status: superseded
topic: memory-rule-organization
created: 2026-07-28
source: "$confirm via $debate: user-level dual-host memory junction hooks"
handoff: "$debate user-level-memory-junction-hooks"
superseded_by: requirements_2026-07-28_project-level-memory-junction-hooks.md
---

# 用户级双宿主 memory junction hook

## 目标

首次安装 BridgeForge 时，在用户一次明确确认后，同时注册 Codex 和 Claude Code 的用户级 SessionStart hook。已安装对应 BridgeForge 骨架的下游项目，在会话启动时自动将宿主系统 memory 目录 junction 到项目内、受 Git 跟踪的 memory 目录。

## 已核实事实

- Codex 支持从 `~/.codex/hooks.json` 注册 `SessionStart`；用户级和项目级同事件 hook 会叠加运行，非受管 hook 定义或脚本变更后须重新信任。
- 当前 Codex 模板把 hook 定义写在 `.codex/settings.json`，而 Codex 的有效项目 hook 承载面是 `.codex/hooks.json` 或 `.codex/config.toml` 的 `[hooks]`，故该定义不会被 Codex 发现。
- 现有共享 updater 仅管理 manifest 登记的用户级 skill 及其账本，尚不具备安全管理用户级 runtime 与 hook 配置的能力。
- 当前项目级 `memory_junction_check.py` 通过脚本路径定位项目根；用户级实现必须改用 hook payload 的 `cwd` 和 Git 根。

## 已确认规则

1. 首次安装 BridgeForge 时，经一次明确确认后，同时注册 Codex 与 Claude Code 的用户级 hook 和受管 runtime。
2. 存量下游只在其后续无参 `/bridgeforge` 展示迁移计划，并在用户确认后移除项目级旧 hook、写入切换标记并由用户级 hook 接管。
3. 用户级 hook 遇到仍注册或仍存在的项目级 legacy junction hook 时必须 no-op，禁止双跑。
4. 仅当当前宿主的 `.codex/.bridgeforge_version` 或 `.claude/.bridgeforge_version` 与对应项目内 `memory/` 目录都存在时才执行；其他仓库完全 no-op。
5. 不得自动补建另一宿主骨架或其 memory 目录，不得扫描用户项目目录，不得硬删除系统 memory。
6. 系统 memory 与项目 memory 均有内容时禁止自动合并；首次迁移保留 `memory.premigrate.bak`。

## 数据映射

| 宿主 | 系统目录 | 项目唯一事实源 |
|---|---|---|
| Codex | `~/.codex/projects/<hash>/memory` | `<repo>/.codex/memory/` |
| Claude Code | `~/.claude/projects/<hash>/memory` | `<repo>/.claude/memory/` |

## 拟修改范围

- 新增用户级受管 runtime、独立账本和安全的双宿主 hook 配置 merge/rollback。
- 将现有双份项目级 junction 实现收敛为一份按 `--host` 分支的用户级实现。
- 更新 BridgeForge 安装、updater、下游迁移、双宿主切换、模板、测试、文档和 `[product]` CHANGELOG。

## 验收

1. 首次安装确认后，两侧用户级 hook 与 runtime 都安装成功，且可完成各自宿主的信任流程。
2. Codex 和 Claude Code 各自在已安装对应骨架的下游项目中建立正确 junction；重复启动无改动。
3. 普通 Git 仓库和仅安装另一宿主骨架的项目均不创建、修改或扫描任何路径。
4. legacy 项目迁移前用户级 hook 不接管；确认迁移后无双跑。
5. 子目录启动、Windows 路径大小写/特殊字符、新 clone、系统与项目 memory 冲突均有定向测试。

## 风险与边界

- 用户级 hook 更新会触发宿主重新信任；不得承诺静默生效。
- 对用户级配置的 merge 必须精确管理 BridgeForge 自有 handler，保留第三方 hook；冲突或无法解析时阻断。
- 本确认卡仅授权 debate 与方案收敛；用户确认最终方案前不得开始实现。

## 实施与验证记录

- 待 debate 收敛并经用户确认后填写。
