# `$bridgeforge-codex-batch` 需求确认卡

- 状态：实现与自动验证完成，待 BridgeForgeCodex 发布及四项目真实验收
- 日期：2026-08-21
- 调用来源：用户直接调用 `$confirm`
- 后续交接目标：`$develop`

## 原始需求摘要

用户在本地维护多个 BridgeForgeCodex 下游项目。当前必须切换到各项目的 Codex
对话框，依次运行 `$bridgeforge-codex` 和 `$git-sync`，操作分散且不利于集中处理
共性骨架问题。需要一个仅供 BridgeForgeCodex 仓库调用的批量 Skill，在当前对话中
集中完成多个下游项目的骨架升级和 Git 同步，并把共性异常直接沉淀到 BridgeForge
文档中。

## 目标

新增 BridgeForgeCodex 仓库专属 Skill `$bridgeforge-codex-batch`。用户每次调用时输入
本次下游项目路径，Skill 在当前对话中串行完成骨架升级、Git 提交和推送，并以结论式
话术汇总结果。

## 不做

- 不保存固定下游项目清单。
- 不把该 Skill 加入公共 `skills/`、Template 或共享 manifest。
- 不允许其他项目调用该 Skill。
- 不并行更新下游项目。
- 不自动处理 Git 分叉、冲突、破坏性恢复或强制推送。
- 默认不向用户展示内部状态码、逐文件清单或验证流水；只有用户追问时才展开。
- 新 Skill 按 BridgeForgeCodex 现有发布机制正常升级产品版本；禁止为它建立例外发布规则。

## 规模与预算

- 规模：L。
- 判定依据：新增跨仓库批量能力，包含真实提交推送、异常恢复、共性缺陷落盘、
  BridgeForgeCodex 修复与全量重跑闭环。
- 时间上限：90 分钟。
- Token 上限：40k 新增 token（估算，平台无可靠计量器，未实测）。
- 子 agent：最多 3 个，分别用于只读调研、实现和独立复核。
- 验证预算：最多 2 轮。
- 超预算停止点：预计超过时间、token、agent 或验证轮次任一预算时立即停止，交由
  用户选择扩大预算或缩小范围。

## 需求确认时已核实事实

- BridgeForgeCodex 的交付文档采用 `flat` 布局，本卡应位于
  `doc/1_delivery/bridgeforge-codex-batch/`。
- 项目级 Skill 的约定位置是 `.codex/skills/<name>/SKILL.md`；需求确认时仓库尚无
  `.codex/skills/` 目录，本交付随后按该边界创建项目专属 Skill。
- 现有 `$bridgeforge-codex` 已定义事务化骨架升级和结论式用户输出规则。
- 现有 `$git-sync` 强制使用每个项目自己的
  `.venv/Scripts/python.exe .codex/scripts/codex_git_sync.py`，并在分叉、冲突或
  破坏性场景停止。
- 四个首批项目路径均存在，均有项目 `.venv`、骨架版本戳和项目本地 Git 同步脚本。
- `D:\Quant\StratusAgent` 与
  `D:\Quant\CodexWorktree\1d62\StratusAgent` 共享同一个 Git 仓库，必须串行处理。
- `D:\Quant\StratusAgent` 和其 `codex/m2` worktree 当前有大量未提交改动；
  `D:\Quant\ClaudeBridgeAssist` 与 `D:\Quant\causis_risk_suite` 当前干净。
- 需求确认时 BridgeForgeCodex 版本为 `1.4.39`，当时有 7 个未提交文件，尚不满足下游
  分发前置条件；实施后的真实状态必须在分发前重新检查。

## 需求确认时未核实事实

- 四个真实项目执行时的网络、凭据、远端分支和 GitHub 可写状态，要到真实验收时
  才能确认。
- 当前 BridgeForgeCodex 未提交变更尚未执行 `$git-sync`，因此尚未证明本地与 GitHub
  完全一致。
- 需求确认时新 Skill 尚未实现；当前已完成实现和首轮测试，但四项目真实端到端结果仍未产生。

## 已确认业务规则

### 调用与输入

- Skill 名称固定为 `$bridgeforge-codex-batch`。
- 只允许在 BridgeForgeCodex 仓库中调用；其他项目调用时必须拒绝执行。
- 每次调用由用户输入本次要处理的项目路径，不读取或维护固定项目清单。
- 输入路径按独立 worktree 作为处理单位；共享 Git 仓库的 worktree 仍分别处理，
  但禁止并行。

