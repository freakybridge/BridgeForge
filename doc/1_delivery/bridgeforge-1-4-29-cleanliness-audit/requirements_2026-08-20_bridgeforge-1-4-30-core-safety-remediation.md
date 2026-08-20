---
status: completed
next: phase-2-cleanliness-requirement
scale: L
budget: 180_minutes_60k_tokens_unmeasured_3_subagents_2_validation_rounds
source: develop-confirm-user-approved-2026-08-20
audit: collabs_2026-08-20_bridgeforge-1-4-29-cleanliness-audit.md
debate: debates/2026-08-20_cleanliness-remediation-architecture.md
---

# BridgeForge 1.4.30 核心安全修复需求

## 原始需求摘要

用户授权实施 1.4.29 洁净审计与 debate 已确认方案，但选择拆成两期。本期只关闭审计确认的
2 个 Blocker、9 个 High 及其依赖的六项架构；普通 Medium、Low、广泛死代码和非核心文档债另开需求。

调用来源：L 级 `$develop` 因缺少匹配实施卡转入 `$confirm`，用户逐项确认预算、版本和范围。

## 背景与已核实事实

- 当前产品版本为 1.4.29，本轮产品行为变更必须发布为 1.4.30。
- 1.4.29 完整 factory 测试为 212 项，结果 `2 failures + 1 error`。
- 独立审计保留 2 个 Blocker、9 个 High，均有静态或动态收据。
- 用户已逐项接受 debate 的六项最终架构，并把 split index 从独立能力合并为事务前置条件。
- 四个真实下游只用于只读规模判断；本期不得写入它们。
- 平台无可靠 token 计量器，token 预算标记为未实测。

## 目标

- 发布 BridgeForge Codex 1.4.30 第一阶段安全修复。
- 关闭审计确认的全部 2 个 Blocker、9 个 High。
- 落地这些问题所依赖的六项架构决策。
- 恢复完整 factory 测试、临时下游和 Git 事务验收。
- 第一阶段只声明“核心安全问题已关闭”，不宣称全部洁净债务清零。

## 非目标

- 不处理普通 Medium、Low、广泛死代码和非核心文档债。
- 不恢复历史版本 hash、adapter、retirement 或兼容表。
- 不写入 StratusAgent、其独立 worktree、causis_risk_suite 或 ClaudeBridgeAssist。
- 不实现 split index 兼容、恢复或自动转换。
- 不执行 `git add`、commit 或 push。
- 不以手工版本戳、绕过 hook 或吸收公共漂移制造通过结果。

## 任务规模与预算

- 规模：L。涉及项目同步器、baseline、版本分类、git-sync、pre-commit、Template/dogfood、测试和文档，包含破坏性重装与 Git 事务边界。
- 时间上限：180 分钟。
- Token 上限：60k，未实测；以 agent 数、验证轮次和范围增长做代理闸。
- 子 Agent：最多 3 个。
- 验证：最多 2 轮。
- 超过任一预算立即停止，不静默缩减验收或把部分完成报告为通过。

## 已确认规则

1. 严格化现有 `bridgeforge-codex-manifest.json`，作为 factory 身份唯一主张；三件 factory 资产只作完整性证明。
2. `PreservationManifest` 只存在于内存或事务临时目录；Apply 重算 fingerprint、完成回灌与验证后先清理，清理成功后才允许 stamp-last。
3. 项目 Hook 使用 `.codex/hooks/project_XXXX/` 浅层目录；一个目录是一个 Python self-contained bundle，整体保留或整体删除。
4. `current_baseline.py` 提供唯一 `OwnershipProjection`，统一判断 public/project/mixed；无法解析时零写阻断。
5. 所有自动写入先形成完整 `SyncWritePlan`，覆盖 HEAD、普通/linked worktree 完整 index 与自动目标；提交前失败按 CAS 完整回滚。split index 只作写前阻断条件。
6. pre-commit 完全只读；生成与暂存只能由 git-sync 写事务执行。

## 本期缺陷范围

### Blocker

- Planner 禁止执行目标项目旧或漂移的 `memory_lint.py`；任何身份 blocker 路径必须事务外零写。
- 修复 1.4.30 后仍硬编码旧版本导致完整测试红灯的发布闸缺陷。

### High

- 未知或损坏的 pre-commit project-extension marker 必须阻断，禁止 safe replace 丢失项目命令。
- 未知或损坏的 AGENTS project marker 必须阻断，`affects_readiness` 必须真实参与 readiness。
- obsolete/current stamp 文件名与版本矩阵必须严格校验，异常身份零写阻断。
- 项目 Hook 注册、bundle 和资源必须形成可验证闭包，禁止保留注册后删除执行文件。
- git-sync 必须完整恢复提交前自动文件、工作区和 index staged/unstaged 边界。
- 共享受管文件中的项目区变化必须触发项目业务版本，禁止按路径误判 skeleton-only。
- current baseline 的 Hook 身份必须绑定 event、matcher、ID 和内容。
- 下游缺戳不得通过复制 factory 支撑文件或根 VERSION 伪装为 factory。
- shared Skill manifest 的 schema、重复键、role/platform、target 和允许字段必须 fail-closed。

