---
status: accepted
requirements: ../requirements_2026-08-20_bridgeforge-1-4-29-cleanliness-audit.md
audit: ../collabs_2026-08-20_bridgeforge-1-4-29-cleanliness-audit.md
head: 6b878df6a813bceddb3ad85b2bf0f09fdeee1422
---

# 1.4.29 洁净缺口修复架构 Debate

## 目标

在不恢复历史兼容链的前提下，为四个存在真实方案分歧的问题收敛长期低复杂度、fail-closed、可验证的实现方案：

1. 旧项目 rules/hooks/AGENTS/memory/Skills 的发现、逐项确认和依赖闭包。
2. git-sync 对工作树、index、自动版本文件和衍生产物的事务回滚模型。
3. 共用受管文件中公共区与项目区的业务/骨架语义分类。
4. factory 身份的单一事实源与下游缺戳阻断。

## 边界

- 只讨论并形成方案，不修改产品代码。
- 不恢复 historical/schema-v1/adaptation/retirement 机制。
- 不读取或写入四个真实下游。
- 方案必须同时满足活动部件少、单一事实源、项目资产不丢、Planner 零写、失败全恢复。
- 用户确认收敛方案前不得实施。

## 证据入口

- 确认卡：`../requirements_2026-08-20_bridgeforge-1-4-29-cleanliness-audit.md`
- 完整审计：`../collabs_2026-08-20_bridgeforge-1-4-29-cleanliness-audit.md`
- 核心实现：`scripts/bridgeforge_codex_project_sync.py`、`templates/scripts/codex_git_sync.py`、`templates/scripts/version_release.py`、`templates/scripts/current_baseline.py`
- 审计结论：2 个 Blocker、9 个 High；本 debate 只覆盖其中存在方案分歧的四个主题。

## 角色

- A：`/root/audit_rebuild_transaction`，implementation-worker；主张最小显式合同和低活动部件方案。
- B：`/root/audit_final_review`，review-auditor；对抗审查数据损失、错误放行、事务和隐性复杂度。

## 第一轮

- 状态：完成。
- A 主张：用 `PreservationManifest`、`SyncWritePlan`、`OwnershipProjection` 三个显式合同替代正则/路径启发；factory 新增稳定 `.bridgeforge-factory.json` marker 作为身份 SSOT。
- B 挑战：同意显式 inventory/write plan/projection，但反对新 marker 和任意 shell 依赖解析；主张 canonical 项目命名空间、声明式自动写集 + 完整 index、四件现有 factory 资产的 tri-state 身份。
- 第一轮共识：未知结构必须阻断；禁止扩展 shell 正则；版本分类复用 current baseline ownership projection；git-sync 必须在写前知道自动写集并恢复完整 index。
- 第一轮分歧：factory 新 marker vs 既有四件套；一次性 hook bundle 映射 vs canonical namespace；pre-commit 是否必须完全只读。

## 第二轮

- 状态：完成，但存在并行修订分歧。
- A 修订：撤回 factory 新 marker，采用现有 manifest 主张 + 三件完整性证明的 tri-state；canonical Python self-contained hook bundle；pre-commit 派生写可预声明纳入事务；split index 本版阻断。
- B 修订：转而有条件接受 versionless factory marker；旧项目临时 PreservationManifest + 长期 canonical namespace；pre-commit 必须彻底只读；split index 记录 shared index hash 后支持。
- 第二轮共识：PreservationManifest 只作一次性事务输入/receipt、不累积版本历史；OwnershipProjection 为唯一分类器；SyncWritePlan 覆盖完整 index 和自动写目标；未知 marker/闭包/身份 fail-closed。
- 第二轮分歧：factory 身份载体、pre-commit 派生写策略、split index 支持边界、项目 hook 是否强制 Python self-contained。

## 第三轮

- 状态：完成；三项收敛，一项交用户裁决。
- 共识一：项目 hook 统一为 canonical Python filesystem-self-contained bundle；旧项目用临时、hash 绑定的 PreservationManifest 一次性规范化，不积累历史迁移知识。
- 共识二：pre-commit 彻底只读；memory、contract、manifest 等派生输出在写前纯 render，并统一进入 git-sync 的 SyncWritePlan。
- 共识三：linked worktree 支持；split index 本版本在任何写入前 fail-closed，不建立跨 worktree shared-index 回滚子系统。
- 分歧：A 选择新增 versionless `.bridgeforge-factory.json` 作为显式身份 SSOT；B 选择复用 strict `bridgeforge-codex-manifest.json` 作为身份主张，现有三件 factory 资产只作完整性证明。

