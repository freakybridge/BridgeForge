---
name: BridgeForge 单次确认与零确认更新协议
description: 将 init、adopt、update、switch 的安全动作自动执行，风险动作集中确认一次，并减少 Codex 重复权限弹窗。
type: requirements
category: architecture
status: completed
date: 2026-08-15
scale: L
source: confirm
---

# BridgeForge 单次确认与零确认更新协议确认卡

## 原始需求摘要

用户反馈下游运行 `/bridgeforge` 完成更新需要多次确认，操作负担过高。目标从只优化
`update` 扩展为统一治理 `init`、`adopt`、`update`、显式 `switch` 四种模式，同时减少
BridgeForge 对话确认和 Codex 平台权限弹窗。

调用来源：用户直接调用 `$confirm` 完成逐项确认。

## 目标

- 常规路径不产生 BridgeForge 业务确认。
- 存在可安全执行的确定性风险动作时，先展示完整计划，再集中确认一次。
- 不确定或冲突项保持原样、跳过并形成 gap，不继续追问；其余安全动作继续执行。
- 对 `init`、`adopt`、`update`、`switch` 使用同一确认协议和收据语义。
- 用户首次认可窄范围 Codex `prefix_rule` 后，后续相同 BridgeForge 用户级维护命令不再
  重复触发平台权限询问。
- 用户拒绝开启 Codex 原生 memories 后持久记录决定，后续不再重复询问；只有用户明确
  要求开启时才重新进入授权流程。

## 不做

- 不设置 `approval_policy = "never"`。
- 不使用 `danger-full-access`、`--yolo` 或宽泛命令白名单。
- 不静默覆盖下游定制内容。
- 不绕过 Codex 强制要求的 `/hooks` review/trust。
- 不自动 `git add`、commit、push 或跨项目更新。
- 不把项目版本戳、已安装状态或 `/bridgeforge` 调用解释为任意用户级写入授权。

## 任务规模与预算

- 规模：L。
- 依据：同时改变四种 BridgeForge 模式、用户级授权状态、下游文件合并策略和 Codex
  平台权限交互。
- 时间预算：90 分钟。
- token 预算：约 40k 新增 token（估算；平台没有可靠计量器，未实测）。
- agent 预算：最多 3 个阶段 agent，分别用于只读 discovery、实现和独立审计。
- 验证预算：最多 3 轮。
- 超预算停止点：超过任一预算、需要新增第二套持久状态源、或发现无法在一次确认内安全
  表达的破坏性操作时停止，由用户选择扩大预算或缩小范围。

## 已核实事实

- 当前根入口会分别处理 Codex 原生 memories、遗留 `.agents/`、模式分流和当前项目维护。
- 当前 `update` 会分别确认 A/B/C/D/F、memory 分类、junction、遗留 note、孤儿目录等动作。
- 当前 `init`、`adopt` 也存在覆盖、基线、参数和 hook trust 询问。
- 当前 `switch` 已具备冲突保留、其余继续并输出 `completed_with_gaps` 的基础语义。
- Codex 的 sandbox mode 决定技术访问边界，approval policy 决定何时询问；二者是独立的
  安全层。
- Codex 可将用户认可的窄命令前缀写入用户级 rules，后续匹配命令可跳过相同询问。
- 本仓库 `doc/README.md` 使用 `delivery_layout: flat`。
- 确认时 BridgeForge 版本为 `0.88.4`，Git 工作区未显示已跟踪或未跟踪变更，仅报告
  用户级 Git ignore 读取权限警告。

## 未核实事实

- Codex Desktop 当前版本对相同 `prefix_rule` 的实际弹窗文案和持久化时序尚未 smoke。
- 管理员策略是否允许下游用户保存 BridgeForge 的窄 `prefix_rule` 取决于实际运行环境。
- `/hooks` review/trust 是否因具体 hook 内容变化而出现，必须由真实下游运行验证。

## 已确认业务规则

### 统一确认协议

1. `/bridgeforge` 调用本身授权当前项目内可证明安全、确定、幂等的变更，以及 manifest
   已登记的用户级 skill 更新。
2. 确认协议必须先完成全部只读盘点，再决定本轮是零确认路径还是单次确认路径。
3. 同一轮最多展示一张风险确认卡；卡片必须列出精确路径、动作、影响、是否可恢复、
   fingerprint 和推荐处理。
