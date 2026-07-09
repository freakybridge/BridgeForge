# 需求：Codex ctx-budget 适配修复
> 日期：2026-07-09
> 状态：trial
> 入口：用户发现 Codex 中 ctx 管理没有像 Claude 骨架一样有效，几次仍触发自动 compact；补充确认 Claude 侧 1M 机制可作为参考，不应重造。

## 背景与目标

BridgeForge 已有 Claude / Codex 两套 `context_warning.py`，机制相同：读取 transcript usage，在 `UserPromptSubmit` 注入 `[ctx-budget]` 软提醒。Claude 侧工作效果可接受，且用户确认 Claude 可继续硬编码 `1_000_000`。

本轮目标是修复 Codex 侧照抄 Claude 1M 窗口的问题：保留 Claude 成熟机制作为样板，只对 Codex 的有效窗口、阈值文案和校准提示做适配，避免真实窗口较小时预警静默失效。

## 非目标

- 不重写 Claude 侧 ctx-budget 机制。
- 不引入硬阻断；上下文预算仍是软提醒，最终决定权在用户。
- 不实现 LLM judge 类 Stop hook。
- 不试图改变 Codex Desktop 自身自动 compact 行为。

## 用户可见行为

- Codex 侧 `[ctx-budget]` 默认按保守有效窗口计算，不再假定 1M。
- 预警输出会标明 `surface=codex`、窗口大小、窗口来源、token 统计来源，便于后续校准。
- `$snapshot` / `$resume` / `/` 开头命令仍然豁免，避免保命操作被上下文预警干扰。

## 约束 / 风险边界

- Claude 侧 `WINDOW = 1_000_000` 保持不动。
- Codex 侧默认窗口采用当前 `/status` 实测约 `258K`；若未来实测 Codex 可用窗口不同，应只调配置常量或环境变量，不改算法。
- BridgeForge 是骨架工厂，产品层改动必须同步 dogfood 副本、版本号和 CHANGELOG。

## 验收清单

- [x] `templates/codex/hooks/context_warning.py` 默认窗口不再是 `1_000_000`。
- [x] `.codex/hooks/context_warning.py` 与模板同步 dogfood。
- [x] Codex 预警输出包含 surface / window / window_source / token_source。
- [x] Claude 模板 `context_warning.py` 保持 1M 不变。
- [x] `/` 和 `$` 开头命令仍豁免。
- [x] 文档、版本号、CHANGELOG 同步。
- [x] 运行语法检查和可控样例验证。

## 暂缓项

- Codex Desktop 真实 compact 阈值需要后续用实际长会话或官方说明校准。
- 是否增加 Stop 阶段额外提醒暂缓；先修正 Codex 窗口误判，避免重复造轮子。

## 实施计划

1. 修改 Codex `context_warning.py`：保留 Claude 结构，新增 Codex 专属有效窗口默认值和环境变量覆盖。
2. 同步模板和 dogfood 副本。
3. 更新 Codex 侧说明文档与版本流水。
4. 运行语法检查、样例 hook 输入验证、Claude 不变性核验。

## 实施记录

- 2026-07-09：保留 Claude 侧 1M 机制不动；Codex 模板和 dogfood 副本先改为 `DEFAULT_CODEX_WINDOW = 200_000`，随后根据 Codex `/status` 显示的“背景信息共 258K”校准为 `258_000`，并支持 `BRIDGEFORGE_CODEX_CTX_WINDOW` 覆盖。
- 2026-07-09：`[ctx-budget]` 输出增加 `surface=codex`、`token_source`、`window_source`，便于后续校准 Codex Desktop 实际窗口。
- 2026-07-09：同步 `templates/codex/AGENTS.md`、`templates/codex/rules/anti_drift_hooks.md`、版本号、CHANGELOG、`doc/README.md` 和 harness parity 报告。

## 验证记录

- `python -m py_compile .codex\hooks\context_warning.py templates\codex\hooks\context_warning.py templates\claude\hooks\context_warning.py`：通过，三份 hook 语法有效。
- `python .codex\scripts\harness_parity_check.py`：通过并刷新 `doc/3_design/codex-harness-parity.md`；Codex/Claude 差异仍归类为 expected/codex-only。
- `python .codex\hooks\model_policy_check.py`：通过，模型/effort 路由策略未漂移。
- `python .codex\hooks\rule_size_check.py`：通过，rule 体积红线未触发。
- 样例 transcript：200k usage 在 Codex 默认 258k 窗口下输出 `MEDIUM`，包含 `surface=codex`、`token_source=usage`、`window_source=default`。
- 样例 transcript + `BRIDGEFORGE_CODEX_CTX_WINDOW=1000000`：同样 160k usage 不输出预警，证明窗口覆盖生效。
- `rg -n "WINDOW = 1_000_000|DEFAULT_CODEX_WINDOW|surface=codex|BRIDGEFORGE_CODEX_CTX_WINDOW" templates\claude\hooks\context_warning.py templates\codex\hooks\context_warning.py .codex\hooks\context_warning.py`：确认 Claude 仍是 `WINDOW = 1_000_000`，Codex 模板与 dogfood 使用 `DEFAULT_CODEX_WINDOW = 258_000`。

## 用户试用反馈

- 待用户在后续 Codex 长会话中观察 `[ctx-budget]` 是否提前出现。
