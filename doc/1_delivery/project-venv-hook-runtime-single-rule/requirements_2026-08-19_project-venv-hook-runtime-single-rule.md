---
status: implemented-awaiting-user-acceptance
product_version: 1.4.21
delivery_size: L
delivery_budget: 120m / 50k estimated new tokens / 4 subagents / 3 validation rounds
token_measurement: unavailable
source_bug: doc/2_bugs/BUG-project-sync-schema-v1-baseline-and-native-memory-hook-race.md
source_issue: "#6"
next: user-acceptance
---

# 项目 `.venv` Hook Runtime 单一规则需求卡

## 原始需求摘要

用户要求 BridgeForgeCodex 骨架把项目自己的 `.venv` 设为所有骨架代码与 Hook 的唯一
Python runtime，不再为用户级 Native Memory Hook 安装或推导额外的用户级固定 Python。
首次初始化允许一次性使用 PATH 中经过验证的 CPython 3.11+ 创建 `.venv`；创建成功后，
所有日常入口永久禁止回退 PATH。

本卡由 `$develop` 调用 `$confirm` 形成，后续交接 `$collab` 分治实现与独立审计。

## 背景与目标

当前项目 Hooks 已通过 Git 根目录调用项目 `.venv/Scripts/python.exe`，但
`scripts/codex_memory_sync.py` 仍从执行它的项目环境推导一个绝对 Python 路径并持久化到
用户级 `~/.codex/hooks.json`。不同项目可能因此轮流改写同一份用户级配置。

目标是建立一条长期单一规则：

1. 每个 BridgeForgeCodex 项目必须存在自己的 `.venv`；
2. `.venv` 必须为 CPython 3.11 或更高版本；
3. 所有骨架脚本、项目 Hook 与用户级 Native Memory Hook 都调用当前项目 `.venv`；
4. 用户级 Hooks 禁止持久化任一具体项目的 Python 绝对路径；
5. 用户级 Hooks 的实际写入使用用户级互斥锁与写前 compare-and-swap 复核；
6. 非 BridgeForge handler 与未知 ownership 继续保留或 fail closed。

## 已核实事实

- 产品同步器、Hook dispatcher、Hooks merger 与配置健康检查已经以 CPython 3.11+ 为最低要求。
- Template 项目 Hooks 已通过 `git rev-parse --show-toplevel` 定位项目 `.venv`。
- 当前 Skill 仍允许缺少 `.venv` 时长期回退 PATH，并宣称用户级 Hook 应使用稳定基础解释器；
  这两条与本卡的新单一规则冲突。
- Native Memory 的三个用户级 handler 当前持久化由 `stable_hook_python()` 推导出的绝对路径。
- `repair_user_hooks()` 有单文件原子替换，但没有跨项目用户级锁、CAS 冲突收据或并发 fixture。
- 四个真实项目的 `.venv` 分别为 3.12.9、3.12.13、3.12.13 与 3.11.9，均满足 3.11+。
- BridgeForge 工作树在本卡创建前已经包含 #1～#5 的 dirty 改动，必须完整保留。

## 已确认规则

### 稳态规则

- 项目 `.venv` 是当前项目所有 BridgeForgeCodex Python 代码的唯一 runtime authority。
- 最低版本是 CPython 3.11；3.11.x、3.12.x 及未来兼容版本均合法，不固定精确补丁版本。
- update、status、repair、Hook、validator 和 Git 同步入口均禁止回退 PATH。
- `~/.codex/hooks.json` 只能保存根据当前 Git 项目根动态定位 `.venv` 的通用命令；禁止写入
  `D:\Quant\<project>\...` 等项目绝对 Python 路径。

### 首次 bootstrap

- 仅在 init/adopt 的项目尚无 `.venv` 时，允许从 PATH 选择一次 CPython 3.11+。
- 该解释器只用于创建项目 `.venv`；创建后必须立即验证实际解释器与版本并切换。
- `.venv` 创建或验证失败时零产品写入并明确阻断，禁止继续用 PATH 完成骨架更新。
- 已存在但损坏、低于 3.11 或不是 CPython 的 `.venv` 不属于 bootstrap 缺失场景，必须阻断。

### 用户级 Hooks 并发与 ownership

