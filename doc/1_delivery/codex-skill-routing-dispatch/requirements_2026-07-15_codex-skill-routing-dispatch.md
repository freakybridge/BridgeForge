# 需求：Codex skill 分段模型分派
> 日期：2026-07-15
> 状态：trial
> 入口：用户要求把下游 Codex 骨架的 18 个通用 skill 按任务阶段分派给不同模型，在质量不降级前提下节省 token。
> 调用来源：`$confirm` → `$debate`

## 背景与目标

现有 Codex 骨架已定义主对话和四类 custom agent 的模型 / reasoning-effort 档位，但共用 skill 本体没有声明实际应分派哪个 named custom agent。本需求把已存在的档位落到 18 个通用 skill 的具体阶段，使独立的只读工作转给轻量 agent，实施与独立审计保留高强度 agent。

## 非目标

- 不修改 Claude 骨架的模型策略，不复制 Codex 专属 skill 本体。
- 不依赖 `SKILL.md` frontmatter 的 `model:` 字段自动切换模型。
- 不改变主对话默认 `gpt-5.6-terra + medium`。
- 不自动使用 `xhigh-auditor`；仍必须由用户当次明确确认。
- 不承诺每次调用的绝对 token 均下降。

## 已核实事实

- `templates/codex/` 是下游 Codex 骨架的权威产品层。
- `.codex/agents/*.toml` 已定义 `light-explorer`（Luna / low）、`implementation-worker`（Terra / high）、`review-auditor`（Sol / high）和 `xhigh-auditor`（Sol / xhigh）。
- 未显式分派 custom agent 的 skill 由主对话执行；skill frontmatter 的 `model:` 不是本骨架的自动路由依据。
- Codex custom agent 的模型与 reasoning effort 由 spawned session 加载的 `.codex/agents/*.toml` 覆盖。

## 已确认业务规则

- 本轮一次覆盖已盘点的 18 个下游通用 skill；全局 `$bridgeforge` 入口单列说明，不纳入下游复制 skill 的计数。
- 路由表中标为 Luna 的阶段，每次调用该阶段都必须分派 `light-explorer`，不采用规模阈值。
- 实现阶段用 `implementation-worker`，独立复核 / 审计阶段用 `review-auditor`。
- 模型分派契约仅放在 Codex 骨架入口；共用 `skills/*` 只保留模型无关的流程阶段。
- `$git-sync` 使用新增的可写、受限 `mechanical-sync-worker`（Luna / low）；它只运行确定性的同步脚本，遇到分叉、冲突或脚本停止必须交回主对话。
- `$bridgeforge` 保持主对话 Terra / medium：它涉及骨架冲突、agent switch、memory / settings 迁移与用户确认，不整体降档。

## 数据映射

| 工作阶段 | Codex custom agent | 模型 / effort |
|---|---|---|
| 独立、只读、可验收的检索或摸底 | `light-explorer` | `gpt-5.6-luna + low` |
| 已授权、确定性且受脚本安全闸保护的 Git 同步 | `mechanical-sync-worker` | `gpt-5.6-luna + low` |
| 主控、用户意图判断、短小上下文操作 | 主对话 | `gpt-5.6-terra + medium` |
| 明确实现、跨文件修改与验证 | `implementation-worker` | `gpt-5.6-terra + high` |
| 独立复核、验收审计、反驳假设 | `review-auditor` | `gpt-5.6-sol + high` |

## 拟修改

- `templates/codex/AGENTS.md`：写入完整 skill → 阶段 → named custom agent 路由契约。
- `templates/codex/agents/mechanical-sync-worker.toml`：定义只允许执行受控同步脚本的 Luna worker，并镜像到 dogfood。
- `.codex/AGENTS.md`：按 dogfood 约定镜像同一契约。
- `templates/codex/hooks/model_policy_check.py` 与 `.codex/hooks/model_policy_check.py`：机检路由契约存在、禁止自动 xhigh，且保持模板 / dogfood 一致。
- 对应 harness fixture：覆盖正常路由与关键负例。
- 本需求包和 `doc/README.md`：记录实施、验证和用户试用结果。

