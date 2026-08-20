---
status: audit-complete-awaiting-debate
requirements: requirements_2026-08-20_bridgeforge-1-4-29-cleanliness-audit.md
head: 6b878df6a813bceddb3ad85b2bf0f09fdeee1422
---

# BridgeForgeCodex 1.4.29 完整洁净审计协作记录

## 目标与边界

- 目标：只读审计 1.4.29 的结构与行为洁净度，输出分级问题清单和唯一结论。
- 范围：BridgeForge 工厂、Template/dogfood、发布与事务链、测试、临时下游和活跃文档。
- 禁止：修改产品代码、commit/push、读写四个真实下游、在问题清单前启动 debate。
- 运行时复现仅使用项目 `.venv` 和临时目录。
- 当前允许的既存治理文档 diff：本 topic 需求卡、本协作记录和 `doc/README.md` 索引；除此之外不得新增 diff。

## 预算

- 3 小时。
- 60k 新增 token，未实测。
- 最多 5 个 agent：1 个 light-explorer、3 个分域审计 agent、1 个 review-auditor。
- 最多 3 轮验证。

## 研读收据

- light-explorer 已完成确认卡匹配、模块边界、验证入口和已知问题候选研读。
- 研读确认三个执行域可并行，主要源码 ownership 不重叠。
- 审计对象固定为 HEAD `6b878df6a813bceddb3ad85b2bf0f09fdeee1422`。

## 并行组 1：分域审计

| ID | 责任域 | 独占主要文件 | 支撑输入/测试 | 依赖 |
|---|---|---|---|---|
| A | 旧项目识别、白名单重装与事务 | `scripts/bridgeforge_codex_project_sync.py`、`scripts/tests/test_current_baseline_project_sync.py`、`scripts/tests/run_downstream_fixture.py`、`templates/hooks/memory_lint.py`、`templates/hooks/skill_metadata_check.py` | Template AGENTS/hooks/pre-commit 仅作输入样本 | 将 current-baseline 内部视为黑盒 |
| B | current baseline、发布与 git-sync | `templates/scripts/current_baseline.py`、`templates/scripts/version_release.py`、`templates/scripts/codex_git_sync.py`、`templates/.githooks/pre-commit`、`scripts/tests/test_current_baseline_release.py` | dogfood 镜像及 runtime/version 测试 | 将 schema 合同与生成器视为输入 |
| C | schema 3、ownership、manifest 与 dogfood | `templates/managed-skeleton.json`、`scripts/rebuild_shared_skill_manifest.py`、`templates/scripts/hooks_ownership.py`、`templates/hooks/mirror_drift_check.py`、`scripts/tests/test_factory_template_dogfood.py` | dogfood contract、shared manifest、ownership/distribution 测试 | 不审计 project-sync 身份与事务 |

### A 接口与验收

- 独占审计 `init/adopt/update/rebuild` 身份路由、旧戳合法性和缺戳/双戳/非法戳零写。
- 独占审计 rules/hooks/AGENTS/memory/Skills 白名单、依赖闭包、Planner 零写、Apply rollback 与 stamp-last。
- 运行 `test_current_baseline_project_sync` 和 downstream fixture；只在临时目录补最小复现。

### B 接口与验收

- 独占审计 HEAD/index/worktree 三态、1.4.28+ 漂移阻断、release classification 和版本发布。
- 独占审计 git-sync 失败回滚、衍生合同/manifest 与暂存区恢复，以及四入口失败语义。
- 运行 current release/runtime/version 定向测试和 current baseline worktree/index 检查；hook 复现只在临时 Git 仓库。

### C 接口与验收

- 独占审计 schema 允许字段、稳定 asset id/target/source/strategy、历史数据清除和增长闸。
- 独占审计 hooks ownership、Template/dogfood/manifest 单一事实源和镜像。
- 运行 factory dogfood、hook ownership、shared distribution 测试和 manifest `--check`。

## 主对话串联域：活跃文档

