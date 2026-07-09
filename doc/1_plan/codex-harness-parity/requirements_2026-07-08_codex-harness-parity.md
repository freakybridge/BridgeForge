# 需求：Codex harness 与 Claude harness 对齐清单
> 日期：2026-07-08
> 状态：trial
> 入口：用户从 Claude 切到 Codex 开发，希望先对比 Claude/Codex 骨架，列出并修正明确需要改善的问题。

## 背景与目标

Claude harness 已较成熟，Codex 骨架应继承同等的节流、证据、文档和同步治理能力，同时保留 Codex 自己的配置与 skill 机制。

本轮目标是修正已确认的 Codex 迁移残留，并建立长期对照检查，让后续 git-sync 前能维护 Claude/Codex harness 差异清单。

## 非目标

- 不重写 Codex 模型路由；本轮只保留已有模型路由，不扩展验收。
- 不把 Claude 骨架整套覆盖到 Codex。
- 不改历史 CHANGELOG 条目的当时表述。
- 不自动 commit / push。

## 用户可见行为

- Codex 侧 `/bridgeforge` 入口口径与 Claude 保持一致。
- Codex hook 的输入读取说明不再像直接残留 Claude 通道。
- git-sync 前会刷新 Claude/Codex harness 对照报告，便于发现未来漂移。

## 约束 / 风险边界

- Codex 专属文件如 `config.toml`、`agents/*.toml`、`model_policy_check.py` 必须保留。
- hook 输入以官方 Codex stdin JSON 为权威；环境变量只作为兼容兜底。
- 改 `templates/codex/hooks/**` / `templates/codex/settings.json` 时必须同步 dogfood 到 `.codex/**`。
- 产品层变更必须 bump `templates/codex/VERSION` 和根 `VERSION`，并同步 CHANGELOG。

## 验收清单

- [x] Codex hook 中的 `CLAUDE_TOOL_INPUT` / `CLAUDE_TOOL_NAME` 不再作为唯一环境变量回退通道。
- [x] 当前 Codex 模板用户提示中，BridgeForge 日常入口统一为 `/bridgeforge`。
- [x] 新增只读 harness parity 检查脚本，可生成/刷新 `doc/3_design/codex-harness-parity.md`。
- [x] Codex git-sync 执行器在暂存前刷新 harness parity 报告。
- [x] `templates/codex/**` 与 `.codex/**` dogfood 副本保持同步。

## 暂缓项

- Codex 模型路由的专项验收本轮跳过。

## 实施计划

1. 修正 Codex hook 输入回退策略与文案。
2. 统一 `/bridgeforge` 用户入口文案。
3. 新增 harness parity 检查脚本与报告。
4. 将 parity 检查接入 Codex git-sync 执行器。
5. 同步版本、CHANGELOG、需求文档和索引。

## 实施记录

- Codex hooks 改为 stdin JSON 优先，环境变量回退优先 `CODEX_TOOL_INPUT` / `CODEX_TOOL_NAME`，旧 `CLAUDE_TOOL_INPUT` / `CLAUDE_TOOL_NAME` 仅保留为兼容兜底。
- Codex 用户入口文案统一为 `/bridgeforge`；历史 CHANGELOG 中当时版本的 `$bridgeforge` 记录保留不改。
- 新增 `templates/codex/scripts/harness_parity_check.py` 并 dogfood 到 `.codex/scripts/`，生成 `doc/3_design/codex-harness-parity.md`。
- `templates/codex/scripts/codex_git_sync.py` 与 `.codex/scripts/codex_git_sync.py` 在暂存前刷新 harness parity 报告。
- 已同步 `templates/codex/VERSION` 到 `0.27.0`，根 `VERSION` / `SKILL.md` / 两套 `/bridgeforge` 薄入口到 `0.55.0`。

## 验证记录

- `python .codex\scripts\harness_parity_check.py`：通过，已刷新报告状态；当前仍有 20 个同名文件差异待人工归类。
- `python templates\codex\scripts\harness_parity_check.py --check`：通过，模板路径也能定位仓库根。
- `python -m py_compile ...`：通过，覆盖新增 parity 脚本、Codex git-sync 执行器和改动过的 Codex hooks。
- `rg -n '\$bridgeforge' ... -g '!CHANGELOG.md'`：无命中；非历史文案中不再保留 `$bridgeforge`。
- `git diff --check`：通过，仅有 Git 换行提示，无 whitespace error。
- `python tests\harness\run_downstream_fixture.py`：通过 20 项 harness 回归。
- 独立 subagent 复核未运行：当前工具策略要求只有用户明确要求 subagent/并行 agent 时才能 spawn。

## 用户试用反馈

- 待填写。