## 拟修改范围

- `scripts/bridgeforge_codex_project_sync.py` 及对应 Template/dogfood 传播面。
- `templates/scripts/current_baseline.py`、`templates/scripts/version_release.py`、`templates/scripts/codex_git_sync.py` 及 dogfood 镜像。
- `scripts/rebuild_shared_skill_manifest.py`、相关 manifest 和严格解析辅助代码。
- `templates/.githooks/pre-commit`、工厂镜像和必要 Hook 检查器。
- `scripts/tests/**` 中覆盖 11 个缺陷和事务边界的定向回归。
- 根 `VERSION`、`CHANGELOG.md`、必要活跃设计/安装文档和受管合同。

## 数据与自动化边界

- 不涉及外部数据库、交易数据、账户、网络服务或用户级配置写入。
- 下游验收只使用临时目录与临时 Git 仓库。
- 所有生成、更新和回滚必须通过项目本地 `.venv` 与受管入口。
- 自动写入必须在 `SyncWritePlan` 中预先声明；未声明写入视为缺陷并阻断。

## 验收标准

- 2 个 Blocker、9 个 High 各有定向回归测试。
- 完整 factory unittest 全绿。
- downstream fixture 全绿。
- 临时旧项目破坏性重装、临时 1.4.28+ 更新、stamp-last 和 no-op replan 通过。
- Planner blocker 前后 exact-tree 零变化；Apply 各关键失败点能恢复本轮全部写入。
- git-sync 提交前失败恢复自动目标、完整 index 和原 staged/unstaged 边界；commit 成功而 push 失败时保留合法本地 commit。
- 直接 commit 的 pre-commit 只读；派生文件过期时零写阻断。
- factory dogfood、shared manifest、skill metadata、project structure、mirror drift 和 current baseline 硬闸通过。
- 独立 review 无剩余 Blocker/High；未执行真实下游或 runtime 的部分明确标为未验证。
- `git diff --check` 通过。

## 合理假设与风险

- 180 分钟对 11 个高严重度问题较紧；若首次完整验证暴露新的 Blocker/High，必须先走预算升级闸。
- 项目 Hook 统一 Python self-contained bundle 会阻断旧 PowerShell/CMD 或跨目录依赖；本期不自动转译这些 Hook。
- 第一阶段完成后仍存在已记录的 Medium、Low、死代码和文档债，必须由第二期清理后才能重新评估“整体洁净”。
- 真实下游与真实 Codex runtime 未纳入写入验收，禁止宣称对应验证已通过。

## 实施计划

1. 只读 discovery 闭合六项架构的调用链、单一事实源、传播面与测试边界。
2. 按文件边界实施核心安全修复、Template/dogfood 传播、1.4.30 发布元数据和定向测试。
3. 执行最多两轮预定验收集，并由独立 review Agent 读取真实 diff 给出交付结论。

## 实施记录

- 状态：六项核心架构、11 个原始缺陷及首次独立审计追加的 manifest/Git 事务问题均已闭合；第一期 release-ready。
- Agent 使用：2/3（只读 discovery、project-sync 实现）；第三个名额保留给独立 review。
- 发布面：VERSION/CHANGELOG、Template/dogfood、合同/manifest、直接相关安装与同步文档已同步到 1.4.30。
- project-sync 定向验证：23/23；临时 downstream fixture：3/3。
- 范围或预算变化：无。

## 验证记录

- 验证轮次：初始 2/2 后发现 3 个 High；用户明确授权继续，追加定向修复、完整验证与独立复核。
- 定向测试：project-sync 23/23；两条修正后的失败用例 2/2。
- 完整 factory：`.venv\\Scripts\\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py" -q`，236/236。
- 临时下游：`scripts/tests/run_downstream_fixture.py`，3/3；覆盖 current init/no-op、旧项目确认重建、current drift 零写阻断。
- 发布硬闸：manifest、current baseline 1.4.30、project structure、mirror drift、Skill metadata、memory `--check`、config health、`git diff --check` 与真实 pre-commit 均退出 0。
- 独立 review：复用原审计 Agent 动态重放 failing commit、畸形/自认证 manifest、PowerShell exact schema 与非 `-B` bytecode 零写场景；最终 Blocker 0、High 0、必要 Medium 0，第一期 release-ready。

## 后续交接

- 目标 Skill：`$develop`。
- 开工前只需确认是否按本卡开始开发，不重复业务访谈。
