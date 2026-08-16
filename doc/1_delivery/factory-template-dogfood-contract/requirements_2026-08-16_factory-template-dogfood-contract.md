---
status: implemented-awaiting-user-acceptance
size: M
---

# BridgeForgeCodex Template 基线与工厂 Overlay 需求卡

## 原始需求摘要

用户希望 BridgeForgeCodex 自身在 AGENTS 和 Rules 层面遵守 `templates/**` 的公共规则，同时完整保留工厂专属约束，禁止两边对同一规则分别复述后逐渐漂移。

## 调用来源与后续交接

- 调用来源：用户在 Template 根扁平化完成后要求明确工厂 dogfood 规则，由 `$confirm` 完成逐项确认。
- 当前状态：实现、自动验证与独立审计均已完成，等待用户验收。
- 后续交接：独立审计通过后等待用户试用与验收；未经用户明确要求不 commit/push。

## 目标

1. `templates/**` 成为公共 AGENTS 与 Rules 的单一事实源。
2. BridgeForgeCodex 原样运行公共规则，同时用明确的项目定制区和工厂 Overlay 承载自身事实。
3. 同一公共规则禁止在工厂侧压缩、复述或另写近义版本。
4. 建立编辑后提示、pre-commit、测试与发布四层防漂移验证。
5. 重组前完成旧规则逐条映射，保证无丢失、无重复、无弱化。

## 不做

- 不要求 `doc/README.md` 与 Template 逐字一致，只要求遵守五层文档红线。
- 不让 BridgeForgeCodex 自身执行下游 `project_sync adopt`。
- 不写 `.codex/.bridgeforge_codex_version`。
- 不自动覆盖暂时不一致的文件。
- 不修改用户级安装、两个真实样本、GitHub、本地仓库名或 origin。
- 未经用户明确要求，不 commit/push。

## 规模与预算

- 规模：M。
- 判定依据：跨 AGENTS、Rules、schema、dogfood hook 与测试，但所有权边界和验收已明确。
- 时间预算：45 分钟。
- Token 预算：约 20k 新增 token；平台无可靠计量器，未实测。
- Agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多 2 轮。
- 停止点：发现规则无法确定唯一归属、需要削弱 Template 红线、必须覆盖未知项目内容，或预计超过任一预算。

## 已核实事实

1. `templates/AGENTS.md` 已将 `§1.1 架构红线`、`§3 项目目录地图`、`§4.2 快速命令`定义为项目定制区。
2. 当前根 `AGENTS.md` 仍使用旧工厂章节结构，与 Template 公共结构不一致。
3. 当前 `.codex/rules/` 只有工厂专属 `bridgeforgecodex-product-change.md`；8 个 Template rule 尚未全部 dogfood。
4. schema 当前把 `architecture.md` 定义为下游 project-owned seed；本需求不改变下游 ownership，只规定 BridgeForgeCodex 自身镜像 Template 版本。
5. 当前根 AGENTS 与工厂 rule 中存在专业表达、自改审计、Skill 分工、`$git-sync`、dogfood、验证证据等重复或近义规则。
6. 当前自身只读 planner 为 adopt，并产生安全动作和 gap；该 planner 不适合作为工厂合规凭证。

## 已确认规则

### 1. 单一事实源

- `templates/AGENTS.md` 与 `templates/rules/**` 是公共规则唯一事实源。
- 公共规则必须先修改 Template，并在同一轮原样同步到 BridgeForgeCodex。
- 两边都有的规则必须逐字一致；禁止压缩复述、近义重复或设置“冲突时谁优先”。

### 2. AGENTS 所有权

根 `AGENTS.md` 与 Template 使用同一章节结构。只允许以下差异：

1. `{{PROJECT_NAME}}` 渲染为 `BridgeForgeCodex`。
2. `§1.1 架构红线` 填写工厂身份、分层、传播四问与 playbook 指针。
3. `§3 项目目录地图` 填写工厂真实目录。
4. `§4.2 快速命令` 填写工厂真实命令。
5. `§2.1 规则文件索引` 在公共行之外增加工厂 rule 行。

除上述白名单外，公共区块必须与 Template 一致；根文件禁止新增 Template 未定义的顶层章节。

### 3. Rules 所有权

以下 8 个 rule 必须从 Template 原样镜像到 `.codex/rules/`：

- `anti_drift_hooks.md`
- `anti_fabrication.md`
- `architecture.md`
- `debugging.md`
- `meta_rule_design.md`
- `modules.md`
- `portability.md`
- `workflow.md`

BridgeForgeCodex 的真实工厂架构不写入 `architecture.md`，只写在 `AGENTS.md §1.1` 和工厂专属 rule。`bridgeforgecodex-product-change.md` 是允许额外存在的工厂 Overlay；未来新增工厂 rule 必须登记索引并证明不属于公共规则。

### 4. 工厂规则分配

- 始终生效的工厂身份、产品/自身/元文档分层、传播四问写入 `AGENTS.md §1.1`。
- 仅在产品资产路径触发的 manifest、ownership、迁移事务、发布完整性和工厂专属证据要求写入 `bridgeforgecodex-product-change.md`。
- Overlay 禁止重复 Template 已有规则；已有重复必须删除或上移 Template，不能保留近义摘要。
- 删除旧章节前必须建立逐条映射；没有唯一承载位置的规则禁止删除。

