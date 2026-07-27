---
status: confirmed
topic: memory-rule-organization
created: 2026-07-28
source: "$confirm: simplified dual-host project-level memory junction hooks"
supersedes: requirements_2026-07-28_user-level-memory-junction-hooks.md
handoff: "$collab project-level-memory-junction-hooks"
---

# 项目级双宿主 memory junction hook

## 目标

以项目级 hook 支持 Codex 与 Claude Code：已安装对应 BridgeForge 骨架的下游项目，在会话启动时将宿主系统 memory junction 到项目内、受 Git 跟踪的 memory 目录。

## 不做

- 不新增用户级 runtime、用户级 hook 配置、独立用户账本或全局 reconciler。
- 不自动补建另一宿主骨架或其 memory 目录。
- 不在普通 Git 仓库运行。

## 已核实事实

- Codex 的项目级 hook 有效承载面是 `.codex/hooks.json` 或 `.codex/config.toml` 的 `[hooks]`；当前 `.codex/settings.json` 的 junction 注册不会被 Codex 发现。
- Claude Code 的项目级 `SessionStart` 注册位于 `.claude/settings.json`。
- 当前两侧 `memory_junction_check.py` 基本同构，但“任意链接即成功”和首迁失败回滚不足。

## 已确认规则

1. Codex 使用项目 `.codex/hooks.json` 注册 junction hook；Claude 保持 `.claude/settings.json` 注册。
2. 两宿主各自独立处理，不触碰另一宿主骨架。
3. 系统 memory 与项目 memory 合并时，只复制各自独有文件；同路径且内容相同跳过；同路径内容不同即阻断，不覆盖任一侧。
4. 合并后必须校验项目 memory 包含系统 memory 的全部文件与内容；校验通过后直接删除原系统 memory 目录，再建立并验证 junction；不得创建 `memory.premigrate.bak`。
5. 错误或断裂 junction、路径异常、合并冲突或校验失败均 fail-closed，不自动覆盖或重建。
6. 新 clone 的系统 memory 不存在且项目 memory 存在时，可直接建立 junction。

## 数据映射

| 宿主 | 系统目录 | 项目唯一事实源 | 注册位置 |
|---|---|---|---|
| Codex | `~/.codex/projects/<hash>/memory` | `<repo>/.codex/memory/` | `<repo>/.codex/hooks.json` |
| Claude Code | `~/.claude/projects/<hash>/memory` | `<repo>/.claude/memory/` | `<repo>/.claude/settings.json` |

## 拟修改范围

- Codex/Claude 模板及 dogfood 的 junction 注册、脚本和 portability 说明。
- 下游 `/bridgeforge` 更新的合并、校验、删除与建链迁移逻辑。
- 双宿主 junction 专项测试、模板/根版本及 `[product]` CHANGELOG。

## 验收

1. Codex 和 Claude 项目级 hook 都能被宿主发现并正确建链；重复启动 no-op。
2. 新 clone、系统 memory 存在、项目 memory 存在、两边都有独有文件、同路径同内容、同路径冲突均按规则处理。
3. 合并后校验失败时不删除系统 memory；成功时系统目录删除且最终 junction 指向当前项目 memory。
4. 错误 junction、断裂 junction 和路径异常零写入。
5. 下游 update 先展示迁移计划，用户确认后才执行删除系统 memory 的操作。

## 风险

- 用户明确选择不保留系统 memory 备份；合并后删除不可恢复，唯一保护是合并冲突阻断与完整性校验。
- SessionStart 不包含删除或合并行为；删除仅在下游 update 的确认式迁移中执行。

## 实施与验证记录

- 已实现：Codex junction 注册迁至 `.codex/hooks.json`；Claude 保持 `.claude/settings.json`；三份 dogfood/模板脚本逐字一致。
- 已验证：`.venv\\Scripts\\python.exe -B tests\\harness\\test_memory_junction_check.py -v`（15 tests）；`.venv\\Scripts\\python.exe -B tests\\harness\\test_shared_skill_distribution.py`（14 tests）；`.venv\\Scripts\\python.exe -B tests\\harness\\run_downstream_fixture.py`（33 checks）；`git diff --check`。
- 未验证：真实 Codex `/hooks` trust 后的新会话 SessionStart 与 Claude Code 新会话 smoke，均需在实际宿主中执行后留收据。
