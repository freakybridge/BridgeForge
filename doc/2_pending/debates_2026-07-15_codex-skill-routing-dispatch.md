# 讨论：Codex skill 分段模型分派
> 日期：2026-07-15
> 确认卡：`doc/1_plan/codex-skill-routing-dispatch/requirements_2026-07-15_codex-skill-routing-dispatch.md`
> 目标：审查 18 个 skill 的 named custom-agent 路由能否在质量不降级前提下节省 token。
> 范围：Codex 产品层与 dogfood 路由契约、策略检查及 fixture；不修改 Claude 策略。
> Agent A：`/root/routing_proposer` / Agent B：`/root/routing_reviewer`

## 已确认事实

- custom agent 配置已存在，但 skill 未绑定 named custom agent。
- 用户已确认 Luna 阶段每次强制分派，且接受短任务可能出现额外调度成本的风险。
- 当前 Codex custom agent 的可用调用语法和精确 token 遥测能力仍待审查。

## Round 1

### 🔵 提议者

- 可落地的不是声明式“skill 自动选模器”，而是入口契约驱动的显式 named dispatch：在 Codex `AGENTS.md` 写清命中阶段后必须分派哪个 custom agent，主对话只做决策、用户交互与跨阶段整合。
- 路由应按阶段而非整个 skill 表示：`archive-scan` 的扫描可由 `light-explorer` 做，但归档判断、用户确认、移动与 README 更新必须留主对话；`develop` / `collab` / `debate` 分别用轻量研读、实现 worker 和独立 auditor。
- 建议把路由表设为带 marker 的 AGENTS 契约，扩展策略检查与 fixture 校验完整性、禁止把写入 / 复核降到 Luna、禁止自动 xhigh；但静态检查不得宣称运行时已实际分派。
- 运行时验收需在下游 fixture 中观察 `$find-doc`、`$archive-scan`、`$develop` 的子 agent 名称、交付结果与主线程摘要边界。

### 🔴 审阅者

- P0：官方只保证 custom agent 可由 name 识别，且 AGENTS / skill 指令可要求 delegation；当前可调用 spawn 能力没有 named-agent selector。路由契约与 hook 只能证明“指令已部署”，不能机械证明某次运行真的选中相应模型。
- P0：每个子 agent 都有独立模型和工具调用成本。强制 Luna 可以隔离主线程检索噪声，却不能保证总 token 下降；验收必须把“路由 / 质量”与“成本”拆开，缺乏遥测时禁止声称节省。
- P1：现有 4 档 TOML 与检查器不等于当前账号实际可用。首次发布需做四档 named agent 的最小运行时健康检查；失败时停止并报告，不能静默退化。
- P1：现有 policy checker 只校验模型 TOML 和 xhigh 文案，不读 AGENTS 或 skill 路由；需扩展检查或新增专用检查。产品层仅写 Codex AGENTS 的边界正确，但须在 smoke test 中确认实际选中的 skill 来源，防止同名 repo skill 遮蔽。

## Round 2

### 🔵 提议者修订

- 采用“两道门”：先在独立下游 fixture 中做 `light-explorer`、`implementation-worker`、`review-auditor` 的最小 named-agent 健康检查；名称或行为无法在运行时观测即停止发布，不把路由说明伪称为实际分派。
- 再发布 Codex 入口中的显式分派契约与静态防漂：主对话必须按阶段 spawn 指定名称并等待摘要，静态检查只验证契约、档位与模板 / dogfood 一致性，不谎称验证了运行时。
- 实测 `skills/*/SKILL.md` 为 18 个；`$bridgeforge` 是用户级安装 wrapper，不属于下游项目复制的 18 个产品 skill，保持主对话且不纳入本矩阵。
- 缺少 root + children 总 token 遥测时，成本结论只能标为“待验证”；可交付路由正确性、质量和可观测性，但不得声称节省 token。

### 🔴 审阅者复核

- 同意上述边界，前提是路由规则按阶段写明：skill、阶段、named agent、只读 / 写入边界，以及 root 必须保留的动作。
- 推荐使用机器可读 manifest 作为路由单一事实源，AGENTS 仅引用并说明执行语义；策略检查读取 manifest，校验 18 skill 覆盖、Luna 仅只读、实现 / 审计不降档、无自动 xhigh、模板 / dogfood 一致。
- 无静默 fallback：运行时实际子线程不是预期名称、Luna / Sol 不可用、质量 smoke 失败，均阻断产品发布；不得让主对话替代后仍报告已分派。
- 只有获得等价输入的 fresh-thread baseline 与 routed 对照，并能汇总 root + child 的精确 token，才可声称“节省 token”。否则只能说“隔离主线程检索噪声 / 成本待实测”。

## 共识结论

- 推荐实施“阶段级显式 named-dispatch 契约 + 机器可读路由 manifest + 静态 policy gate + 运行时健康 / 质量 smoke test”。
- 不存在 Codex 声明式的 `$skill → model` 自动映射；实现只能要求主对话显式分派 named custom agent，并以运行时收据验证当前环境是否遵守。
- 用户确认的强制 Luna 路由可以保留，但它不能作为总 token 节省承诺。无精确汇总遥测时，发布结论必须是“质量 / 路由可验证，成本待验证”。
- 需要用户确认该收敛方案后，才可修改产品层、dogfood、检查器与 fixture。

## 已确认的实施补充

- `$git-sync` 属于 18 个下游通用 skill，但其确定性同步阶段改由新增的可写 `mechanical-sync-worker`（Luna / low）承担；它只能运行现有安全同步脚本，任何分叉或冲突交回主对话。
- `$bridgeforge` 是用户级全局薄入口 / 工厂流程，不属于下游复制的 18 个 skill。它涉及 switch、冲突和迁移判断，保持主对话 Terra / medium；仅可在未来拆出独立的纯机械子阶段。
