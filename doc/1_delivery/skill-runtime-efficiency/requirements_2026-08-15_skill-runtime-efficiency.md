---
title: BridgeForge Skill 运行效率优化需求确认卡
status: confirmed
date: 2026-08-15
source: plan -> confirm
handoff: develop
---

# BridgeForge Skill 运行效率优化需求确认卡

## 原始需求摘要

用户要求再次检查 BridgeForge 骨架中除根 `bridgeforge` 外的其他 skill，定位运行效率问题，
并在不降低功能、结果质量、安全校验和兼容性的前提下优化。用户已审阅完整只读计划并选择
“A. 开始实施”。

## 目标

- 删除轻量、确定性 skill 外层无条件子 agent 往返，只在冲突或深度 fallback 时分派。
- 消除 `debate` 中独立 research 与 A/B 真实代码研读的重复阶段。
- 保证项目 memory 派生索引只由 writer 或统一索引器维护，不再人工同步或重复重建。
- 把每次 UserPrompt 的 Git 状态采集从三个 Git 进程合并为一个，并保持输出语义不变。
- 在能证明逐候选结果等价时，减少 `archive_scan.py` 的线性 Git 子进程数。
- 用行为等价测试和进程数断言证明优化未削弱安全与结果质量。

## 不做

- 不修改根 `$bridgeforge` 更新执行器及刚发布的 `0.92.0` 更新 fast path。
- 不减少 `create-worktree` 的创建前后 Git、路径、分支和 worktree 注册安全断言。
- 不删除 `collab` 的 implementation/review 隔离、L 级 `develop` 或 `escalate` 的独立审计。
- 不弱化 `$git-sync` 的 fetch、pre-commit、分叉停机或最终 ahead/behind 核验。
- 不新增缓存、后台服务、守护进程、第二份 memory 索引或额外状态文件。
- 不承诺网络、模型或平台调度的固定总耗时。

## 任务规模与预算

- 规模：M。
- 判定依据：涉及多个共享 skill、Codex routing、双宿主模板/dogfood Hook 与回归测试，
  但不改变用户数据、业务接口或高风险迁移契约。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算，平台无可靠精确计量器，未实测）。
- agent 预算：最多 1 个；只读计划阶段已使用 1 个 `light-explorer`，实施阶段不再新增。
- 验证预算：最多两组；第一组行为/进程等价，第二组分发/parity/metadata。
- 超预算停止点：范围升为新缓存架构、无法用两组测试证明等价，或需要第二个 agent 时停止。

## 已核实事实

- 共有 20 个产品 skill；本轮审计 19 个非根 `bridgeforge` skill。
- `archive-scan` 的确定性 JSON 脚本仍被 routing 无条件分派给 `light-explorer`。
- `find-doc`、`find-memory` 已有精确命中/热索引退出条件，但 routing 仍把搜索阶段整体分派。
- `debate` 先启动 `light-explorer`，随后 A/B 仍被要求基于真实代码独立交锋。
- `MEMORY.md` 与 `MEMORY_COLD.md` 是统一索引器生成的派生文件，禁止人工维护。
- `project_memory_writer.py` 写入正文后已自动调用 `memory_rebuild_index.py` 并验证索引收据。
- `show_state.py` 每次 UserPrompt 分别运行 branch/status/rev-list 三个 Git 进程。
- 本机只读基线：`show_state prompt-state` 五次约 99-119ms；三 Git 状态约 67ms，
  单 Git 状态约 27ms；`memory_search` 约 65ms；稳定 `archive_scan` 约 50ms。
- 既有 named-agent 路由报告明确记录短任务绝对成本未验证，真实 smoke 仍缺证据。

## 已确认规则

- 快速路径只能覆盖确定性、单一高置信结果；冲突、多候选或深度检索必须保留 explorer fallback。
- 用户确认、写入、归档决定与跨阶段整合始终留在主对话。
- `debate` 保留两个不同立场 agent、真实代码独立读取、2-3 轮上限和最终用户确认。
- Git 状态合并后必须逐项保留 branch、dirty、ahead/behind、detached 和 no-upstream 语义。
- archive 批量查询无法证明 `last_modified_days`、score、排序和未跟踪文件语义等价时不实施。
- 任何行为、结果集合、排序或安全断言变化都撤回对应优化，不以速度换正确性。

## 拟修改

- `skills/archive-scan/SKILL.md`
- `skills/find-doc/SKILL.md`
- `skills/find-memory/SKILL.md`
- `skills/todo/SKILL.md`
- `skills/debate/SKILL.md`
- `skills/summary/SKILL.md`
- `.codex/skill-routing.json` 与 `templates/codex/skill-routing.json`
- Codex/Claude 模板与 dogfood `hooks/show_state.py`
- 仅在等价性成立时修改四份 `scripts/archive_scan.py`
- 相关 harness、shared manifest、本文档与 `doc/README.md`