4. 单次确认必须同时满足项目高风险提示格式：`我要执行 [Action]，这可能导致 [Impact]，
   是否继续?`
5. 用户确认后，apply 前必须重算或验证 plan fingerprint；状态漂移时零写入并停止，禁止
   沿用旧授权。
6. 用户拒绝风险计划时，风险项保持原样；仍可执行与风险项无依赖的安全动作，并明确
   输出 gaps。

### 零确认安全动作

- manifest 已登记且由现有托管账本约束的用户级 skill 原子更新。
- 缺失受管文件的补齐。
- 下游文件仍与已知旧模板逐字一致时的确定性 fast-forward。
- 只修改 `BRIDGEFORGE_MANAGED` 区块且逐字保留下游扩展的 merge。
- settings/hooks 的稳定身份 merge，前提是第三方字段和 handler 逐字保留。
- `.gitignore` BridgeForge 机制块幂等补缺。
- 无冲突的版本戳 finalization、校验、smoke test 和只读收据。
- `switch` 中有确定 map 证据的原生 projection；source 保持不变。

### 单次确认风险动作

- 已完整盘点并可回滚的文件移动或删除。
- Codex 原生 memories 首次启用、用户级同步 hook 安装和 private 仓库创建。
- 同名 public memories 仓库转为 private。
- 遗留 `.agents/` 中已确定归属内容的迁移或已知公共副本删除。
- memory、junction、遗留 note、孤儿目录和 `doc/` 布局中具备精确来源、目标、hash 与
  回滚边界的迁移。
- 其他虽有影响但无需用户进行业务判断、且能由一张完整计划安全表达的确定性动作。

### 不确定项与冲突

- 下游人工修改、来源不可信、分类低置信、目标已存在且内容不同、map 损坏、路径异常、
  plan 竞争或无法证明 ownership 时，一律保留并跳过。
- 不确定项不得进入“全部按推荐自动覆盖”路径，也不得触发第二轮逐项询问。
- 其他安全动作继续执行；最终状态为 `completed_with_gaps`，逐项报告 source、target、
  原因和保持不变的证据。
- 用户以后若明确要求解决某个 gap，必须作为新的显式任务处理，不复用旧授权。

### Codex 原生 memories 拒绝状态

- 用户在唯一确认卡中拒绝开启原生 memories 时，在现有 Codex BridgeForge 托管账本写入
  明确的 consent 状态；禁止新建第二套偏好账本。
- 拒绝状态只表示“不再主动询问”，不得创建仓库、安装同步 hook 或修改 memories 开关。
- 后续 `/bridgeforge` 只在收据中报告已选择不启用，不再弹出问题。
- 用户明确要求开启时，才清除拒绝状态并重新生成包含外部影响的唯一确认卡。
- memories 已启用时继续执行幂等 health check 和 reconcile，不重复询问。

### init / adopt 参数推导

- Windows 平台等可由真实环境确定的事实直接采用。
- 语言、现有骨架、Git 状态和文档布局优先从项目文件确定，不让用户重复输入。
- 无法确定且会改变结果的参数进入唯一确认卡，并提供基于已核实事实的推荐值。
- 若用户拒绝推荐值，该参数对应动作跳过并形成 gap，不开启第二轮问题。

### Codex 平台权限

- BridgeForge 不修改用户全局 `approval_policy`、sandbox mode 或 permission profile。
- 用户级外部写入尽量收口到单一、窄范围、可审计的 BridgeForge 维护入口；Codex 请求
  escalation 时只建议与该入口匹配的窄 `prefix_rule`。
- `prefix_rule` 必须固定到 BridgeForge 维护脚本及必要子命令，禁止使用 PowerShell、
  Python 或任意脚本解释器级宽前缀。
- 用户拒绝持久规则时功能仍可运行，但平台可能继续弹窗；收据必须标明限制。
- `/hooks` review/trust 是平台强制边界。BridgeForge 不额外重复确认；未完成时可结束骨架
  更新，但必须报告 `trust 未验证`，禁止声称 hook runtime 已验收。

## 数据映射与单一事实源

