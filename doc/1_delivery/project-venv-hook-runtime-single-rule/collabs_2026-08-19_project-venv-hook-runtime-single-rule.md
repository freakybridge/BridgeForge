---
status: implemented-awaiting-user-acceptance
requirements: requirements_2026-08-19_project-venv-hook-runtime-single-rule.md
budget: 120m / 50k estimated new tokens / 4 subagents / 3 validation rounds
---

# 项目 `.venv` Hook Runtime 单一规则协作记录

## 目标与边界

实现需求卡确定的单一 runtime 规则：项目 `.venv` 为所有骨架与 Hook 的唯一 Python；仅
init/adopt 且 `.venv` 完全缺失时允许一次 PATH CPython 3.11+ bootstrap；用户级 Native
Memory handler 不保存项目绝对 Python 路径，并以用户级锁、锁内重读和 CAS 维护共享
`hooks.json`。

禁止写真实下游、真实用户级 Hooks 或 memories，禁止 commit/push，禁止覆盖 #1～#5 及用户
现有 dirty 改动。

## 只读调研收据

- 当前仓库没有任何 `python -m venv` 产品实现；只有 Skill 文本允许 PATH fallback。
- Skill 当前在判定 init/adopt 之前运行 Native Memory status；缺少 `.venv` 时无法满足新规则，
  因此必须先判模式、完成唯一 bootstrap，再进入所有 Python planner。
- 项目 `templates/hooks.json` 已通过 Git 根调用 `.venv`，无需重写项目 Hook 命令。
- `stable_hook_python()` 将 base interpreter 绝对路径写入三个用户级 handler；
  `launch_background_reconcile()` 再次调用它，形成跨项目抖动。
- `repair_user_hooks()` 在锁外读取 hooks/ledger，`merge_user_hooks()` 直接原子替换，没有跨项目
  锁、锁内重读、CAS 或 conflicted/rolled_back 收据；setup 也走同一无锁写入。
- 用户级 lifecycle 的当前工作目录必须能定位 BridgeForgeCodex Git 根；需求卡已确认无法定位时
  阻断，不建立 PATH fallback。
- CAS 对遵守本产品锁的多个 BridgeForge writer 可以证明只有一个提交；对完全不遵守该锁的
  第三方进程只能做到写前漂移检测，文档和测试不得夸大为操作系统级原子 CAS。

## 固定共享接口

新增 `templates/scripts/project_runtime.py`，Template 为单一事实源，dogfood 镜像机械传播。
实现任务按以下接口协作，禁止各自再定义第二套版本规则：

- `MIN_PYTHON = (3, 11)`；
- `ProjectRuntimeError`：所有 runtime contract 阻断的唯一异常；
- `ProjectRuntime`：包含解析后的项目根、`.venv` Python 和实际 CPython 版本；
- `expected_project_python(project_root)`：只返回项目内规范路径；
- `validate_project_runtime(project_root, executable=...)`：证明当前解释器属于该项目 `.venv`、
  为 CPython 且版本 >= 3.11；
- `bootstrap_project_venv(project_root, mode, bootstrap_executable=...)`：只允许 init/adopt 且
  `.venv` 完全不存在时执行 `-m venv`，随后用新解释器自检；
- CLI `bootstrap` / `validate`：供 Skill 和测试调用，输出稳定 JSON 收据。

Native Memory 入口新增显式 `--project-root`，repair 本身禁止调用 Git；用户级 lifecycle 命令
负责从当前 Git 上下文解析根目录，再调用 `<root>/.venv/Scripts/python.exe` 和正式产品脚本。
background reconcile 使用已经验证的 `sys.executable` 并显式继承该项目根，不再重新推导 base。

## 拆分表

| 任务 | 职责 | 唯一主文件边界 | 并行/依赖 |
|---|---|---|---|
| A. 项目 runtime contract | 新增 bootstrap/validate 单一模块；project sync 强制当前项目 `.venv`；config health 共用规则；补 bootstrap/低版本/非 CPython/路径逃逸测试 | `templates/scripts/project_runtime.py`、`scripts/bridgeforge_codex_project_sync.py`、`templates/hooks/config_health_check.py`、`scripts/tests/test_project_runtime.py`、`scripts/tests/test_codex_hook_single_source.py` | 与 B 并行；必须遵守固定接口 |
| B. Native Memory 共享 Hooks | 删除 base Python 推导；生成动态项目 `.venv` lifecycle 命令；status/repair/setup 共用锁内重读+CAS；补顺序/并发/回滚/幂等 fixture | `scripts/codex_memory_sync.py`、`scripts/tests/test_memory_native_sync.py`、`scripts/tests/native_memory_repair_worker.py` | 与 A 并行；只 import 固定接口，不修改 A 文件 |
| 主 agent 串联 | 调整 Skill 模式判定和 bootstrap 顺序；同步公共 AGENTS、dogfood 镜像、contract/manifest、版本与文档；解决 import/注册衔接 | 其余确认范围内文件 | A/B 完成后 |
| 独立审计 | 独立读取最终 diff，核对需求、并发语义、传播、真实零写边界和测试 | 只读 | 整合与验证后 |

## 并行写入约束

- A、B 不得编辑对方文件；发现接口不足必须先消息通知主 agent，禁止自行改固定共享接口。
- 机械镜像、manifest、VERSION、CHANGELOG、AGENTS、Skill、Bug 与本 topic 全由主 agent串联。
- 所有用户级 Hooks 测试必须覆盖临时 `CODEX_HOME`，禁止访问真实 `~/.codex/hooks.json`。
- 两个实现任务都不是独立仓库，必须保留他人和用户的现有 dirty 改动，禁止 reset/restore。

## 验收命令规划

- 定向：`test_project_runtime.py`、`test_memory_native_sync.py`、`test_codex_hook_single_source.py`。
- 产品：完整 `unittest discover` 与 `run_downstream_fixture.py`。
- 传播：manifest `--check`、mirror、instruction source、project structure、skill metadata。
- 格式与边界：`git diff --check`、临时 HOME/CODEX_HOME 写入清单、真实下游/用户配置 hash 不变。
- 最终：独立 review-auditor 给出 Blocker/High/Medium/Low 结论。

## 执行记录

- 用户选择 A，确认按拆分表启动实现。
- 任务 A 与任务 B 使用固定共享接口和互不重叠文件边界并行执行。
- 任务 A 完成共享 runtime contract、项目同步与 config health 接入，定向测试 32/32 通过。
- 任务 B 完成动态项目 `.venv` lifecycle、共享 writer 锁/CAS/回滚，定向测试 46/46 通过。
- 主 agent 已完成 Skill、公共 AGENTS、dogfood 镜像、contract、manifest、1.4.21 与文档串联。
- 集成测试第二轮的三个失败已定位为旧 fixture 缺少新 runtime 前提并修正；产品 contract 未放宽。
- 剩余唯一 agent 名额用于最终只读独立审计；最终完整验证仍在 3 轮预算内。
- 首次审计发现 6 High / 2 Medium / 1 Low；主 agent 已在原范围内封闭全部旁路并补测试，现由同一
  auditor 复审，不新增 agent。
- 同一 auditor 最终复审 0 / 0 / 0 / 0，独立定向测试 192/192。
- 用户批准第 4 轮验证后，完整 unittest 291/291、downstream fixture 与全部发布硬闸通过。
