---
status: validating
scale: L
date: 2026-08-16
source: $confirm -> $develop
---

# Codex AGENTS 信息架构重组与安全迁移需求卡

## 原始需求摘要

重组 `templates/codex/AGENTS.md` 的章节和职责边界，降低重复与常驻上下文负担；同步处理受管标题迁移、项目必填区就绪硬闸、`ctx-budget` 产品能力退役，并用两个高定制 worktree 完成强制验收。

## 背景与目标

当前 Codex 模板 AGENTS 中，架构、目录地图、文档治理、Skill 清单、模型调度和 Debug 契约存在信息位置不直观或职责交叉的问题。标题又是 BridgeForge 受管区块识别的一部分，不能把本需求当作纯文案重排。

目标：

1. 形成稳定、可解释的 AGENTS 信息架构。
2. AGENTS 只常驻所有任务都必须知道的红线和索引，具体 SOP 下沉到 rule 或 Skill。
3. 已发布旧标题能够确定性迁移，高定制项目内容不丢失、不误覆盖。
4. 三个项目自定义区形成可执行的就绪硬闸。
5. 完整退役 `[ctx-budget]`，不遗留 hook、注册、schema、文档或测试入口。
6. 两个用户指定的高定制 worktree 全部达到完美更新状态。

## 不做

- 不使用标题相似度或语义猜测迁移未知章节。
- 不由 BridgeForge 编造项目架构、目录地图或快速命令。
- 不保留新旧两套重复章节。
- 不在 AGENTS 中重新维护具体模型名称或详细模型路由表。
- 不自动 commit 或 push。
- 不回退当前工作树中已完成的 shared-skill model inheritance 改动。

## 任务规模与预算

- 规模：L。
- 判定依据：涉及产品信息架构、受管 schema、历史标题迁移、下游状态语义、hook 退役和两个真实高定制项目验收。
- 时间预算：90 分钟。
- Token 预算：约 40k 新增 token，平台无可靠计量器，未实测。
- Agent 预算：最多 1 个独立审计 agent。
- 验证预算：原定最多 3 轮；2026-08-16 用户要求预算一次给足，当前任务上限统一调整为 10 轮。
- 超预算停止点：需要模糊标题推断、出现新的用户行为分叉、需要第 4 轮验证、第二个 agent 或预计超过既定时间时停止并回到用户确认。

## 已核实事实

1. 旧章节到新结构的映射完整，唯一明确删除项为旧 `#10`。
2. 规则索引表被 hook 机器读取，不能下沉为纯指针。
3. 当前 managed schema 以标题识别 Markdown 受管区块，全面重编号必须提供历史标题迁移。
4. `[ctx-budget]` 是有 hook、注册、schema、文档和测试串联的产品能力，不是单段说明。
5. BridgeForge 主工作树已有 shared-skill model inheritance 未提交改动，本需求必须兼容并保留。
6. 两个用户指定目录可访问；沙箱 Git 需要命令级 `safe.directory`，禁止修改全局 Git 配置。

## 实施前待核实事实

- 两个验收 worktree 的分支、工作区和 BridgeForge 版本基线。
- 当前工作树改动与本需求触及文件的逐文件重叠。
- 旧章节编号、`ctx-budget`、必填占位标记和 managed heading 的完整引用清单。

## 新信息架构

```text
1 项目基础约束
  1.1 架构红线
  1.2 专业表达风格
  1.3 工具与证据红线

2 BridgeForge 协作骨架
  2.1 规则文件索引
  2.2 Memory 项目内托管
  2.3 文档管理
  2.4 Skills

3 项目目录地图

4 开发
  4.1 换机首次启动 Checklist
  4.2 快速命令
  4.3 模型与 Skill 执行分工
  4.4 较大需求主动澄清 — [clarify]
  4.5 任务防漂移 — [focus]

5 Debug 与验证
  5.1 主观体验报告主动问范式
  5.2 鬼打墙觉察与渐进升级
  5.3 自改审计独立性
```