## 收敛

- 状态：用户已逐项确认最终实施架构；原七项说明合并为六项正式决策，无悬空架构选择。

### 已收敛核心合同

1. `PreservationManifest`：一次性全 inventory、每项显式 disposition、canonical hook bundle 原子保留、memory/Skills required-preserve。
2. `OwnershipProjection`：current baseline 唯一实现 public/project 投影，Planner/release/pre-commit/git-sync 共用。
3. `SyncWritePlan`：写前包含全部自动输出，完整普通/linked index 快照，HEAD/index/target CAS 回滚，pre-commit 只读。
4. `RepositoryRole`：factory/downstream/ambiguous 三态；严格化后的现有 manifest 是唯一身份主张，三件 factory 资产只作完整性证明。

### Factory 身份分歧证据

- 现有 manifest 路线：零新增文件，复用 H9 同轮必须严格化的 active factory-only manifest；缺失但存在任一 factory 支撑资产时仍判 ambiguous。
- 新 marker 路线：职责最单一、内容永不随版本/hash变化，可删除其他身份 heuristic；但新增一个永久文件，且 marker 缺失保护仍需查看现有 factory 支撑资产。

## 用户裁决

- Factory 身份：选择现有 manifest 路线。
- `bridgeforge-codex-manifest.json` 是唯一身份主张；必须补 strict schema、duplicate-key、固定 role/platform 和规范化 target 检查。
- `templates/managed-skeleton.json`、`skills/bridgeforge-codex/SKILL.md`、`scripts/bridgeforge_codex_project_sync.py` 只作完整性证明。
- manifest 不存在且三件证明均不存在为 downstream；manifest 合法且三件证明齐全为 factory；其他组合为 ambiguous 并零写阻断。
- 删除 current baseline、version release 和其他入口各自维护的 factory heuristic。
- `PreservationManifest` 只存在于内存或事务临时目录；Apply 重算 fingerprint、完成回灌与验证后必须先清理该清单，清理失败不得写最终版本戳。
- 项目 Hook 使用浅层 `.codex/hooks/project_XXXX/` 目录；一个目录是一个 Python self-contained bundle，整体保留或整体删除。
- `OwnershipProjection` 必须统一判断同一文件内的 public/project/mixed 变化，无法解析时零写阻断。
- `SyncWritePlan` 必须在首次写入前覆盖全部自动输出、HEAD、完整 index 与目标快照，并负责提交前失败回滚。
- pre-commit 彻底只读；生成与暂存只能由 git-sync 的写事务执行。
- split index 不再作为独立能力；只并入 `SyncWritePlan` 前置条件，检测到时零写阻断，不建设兼容、恢复或转换机制。

## 最终实施大纲

1. 严格化现有 shared manifest，并落唯一 `RepositoryRole(factory|downstream|ambiguous)` 检测器。
2. 建立用后即清理的临时 `PreservationManifest`：旧项目全 inventory、每项显式 preserve/delete、memory/Skills required-preserve、未知 marker 阻断；清理完成后才允许 stamp-last。
3. 项目 Hook 统一为 `.codex/hooks/project_XXXX/` 浅层 canonical Python self-contained bundle；删除 shell/path 依赖正则和默认删除语义。
4. `current_baseline.py` 提供唯一 `OwnershipProjection`；hooks identity 绑定 event/matcher/id/hash；release 删除路径级 skeleton 分类。
5. memory、contract、manifest 改为写前 pure render，聚合进唯一 `SyncWritePlan`；git-sync 快照普通/linked worktree 的完整 index 与所有自动目标，按 HEAD/index/target CAS 回滚；split index 只作写前阻断条件。
6. pre-commit 全面只读，删除 memory 写盘、`git add` 和吞异常路径。

实施仍须完成冗余资产清理、1.4.29 测试硬编码修复、活跃文档同步，并依次执行 focused 故障矩阵、完整 factory、临时旧项目重装/current update/direct commit/git-sync 回滚验收；不触碰真实下游。
