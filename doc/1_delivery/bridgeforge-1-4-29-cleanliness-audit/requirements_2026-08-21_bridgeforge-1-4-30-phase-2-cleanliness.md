---
status: implemented-awaiting-user-acceptance
next: user-acceptance
scale: L
budget: 180_minutes_60k_tokens_unmeasured_3_subagents_2_validation_rounds
source: develop-confirm-user-approved-2026-08-21
predecessor: requirements_2026-08-20_bridgeforge-1-4-30-core-safety-remediation.md
---

# BridgeForge 1.4.30 第二期洁净清理需求

## 原始需求摘要

用户要求在 1.4.30 第一阶段核心安全修复完成后启动第二期，清理普通 Medium/Low、死代码、
重复实现、无效下游资产、重复测试和活跃文档债，并重新判断产品是否整体达到洁净要求。

调用来源：L 级 `$develop` 因第一期需求卡明确要求第二期另开，转入 `$confirm` 逐项确认。

## 背景与已核实事实

- Git `HEAD` 仍为 1.4.29，工作区中的 1.4.30 尚未提交或发布；第二期继续归入同一 1.4.30。
- 第一阶段完整 factory 测试 236/236、downstream fixture 3/3，独立审计为 Blocker 0、High 0、必要 Medium 0。
- 第一阶段工作区统计约为新增 2868 行、删除 608 行；安全架构达标，但尚不能据此声明整体代码洁净。
- 原始洁净审计仍记录普通 Medium、Low、约 479 行下游恒 no-op/无调用资产、重复测试和活跃文档债。
- 平台无可靠 token 计量器，token 预算标记为未实测。

## 目标

- 在不削弱第一期六项安全架构的前提下，完成 1.4.30 第二期结构洁净清理。
- 让每个保留模块都具备当前调用方或独立安全职责证据。
- 删除历史兼容、重复实现、无效下沉资产和未发布接口别名。
- 在保持现行安全边界回归覆盖的前提下合并重复测试。
- 将活跃说明同步为 1.4.30 当前事实，并重新给出整体洁净结论。
- 产品源码相对第二期开工基线实现净减量，不设置机械绝对行数上限。

## 非目标

- 不恢复历史版本 hash、adapter、retirement、migration 表或其他谱系状态。
- 不为追求行数重写或削弱已经验证通过的六项核心安全架构。
- 不修改、压缩或删除第一期审计、debate 和验收记录。
- 不写入 StratusAgent、其独立 worktree、causis_risk_suite 或 ClaudeBridgeAssist。
- 不执行 `git add`、commit 或 push。
- 不把未执行的真实下游 runtime 验证包装为通过。

## 任务规模与预算

- 规模：L。涉及同步器、current baseline、发布与事务脚本、Template/dogfood、受管合同、测试和活跃文档，且包含受管资产删除与等价性验收。
- 时间上限：180 分钟。
- Token 上限：60k，未实测；以 agent 数、验证轮次和范围增长做代理闸。
- 子 Agent：最多 3 个，分别用于只读盘点、实现和独立审计。
- 验证：最多 2 轮。
- 超过任一预算立即停止，不静默缩减验收或把部分完成报告为整体洁净。

## 已确认规则

1. 洁净按“存在理由”验收：每段保留产品代码必须有当前调用方或独立安全职责；同时要求产品源码净减量。
2. 工厂专用脚本只在工厂保留唯一实现，不再作为公共资产下沉；临时下游升级必须证明旧受管冗余副本被删除。
3. 删除旧 `whitelist` 命名、CLI 参数和输出别名，只保留 `PreservationManifest` 单一术语；1.4.30 尚未发布，不维护未发布接口兼容层。
4. 重复测试按行为覆盖合并；允许减少用例和行数，但每个安全边界必须保留回归证据。
5. README、INSTALL 和活跃架构文档更新为 1.4.30 当前事实；历史交付证据原样保留。
6. 四个真实下游只读核对项目资产形态；升级、删除和 runtime 验收只在临时副本或 fixture 中执行。
7. 项目 Memory、Skills、rules、`.codex/hooks/project_XXXX/` bundles 和 AGENTS 项目区必须保留，不得作为冗余删除。

## 已知清理范围

- 从下游合同、Template 和 dogfood 中移除 `mirror_drift_check.py`、`hooks_ownership.py` 等没有下游调用方的工厂专用资产；工厂调用收敛到唯一实现。
- 将 duplicate JSON key 在 current baseline、release evaluator 和 git-sync 中统一为稳定领域异常。
- 补齐项目 Skill 孤儿目录、缺失 `SKILL.md` 和不完整 skill tree 的 fail-closed 检查。
- 统一 Windows `/` 与 `\\` target 规范化和 ownership 唯一性。
- 删除 `project_asset_whitelist`、`--confirmed-whitelist`、`confirmed_whitelist` 等过渡接口和内部命名。
- 合并重复故障注入、镜像重复和被更强 schema 检查覆盖的弱测试。
- 清算仍描述 1.4.28、退役链、旧 `.claude` 和已删除 rule hooks 的活跃文档。
- 继续盘点无调用文件、重复 parser/validator、无效镜像和不可删除的独立安全职责；新增发现必须按同一证据口径处理。

## 拟修改范围

- `scripts/bridgeforge_codex_project_sync.py` 及其 Skill/fixture/测试调用面。
- `templates/scripts/current_baseline.py`、`version_release.py`、`codex_git_sync.py` 与必要 dogfood 镜像。
- `templates/managed-skeleton.json`、Template hooks/scripts 和工厂专属脚本位置。
- `scripts/rebuild_shared_skill_manifest.py`、共享 manifest 验证和相关测试。
- `scripts/tests/**` 中重复或缺口测试。
- `README.md`、`INSTALL.md`、活跃架构/参考文档、`CHANGELOG.md` 和受影响索引。