必须使用真实 Markdown 层级，不使用 `1.0`、`3.0`。

## 已确认职责边界

### 项目基础与地图

- 架构红线只管系统边界、核心不变量和禁止事项。
- 项目目录地图只管目录、模块和代码入口等事实。
- 文档管理只管文档分层、登记、流转和归档。

### BridgeForge 协作骨架

- 规则文件索引保留完整机器可读表格。
- Memory 与文档章节只保留 always-on 红线和索引，参数、冷热区、writer 细节和完整流程下沉到对应 Skill/rule。
- Skills 只说明可用能力、位置和调用方式。

### 开发

- 换机 Checklist 只放新环境首次执行一次的检查。
- 快速命令只放项目日常反复使用的启动、测试和检查命令。
- 模型与 Skill 分工只保留稳定边界：主对话负责用户确认和最终决策，Skill 定义工作流程，子 agent 负责适合独立执行或独立审计的阶段；具体模型和调度由 Codex 运行时决定。

### Debug 与验证

- 主观体验报告处理尚未形成技术结论的体验反馈。
- 鬼打墙觉察处理同一修复反复失败或无进展。
- 自改审计独立性处理实现者不能独自证明自己修改正确的问题。

## 项目必填区与双状态

以下三个区域必须由项目填写：

1. `1.1 架构红线`。
2. `3 项目目录地图`。
3. `4.2 快速命令`。

检测边界：只检查官方占位标记或结构性空内容，不对用户文字质量做语义评分。

仍未填写时：

- 已完成的安全骨架更新可以写入当前 BridgeForge 版本戳。
- 项目 `readiness` 必须为 `needs_user_action`。
- 收据必须逐项列出待填写区域。
- 禁止宣称项目已完美就绪。
- 再次运行不得重复应用已经完成的骨架更新。

## 历史标题迁移规则

1. 只识别 BridgeForge 历史正式发布过的精确旧标题。
2. 精确且唯一匹配时迁移标题、编号和结构，同时遵守既有 ownership，保留项目自定义内容。
3. 项目自定义标题、重复标题、解析歧义或映射不唯一时禁止猜测、禁止写入该区块，列为 gap。
4. 禁止模糊匹配。
5. 禁止通过追加新版章节造成新旧重复。

## `ctx-budget` 完整退役

同轮删除：

- AGENTS 中的常驻章节和引用。
- `[ctx-budget]` 信号与 `context_warning.py`。
- hook 注册、dispatcher 或 merge 入口。
- schema/manifest 中的受管资产登记。
- rules、Skill、设计文档中的运行契约引用。
- dogfood 镜像、fixture 和测试。

退役后不得出现失效入口或声称仍支持该信号的说明。

## 拟修改范围

- `templates/codex/AGENTS.md`。
- Codex managed schema、历史 lineage 和同步器。
- 读取规则索引或引用旧章节编号的 hooks 与 dogfood 镜像。
- 相关 rules、Skill 运行手册、设计说明。
- `ctx-budget` hook、注册、schema、fixture 和测试串联。
- manifest、parity、VERSION 和 CHANGELOG 等产品派生资产。
- 本需求卡与 `doc/README.md`。

具体文件以 discovery 结果为准；机械镜像不得扩张业务范围。

## 自动化边界与安全规则

- 更新仍遵守单事务、验证后写戳和失败回滚。
- 未知标题、解析歧义或 fingerprint drift 必须 fail-closed。
- 不修改全局 Git `safe.directory`；测试 worktree 使用命令级临时配置。
- 用户已授权直接修改两个专用验收 worktree并保留升级结果。
- 如果样本缺少必须由项目提供的真实内容，禁止编造；该样本不能判为通过，需报告用户输入卡点。

## 强制验收

### 仓库级

