# 需求：Codex 按任务成本路由与用户级配置保护
> 日期：2026-07-10
> 状态：trial
> 入口：用户认为当前 Codex 模型选择消耗偏高，要求以任务类型分流模型与思考强度，同时保证骨架不写用户级配置。

## 背景与目标

当前 Codex 骨架把主对话固定为 `gpt-5.6-terra + medium`，并将实现和审计都设为 `gpt-5.6-sol + high`。这使轻量咨询、检索和状态查询也从中档主对话开始，无法有效控制日常消耗。

本轮将项目级默认与 custom agent 路由改为“成本分层 + GPT-5.6 家族内选择”：

- 默认主对话：`gpt-5.6-terra + medium`。
- 纯检索、状态查询：`gpt-5.6-luna + low`。
- 明确开发或跨文件判断：`gpt-5.6-terra + high`。
- 高风险实现与独立审查：`gpt-5.6-sol + high`。
- `xhigh` 只由用户当次自行选择，骨架不自动提升。

同时将模型策略守卫扩展为：骨架 hook、脚本和测试都只操作项目 `.codex/**`，不得写用户级 `~/.codex/config.toml`。

## 非目标

- 不修改用户级 `C:\Users\bridg\.codex\config.toml`，也不在 SessionStart 或 Stop 自动复位它。
- 不支持对已经运行中的主对话无缝换模型；任务升级通过 custom agent 分流完成。
- 不修改 Claude 骨架的模型策略。
- 不自动启用 `xhigh`。

## 用户可见行为

- 新安装或同步 Codex 骨架后，项目 `.codex/config.toml` 默认使用 `gpt-5.6-terra + medium`。
- 只读检索使用轻量 agent；明确开发/跨文件判断使用 `terra + high`；高风险实现和独立审查使用 `sol + high`。
- 模型策略 hook 会检测产品层与 dogfood 层的路由是否漂移，并在提交前阻断。
- 任何骨架生命周期流程均不改用户级模型配置。

## 约束 / 风险边界

- `config.toml` 和 `.codex/agents/*.toml` 仍是模型路由权威；hook 只检查与阻断漂移。
- 产品层 hook、settings 和配置改动必须逐字同步 dogfood 层，命令前缀差异除外。
- 用户级配置保护只约束骨架自身操作；用户在 Codex 界面手动修改全局设置不受干预。
- 分流不等于主对话中途切档；不要宣传为实时自动换模型。

## 验收清单

- [x] `templates/codex/config.toml` 与 `.codex/config.toml` 为 `gpt-5.6-terra + medium`。
- [x] `light-explorer = gpt-5.6-luna + low`，`implementation-worker = terra + high`，`review-auditor = sol + high`，`xhigh-auditor = sol + xhigh`。
- [x] AGENTS、portability rule 和模型策略检查同步新的角色映射。
- [x] 新增用户级模型配置写入保护，并在 template / dogfood settings 中注册。
- [x] 下游 fixture 覆盖正常路由、xhigh 确认门槛和用户级配置保护正反例。
- [x] 生命周期保护测试断言用户级配置哨兵文件内容不变。
- [x] `model_policy_check.py --pre-commit`、相关 fixture、parity 和文本检查通过。

## 暂缓项

- 不做不同模型和 effort 的真实 token 成本 benchmark。
- 不尝试改 Codex Desktop 的线程内模型切换能力。

## 实施计划

1. 更新需求包和文档索引。
2. 更新 Codex template 与 dogfood 的配置、agents、说明和模型策略检查。
3. 增加用户级模型配置写入保护及 fixture。
4. 更新版本与 CHANGELOG，刷新生成性文档。
5. 运行可执行验证并启动独立复核。

## 实施记录

