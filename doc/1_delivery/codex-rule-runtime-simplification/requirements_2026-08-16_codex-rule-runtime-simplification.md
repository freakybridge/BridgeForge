---
status: implemented-awaiting-user-acceptance
date: 2026-08-16
topic: codex-rule-runtime-simplification
source: direct-confirm
next: user_acceptance
---

# Codex Rule 运行时精简需求卡

## 原始需求摘要

用户要求审计并精简 BridgeForgeCodex 当前 rule，消除冗余与不合适内容，且不得产生内容损失。

## 目标

将当前 Markdown rule 体系重构为 Codex 原生可执行的指令架构，并按“有效语义零损失”完成迁移：

- 所有仍然正确的“必须 / 禁止”条款都有唯一、实际生效的承载位置。
- 说明、案例、参数与 SOP 迁入对应文档或 skill。
- 过时、错误或互相矛盾的内容必须修正，不因字面保留而继续误导。
- 不新增自研 Markdown rule 加载器。

## 不做

- 不实现 `.codex/rules/*.md` 的自定义运行时加载器。
- 不修改 Codex 官方 `.rules` 命令权限机制。
- 不自动把下游自定义 rule 拼接进 AGENTS 或文档。
- 不触碰真实生产项目。
- 本交付不执行 Git commit、push、GitHub 仓库改名或远程地址修改。

## 任务规模与预算

- 规模：L。
- 判定依据：涉及公共指令架构、模板传播、下游受管资产退役、历史 lineage 与真实高定制样本迁移。
- 时间预算：90 分钟。
- Token 预算：45k 新增 token 估算；平台无可靠计量器，标记为未实测。
- Agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多 3 轮。
- 超预算停止点：范围扩大到运行时加载器、超过 3 轮验证、或发现无法无损分类的下游定制格式时，停止并只让用户选择扩大预算或缩小范围。

## 已核实事实

- Codex 官方自动发现机制是分层 `AGENTS.md` / `AGENTS.override.md`。
- Codex 官方 `.codex/rules/*.rules` 用于命令执行策略，不是 Markdown 指令的路径加载机制。
- 仓库未实现“读取 Markdown frontmatter `paths:` → 匹配当前操作路径 → 注入正文”的运行时加载器。
- 当前 hook 只执行 rule 大小、索引、镜像与静态一致性检查，不能证明 Markdown rule 正文进入运行时上下文。
- 8 个公共 Markdown rule 约 1109 行，存在 AGENTS/skill/doc 重复、过时事实、触发范围与正文不匹配及项目专属内容公共化等问题。

## 已确认架构

- 常驻红线进入根 `AGENTS.md`。
- 目录专属约束使用 Codex 原生嵌套 `AGENTS.md`；通用模板不得预设不存在的业务目录。
- 可机器判断的硬闸进入 hook / pre-commit。
- 操作流程进入对应 skill。
- 原理、案例、参数和长篇 SOP 进入 `doc/`。
- 同一有效约束只保留一个正文事实源，其他位置只允许精确指针。

## 逐文件语义迁移

### `architecture.md`

- 架构红线迁入 AGENTS §1.1。
- 项目结构与模块地图迁入 AGENTS §3。
- 长示例迁入参考文档。
- 公共 Markdown rule 退役。

### `modules.md`

- 项目模块地图迁入 AGENTS §3。
- 仍然通用的模块封装与依赖方向红线并入架构约束。
- Python 专属示例迁入参考文档，不作为所有项目的强制架构。
- 公共 Markdown rule 退役。

### `anti_fabrication.md`

- “先验证、不得编造、缺证据明确说明、发现错误立即更正”并入 AGENTS §1.2。
- 完整框架和案例迁入文档。
- 独立 Markdown rule 退役。

### `debugging.md`

- 证据先行、防循环、外部副作用隔离和性能量化并入 AGENTS §5。
- 排障步骤交由 `$escalate`、`$debate` 及参考文档承载。
- 独立 Markdown rule 退役。

### `workflow.md`

- 文档治理红线由 AGENTS §2.3 承载。
- 需求、总结、文档同步和归档流程分别由 `$develop`、`$summary`、`$sync-docs`、`$archive-scan` 承载。
- 长说明迁入文档。
- 独立 Markdown rule 退役。

### `portability.md`

- 环境隔离、禁止隐式用户级写入、可复现依赖等常驻红线进入 AGENTS。
- 可机器判断的编码、hook 注册和配置问题交由 hook。
- 安装、换机、打包流程迁入参考文档。
- 工厂 dogfood 约束不得下沉到普通项目。
- 独立 Markdown rule 退役。

### `anti_drift_hooks.md`

- `[clarify]`、`[focus]` 响应红线保留在 AGENTS。
- 机制、路径、参数和调试方法迁入 `doc/3_reference/`。
- 独立 Markdown rule 退役。

### `meta_rule_design.md`

- 删除错误的优先级理论、伪自动加载模型及无官方依据的阈值声明。
- “只写必须/禁止、单一事实源、可机判优先交 hook、说明迁 doc”压缩为少量 AGENTS 红线。
- 完整设计迁入 `doc/0_architecture/`。
- 独立 Markdown rule 退役。

### `bridgeforgecodex-product-change.md`

- 十条工厂产品发布红线迁入 BridgeForgeCodex 根 AGENTS 工厂自定义区。
- 可机器判断部分继续由 hook / pre-commit 硬拦。
- 工厂专属内容不得进入模板公共 AGENTS。
- 独立 overlay 退役。

## 下游迁移规则