| 数据 | 唯一事实源 | 写入规则 |
|---|---|---|
| 当前项目计划 | 本轮只读盘点结果 + plan fingerprint | 不跨会话复用；apply 前重新验证 |
| BridgeForge 受管 skill ownership | 现有用户级 managed ledger | updater 原子维护，不接受项目版本戳替代 |
| Codex native memories consent | 现有 Codex managed ledger 的显式字段 | 只记录明确同意/拒绝，不新建第二账本 |
| 下游定制内容 | 当前项目真实文件 | 无可靠 ownership 证据时永远保留 |
| switch 映射状态 | 当前宿主 `.bridgeforge-map.json` | 只保存确定性映射、状态和 hash |
| 平台命令允许规则 | Codex 用户级 rules | 只由 Codex 在用户认可后持久化，BridgeForge 不直接写 |

## 拟修改范围

### 产品层

- `skills/bridgeforge/SKILL.md`。
- `skills/bridgeforge/references/init.md`。
- `skills/bridgeforge/references/adopt.md`。
- `skills/bridgeforge/references/update.md`。
- `skills/bridgeforge/references/switch.md`。
- `skills/bridgeforge/references/user-skill-maintenance.md`。
- 用户级维护入口、原生 memories consent 状态和托管账本 schema 的相关 `scripts/`。
- 必要时调整确定性 plan/apply 工具，但不得引入第二套常驻状态或开放式执行载荷。
- `tests/harness/` 与 `run_downstream_fixture.py` 中的双宿主、四模式和权限边界覆盖。
- 共享 skill manifest 及其重建收据。

### 元文档与发布

- 本需求卡与 `doc/README.md`。
- 必要的架构说明。
- `VERSION` 与 `CHANGELOG.md`，产品层变更使用 `[product]` 标签。

### dogfood

- 若实施触及 `templates/codex/hooks/` 或 `templates/codex/settings.json`，必须同步自身
  `.codex/` 并通过 mirror drift；当前确认范围不预设需要修改 hook/settings。

## 验收标准

1. `init`、`adopt`、`update`、`switch` 分别覆盖零确认安全路径。
2. 四种模式分别覆盖多个确定性风险动作只生成一张完整确认卡。
3. 多个冲突同时存在时全部保留，只形成 gaps，不追加询问。
4. 安全项可在同轮继续完成，并输出 `completed_with_gaps` 和逐项保持证据。
5. memories 拒绝状态跨会话生效；后续普通运行不再询问；明确重新开启可恢复授权流程。
6. `init/adopt` 可确定参数自动推导，无法确定参数只进入唯一确认卡。
7. 用户级维护使用单一窄命令入口；接受持久规则后，相同维护入口的重复运行不再请求
   同类平台权限。
8. 持久规则测试证明前缀不能扩大到通用 PowerShell/Python、其他 BridgeForge 脚本或任意
   参数载荷。
9. 下游定制文件、第三方 hook、项目业务版本、另一宿主 source 和项目外路径保持不变。
10. plan fingerprint 漂移、未知 ownership、损坏账本、链接和路径逃逸均 fail-closed 且
    零风险写入。
11. Codex 与 Claude 下游 fixture、共享分发、manifest check、相关 JSON/TOML 解析、
    `git diff --check` 通过。
12. 真实 Codex Desktop `prefix_rule`、权限弹窗和 `/hooks` trust 若未完成现场 smoke，必须
    明确标记“未验证”，不得用静态测试冒充。

## 合理假设与风险

- 用户接受 `/bridgeforge` 调用授权 manifest 受管 skill 和当前项目内的确定性安全更新。
- 用户级维护脚本由 BridgeForge manifest/hash 供应链约束；窄 `prefix_rule` 会信任该入口
  的未来受管版本，因此脚本参数面必须保持封闭并经过测试。
- 管理员可能禁止用户持久化 allow rule；这种环境无法保证平台弹窗归零。
- 新增或改变 hook 时，平台仍可能要求独立 `/hooks` trust；BridgeForge 不能替用户接受。
- 为避免多轮询问，不确定项默认保留可能导致本轮只部分升级；`completed_with_gaps` 是完成态，
  不是全部能力等价。

## 官方依据