- 相关单测、集成测试和完整 downstream fixture 通过。
- manifest `--check`、mirror drift、harness parity、skill metadata、`git diff --check` 通过。
- 历史精确标题可迁移；自定义、重复和歧义标题零写入并列 gap。
- 必填区双状态、收据和 no-op 有确定性测试。
- `ctx-budget` 代码、注册、schema 和有效引用全部消失。

### 高定制 worktree 1

- 路径：`D:\Quant\CodexWorktree\test_bridgeforge`。
- 首次升级后：骨架版本为 current、`readiness=ready`、无 gap、定制内容无丢失或误覆盖。
- hooks、memory、rules 和文档验证通过。
- 第二次运行为 no-op。
- Git 差异只包含预期迁移结果。

### 高定制 worktree 2

- 路径：`D:\Quant\CodexWorktree\test_bridgeforge_crs`。
- 验收条件与高定制 worktree 1 完全相同。

两个项目缺一不可；任一失败，本需求不得标记完成或发布。

## 风险与合理假设

- 标题既是用户界面也是 schema 身份，遗漏 alias 会让高定制项目产生 gap。
- 直接退役 hook 需要同步清理四份产品/dogfood 承载面和派生清单。
- 当前已有未提交改动可能与模板 AGENTS、schema、测试和文档索引重叠；实施必须在现状上增量修改，禁止恢复或覆盖用户改动。
- 假设两个专用 worktree 不承载需要保留的未提交业务开发；实施前必须用只读 Git 状态核验。

## 后续交接目标

交给 `$develop`：完成 discovery、实现、仓库验证、两个高定制 worktree 验收和独立发布审计。

## 实施计划

1. 重组 Codex AGENTS 信息架构并登记逐章节 ownership、历史精确标题和项目必填区。
2. 扩展单事务同步器、发布所有权扫描器和 manifest 重建器；完整退役 `ctx-budget`。
3. 跑仓库硬闸、两个高定制样本的首次更新与二次 no-op，最后交独立 agent 审计。

## 实施记录

- 已完成模板 AGENTS 五章重组、三个项目必填区双状态和精确旧标题迁移。
- 已完成 `context_warning.py`、注册、dispatcher、schema、parity、文档和测试入口退役。
- 已扩展 `bridgeforge_project_sync.py`、四份 `version_release.py` 和 manifest 重建器，并重建 schema/manifest。
- 已修复验证中发现的 Markdown gap 仍发生同资产局部写入问题；现在该资产 fail-closed、逐字保留。
- 已同步 Hook handler audit 的退役后连续编号。

## 验证记录

- 第 1 轮：59 项定向测试因修改 `version_release.py` 后派生哈希未重建而失败；重建器按设计 fail-closed。
- 第 2 轮：59 项定向测试暴露旧断言和两个实现边界；已修正历史项目名归一化与 gap 零写入。
- 第 3 轮：完整 harness 238 项中 230 通过、7 个断言失败、1 个 `.runtime/harness` ACL 错误。失败中 6 项已按证据修正为当前章节、项目占位和退役编号契约；ACL 属验证环境。
- 第 4 轮：用户已批准。长任务两次被桌面 stdout/父子进程中断；改跑 7 组直接相关回归后，110 项中 108 通过，发现项目区末尾空格被迁移器裁剪，以及测试复用旧 fingerprint 两项问题。同步器已改为保留项目正文末尾空格，测试已在安全规范化后重新 plan；manifest 已重建。第 4 轮因此未通过。
- 第 5 轮：用户已批准。7 组直接相关回归 110 项中 109 通过；唯一失败确认布局组装层仍会裁掉项目正文末尾空格。已完成同一 bug 的第 2 次也是最后一次修补：布局边界只裁换行、禁止裁正文空格；manifest 已重建。
- 第 6-10 轮已一次纳入当前任务上限；仅同一 bug 两次修复仍失败、新增高风险决策或 10 轮耗尽时停止。