## 验收

- [ ] 18 个 skill 的分段路由均有明确的 named custom agent 或明确保留主对话。
- [ ] Luna 阶段强制指定 `light-explorer`；高风险实现 / 独立复核不得降到 Luna。
- [ ] `$git-sync` 只可分派给受限的 `mechanical-sync-worker`；它不得处理分叉或冲突决策。
- [ ] `$bridgeforge` 被单列为全局入口，明确保持主对话编排。
- [ ] `xhigh-auditor` 没有任何自动分派路径。
- [ ] 模板与 dogfood 路由说明、hook 检查和 fixture 一致。
- [ ] `find-doc`、`archive-scan`、`develop` 完成前后对照，结果完整且质量不降级。
- [ ] 记录可获得的 token / 子线程数证据；无精确 token 遥测时明确说明限制。

## 合理假设与剩余风险

- 子 agent 有独立 token 成本；本改造主要减少主线程上下文污染，不能保证短任务的绝对 token 均下降。
- 当前 Codex app 对“调用 named custom agent”的实际语法与可观测遥测能力，须在 debate 中按本机可用能力复核。
- 强制 Luna 分派是用户已确认的策略；若代表任务显示质量或成本反向恶化，必须回报证据并等待后续调整，不得自行扩大或撤销范围。

## 实施记录

- 2026-07-15：`$confirm` 完成；用户确认覆盖 18 个 skill、Luna 阶段强制分派、仅改 Codex 骨架入口，并要求以 debate 审查后再实施。
- 2026-07-15：用户补充确认 `$git-sync` 应使用专用 Luna / low 机械同步 worker；`$bridgeforge` 是全局入口，保留 Terra / medium 主控并在路由说明中单列。
- 2026-07-15：新增模板 / dogfood `skill-routing.json`、`mechanical-sync-worker` 与入口契约；扩展模型策略检查和下游 fixture，版本与 CHANGELOG 已同步，待运行验证与实际 Codex named-agent smoke test。

## 验证记录

- 2026-07-15：`python -m json.tool templates/codex/skill-routing.json` 与 `.codex/skill-routing.json` 均 exit 0；验证两份路由清单均为合法 JSON。
- 2026-07-15：`python -m py_compile templates/codex/hooks/model_policy_check.py .codex/hooks/model_policy_check.py tests/harness/run_downstream_fixture.py` exit 0；验证策略检查与 fixture 语法。
- 2026-07-15：`python .codex/hooks/model_policy_check.py --pre-commit` 与 `python templates/codex/hooks/model_policy_check.py --pre-commit` 均 exit 0；验证模板 / dogfood 的五个 agent 档位、18-skill manifest、git-sync worker、bridgeforge 主控和无自动 xhigh。
- 2026-07-15：`python tests/harness/run_downstream_fixture.py --case model-policy` PASS；fixture 分别拦截缺失 `find-doc → light-explorer`、把 `develop` 独立复核降到 Luna、自动 xhigh、xhigh 确认词漂移和用户级配置 guard 注册丢失。
- 2026-07-15：`python tests/harness/run_downstream_fixture.py` 全量 PASS；其余 28 项 harness 回归通过。
- 2026-07-15：`python .codex/hooks/encoding_check.py --pre-commit` 与 `git diff --check` exit 0。`mirror_drift_check.py` 仅提示既有 `skill_sync_check.py` 软漂移，和本次无关。
- 未验证：当前可用协作接口没有 named custom-agent selector，无法在此会话中证明桌面端实际将 `$find-doc` / `$archive-scan` / `$develop` 分派给指定名称。下游 Codex app smoke test 仍是发布前人工门槛。

## 用户试用反馈

- 请在已复制骨架的下游 Codex 项目中依次运行 `$find-doc <已知主题>`、`$archive-scan`、`$develop <小型需求>`，检查 Subagents 面板是否分别出现 manifest 指定的 agent 名称，并记录结果完整性。若能导出 root + children 汇总 token，再用同输入的新线程单线基线对比；否则仅报告路由 / 质量已验证，成本待验证。
