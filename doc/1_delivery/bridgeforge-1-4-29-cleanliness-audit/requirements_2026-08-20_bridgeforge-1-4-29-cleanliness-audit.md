---
status: audited
next: implementation-card-confirmed-awaiting-develop-start
scale: L
budget: 180_minutes_60k_tokens_unmeasured_5_agents_3_validation_rounds
source: user-confirmed-2026-08-20
---

# BridgeForgeCodex 1.4.29 完整洁净审计需求

## 原始需求摘要

用户要求判断 BridgeForge 1.4.29 是否真正达到洁净要求，先执行一次完整审计并展示问题清单，
再由用户根据具体问题决定 debate 范围。

调用来源：用户直接调用 `$confirm`。

## 目标

- 审计 1.4.29 是否同时达到结构洁净与行为洁净。
- 核对历史兼容代码、合同数据和派生机制是否已从运行时删除。
- 核对旧项目重装、1.4.28+ 更新、事务回滚和四入口检查是否满足确认契约。
- 输出带文件、行号、行为、影响、复现证据和修复方向的问题清单。
- 按 Blocker、High、Medium、Low 排序，并给出达标、有条件达标或未达标结论。
- 问题清单交付后，再由用户单独确认 debate 范围。

## 不做

- 本审计阶段不修改代码或文档。
- 不执行 Git commit 或 push。
- 不读取、更新或验证四个真实下游项目。
- 不在问题清单完成前预设 debate 范围。
- 不在本卡内直接实施问题修复。

## 规模与预算

- 规模：L。依据是审计跨越同步器、schema 合同、hooks、事务、发布、测试与活跃文档，且涉及破坏性重装和零写安全规则。
- 时间上限：3 小时。
- Token 上限：60k 新增 token，平台无可靠计量器，标记为未实测。
- Agent 上限：5 个，完整审计与后续 debate 共用。
- 验证上限：最多 3 轮。
- 超过时间、token、agent、验证轮次或真实下游边界时立即停止，由用户选择扩大预算或缩小范围。

## 已核实事实

- 当前 HEAD 为 `6b878df6a813bceddb3ad85b2bf0f09fdeee1422`，产品版本为 1.4.29。
- Git 工作区干净，`main` 与 `origin/main` 同步。
- schema 3 合同为 692 行、55 个资产；旧合同基线为 7163 行，减少约 90.3%。
- `project_sync.py` 为 1924 行，`version_release.py` 为 466 行，合计 2390 行；旧基线为 9216 行，减少约 74.1%。
- 运行时精确检索只命中 current checker 对历史字段和 retirement 策略的拒绝逻辑，没有命中历史兼容实现。
- 1.4.29 当前完整 factory 测试共 212 项，结果为 `2 failures + 1 error`；失败测试仍硬编码 1.4.28。
- 已发现候选阻断：旧项目 Planner 执行项目自带旧 memory lint、obsolete stamp 大于等于 1.4.28 仍可能误入破坏性重建、git-sync 失败回滚未覆盖衍生合同与暂存区。
- 1.4.28 需求卡和部分历史 Bug 文档存在陈旧状态或关闭条件冲突。

## 未核实事实

- 候选阻断的全部触发条件、写入范围与最小复现尚未完成独立闭合。
- 当前所有 project-only 白名单组合是否均保持依赖闭包尚未重新审计。
- Planner、Apply、pre-commit 与 `$git-sync` 的失败语义是否在全部异常路径一致尚未重新审计。
- 活跃 Bug 文档中哪些属于仍有效的产品债、哪些已被 current-only 架构废止尚未完成清算。
- 临时下游 CLI 和 hook runtime 在 1.4.29 的最新结果尚未重新执行。

## 审计范围