### 5. 一致性与硬闸

- 文本一致性按 UTF-8、无 BOM、LF 归一化后比较，避免 Windows 行尾造成假漂移。
- 编辑后发现单边变化立即报告具体文件/区块；允许当前修改继续完成，但禁止自动覆盖。
- 在重新一致前，pre-commit、自动测试和发布检查必须 exit 2。
- AGENTS 项目定制区变化必须放行，不得误报。
- 精确文本差异由机器检查；是否存在近义重复或规则弱化由独立审计复核。

### 6. 工厂身份

- BridgeForgeCodex 是 Template 工厂和 dogfood 样板，不是普通下游。
- 工厂合规由 factory dogfood 硬闸证明，不执行下游 adopt，不写下游版本戳。

## 规则迁移映射

| 当前内容 | 唯一新承载位置 |
|---|---|
| 专业表达、证据、Memory、文档、Skills、Debug | Template 公共 AGENTS 区块 |
| 工厂双重身份、分层地图、传播四问 | 根 `AGENTS.md §1.1` |
| CHANGELOG 标签、manifest、ownership、发布完整性 | 工厂 product rule |
| `$git-sync`、Skill 调度、自改审计 | Template 公共区；删除工厂重复表述 |
| 上下游传播 playbook | 根 `AGENTS.md §1.1` 架构指针 |
| `[find-doc]` | hook 自带动作；AGENTS 不重复 |
| 8 个通用 rule | Template 到 `.codex/rules/` 原样镜像 |

## 拟修改

- 按 Template 结构重组根 `AGENTS.md`，填写三个项目定制区。
- 将 8 个 Template rule 原样同步到 `.codex/rules/`。
- 对现有根 AGENTS 与工厂 product rule 做逐条差集迁移，删除公共规则重复正文。
- 扩展现有 factory dogfood 检查，验证 AGENTS 公共区块、rule 镜像、项目区豁免和工厂 rule 索引。
- 更新 managed contract、dogfood 镜像、manifest、CHANGELOG 与相关测试。

## 验收

1. AGENTS 公共区块对账通过；只有确认的项目区和索引扩展不同。
2. 8 个 Template rule 与 `.codex/rules/` 镜像全部一致。
3. 三个项目区包含 BridgeForgeCodex 真实内容，不保留空占位。
4. 当前工厂规则全部有唯一承载位置，无丢失、无重复、无弱化。
5. 故意修改单边公共区或 common rule 时，编辑后信号、pre-commit 和测试能稳定拦截。
6. 修改项目定制区时不误报。
7. BridgeForgeCodex 自身不出现下游版本戳，不调用 project sync apply。
8. manifest、metadata、project structure、mirror、完整 fixture 与完整自动测试通过。
9. 独立审计确认规则差集与自动化 allowlist 完整。

## 合理假设与风险

- 根 AGENTS 会发生大段重排，但旧规则只在完成逐条映射后删除。
- `architecture.md` 在工厂侧保持 Template 文本；真实工厂架构由项目定制区和 Overlay 承载。
- 机器可以可靠判断文本差异，但不能完全判断近义重复，因此仍需独立审计。
- 本轮继续归入尚未发布的 BridgeForgeCodex `1.0.0`；不单独 bump 新版本。

## 自动化边界

- 只检查并阻断，不自动复制或覆盖文件。
- factory 检查在普通下游无 Template 源时必须自门控 no-op。
- `--check`、planner 和审计必须只读。
- 任何迁移失败都必须保留原规则内容并停止，不得用 Template 整文件覆盖未知内容。

## 实施记录

- 根 `AGENTS.md` 已按 `templates/AGENTS.md` 公共结构重组，仅填写 §1.1、§3、§4.2，并追加一行工厂 rule 索引。
- 8 个 Template common rule 已精确镜像到 `.codex/rules/`；`bridgeforgecodex-product-change.md` 只保留工厂 ownership、事务与发布约束。
- `mirror_drift_check.py` 已扩展 AGENTS 公共区、8 个 rule 与 Overlay/index 对账；PostToolUse 编辑后只报告，pre-commit/default exit 2。
- `hook_dispatcher.py` 已接入编辑后信号；Template 与 `.codex` 镜像、managed contract 和两份 manifest 已重建。
- 已增加允许项目区变化、拒绝公共区/rule 漂移、要求 Overlay/index、普通下游 no-op 的自动测试。

## 验证记录

- 第 1 轮定向验证暴露旧 dispatcher 临时 fixture 未创建新增 hook；仅补齐 fixture 后进入最终轮。
- 第 2 轮：`unittest discover` 214/214 通过；`run_downstream_fixture.py` 通过 19/19 个 `0.86.0+` 已发布迁移基线。
- manifest `--check`、skill metadata、project structure、mirror drift、rule index、`git diff --check` 全部 exit 0。
- 根与 `.codex` 均不存在 `.bridgeforge_codex_version`；未执行 project sync apply。
- 首次独立审计发现 3 个 High：§2.1 索引行位置绕过、旧专业表达红线弱化、Overlay 根级路径漏配；经用户追加一次修补预算后全部关闭。
- 追加定向复测 33/33；manifest、mirror、metadata、structure、rule-index、diff-check 全部 exit 0。
- 最终独立复核：0 blocker / 0 high，可验收；完整 214/214 与 fixture 19/19 复用第 2 轮主验证收据，未无意义重复。