- 主要文件：`README.md`、`INSTALL.md`、`doc/README.md`、`doc/0_architecture/design/codex-project-sync.md`、1.4.28 干净基线需求卡。
- 支撑扫描：`doc/2_bugs/*.md`、上下游 playbook、`CHANGELOG.md`。
- 只用 A/B/C 已证明的行为核对活跃说明和 Bug 状态，不自行提升缺陷严重度。

## 串行组 2：独立复核

- review-auditor 独立读取 HEAD、三个域的证据和主对话文档结论。
- 对每个 Blocker/High 在临时目录复现，拒绝只靠静态推断的高严重度问题。
- 检查问题去重、严重度、触发条件、写入范围与遗漏面。

## 统一问题接口

每项输出：严重度、类别、文件行号、触发条件、真实行为、影响、复现收据、修复方向、是否建议 debate。

## 计划验证

1. 三个审计域各自运行定向测试与临时复现。
2. 主对话运行一次完整 factory 测试、downstream fixture、manifest `--check` 和 `git diff --check`。
3. review-auditor 对 Blocker/High 做独立复核。

## 当前状态

- 拆分：用户已确认。
- 并行组 1：A/B/C 已完成；产品文件零修改。
- 文档串联：已完成；确认当前版本入口、1.4.28 需求卡、历史 Bug 关闭表和两份 active harness 设计存在陈旧冲突。
- 独立复核：已完成。
- 最终问题清单：已生成；等待用户确认 debate 范围。

## 并行组 1 阶段收据

- A：确认 Planner 执行下游旧 memory lint、未知 pre-commit/AGENTS 丢失、Windows hook 依赖断链、旧戳版本矩阵错误等问题；fixture 3/3 不能覆盖这些缺口。
- B：确认 git-sync 失败回滚不完整、共用路径内项目内容误判 skeleton-only、hook event/matcher 漂移漏检、普通项目伪 factory 身份等问题。
- C：确认 shared manifest 校验 fail-open、Windows target 规范化缺口，以及两个可从下游删除的 factory-only/dead runtime 资产。
- 三个域起止 Git 状态一致，仅有已授权审计治理文档 diff。

## 主对话完整验证收据

- 完整 factory：212 项，93.731 秒，`FAILED (failures=2, errors=1)`；三处均为测试硬编码 1.4.28 与当前 1.4.29 冲突。
- downstream fixture：3/3 passed，但场景覆盖不足，不能反证 A 域 Blocker/High。
- shared manifest `--check`：当前真实 manifest unchanged；C 域已证明 mutation 形态可 fail-open。
- `git diff --check`：通过。

## 最终独立复核问题清单

### Blocker

| ID | 类别 | 位置 | 已确认行为 |
|---|---|---|---|
| B1 | 确认缺陷 | `scripts/bridgeforge_codex_project_sync.py:1093-1116,1188-1228` | Planner 在双戳 blocker 下仍执行下游旧 `memory_lint.py --organize` 并实际写盘，零写收据失真。 |
| B2 | 发布阻断 | `scripts/tests/test_current_baseline_project_sync.py:35-39,98-108`；`scripts/tests/test_current_baseline_release.py:260-271` | HEAD 1.4.29 全量 212 项测试为 2 failures + 1 error，测试仍硬编码 1.4.28。 |

### High