- OpenAI Docs：<https://learn.chatgpt.com/docs/agent-approvals-security>
- OpenAI Docs：<https://learn.chatgpt.com/docs/agent-configuration/rules>

## 自动化与权限边界

- 本确认卡授权写入本仓库需求文档；产品实现仍需用户选择后续开发流程并完成对应开工闸。
- 开发测试必须使用临时用户目录、mock 外部命令或隔离 fixture，禁止修改真实用户级
  approval policy、rules、memories 仓库或 hook trust 状态。
- 真实 public→private、用户级 hook 安装和持久 `prefix_rule` 只在用户实际运行
  `/bridgeforge` 并通过对应平台/业务授权时发生。
- 不自动 `git add`、commit 或 push。

## 实施计划占位

- [x] 设计并实现统一 plan / single-consent / apply 契约。
- [x] 收口四种模式的安全、风险和 gap 分类。
- [x] 实现 native memories 拒绝状态与显式重新开启。
- [x] 收口用户级维护入口和窄权限建议。
- [x] 同步测试、manifest、版本、CHANGELOG 和文档。
- [x] 经用户明确授权后，实现已批准且发生漂移时的 health repair / reconcile 外部副作用。

## 实施记录

- 根入口增加统一 safe / risk / gap accumulator、聚合指纹、零或一张风险卡，以及
  `completed_with_gaps` 收据；init、adopt、update、switch 统一人工差异保留策略。
- `.agents` migration 与 switch apply 增加紧邻重算的 plan/risk fingerprint，输入漂移时
  零写入；未知内容和人工修改不覆盖，只形成 gap。
- 复用 Codex schema-v1 managed ledger 保存 `approved|declined`；旧版已启用但无 consent
  的安装按 `legacy_enabled` 处理，不重复询问。
- 新增封闭的 `bridgeforge_user_maintenance.ps1 -Action refresh`；持久权限规则只覆盖这一
  固定入口，wrapper 不读取 hooks.json、不执行用户提供的 Python，也不开放 source/payload。
- 用户已明确授权：`approved + enabled` 且只读健康检查发现漂移时，以非持久平台审批运行
  `codex_memory_sync.py maintain`，修复受管 hook/remote 并 reconcile；legacy 无 consent
  或已关闭状态均 fail-closed，不创建仓库、不写用户配置。
- 版本提升到 `0.89.0`，更新 CHANGELOG、共享 manifest 和五份 switch 镜像。

## 验证记录

- `.venv\\Scripts\\python.exe -m unittest tests.harness.test_bridgeforge_root_skill
  tests.harness.test_memory_native_sync tests.harness.test_shared_skill_distribution -v`：69 项通过；
  覆盖四模式禁用旧确认措辞、legacy enabled、consent fail-closed、wrapper 拒绝 native/任意参数。
- `.venv\\Scripts\\python.exe tests\\harness\\run_downstream_fixture.py`：37 个完整下游场景
  全部通过；覆盖 migration fingerprint/rollback、gap 保留、switch 生命周期和用户 skill 分发。
- `.venv\\Scripts\\python.exe -m unittest tests.harness.test_skill_metadata_budget -v`：7 项通过。
- `scripts\\rebuild_shared_skill_manifest.py --check`、`mirror_drift_check.py`、`git diff --check`
  均通过；五份 `bridgeforge_switch.py` SHA-256 均为
  `E7D6257E043036E8466927EF7CC14A1AFBD6D5F9B9351C78954A7690A59A9539`。
- 独立 review-auditor 首轮发现 4 个 P1，其中 3 项已关闭；聚焦复审发现的最后一项在用户明确
  授权后实现，并新增 approved/legacy 两条维护回归。真实 Codex Desktop `prefix_rule` 持久
  时序与 `/hooks` trust 尚未现场验证，发布前不得宣称这些边界已实测。
- 最终聚焦复审确认 maintain 授权顺序、public→private 阻断、legacy/disabled fail-closed、
  异常不写 pending 均无 P0/P1；其指出的 status/maintain 文案冲突已修正，根契约 8 项复测通过。

## 后续交接目标

用户已选择 `$develop`，并在开工硬闸中明确把 agent 预算从 0 扩大为最多 3 个阶段
agent。后续必须以本卡作为唯一需求输入，进入 L 级实现与最多 3 轮验证。
