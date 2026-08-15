---
status: implemented
topic: bridgeforge-managed-rule-safety
scale: L
confirmed_at: 2026-08-16
source: develop -> confirm
related_bug: doc/2_bugs/BUG-aggressive-absorption-drops-downstream-rule-semantics.md
---

# BridgeForge 受管 Rule 安全升级需求确认卡

## 原始需求摘要

BridgeForge `0.94.2` 在真实高定制下游 `D:\Quant\StratusAgent` 执行 A 激进吸收后，
覆盖项目专属 Rule 语义、追加同义章节，并因误识别 fenced code 内标题生成损坏 Markdown。
用户要求修复升级器，而不是要求下游改写为模板格式。

## 目标

- A 只能覆盖能够证明属于 BridgeForge 的内容；项目填充区和下游增强不得静默丢失。
- 缺失普通标题默认 fail-closed 为 gap；只有 contract 显式声明 additive 才允许追加。
- Markdown 标题解析必须忽略 fenced code，并在 apply 后验证结构；失败纳入原事务回滚。
- 低定制、旧发布版本、keyed-table、A/B/C 单次确认和版本 ownership 行为不得回归。
- 用合成高定制 fixture 与 StratusAgent 故障前 HEAD 的临时副本完成验收。

## 不做

- 不用模糊语义匹配猜测“单向数据流”与“数据流方向”等标题是否等价。
- 不自动三方合并任意自然语言 Rule。
- 不直接修改、恢复、commit 或 push 真实 `D:\Quant\StratusAgent`。
- 本轮不执行 BridgeForge commit/push；发布仅在后续显式 `$git-sync` 中进行。

## 任务规模与预算

- 规模：L。
- 依据：改变 schema ownership、升级事务语义、Markdown parser、四份发布脚本、模板传播及真实高定制验收。
- 预算：120 分钟；45k 新增 token 估算（平台无法实测）；最多 3 个子 agent；最多 3 轮验证。
- 超预算停止点：预计超过时间、agent、验证轮次或范围扩张时，先请求扩大预算或缩小范围。

## 已核实事实

- `architecture.md` 的项目填充章节被登记在 `managed_blocks.headings`，A 可将项目红线替换为模板 TODO。
- `_replace_heading_items()` 会把目标缺失的普通标题无条件追加到文件末尾。
- `_markdown_heading_sections()` 不跟踪 fenced code，示例内 ATX heading 会参与切片。
- `version_release.py::_markdown_heading_parts()` 存在同构的 fence-blind parser。
- 当前终态验证只覆盖 memory、config 与 `git diff --check`，不检查 Markdown fence、章节重复/顺序或项目-owned 字节。
- Codex `anti_drift_hooks.md` 仍把 hook 注册位置写成旧的 `.codex/settings.json`。
- StratusAgent 故障变化尚未 commit/push，可从其 HEAD 恢复；真实恢复属于后续独立授权。
- 当前 BridgeForge 工作区已有用户提供的 Bug 报告与 `doc/README.md` 索引改动，必须保留。

## 已确认规则

- `architecture.md` 整文件采用 project-owned seed：缺失时创建，存在后 BridgeForge 不再修改。
- 对可定制 Rule，已发布整文件 hash 仍可安全升级；一旦发生本地漂移，默认 preserve/gap，A 不得覆盖。
- 普通受管标题缺失时默认 gap；仅 contract 显式 additive 的独立通用章节允许追加。
- 合法 fence 支持反引号和波浪线、不同长度、最多三个前导空格及语言标记；围栏内标题不得被识别为真实章节。
- apply 后校验本轮修改 Markdown 的 fence 配对、受管标题唯一性和显式章节顺序；失败回滚并保持旧版本戳。
- `anti_drift_hooks.md` 模板与索引统一指向 `.codex/hooks.json`；下游增强版不得被 A 静默覆盖。
- 0.94.2 部分落盘状态必须可识别并给出明确 gap/恢复清单，禁止自动从 Git HEAD 覆盖用户工作区。

## 拟修改