| ID | 类别 | 位置 | 已确认行为 |
|---|---|---|---|
| H1 | 确认缺陷 | `project_sync.py:1035-1046,1247-1267` | 未知 pre-commit marker 不产生候选，随后 safe replace 丢失业务 hook。 |
| H2 | 确认缺陷 | `project_sync.py:993-1015,1247-1267,1299-1305` | 未知 AGENTS marker 虽标记 `affects_readiness`，仍显示 ready 并覆盖项目区。 |
| H3 | 确认缺陷 | `project_sync.py:1188-1219` | obsolete stamp 值为 1.4.29 时仍进入破坏性重建。 |
| H4 | 确认缺陷 | `project_sync.py:29-31,1022-1089,1641-1665` | Windows 反斜杠 hook 命令无法形成依赖闭包，可保留注册却删除实际脚本。 |
| H5 | 确认缺陷 | `.codex/scripts/codex_git_sync.py:87-134,287-312` | commit 失败不恢复衍生 manifest/合同和完整 index，留下半更新与错误 staged 状态。 |
| H6 | 确认缺陷 | `templates/scripts/version_release.py:180-194,398-410` | AGENTS 项目区等共用路径内的业务修改被误判 `skeleton-only`，业务版本不 bump。 |
| H7 | 确认缺陷 | `templates/scripts/current_baseline.py:261-333` | managed handler 移到错误 event/matcher 后仍通过 current baseline。 |
| H8 | 确认缺陷 | `templates/scripts/current_baseline.py:514-545` | 下游可凭单一 `templates/managed-skeleton.json` 与根 VERSION 伪装 factory，绕过缺戳阻断。 |
| H9 | 确认缺陷 | `scripts/rebuild_shared_skill_manifest.py:304-356` | shared Skill manifest 的 `--check` 放行 duplicate key、非法 schema 和历史字段。 |

### Medium / 文档债

- duplicate JSON key 在 current baseline、release evaluator 和 git-sync 中没有统一为稳定领域异常。
- 项目 Skill 孤儿目录缺 `SKILL.md` 时完全漏检。
- Windows target 唯一性未统一 `/` 与 `\\`，同一物理路径可登记两次 ownership。
- 232 行 factory-only `mirror_drift_check.py` 被下沉后恒 no-op；247 行 `hooks_ownership.py` 也随下游安装但无下游 caller。
- git-sync 缺少 add/manifest/commit 失败注入测试；fixture 未覆盖双戳副作用、未知 marker、Windows hook 依赖、错误 event、伪 factory 和失败回滚。
- README/INSTALL/同步架构仍写当前 1.4.28；1.4.28 需求卡状态自相矛盾；两份活跃 Bug 关闭表仍引用已退役链或与顶部状态冲突。
- `harness-engineering-design.md` 与 `harness-impl-plan.md` 仍把 `.claude` 和已删除 rule hooks 描述为可直接实施方案，后者还保留对话式生成残文。

## 剔除与合并

- “canonical AGENTS 候选无 action”未保留为独立问题；标准 marker 路径会生成 preserve action，未知 marker 问题已由 H2 覆盖。
- shared manifest 严格性问题不扩张到 schema 3 managed contract；当前 managed contract 的 exact schema 检查有效。
- 未发现上述清单之外的新 Blocker/High。

## 洁净结论

- 结构洁净：有条件达标但未完全达标。数量闸和历史谱系删除达标，仍有约 479 行下游恒 no-op/无调用资产及 ownership 重复逻辑。
- 行为洁净：未达标。重建可能事务外写盘、丢项目资产、错误路由或生成断链注册，current baseline 仍可错误放行。
- 发布洁净：未达标。全量测试失败、shared manifest 硬闸不完整、活跃文档与 1.4.29 不一致。
- 整体：未达到用户确认的“结构与行为同时达标”口径。

## 独立复核与终态

- review-auditor 独立动态闭合全部 2 个 Blocker和 9 个 High。
- 全量 unittest：212 项，2 failures + 1 error。
- downstream fixture：3/3 passed，但覆盖不足。
- current baseline：真实 1.4.29 worktree/index 通过，但 H7/H8 反例仍可漏检。
- manifest：当前实例 `--check` 通过，但 H9 mutation 反例仍可漏检。
- HEAD 保持 `6b878df6a813bceddb3ad85b2bf0f09fdeee1422`，与 `origin/main` 为 0/0。
- 除本次授权的需求卡、协作记录和 `doc/README.md` 索引外，无新增 Git 变化；未触碰真实下游。