### BridgeForgeCodex 分发前置硬闸

向任何下游分发前必须同时满足：

1. BridgeForgeCodex 没有未提交更改；
2. BridgeForgeCodex 本地与 GitHub 完全同步；
3. 本地骨架检查通过。

如果发现 BridgeForgeCodex 有未提交更改，必须留在当前对话，先给出变更结论并单独
确认一次是否执行本仓库 `$git-sync`。只有提交、推送和最终同步检查全部成功后，才能
进入下游批量处理。

### 正常批量流程

1. 读取用户本次输入的项目路径并完成只读预检。
2. 展示项目清单、执行顺序和会发生的保存结果，只统一确认一次。
3. 确认后，逐个项目执行正式 `$bridgeforge-codex` 流程和项目自己的 `$git-sync`。
4. 正常项目自动完成升级、提交和推送，不再逐项确认。
5. 下游已有未提交改动时仍允许进入正式流程，但必须保留既有改动和项目定制。
6. 某个项目出现冲突或需要用户判断时，只暂停并保留该项目现场，继续处理其余项目。
7. 正常项目处理完成后，在当前对话逐个解决异常项目；解决后自动重试升级和同步。

### 共性骨架问题

以下任一条件满足时，判定为共性骨架问题：

- 至少两个下游出现相同问题；
- 已有证据明确表明问题属于 BridgeForgeCodex 通用骨架缺陷。

确认共性问题后必须立即：

1. 停止继续向下游分发；
2. 新建或补充 `doc/2_bugs` 记录，并同步 `doc/README.md`；
3. 用结论式话术说明问题和修复影响；
4. 单独取得修改 BridgeForgeCodex 源码的确认；
5. 在当前对话完成修复、验证、提交和推送；
6. BridgeForgeCodex 再次满足分发硬闸后，从头重新检查本次全部下游项目，包括此前
   已显示成功的项目，确保最终使用同一份已修复骨架。

### 用户输出

- 默认只显示结论、未完成事项和当前唯一下一步。
- 成功时说明项目名称、当前骨架版本以及是否已保存到 GitHub。
- 失败时只说明最关键原因、现场是否保留以及接下来需要用户决定什么。
- 原始状态码、内部枚举、逐文件清单和验证流水只保留为内部收据；用户追问时按问题
  范围展开。

## 数据映射

| 用户输入 | 内部处理单位 | 用户结果 |
|---|---|---|
| 每行一个项目绝对路径 | 独立项目或 worktree | 项目名、完成状态、骨架版本、GitHub 保存状态 |
| 共享 Git 仓库的多个 worktree | 同一互斥执行组内的多个独立目标 | 分别报告，严格串行 |
| 单项目异常 | 保留现场的待处理目标 | 未完成原因与唯一下一步 |
| 两项目相同异常或已证实通用缺陷 | BridgeForgeCodex 共性 Bug | 停止分发、落盘、修复并全量重跑 |

## 拟修改

- 新建 `.codex/skills/bridgeforge-codex-batch/SKILL.md`，作为 BridgeForgeCodex
  项目专属入口。
- 在该 Skill 自有目录增加必要的只读预检或批次状态辅助代码；不得进入公共 Template
  或共享分发清单。
- 在 `scripts/tests/` 增加调用范围、路径输入、串行执行、分发硬闸、异常隔离、共性问题
  和结论式输出测试。
- 根据实现需要增加仓库级设计记录，并同步 `doc/README.md`。
- 在 `CHANGELOG.md` 记录该仓库专属批量能力；根 `VERSION` 由现有官方
  `$git-sync` 发布机制正常升级，禁止手工绕过或建立免升级例外。

## 验收

### 自动验收

- BridgeForgeCodex 根目录允许调用，任意其他项目根目录必须拒绝。
- 多路径输入只产生一次正常批次确认。
- 所有项目严格串行；共享 Git 仓库的不同 worktree 不会并发执行。
- BridgeForgeCodex 不干净、未与 GitHub 同步或骨架检查失败时，零下游写入。
- 已有下游改动不会被覆盖、丢弃或错误归为本轮骨架改动。
- 单项目失败不会阻塞其他正常项目，且现场保持可继续处理。
- 共性问题会停止分发、落盘并要求独立修复确认；修复后触发全量重跑。
- 默认用户输出不暴露内部技术字段。

### 四项目真实端到端验收

以下四个真实项目必须完成实际骨架升级、提交和推送：