- status、repair 与 lifecycle handler 必须按同一个动态项目 runtime contract 判断健康。
- repair 写入前取得用户级互斥锁；锁内重新读取严格 JSON、重算预期变更并比较原始状态。
- 两个 writer 竞争时只能有一个提交；另一方返回 `unchanged` 或 `conflicted`，不得丢失更新。
- duplicate key、未知 managed id、managed hash 漂移或锁状态不可信时零写入 fail closed。
- 所有未标记 handler、第三方字段与用户配置继续按 Hooks Zones 单一 ownership 规则保留。
- repair 继续保持 local-only，禁止访问 GitHub、Git memories 内容或触发 reconcile。

## 数据与命令映射

| 场景 | Python 来源 | 允许行为 |
|---|---|---|
| init/adopt 且 `.venv` 缺失 | PATH 中经验证的 CPython 3.11+ | 仅创建 `.venv`，随后立即切换 |
| `.venv` 已存在且健康 | `<git-root>/.venv/Scripts/python.exe` | 所有骨架与 Hook 操作 |
| `.venv` 损坏、低版本或非 CPython | 无 | 零写入阻断 |
| 用户级 Native Memory lifecycle | 当前 Git 项目根的 `.venv` | 调用产品受管脚本，不持久化项目绝对 Python 路径 |
| 并发 repair | 用户级锁内重读并 CAS | `applied` / `unchanged` / `conflicted` / `rolled_back` |

## 拟修改范围

- 公共 `AGENTS.md` 与 BridgeForge Skill：声明 `.venv`、CPython 3.11+ 和唯一 bootstrap 例外。
- 项目同步入口与配置健康检查：验证当前执行解释器确属目标项目 `.venv`。
- Native Memory 用户级 Hooks：改为动态项目 `.venv` 命令，删除 `stable_hook_python()` 路径推导。
- 用户级 Hooks repair：增加全局锁、锁内重读、CAS 与稳定收据。
- Template/dogfood、ownership contract、manifest、VERSION、CHANGELOG 与源 Bug 同步。
- 自动测试与临时 fixture：覆盖多项目顺序/并发、bootstrap、漂移、回滚和幂等。

## 非目标与自动化边界

- 不安装或维护额外的用户级 Python。
- 不把最低版本提升到 3.12，也不固定 3.12.13 等补丁版本。
- 本产品修复阶段不 apply 四个真实下游，不写真实 `~/.codex/hooks.json`，不调用真实
  Native Memory status/repair。
- 不读取、上传、恢复或 reconcile 用户 memories 内容。
- 不提交、不推送、不清理、不 reset/restore 现有 dirty 工作树。
- Stratus 主工作区与 M2 worktree 的共享 Git 状态禁止并发修改。

## 验收标准

1. 缺少 `.venv` 的临时 init/adopt fixture 可用一次性 PATH CPython 3.11+ 创建并切换；
   随后所有 Python 子流程来自项目 `.venv`。
2. update/status/repair/Hook 在 `.venv` 缺失、损坏、低于 3.11 或非 CPython 时零写入阻断。
3. 3.11.9、3.12.9 与 3.12.13 fixture 均通过同一最低版本规则。
4. 用户级三个 Native Memory handler 不含任一 fixture 项目绝对 Python 路径，且能从当前项目
   调用其 `.venv` 与受管产品脚本。
5. 两个临时项目顺序运行 status/repair 后命令保持同一通用 contract，不产生 runtime 抖动。
6. 两个进程并发 repair 时只有一个 writer；另一方稳定返回 unchanged/conflicted，第三方配置不丢失。
7. repair 写后验证失败时恢复用户 Hooks 原始字节，返回 rolled_back；重复 repair 是 no-op。
8. repair 对 GitHub、Git memories 内容读取和 reconcile 均设置 fail-if-called 并通过。
9. Template/dogfood 镜像、contract、manifest、VERSION、CHANGELOG、源 Bug 和文档索引一致。
10. 针对性测试、完整 factory unittest、downstream fixture、manifest `--check`、mirror、metadata、
    project structure、instruction source、`git diff --check` 与独立审计通过。
11. 后续真实项目阶段保存 before 状态，并分别完成 plan -> apply -> validators -> stamp-last ->
    no-op replan；本卡不提前授权该阶段写入。

## 合理假设与风险