- `scripts/bridgeforge_codex_project_sync.py` 的身份分流、白名单、事务、validators 与 stamp-last。
- `templates/scripts/current_baseline.py`、`version_release.py`、`codex_git_sync.py` 及 dogfood 镜像。
- schema 3 `managed-skeleton.json`、manifest builder 和稳定增长约束。
- AGENTS、rules、hooks、pre-commit extension、memory 与项目 Skills 的 ownership/兼容性边界。
- Planner、Apply、pre-commit、`$git-sync` 的 current-baseline 一致性与零写语义。
- Template/dogfood/manifest 镜像、完整自动测试和临时下游 CLI/fixture。
- README、INSTALL、架构、需求卡、活跃 Bug 与发布记录的一致性。
- 代码行数、活动部件、重复逻辑、派生数据成本、单一事实源和可删除性。

## 已确认规则

- “达到洁净要求”必须同时满足结构与行为；仅达到压缩比例不能判定通过。
- 历史兼容实现与历史合同数据必须清除，允许保留 fail-closed 的历史字段拒绝逻辑。
- 旧项目只能在合法 `<1.4.28` 身份下进入白名单破坏性重装。
- 1.4.28+ 必须使用 current-only 基线，公共漂移和损坏基线零写阻断。
- 任一可捕获失败不得留下半新半旧工作区、衍生合同或错误暂存状态。
- memory、Skills、rules、hooks 和 AGENTS 项目资产按既定 ownership 保留并接受当前规则检查。
- 真实下游迁移债不纳入本次产品洁净验收。

## 问题清单格式

每项必须包含：

- 严重度与类别：确认缺陷、测试缺口、文档债或真实下游债。
- 精确文件与行号。
- 当前真实行为和触发条件。
- 用户可见影响、数据/事务风险和传播范围。
- 已执行的复现或静态证据。
- 推荐修复方向；存在真实方案分歧时标记为 debate 候选。

## 验收标准

- 完成全仓约束、实现、测试、临时 runtime 和活跃文档的独立审计。
- 完整测试与临时下游验证结果如实记录，失败不得包装为通过。
- 每个 Blocker/High 都有可复核证据，不以推断代替事实。
- 明确区分产品阻断、测试版本化缺口、文档陈旧和范围外真实下游债。
- 给出唯一洁净结论及主要依据。
- 审计结束时 Git 工作区保持干净。
- 用户查看清单后，才进入 debate 范围确认。

## 合理假设与风险

- 以 HEAD `6b878df` 和版本 1.4.29 作为本次审计对象；HEAD 变化时必须重新核对。
- 测试仅允许在仓库既有 `.venv` 与临时目录运行，不触碰真实下游。
- 当前已知失败可能包含测试硬编码，也可能掩盖产品缺陷，必须分别判定。
- 审计发现新架构变更或范围扩张时，必须按预算硬闸停止。

## 自动化边界

- 允许只读代码检索、Git 检查、完整测试、临时目录 fixture 和 CLI runtime。
- 禁止绕过 hook、手工吸收公共漂移或修改版本戳来制造通过结果。
- 禁止外部系统写入和真实下游项目写入。

## 后续交接

1. 使用独立 agent 完成分域审计和最终复核。
2. 主对话汇总完整问题清单与洁净结论。
3. 用户查看清单后，单题确认 debate 范围。
4. debate 只讨论用户选定的问题，不自动实施修复。

## 实施记录占位

- 审计状态：已完成；结论为整体未达到洁净要求。
- Agent 使用：5/5。1 个 light-explorer、3 个分域 implementation-worker、1 个 review-auditor。
- 范围或预算变化：无。

## 验证记录占位

- 静态与动态审计：完成；最终保留 2 个 Blocker、9 个 High 及 Medium/文档债。
- 完整 factory 测试：212 项，93.731 秒，`FAILED (failures=2, errors=1)`。
- 临时下游 fixture/CLI：3/3 passed，但覆盖不足，不能反证高严重度问题。
- shared manifest `--check`：当前实例通过，但非法 schema/重复键反例可漏检。
- 独立复核：完成；全部 Blocker/High 均有独立动态收据，无悬空高严重度项。
- Git 终态：HEAD 与 `origin/main` 仍为 0/0；仅保留本需求卡、协作记录和 `doc/README.md` 索引的授权 diff。