- hash 精确匹配官方历史版本的旧 rule 作为 retirement 安全删除。
- 被下游修改过的旧 rule 必须逐字保留并列为 gap；禁止覆盖、删除或自动拼接。
- 收据必须逐文件列出保留原因、建议迁移目标和人工动作。
- 未解决定制文件存在时 readiness 必须降级，禁止声称完美更新。
- 历史 `0.86.0+` lineage、可信 hash 和 rollback/stamp-last 契约必须保留。

## 拟修改范围

- 根与模板 `AGENTS.md`。
- `templates/rules/**`、`.codex/rules/**` 及退役 lineage。
- rule index、size/mirror/structure 等相关 hook。
- `templates/managed-skeleton.json` 与 `.codex/managed-skeleton.json`。
- 项目同步器、plan/receipt 与 retirement advisory。
- 相关 skills、references、架构文档和参考文档。
- `doc/README.md`、VERSION、CHANGELOG、active/compat manifest 及测试。

## 验收标准

1. 生成逐条“旧位置 → 新位置”语义映射清单；所有仍正确的红线均有唯一承载位置。
2. 活跃文案不再声称 Markdown rule 会按 `paths:` 自动加载。
3. 模板公共 AGENTS 与 BridgeForgeCodex 根 AGENTS 的公共区域精确一致；工厂规则只位于允许的自定义区。
4. 退役文件进入 schema 历史 lineage，官方旧副本可安全退休。
5. 下游修改过的旧 rule 不被删除、覆盖或自动吸收，且在收据中逐文件展示。
6. 有 gap 或验证失败时禁止写新版本戳；任何可捕获失败必须完整回滚。
7. 完整自动测试、发布基线 fixture 与静态发布硬闸通过。
8. 两个高定制测试 worktree 均完成验收：
   - `D:\Quant\CodexWorktree\test_bridgeforge`
   - `D:\Quant\CodexWorktree\test_bridgeforge_crs`
9. 独立审计确认没有有效语义损失、无下游定制覆盖、无发布阻断。

## 合理假设与风险

- “零损失”指有效语义零损失，不要求保留错误、矛盾或已失效实现说明的原句。
- 两个指定 worktree 是用户授权的测试副本；仍需在写入前记录 Git 状态和目标文件 hash。
- 规则退役会改变下游受管资产集合，必须通过可信历史 hash 和 fail-closed ownership 防止误删。
- AGENTS 内容增长可能触及上下文预算；迁入时必须保持常驻红线短小，长说明只留指针。

## 自动化边界

- 允许在本仓库修改产品、dogfood、文档、测试与派生 manifest。
- 允许按统一同步器协议测试两个指定高定制 worktree；不得手工复制或覆盖其自定义文件。
- 不允许操作用户真实生产项目、用户级安装目录、Git remote、commit 或 push。

## 实施计划

1. 建立旧 rule 逐节语义映射和 1.0.0 可信 lineage，先锁定所有仍有效条款及项目定制边界。
2. 将常驻红线迁入模板 AGENTS，将工厂产品红线迁入根 AGENTS 自定义区；流程、SOP 与设计说明分别迁入 skill 和 doc。
3. 退役 8 个公共 Markdown rule、工厂 overlay 及其专用 index/size hook，更新 dispatcher、pre-commit、mirror、schema、同步器收据和测试。
4. 重建 managed contract 与 active/compat manifest，运行定向测试、完整测试、发布基线 fixture 和两个高定制 worktree。
5. 启动独立审计，按逐条语义映射核对内容损失、下游 ownership、stamp-last 与发布完整性。

## 实施记录

- 已将 8 个公共 Markdown rule 与工厂 overlay 从活跃产品面退役；官方历史 hash 纳入 retirement lineage，modified / ownership 不明的下游文件保留为逐文件 gap。
- 有效常驻红线已迁入模板与根 `AGENTS.md`；机器可判约束进入 hook / pre-commit；操作流程与长 SOP 分别进入 skill 和 `doc/`。
- 已增加 `instruction_source_check.py`，旧 `rule_index_check.py` / `rule_size_check.py` 文件名只保留兼容入口并委托新硬闸。
- 已修正 README、INSTALL、hook/script 活跃指针，以及 `workflow.md` §9–§10 的版本域隔离与大版本依赖 spike 语义遗漏。
- 已增加 AGENTS 迁移依赖闸：只要 `root.agents` 存在 gap，8 个旧 rule 的 retirement action 必须全部撤销并改报逐文件人工迁移 gap；旧文件与旧版本戳保持不变。
- 已补齐伪 Markdown 自动加载声明的双语序与标点边界识别，覆盖分号、中英文逗号连接的“先否定、后肯定”绕过。

## 验证记录

- 完整自动测试：`.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`，217/217 通过。
- 发布 lineage fixture：`.venv\Scripts\python.exe -B scripts/tests/run_downstream_fixture.py`，19/19 个 `0.86.0+` 可达发布基线迁移通过。
- 发布硬闸：manifest `--check`、`instruction_source_check`、mirror drift、skill metadata、project structure 与 `git diff --check` 全部 exit 0；project structure 仅输出既有归档 advisory。
- 两个高定制样本完成最终只读验收：`test_bridgeforge` 与 `test_bridgeforge_crs` 均为 `rule_action_count=0`、`rule_gap_count=8`、8 个旧 rule 全部存在；版本戳分别保持 0.90.0 与 1.0.0，未写 1.1.0。
- `test_bridgeforge_crs` 的清理仅恢复到 Git 可见版本，不能证明测试前未提交 / 未跟踪状态被完整还原；这属于样本恢复边界，后续不得宣称“原现场完整恢复”。
- 最终独立审计确认 retirement 依赖闸、双 1.0 portability hash lineage、模板/dogfood/manifest 与两个样本安全行为正确；审计追加发现的逗号绕过与需求卡状态不一致均已修复并完成复验。