- 2026-07-10：用户确认路由映射与“用户级只读不写”边界，开始实施。
- 2026-07-10：用户确认混合 5.5 / 5.6 路由：默认主对话为 `gpt-5.5 + medium`，轻量检索为 `gpt-5.5 + low`，实现 worker 为 `gpt-5.6-terra + high`，复核为 `gpt-5.6-sol + high`，`xhigh` 仅由用户当次选择。
- 2026-07-10：新增 `user_config_write_guard.py` 并接入 Bash、PowerShell、Write/Edit/MultiEdit 的 PreToolUse；模型策略检查同步验证 guard 正文与三类 settings 注册。独立复核发现绝对路径解析可被 `$HOME` / `$env:USERPROFILE` / `~` 绕过，以及 parity 未登记；已扩展路径模式、fixture 负例和 parity 分类后复验。
- 2026-07-10：同步 template 与 dogfood 镜像、AGENTS / portability 说明、版本和 CHANGELOG；清理 Codex 设置中关于 `terra + medium` 与不存在 SessionEnd 自动复位的过期说明。
- 2026-07-11：用户要求模型选择范围限制在 GPT-5.6 内；保留成本分层和 effort 档位，将默认主对话切回 `gpt-5.6-terra + medium`，轻量探索切到 `gpt-5.6-luna + low`，实现 / 复核 / xhigh 继续使用 GPT-5.6 Terra/Sol。

## 验证记录

- 2026-07-11 补充收窄到 GPT-5.6 家族后：
  - `$env:PYTHONPYCACHEPREFIX = "$env:TEMP\bridgeforge_pycache"; python -m py_compile .codex\hooks\model_policy_check.py templates\codex\hooks\model_policy_check.py`：exit 0；验证两份模型策略 hook 语法正确，且不写受保护的 `.codex/hooks/__pycache__`。
  - `python .codex/hooks/model_policy_check.py --pre-commit`：exit 0；验证 dogfood 与 template 均满足 `gpt-5.6-terra/luna/sol` 策略。
  - `python tests/harness/run_downstream_fixture.py --case model-policy`：PASS；验证下游 fixture 正常路由、xhigh 确认门槛和 guard 注册仍通过。
  - `python -m json.tool .codex/settings.json` 与 `python -m json.tool templates/codex/settings.json`：exit 0；验证 settings JSON 仍合法。
  - `python .codex/scripts/harness_parity_check.py --no-write` 与 `python templates/codex/scripts/harness_parity_check.py --no-write`：exit 0；报告状态均为 `OK`。
  - `git diff --check`：exit 0；仅有 LF/CRLF 工作区提示，无 whitespace error。
- `python -m py_compile .codex/hooks/model_policy_check.py .codex/hooks/user_config_write_guard.py templates/codex/hooks/model_policy_check.py templates/codex/hooks/user_config_write_guard.py tests/harness/run_downstream_fixture.py`：exit 0。
- `python .codex/hooks/model_policy_check.py --pre-commit`：exit 0。
- `python tests/harness/run_downstream_fixture.py --case model-policy`：PASS；正常路由通过，xhigh description 与 developer_instructions 的缺确认语句负例均被阻断。
- `python tests/harness/run_downstream_fixture.py --case user-config-write-guard`：PASS；用户级 config 读取放行，绝对路径、`$HOME`、`$env:USERPROFILE`、`~` 写入均 exit 2，settings 三类 PreToolUse 均注册 guard，用户级配置哨兵字节不变。
- 修复后 `python .codex/scripts/harness_parity_check.py --check`：exit 0；报告状态为 `OK`，0 个未登记 Codex-only、0 个未分类差异。
- `python -m json.tool .codex/settings.json` 与 `python -m json.tool templates/codex/settings.json`：exit 0。
- `python .codex/scripts/harness_parity_check.py`：exit 0，刷新 `doc/3_design/codex-harness-parity.md`。
- `python .codex/hooks/encoding_check.py --pre-commit` 与 `git diff --check`：exit 0。
- `python .codex/hooks/mirror_drift_check.py`：exit 0；仅报告既有 `skill_sync_check.py` 正文软漂移，和本轮模型路由无关。
- 独立复核（首次）：发现 `$HOME` / `~` 路径绕过、parity 未登记与 settings 注册未进提交闸；均已修复。
- 独立复核（修复后）：未发现 P0/P1/P2；实跑模型策略、两项 fixture 与 parity 均通过，绝对路径、`$HOME`、`$env:USERPROFILE`、`~` 四种模拟写入均被阻断，template / dogfood 镜像一致。未验证真实 Codex Desktop 生命周期事件投递。

## 用户试用反馈

请在新的 BridgeForge Codex 对话中试用：普通咨询应以 `gpt-5.6-terra + medium` 开始；纯检索应分流到 `gpt-5.6-luna + low`；明确开发/跨文件判断应分流到 `gpt-5.6-terra + high`。若桌面端没有按项目配置生效，请提供 `/status` 或界面状态截图作为反馈证据。