## 验收

- 确定性 fast path 不启动子 agent，深度 fallback 仍路由到 `light-explorer`。
- `debate` 不再额外启动 research explorer，A/B 角色和审查强度不变。
- `todo`、`summary` 不要求人工写派生索引或在 writer 后重复 rebuild。
- `show_state` 每次调用最多启动一个 Git 子进程，原有输出字段和降级语义全部通过测试。
- archive 多候选场景最多启动一次 Git 查询，且逐项结果与旧语义一致；否则明确暂缓该项。
- Codex/Claude 模板、dogfood、routing、manifest 和 metadata/parity 检查一致。
- 两组验证记录真实命令、断言、覆盖路径；未完成 runtime smoke 明确标记未验证。

## 合理假设与风险

- named agent 的平台调度成本无法从静态测试精确计量，验收以减少确定性往返和子线程数为主。
- `git status --porcelain=v2 --branch` 的 detached/no-upstream 输出需要显式解析与 fixture。
- 单次批量 `git log` 可能增加历史输出量；若复杂度或语义风险高于收益则保留逐候选实现。
- Hook 是产品层并被下游复制，所有 Codex Hook 修改必须同步 dogfood；Claude 同语义实现也要同步。

## 自动化边界

- 允许修改当前仓库内产品 skill、模板、dogfood、测试、manifest 和交付文档。
- 禁止写用户级 skill、修改其他项目、运行真实归档、创建 worktree 或执行 Git 提交/推送。
- 发布版本与 CHANGELOG 由后续用户显式调用 `$git-sync` 时的确定性发布脚本处理。

## 实施计划

1. 收紧 routing 和 skill fast path，消除重复 research 与派生索引维护。
2. 合并 `show_state` Git 状态读取；在语义等价前提下优化 archive Git 查询。
3. 增加定向回归、同步四份镜像与 manifest，完成两组验证并记录收据。

## 实施记录

- 2026-08-15：完成 19 个非根 skill 静态审计与本机只读基线；用户选择 A 开始实施。
- 2026-08-15：为 `archive-scan`、`find-doc`、`find-memory`、`todo` 增加主对话确定性快速路径，
  仅把歧义、多候选或递归冷检索保留给 `light-explorer`；`debate` 删除重复 research explorer，
  保留 A/B 双立场真实代码研读。
- 2026-08-15：`todo` / `summary` 统一由 writer 或索引器维护派生 memory 索引；writer 成功后复用
  `rebuild_command` 收据，不再重复 rebuild。
- 2026-08-15：四份 `show_state.py` 改为单次 `git status --porcelain=v2 --branch`；四份
  `archive_scan.py` 改为一次批量 `git log`，并同步 Codex / Claude 模板与 dogfood。

## 验证记录

- 第一组：`.venv\\Scripts\\python.exe -B -m unittest tests.harness.test_skill_runtime_efficiency
  tests.harness.test_summary_skill tests.harness.test_downstream_version_sot
  tests.harness.test_skill_metadata_budget`，34 项全部通过；覆盖单 Git 进程、detached / no-upstream、
  archive 单批查询与未跟踪文件、四镜像一致、fast path / fallback 路由、memory 单次 rebuild。
- 性能复测：`.codex/hooks/show_state.py prompt-state` 五次为 76.8 / 62.6 / 64.3 /
  65.0 / 63.3ms，平均 66.4ms；同机优化前为约 99-119ms。该数据只证明本机进程开销下降，
  不承诺不同项目和平台的固定总耗时。
- 第二组：`test_shared_skill_distribution` 与 `test_bridgeforge_root_skill` 共 33 项全部通过；
  `rebuild_shared_skill_manifest.py --check`、`skill_metadata_check.py`、`mirror_drift_check.py`
  和 `git diff --check` 均 exit 0。`harness_parity_check.py --check` 首次只报告新增 harness 后
  parity 文档过期；用同一工具重建后再次 `--check` exit 0。
- 最终边界复核补充了 archive 中文路径的 NUL 分隔测试；修复后
  `test_skill_runtime_efficiency` + `test_shared_skill_distribution` 共 31 项通过，manifest、parity、
  metadata、mirror 与 diff 检查再次全部 exit 0。
- 未验证：平台 named-agent 的实际调度耗时和真实下游端到端总耗时；本轮只确认减少了确定性
  子线程路由与本机 Git 子进程成本，未把静态路由测试冒充运行时 smoke。
