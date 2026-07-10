# 需求：Codex 模型路由升级到 GPT-5.6
> 日期：2026-07-10
> 状态：trial
> 入口：用户反馈 GPT-5.6 已发布，要求 BridgeForge 骨架的模型切换与思考强度配置同步升级。

## 背景与目标

BridgeForge Codex 骨架已经把模型 / reasoning effort 策略固化在 `config.toml`、custom agents 和 `model_policy_check.py` 里。当前策略仍是 GPT-5.5 代际：主对话、开发、复核和 xhigh 使用 `gpt-5.5`，轻量探索使用 `gpt-5.4-mini`。

本轮目标是把 Codex 产品层默认策略升级到 GPT-5.6 代际，同时保留原来的任务分层。当前 Codex 可用 slug 按 Sol / Terra / Luna 三档落地，不使用裸 `gpt-5.6`：

- 主对话默认 `gpt-5.6-terra + medium`。
- 轻量探索子 agent 默认 `gpt-5.6-luna + low`。
- 开发实现与复核审计子 agent 默认 `gpt-5.6-sol + high`。
- `xhigh` 审计默认 `gpt-5.6-sol + xhigh`，仍必须用户当轮明确确认。

## 非目标

- 不改 Claude 骨架。
- 不改用户全局 `~/.codex/config.toml`。
- 不实现每句话实时自动切模型。
- 不放松 `xhigh` 用户确认门槛。
- 不回写历史 CHANGELOG 中旧版本发布时的模型记录。

## 用户可见行为

- 新安装或同步 Codex 骨架后，`.codex/config.toml` 默认主对话使用 `gpt-5.6-terra + medium`。
- `.codex/agents/` 的四档子 agent 升级到 GPT-5.6 代际。
- 启动检查和 pre-commit 仍会检测模型策略漂移。
- `AGENTS.md` 和 portability rule 说明新的任务分层。

## 约束 / 风险边界

- `config.toml` 和 `.codex/agents/*.toml` 是配置权威；`.codex/settings.json` 只注册 hook，不承载模型默认值。
- `model_policy_check.py` 必须同步更新期望值，否则会把升级后的配置误判为漂移。
- 产品层 `templates/codex/**` 的 hook / settings 改动必须同步 dogfood 到 `.codex/**`。
- 产品层改动必须 bump `templates/codex/VERSION`、根 `VERSION` / `SKILL.md` / 入口 wrapper，并更新 CHANGELOG。

## 验收清单

- [x] `templates/codex/config.toml` 和 `.codex/config.toml` 默认 `model = "gpt-5.6-terra"`、`model_reasoning_effort = "medium"`。
- [x] 四档 agent 策略为：`light-explorer = gpt-5.6-luna + low`，`implementation-worker = gpt-5.6-sol + high`，`review-auditor = gpt-5.6-sol + high`，`xhigh-auditor = gpt-5.6-sol + xhigh`。
- [x] `xhigh-auditor` 仍在 `description` 和 `developer_instructions` 中明示必须用户确认。
- [x] `model_policy_check.py --pre-commit` 通过，并能阻断缺少 xhigh 确认的 fixture。
- [x] `AGENTS.md`、`rules/portability.md`、settings 注释、project memory 说明同步到 GPT-5.6。
- [x] `doc/README.md`、root / template CHANGELOG、VERSION 同步。

## 暂缓项

- 不验证 GPT-5.6 模型 slug 在当前 Codex 账号中的实际可用性；本轮只升级骨架策略字符串和机检断言。
- 不做真实子 agent 成本 benchmark。

## 实施计划

1. 新增本需求包并同步 `doc/README.md`。
2. 更新 Codex 产品层和 dogfood 层的 config、agents、hook 期望值、settings 注释和说明文档。
3. 更新版本号与 CHANGELOG。
4. 运行策略 hook、harness 和基础文本检查。
5. 启动独立复核，记录结论。

## 实施记录

- 2026-07-10：需求确认。用户确认开始开发。实施中发现裸 `gpt-5.6` 在当前 Codex + ChatGPT 账号下不可用，改用当前工具暴露的可用 slug 映射：主对话 `gpt-5.6-terra`，轻量探索 `gpt-5.6-luna`，开发 / 复核 / xhigh `gpt-5.6-sol`，effort 档位保持不变。
- 2026-07-10：实现完成。更新 Codex 产品层和 dogfood 层的 `config.toml`、四档 agents、`model_policy_check.py` 期望、settings 注释、AGENTS / portability 说明、project memory、CHANGELOG 和版本号；新增本需求包并同步 `doc/README.md`。

## 验证记录

- `python .codex/hooks/model_policy_check.py --pre-commit`：exit 0；断言 `.codex/` 与 `templates/codex/` 的 GPT-5.6 Sol/Terra/Luna 主对话、四档 agent、xhigh 确认门槛均符合策略。
- `python -m py_compile .codex/hooks/model_policy_check.py templates/codex/hooks/model_policy_check.py tests/harness/run_downstream_fixture.py`：exit 0；hook 与 harness 语法通过。
- `python .codex/hooks/mirror_drift_check.py`：exit 0；仅提示既有 `skill_sync_check.py` 正文软漂移，未阻断，且与本轮模型策略无关。
- `python -m json.tool .codex/settings.json` 与 `python -m json.tool templates/codex/settings.json`：exit 0；两份 settings JSON 可解析。
- `python tests/harness/run_downstream_fixture.py --case model-policy`：exit 0；`model_policy_health` PASS，正常 fixture 通过，缺少 xhigh description / instructions 确认语句的负例均 exit 2。
- `git -c safe.directory=D:/Quant/BridgeForge diff --check`：exit 0；无 whitespace error，仅 Windows 行尾提示。
- `python .codex/hooks/encoding_check.py --pre-commit`：exit 0；受管文本无 BOM / garble 阻断。
- `python tests/harness/run_downstream_fixture.py`：exit 0；26 项全量 harness PASS。
- 初次尝试用 `review-auditor` 复核时，工具返回当前 Codex + ChatGPT 账号不支持裸 `gpt-5.6` model slug；据此把最终策略从裸 `gpt-5.6` 调整为当前工具暴露的 `gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna`。
- 独立 verification agent：未发现阻断问题；确认产品层 `templates/codex` 与 dogfood `.codex` 均已升级到 GPT-5.6 Sol/Terra/Luna 代际，`xhigh` 确认门槛仍在 agent 文本和 hook 分字段检查中；补充说明 `mirror_drift_check.py` 的 `skill_sync_check.py` 软漂移为既有提示，与本轮模型路由无关。

## 用户试用反馈

待交付后记录。