- 生命周期 Hook 在 BridgeForgeCodex Git 项目上下文中运行，可通过 Git 根定位当前项目；无法
  定位时按不合规骨架阻断，不另设 PATH fallback。
- 用户级锁必须放在用户配置作用域，且测试只能使用临时 `CODEX_HOME`，避免污染真实共享资源。
- bootstrap 会新增受忽略的 `.venv` 目录；产品必须先证明目标路径位于当前项目根内。
- 本轮改动跨越公共规则、Skill、同步器与用户配置协议，任何未同步镜像都可能形成第二套规则。

## 规模与预算

- 规模：L。原因是改变 Python bootstrap、骨架运行权威、用户级 Hook 调度与并发写入协议。
- 上限：120 分钟；50k 新增 token 估算，平台无可靠计量器，标记 token 未实测；最多 4 个
  子 agent；最多 3 轮验证。
- 计划使用：1 个只读调研 agent、2 个文件边界独立的实现 agent、1 个独立审计 agent。
- 超过时间、agent、验证轮次或范围增长任一上限时停止并请求扩大预算或缩小范围。

## 实施记录

- `$collab` 只读调研确认：当前无 `.venv` bootstrap 产品实现；Skill 顺序必须先判模式并完成
  bootstrap；Native Memory 的 runtime 推导、background 分支及 repair/setup 共享写入均需收敛。
- 协作拆分与固定接口见
  `collabs_2026-08-19_project-venv-hook-runtime-single-rule.md`；用户已确认并完成两项实现。
- 新增共享 `project_runtime.py`，项目同步入口与 config health 使用同一 CPython 3.11+ `.venv`
  contract；init/adopt 的 missing-only bootstrap 具有失败清理，现存损坏 runtime 保持零写阻断。
- Native Memory 删除固定 base Python 推导；用户 handler 动态定位当前 Git 根 `.venv`，background
  使用已验证的 `sys.executable` 与项目 cwd。status/repair/setup 共用用户级锁、锁内重读、CAS、
  写后验证与回滚收据，repair 继续 local-only。
- 主串联已同步 Skill 执行顺序、公共 AGENTS、Template/dogfood、managed contract、manifest、
  VERSION 1.4.21、CHANGELOG、源 Bug 与文档索引；未写真实项目或真实用户配置。

## 验证记录

- 任务 A：`.venv\Scripts\python.exe -B -m unittest scripts.tests.test_project_runtime
  scripts.tests.test_codex_hook_single_source`，32/32 通过，覆盖 bootstrap、自检、版本/实现、路径逃逸、
  部分创建回滚、sync CLI 与 config health 阻断。
- 任务 B：`.venv\Scripts\python.exe -B -m unittest discover -s scripts\tests
  -p "test_memory_native_sync.py"`，46/46 通过，覆盖两个临时项目顺序/跨进程并发、CAS、rollback、
  duplicate/drift、幂等与 local-only。
- 集成验证第二轮运行 140 项，137 项通过；三个失败均由旧测试 fixture 未创建 `.venv` 或用空 Mock
  替换验证器解释器路径造成，已只修 fixture、不放宽产品规则。等待最终完整验证确认修补结果。
- manifest 重建已成功；最终完整 unittest、downstream fixture、发布硬闸与独立审计待执行。
- 首次独立审计：Blocker / High / Medium / Low = 0 / 6 / 2 / 1。现已修复 lifecycle 错误成功码、
  abandoned mutex、Git/Memory Skill 与 dispatcher/pre-commit runtime 旁路、repair/setup 锁外 config、
  decline 无锁、源 Bug 旧规则和三组 CPython 接受 fixture；等待同一 auditor 复审。
- 独立复审：Blocker / High / Medium / Low = 0 / 0 / 0 / 0；独立定向测试 192/192 通过，manifest、
  mirror、instruction source、project structure、skill metadata 与 diff 硬闸通过。
- 最终第 4 轮（经用户批准扩展）：完整 unittest 291/291；`run_downstream_fixture.py` 为 passed，
  覆盖 init stamp-last、27 个历史版本、8 个 apply/no-op replan 与 19 个旧 pre-commit 显式适配；
  manifest `already current`，mirror、instruction、structure、metadata、`git diff --check` exit 0。
- 未执行真实四项目 apply 或真实用户 Native Memory status/repair/setup；这些属于后续真实项目阶段，
  不影响 #6 产品技术实现关闭。
