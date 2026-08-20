# 四项目 bridgeforge-codex 零卡点更新报告

## 报告状态

- 状态：进行中
- 产品版本：`1.4.26`
- 禁止项：本轮未 commit、未 push、未 reset、未 restore、未 stash、未 clean。
- 项目顺序：用户于 2026-08-20 明确要求先处理 M2；M2 与主 Stratus 仍按共享 Git 状态串行操作。

## 产品最终闸

- Causis 的真实 1.4.25 Planner 暴露 HEAD/current-before 版本轴混用：HEAD 旧 dispatcher 被错误地按
  工作区 1.4.11 查询历史。1.4.26 已改为 HEAD 查 HEAD 合同版本、current-before 查冻结工作区版本；
  新回归先红后绿，相关模块 55/55 通过，真实 Causis 恢复为 G1/1 eligible。完整闸与独立审计待执行。
- 1.4.24 独立审计曾为 `Blocker/High/Medium/Low = 0/0/0/0`，但 M2 第三次真实 Apply 推翻了其写后 current-before 前提；1.4.25 已按新三态实现重新独立审计。
- 1.4.25 完整自动测试最终 `311/311 OK`；downstream fixture `status=passed`，覆盖 29 个已发布版本、9 个自动迁移与 19 个显式适配场景。
- manifest `--check`、mirror drift、project structure、instruction source、skill metadata 与 `git diff --check` 均 exit 0；最终独立审计 `Blocker/High/Medium/Low = 0/0/0/0`。
- Causis 已真实执行 1.4.26：13 个 safe 与 G1 完成，preflight=`passed/mixed`、stamp-last、无回滚；
  no-op replan 全零，9 项项目硬闸及 installed authority Native Memory status 均通过。
- 用户否决继续维护未完成的 1.4.27 release-artifact 路线，产品已回到 1.4.26。后续先对白名单已确认的
  ClaudeBridgeAssist 执行一次性干净安装；M2 与主 Stratus 暂不继续写入，共享 Git 状态保持串行。

## M2 worktree

### Before

- 路径：`D:\Quant\CodexWorktree\1d62\StratusAgent`
- 分支 / upstream：`codex/m2` / `origin/codex/m2`
- HEAD：`ee058f70236505883c05cb0329f6308a7275dabc`
- Python：项目 `.venv`，CPython `3.12.13`，runtime contract 验证通过。
- 骨架戳：旧戳 `.codex/.bridgeforge_version = 0.90.0`；新戳不存在。
- 原有 dirty 内容：`.codex/.bridgeforge_version`、`.codex/hooks/skill_metadata_check.py`、`.codex/scripts/bridgeforge_switch.py`。
- Native Memory：`approved + enabled + remoteConfigured`，项目 runtime 正确；最终由 installed product authority 验证用户级 hook 已安装且健康。
- 零写 Planner：`safe=35 / risk=4 / gaps=23 / blockers=0 / G1 AGENTS eligible`。
- aggregate fingerprint：`sha256:76352e3ea222075679b32169a90989b58dc6be397619b3b032f5e406eb768899`。

### 旧规则与项目工具 before hash

| 路径 | SHA-256 |
|---|---|
| `.codex/rules/anti_drift_hooks.md` | `575c710595ad96e100f7e38c38d28a13ab36ff73b23e4113e9b0c7d4898cd0b7` |
| `.codex/rules/anti_fabrication.md` | `cc1054a53c7dbbd652576ddced1b67aabe1dfc3ae9cf6b5935321084073f0e2b` |
| `.codex/rules/architecture.md` | `ff37a998d1197c4d6c726800a496ce1bdf2bb8dc82feea00ce3d6cf131c071ef` |
| `.codex/rules/debugging.md` | `27c7f62a726628ddd864c04f684c587d43da812d93957273f0b184539ff3abb7` |
| `.codex/rules/meta_rule_design.md` | `18292e4a43cf5caedc3c19ddc9807901115899bd17188148fe864fca55dcbb6c` |
| `.codex/rules/modules.md` | `a7b673e228819e9ca30cda58b6cdbd0836b05c933b7b3e4dcfcad93e9b718647` |
| `.codex/rules/portability.md` | `3258b761c491d06bb095ac42db682b4ce15b9df437c345f3ed8ab2218d257561` |
| `.codex/rules/workflow.md` | `908c8d11e83b82d8c8a2037934904ec516f3ca0a5aca0739354e4250e7fdc132` |
| `.codex/hooks/target_cleanup.py` | `5a09a599a9e1bcea1d0f4cec84ff3df76aca1439f0502082b5ecc5cd3dff3921` |
| `.codex/scripts/harness_parity_check.py` | `4bf6d132cb077586823e7ac0ee3663c6147dcbc09f1bd14b856016b4b1484072` |

