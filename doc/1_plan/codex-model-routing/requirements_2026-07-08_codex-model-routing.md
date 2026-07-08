# 需求：Codex 模型 / effort 分层路由
> 日期：2026-07-08
> 状态：trial
> 入口：用户反馈 Codex 骨架 token 消耗偏快，希望仿照 Claude 骨架建立默认中等 effort、低复杂度轻模型、开发子 agent 按需高 effort、xhigh 需确认的机制，并要求不要只靠文档约束，要用 hook 机检。

## 背景与目标

当前 Codex 骨架已有上下文预算、空转提醒和项目级 `effortLevel` 剔除等治理，但没有把 Codex 官方的 `config.toml` / custom agents 机制固化为产品层默认档位。用户看到日常对话 token 消耗偏快，希望骨架默认更节制，同时保留复杂开发和复核时的高质量档位。

目标是为 Codex 模板提供一套可下沉的模型 / effort 路由：

- 主对话默认 `gpt-5.5 + medium`。
- 轻量探索子 agent 默认 `gpt-5.4-mini + low`。
- 开发实现与复核审计子 agent 默认 `gpt-5.5 + high`。
- `xhigh` 只在用户明确确认后启用。
- 用 hook 检查配置是否漂移，避免只靠 md 约束。

## 非目标

- 不实现“每句话实时自动切模型”；Codex 当前稳定配置面是 `config.toml` 和 custom agent 文件。
- 不把 Claude skill frontmatter 的 `model:` 语义照搬到 Codex；Codex skill 文档未确认该字段能切换当轮模型。
- 不改 Claude 骨架。
- 不自动修改用户全局 `~/.codex/config.toml`。
- 不让 `xhigh` 在无用户授权时静默启用。

## 用户可见行为

- 新装或同步 Codex 骨架后，项目 `.codex/config.toml` 提供默认主对话模型与 effort。
- 项目 `.codex/agents/` 下出现可调用的轻量探索、开发实现、复核审计和超强审计 agent。
- Codex 启动或提交前会检查模型策略配置是否完整；配置漂移会得到明确报错或提示。
- `AGENTS.md` 直接说明什么时候用哪个档位，尤其强调 `xhigh` 需要用户确认。

## 约束 / 风险边界

- 项目级 `config.toml` 是 Codex 官方持久配置面；`.codex/settings.json` 继续只放 hooks / permissions，不再承载模型默认值。
- hook 不能可靠替代模型选择本身；hook 的职责是检查配置、阻止 drift、提示风险。
- 新 hook 必须同步 `templates/codex/hooks/` 与 dogfood `.codex/hooks/`。
- 修改产品层必须 bump `templates/codex/VERSION`、根 `VERSION` / `SKILL.md`，并更新 root / template CHANGELOG。
- 新增 `doc/**.md` 必须同步 `doc/README.md`。

## 验收清单

- [x] `templates/codex/config.toml` 和 `.codex/config.toml` 存在，默认 `model = "gpt-5.5"`，`model_reasoning_effort = "medium"`。
- [x] `templates/codex/agents/` 和 `.codex/agents/` 包含轻量探索、开发实现、复核审计、超强审计四个 agent。
- [x] 轻量探索 agent 为 `gpt-5.4-mini + low`；开发和复核 agent 为 `gpt-5.5 + high`。
- [x] 超强审计 agent 为 `gpt-5.5 + xhigh`，且 `description` / `developer_instructions` 均写明必须用户明确确认。
- [x] 新增 `model_policy_check.py`，能检查 config / agents 策略；SessionStart 只提示，pre-commit 模式硬拦。
- [x] `.codex/settings.json` 与 `templates/codex/settings.json` 注册该 hook。
- [x] `AGENTS.md` 与 `rules/portability.md` 说明 config / agents / hook 的职责边界。
- [x] root / template CHANGELOG、VERSION 和 `doc/README.md` 同步。
- [x] 验证命令覆盖 Python 语法、策略 hook、JSON/TOML 解析和现有 harness。

## 暂缓项

- 不在本轮建立用户全局 `~/.codex/config.toml` 自动修复。
- 不为 Claude 骨架回填同类配置。
- 不做真实子 agent 启动成本 benchmark。

## 实施计划

1. 新增需求包并同步 `doc/README.md`。
2. 新增 Codex 模板与 dogfood 的 `config.toml`、custom agents、模型策略 hook。
3. 注册 hook 到 Codex settings，并同步 AGENTS / portability 说明。
4. 更新 CHANGELOG / VERSION / SKILL.md。
5. 运行策略 hook、语法检查、harness 和独立复核。

## 实施记录

- 2026-07-08：需求确认。用户认可主对话 `gpt-5.5 + medium`，轻量子 agent `gpt-5.4-mini + low`，开发 / 复核 `gpt-5.5 + high`，`xhigh` 必须用户确认；进一步确认约束要 hook 化。
- 2026-07-08：实现完成。新增 Codex `config.toml` 默认档、四档 custom agent、`model_policy_check.py`、SessionStart 注册和 pre-commit 硬闸；同步 dogfood `.codex/` 与 `templates/codex/`，并更新 AGENTS / portability / CHANGELOG / VERSION / harness。
- 2026-07-08：独立复核发现两项 P2：需求包未同步、xhigh 机检只检查合并文本。已修复为 `description` 与 `developer_instructions` 分别检查，并补 harness 双负例。

## 验证记录

- `python .codex/hooks/model_policy_check.py --pre-commit`：exit 0；断言 `.codex/` 与 `templates/codex/` 的默认主对话、四档 agent、xhigh 确认门槛均符合策略。
- `python tests/harness/run_downstream_fixture.py --case model-policy`：exit 0；验证正常 fixture 通过，并分别删除 xhigh `description` / `developer_instructions` 中的确认语句时均 exit 2。
- `python -m py_compile .codex/hooks/model_policy_check.py templates/codex/hooks/model_policy_check.py tests/harness/run_downstream_fixture.py`：exit 0；新增 hook 与 harness 语法通过。
- `python .codex/hooks/mirror_drift_check.py`：exit 0；Codex hook 产品层与 dogfood 副本未缺文件。
- `python -m json.tool .codex/settings.json` 与 `python -m json.tool templates/codex/settings.json`：exit 0；两份 settings JSON 可用普通 UTF-8 解析，模板 BOM 已去除。
- `git -c safe.directory=D:/Quant/BridgeForge diff --check`：exit 0；仅 Git line-ending warning，无 whitespace error。
- `python tests/harness/run_downstream_fixture.py`：20 项全量 harness 全部 `[PASS]`，覆盖 model-policy、pre-commit、settings matcher、switch、skill metadata、git-sync runner 等。
- 独立 verification agent：首次复核发现 2 个 P2；修复后本地复验通过。剩余风险为真实 Codex 运行时是否按 custom agent 名称调度，需下游实际使用时观察。

## 用户试用反馈

待交付后记录。