## 数据与自动化边界

- 不涉及外部数据库、交易数据、账户、网络服务或用户级配置写入。
- 四个真实下游只允许只读文件数量、项目资产形态和调用入口核对。
- 所有破坏性升级、资产删除和 runtime 试验必须使用临时目录或临时 Git 仓库。
- 所有脚本与测试使用项目 `.venv`；禁止 PATH Python 或手工改版本戳制造通过结果。
- 不自动暂存、提交或推送任何改动。

## 验收标准

- 原始审计记录的普通 Medium/Low 和活跃文档债全部关闭，或为每项保留内容给出不可删除证据。
- 下游受管资产数量下降；临时旧/current 项目升级能删除工厂专用冗余文件，同时保留项目资产。
- 产品源码相对第二期开工基线净减量，且无新增永久迁移合同、兼容表或历史状态。
- 仓库中不再出现旧 `whitelist` 接口与运行时命名；fail-closed 的历史字段拒绝测试可保留。
- 每个保留产品文件都有当前调用方、受管入口或独立安全职责证据。
- 完整 factory unittest、downstream fixture、临时旧项目重装/current update、stamp-last/no-op replan、git-sync 回滚和只读 pre-commit 全部通过。
- factory dogfood、shared manifest、skill metadata、project structure、mirror/current baseline、Memory、config health 和 `git diff --check` 硬闸通过。
- 独立审计在第二期范围内为 Blocker 0、High 0、Medium 0；真实下游 runtime 未执行项明确标为未验证。

## 合理假设与风险

- 删除下游受管文件必须依赖 current contract ownership 和临时升级证据；不能按文件名猜测项目自有资产。
- 测试合并以行为矩阵为单位；若无法证明强测试覆盖弱测试，保留原测试。
- 工厂专用与下游公共职责若无法通过调用链闭合，默认阻断删除并交独立审计复核。
- 第二期叠加在第一期未提交工作区上；交付必须区分第一期安全增量、第二期净减量和整体终态。
- 若只读下游发现未确认的资产形态会改变删除规则，必须暂停并单题确认范围变化。

## 实施计划

1. 建立第二期开工基线，独立盘点当前调用图、下游合同资产、重复验证器、测试覆盖和活跃文档债，形成逐项保留/删除证据。
2. 按单一事实源与可删除性实施代码、合同、Template/dogfood、测试和文档清理，并同步 1.4.30 发布面。
3. 执行最多两轮完整验收，由独立 review Agent 读取真实 diff，核对功能等价、遗漏债务、净减量和发布洁净度。

## 实施记录

- 状态：实现、两轮验证与独立审计全部完成，等待用户验收。
- Agent 使用：3/3（light-explorer 盘点、implementation-worker 实现、review-auditor 独立复核）。
- 第二期开工基线：唯一产品源码 48 个文件、14,785 行；dogfood runtime 44 个文件、9,050 行；测试 24 个文件、6,782 行；managed assets 55 个，下沉 Python hook/script 资产 42 个。
- Discovery 结论：确认 4 个可删除下沉资产、1 个工厂模块搬迁、3 个普通 Medium、测试/文档债和未发布 whitelist 接口；保留 current baseline、instruction source、旧戳身份分界与历史字段拒绝闸。
- 传播缺口：current-only update 尚不会删除相邻旧合同中已移除的 whole asset；实现必须先补“旧合同有/新合同无且 baseline 未漂移”的事务删除，merge/region/seed 或身份不清一律阻断。
- 真实下游只读收据：四个 checkout 均为 `<1.4.28` 且仍有非 canonical 项目 hooks；只证明资产形态，不作为 1.4.30 可升级证明，本期不写入。
- 已移除 4 个下游无调用资产：`mirror_drift_check.py`、`find_doc_reminder.py`、`context_cost_report.py`、`hooks_ownership.py`；其中 ownership 校验仅在工厂保留 `scripts/hooks_ownership.py` 唯一实现。
- 已删除旧 whitelist 接口，统一为临时 `PreservationManifest`；相邻 current 合同支持对未漂移 whole 资产执行事务删除，partial ownership 与损坏合同零写阻断。
- 已收紧 Skill 完整树、duplicate JSON、Windows target canonicalization，并补齐 git-sync add/render/push 故障注入。
- 已删除三份退役 Claude/harness 活跃设计，并把 `design-rationale.md` 重写为 current-only 设计。
- 终态规模：唯一产品源码 45 个文件、14,451 行，相对开工净减 3 个文件、334 行；managed assets 51 个，下沉 Python 资产 38 个。
- 范围或预算变化：无。

## 验证记录

- 验证轮次：2/2，预算用满且均通过。
- 自动测试：终态完整 factory unittest 242/242；第一轮终态重点回归 61/61；project-sync/root Skill 39/39；git-sync transaction 7/7，均通过。
- 临时下游：fixture 3/3，通过 current init/no-op、旧项目确认式重装、current 漂移零写；相邻合同安全删除及 rollback 由 project-sync 回归覆盖。
- 发布硬闸：manifest `--check`、current baseline 1.4.30、instruction source、config health strict、project structure、skill metadata、Memory `--check`、pre-commit、`git diff --check` 均通过；结构检查仅输出既存归档 advisory。
- 独立审计：Blocker 0、High 0、Medium 0、Low 0；另有 26 项定向反例通过，Template/dogfood Python 镜像 38 对、missing 0、mismatch 0。
- 未验证：真实四下游 apply/runtime smoke，本期明确不授权写入，不能宣称真实升级通过。

## 后续交接

- 目标 Skill：`$develop`。
- 开工前只需确认是否按本卡开始开发，不重复业务访谈。