- `D:\Quant\StratusAgent`
- `D:\Quant\CodexWorktree\1d62\StratusAgent`
- `D:\Quant\ClaudeBridgeAssist`
- `D:\Quant\causis_risk_suite`

真实执行前仍须展示一次项目清单并取得统一确认。最终成功标准是：所有目标完成骨架
检查，工作区干净，并与各自 GitHub upstream 保持 `ahead=0`、`behind=0`。

## 合理假设与风险

- 假设四个项目在真实验收时仍可访问其远端并具有推送权限；若事实变化，按单项目异常
  保留现场。
- 两个 StratusAgent worktree 共享 Git 元数据，任何并发 fetch、stash、commit 或 push
  都可能互相影响，因此串行是硬约束。
- 未知共性缺陷的修复范围无法预先授权；每次修改 BridgeForgeCodex 源码前必须单独确认。
- 用户对正常批次的一次确认不授权 force push、reset、丢弃改动、自动解决冲突或其他
  破坏性操作。
- “仓库专属”只限定 Skill 的调用范围，不代表免除 BridgeForgeCodex 的正常版本发布；
  该边界曾被错误推断为“不升级版本”，现已按用户更正。

## 自动化边界

- 正常批次：一次统一确认后自动完成下游升级、提交和推送。
- BridgeForgeCodex 自身存在变更：另行确认本仓库同步。
- 共性缺陷需要修改 BridgeForgeCodex：另行确认源码修复。
- Git 分叉、冲突、缺 upstream、验证失败或无法证明安全时：停止对应流程并交回主对话。
- 禁止自动 `git add`、手工拆分 fetch/commit/push、force push、reset、rebase、merge 或
  删除用户改动；Git 保存只能使用各仓库自己的 `$git-sync` 确定性入口。

## 实施与验证记录

- 实施计划：
  1. 新建项目专属编排 Skill，并以工厂身份、canonical origin、`main/origin-main`
     和 factory witness 组成调用硬闸；
  2. 新建只读预检与批次状态助手，只负责路径、Git 只读证据、共享 Git 分组、串行状态、
     异常签名和结论式输出；
  3. 主对话在每个目标的真实工作目录完整执行现有 `$bridgeforge-codex` 与目标自己的
     `$git-sync`，新助手不得复制升级、commit 或 push 能力；
  4. 增加自动测试，验证调用隔离、零固定清单、串行、异常隔离、共性阻断、全量重跑
     和默认输出边界；
  5. 独立复核通过后，再展示四个真实项目清单并取得一次统一执行确认。
- 实施记录：已完成项目专属 Skill、只读预检与批次状态助手、自动测试和仓库级
  CHANGELOG 记录；未把新能力加入公共 Skill、Template、routing 或 manifest。
- 自动验证记录（第 1 轮）：
  - `23` 项批量 Skill 与根 Skill 专项测试通过；
  - `278` 项全量单元测试通过；
  - 隔离下游 fixture 的 current init 幂等、旧项目确认重建和 current drift 零写阻断通过；
  - project structure、skill metadata、shared manifest、current baseline 与
    `git diff --check` 全部通过；
  - project structure 只报告既有归档 advisory，不影响本需求。
- 独立复核记录：首版发现 4 项 P1，分别是成功收据可由参数伪造、统一确认后缺少
  防漂移绑定、普通 Git 异常可能被误判为共性骨架问题、批次状态缺少真正互斥；已全部
  修复为现场验真、计划指纹、`bridgeforge:` 命名空间、Bug 文档与新工厂版本重启硬闸、
  全工厂单 active batch 和原子状态锁。
- 自动验证记录（第 2 轮，最终轮）：
  - `24` 项批量 Skill 与根 Skill 专项测试通过，`1` 项 Windows symlink 能力测试因当前
    环境无法创建 symlink 而条件跳过；
  - `279` 项全量单元测试通过；
  - 隔离下游 fixture 三项场景全部通过；
  - project structure、skill metadata、shared manifest、current baseline 与
    `git diff --check` 全部通过；
  - 已验证成功结论必须来自真实 baseline、版本戳、clean 工作区和 Git `0/0`，确认后
    漂移会阻断，Git 类重复异常不会触发共性骨架修复，原工厂版本无法绕过全量重跑硬闸。
- 四项目真实验收记录：待后续交付流程填写。
- 未完成风险：BridgeForgeCodex 尚未通过官方 `$git-sync` 发布，四项目真实端到端验收
  尚未开始；Codex Desktop 已在本会话发现该项目专属 Skill，但其他项目不可发现仍需在
  真实验收边界内确认。