- `scripts/bridgeforge_project_sync.py`：ownership policy、缺失标题策略、fence-aware parser、结构验证与 receipt。
- `templates/codex/managed-skeleton.json` 及 `.codex/managed-skeleton.json`：逐资产 policy 与 architecture seed。
- 四份 `version_release.py`：与同步器一致的 Markdown ownership/parser 语义。
- `scripts/rebuild_shared_skill_manifest.py`、`shared-skill-manifest.json`：schema 校验与派生哈希。
- `templates/codex/rules/anti_drift_hooks.md`：Codex hook 注册源纠正。
- `skills/bridgeforge/SKILL.md`、`doc/0_architecture/design/codex-project-sync.md`：用户行为和 schema 事实源。
- harness 单测、完整 downstream fixture、高定制回归和真实下游只读/临时副本验收。

## 验收标准

1. StratusAgent 风格的 Gateway/Trader/UI/RiskEngine 项目红线经过 A 后逐字保留。
2. 同义不同名章节产生 gap，不追加第二套章节。
3. fenced Markdown 示例提取完整，apply 后 fence 配对。
4. `anti_drift_hooks.md` 项目增强保留，Codex 注册源统一为 `.codex/hooks.json`。
5. 结构校验失败时目标、版本戳和其他事务写入全部回滚。
6. 0.86.0+ 低定制升级、keyed-table、A/B/C、版本 ownership 和 retirement 回归通过。
7. 完整 fixture、StratusAgent HEAD 临时副本和独立发布审计通过。

## 风险与合理假设

- 采用 fail-closed 会让部分高定制项目收到更多 gap，这是为了避免语义损失的明确取舍。
- `architecture.md` 改为 seed 后不会自动获得上游新增内容；通用改进应进入其他明确受管资产。
- 不依赖自然语言相似度，因此不会自动合并同义标题。
- 真实 StratusAgent 恢复必须另行确认精确文件范围。

## 自动化边界

- 本轮允许修改 BridgeForge 仓库内产品、dogfood、文档和测试。
- 允许构建临时 fixture、只读访问 StratusAgent HEAD；禁止写入真实 StratusAgent。
- 禁止自动 commit/push。

## 实施计划

1. 收紧 schema ownership 与缺失标题策略，修正模板注册源。
2. 实现 fence-aware Markdown scanner 与事务终态结构验证，并同步 version-release。
3. 补齐低/高定制回归、完整 fixture、真实下游临时副本与独立审计。

## 实施 / 验证记录

- 源码：`architecture.md` 改为既有文件不写的 `seed`；普通 heading 漂移/缺失保留为
  gap；仅显式 `additive_headings` 缺失时 safe 追加；Markdown scanner 识别反引号/波浪线
  fence，apply 在写戳前验证结构并保护 seed 字节；当前版本 no-op 不重写版本戳。
- 旧伤恢复：partial-upgrade advisory 明确要求把所有既有 Rule seed（含
  `.codex/rules/architecture.md`）与可信升级前快照比较，禁止自动从 Git 恢复。
- 产品传播：Codex schema/manifest、BridgeForge skill、模板 AGENTS/config/Rule、四份
  `version_release.py` 与架构文档已同步；Codex hooks 单一注册源统一为 `.codex/hooks.json`。
- 自动化：相关 unittest `57/57`；完整 downstream fixture `39/39`；manifest `--check`、
  harness parity、mirror drift、skill metadata 与 `git diff --check` 均通过；四份
  `version_release.py` SHA-256 一致。
- 真实副本：`D:\Quant\CodexWorktree\test_bridgeforge`，基线 HEAD `33d2f1fa...`、版本
  `0.90.0`。A 更新执行 `safe=9/risk=3/U=0`，审计补丁后增量 `safe=1/risk=0/U=0`；
  `architecture.md`、`anti_drift_hooks.md`、`meta_rule_design.md`、`AGENTS.md` 哈希前后
  不变，旧戳保留且副本 `git diff --check` 通过。
- 独立审计：首轮发现 partial recovery、hooks 文档传播、写戳执行器说明和测试/文档状态
  四类阻断，均已修复；最终独立发布审计通过，未发现发布阻断。
- 未验证：未修改/运行真实 `D:\Quant\StratusAgent` 工作区；Codex Desktop `/hooks`
  trust、新会话 lifecycle 与用户手工恢复旧伤仍需真实现场验收。