### 处置原则

- `architecture/modules` 是项目规则，改为 `project_*` 名称并逐字保留。
- 其余退役通用 rule 原文移入 `doc/4_archive/bridgeforge-legacy-rules/`，退出运行时规则面；现行红线只由公共 `AGENTS.md` 与项目专区承载。
- 项目 `target_cleanup` 与旧 parity 工具改为项目专属名称，禁止被骨架收编或删除。
- hooks/pre-commit/README 只做结构适配，项目 handlers、项目扩展和索引内容保持。

### Apply 与验证收据

- 第一次正式 Apply 在确认 4 个 risk 后由 release preflight 零写阻断：`0.86.7` 的 HEAD schema v1
  contract hash 未按该版本登记。旧戳仍为 `0.90.0`，新戳不存在，`rollback_performed=false`；没有
  发生半更新。
- 该现场暴露并推动 1.4.24 修复：Planner 预检完整推荐动作集；四类版本化历史逐发布版本留证。
- 第二轮零写 Planner 继续暴露非阻断 N1 跳过预检，以及 schema-v1 current-before/no-target retirement
  两个固定点证明边界；修复后真实 M2 为 `safe=43 / risk=4 / gaps=0 / blockers=0`，一次列出
  `G1-G32` 且 `32/32 adaptation_eligible=true`，fingerprint
  `sha256:a13e5191f1ec03bc8e9bd0893806334e75456882cc3cc501acdd2aa572eb92bb`。
- 随后三次真实 Apply 均完整回滚：README heading 顺序、写后旧戳缺失、旧 Hook 被按目标版本验证。
  第三次确认产品把 after 磁盘误作 current-before；旧戳仍为 `0.90.0`，新戳不存在，没有半更新。
- 1.4.25 改为 HEAD / frozen before / after 三态 proof。最终真实 M2 Planner 为
  `safe=43 / risk=4 / gaps=0 / blockers=0 / G=32 / eligible=32`，aggregate fingerprint
  `sha256:0f32d86b6f289920920f025b995089e775fc7e90cba95c1d272b3db4a39ca3a6`。
- 用户已确认 A；事务 Apply 返回 `completed / ready`，43 个 safe、4 个 risk 与 G1-G32 全部执行；
  `release_preflight_status=passed`、classification=`mixed`、`stamp_written_last=true`、
  `rollback_performed=false`。selection fingerprint 为
  `sha256:ed73c2f0792bef7252e580613a44e776f16da8a1b02a36c847fc42d9aceb7bb8`，显式适配
  fingerprint 为 `sha256:58d00d70a4b47a5bb76b3ae29a97ff8b99c7bba0bbe5675f0bd3b4c315facf05`。
- 终态新戳 `.codex/.bridgeforge_codex_version=1.4.25`，旧 `.codex/.bridgeforge_version` 已退役；
  no-op replan 为 `safe=0 / risk=0 / upstream_absorption=0 / gaps=0 / blockers=0 / G=0`。
- 独立补跑项目硬闸发现 `ui-ladder`、`ui-option-chain` 两个既有活跃 topic 未进入项目
  `doc/README.md`；仅补两条项目索引后 `project_structure_check.py` exit 0，剩余输出均为历史归档
  advisory。再次 no-op replan 仍全 0。
- Native Memory 必须按 installed product home 判定 ownership。工厂工作树路径的误用 repair 正确
  `conflicted` 且零写；改用 hook 实际指向且脚本 SHA-256 相同的 installed authority 后，状态为
  `enabled=true / hookInstalled=true / pending=false / remoteConfigured=true`，未执行 reconcile。
- M2 工作树保持 dirty；未 commit、未 push，且未并发修改共享 Git 状态。
- 未完成的 1.4.27 artifact 路线及其 Planner 收据已作废；本轮不再对 M2 Apply。

## 其余项目

| 项目 | 当前状态 |
|---|---|
| `D:\Quant\ClaudeBridgeAssist` | 已按用户确认放弃旧谱系并对白名单执行 1.4.26 一次性新基线安装：项目资产保留、公共 canonical 就位、validators 通过、stamp-last、no-op 全零；等待独立审计。 |
| `D:\Quant\causis_risk_suite` | 1.4.26 已完成：13 safe + G1，preflight `passed/mixed`、stamp-last、无回滚；no-op、9 项项目硬闸与 Native Memory healthy。 |
| `D:\Quant\StratusAgent` | 只读 Planner `0 gaps / 0 blockers`，32 项显式适配可执行；尚未 Apply。 |
