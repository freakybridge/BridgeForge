---
status: completed
date: 2026-08-17
topic: codex-project-zone-ownership
source: confirm-via-develop
next: archive_candidate
scale: L
---

# Codex 项目专区与公共区 Ownership 需求卡

## 原始需求摘要

在 BridgeForgeCodex Template 的 `AGENTS.md` 中建立明确的公共区与项目级专区。下游项目只允许在项目专区、嵌套 `AGENTS.md` 和项目自有 hook 中维护约束，不得修改 BridgeForge 公共区；使用 `D:\Quant\CodexWorktree\test_bridgeforge` 与 `D:\Quant\CodexWorktree\test_bridgeforge_crs` 完成真实兼容验收。

## 目标

1. 根 `AGENTS.md` 使用机器可识别的双区域 ownership：BridgeForge 公共区与项目级专区。
2. BridgeForge 只更新公共区；项目专区由下游完全所有并逐字保留。
3. 下游对公共区的直接修改由 hook / pre-commit 阻断，并提示迁移到项目专区。
4. 目录专属约束使用 Codex 原生嵌套 `AGENTS.md`；项目 hook 使用项目自有文件名并通过 `.codex/hooks.json` 合并保留。
5. 旧下游无法安全分类时 fail-closed：保留原文、列出逐项迁移清单、不删除旧 rule、不推进版本戳。

## 不做

- 不重新引入 Markdown frontmatter `paths:` 指令加载器。
- 不把 `.codex/rules/*.md` 恢复为活跃运行时约束。
- 不修改两个样本的业务代码，不清理其既有 gap 或历史定制。
- 不安装或更新用户级 BridgeForgeCodex。
- 不执行 commit、push、reset、clean 或 worktree 清理。

## 任务规模与预算

- 规模：L。
- 判定依据：涉及公共指令架构、AGENTS ownership、schema、同步器、hook、历史迁移与两个真实高定制样本写入验收。
- 时间预算：4 小时。
- Token 预算：60k 新增 token 估算；平台不可实测，以范围、agent 数与验证轮次作为代理闸。
- Agent 预算：最多 3 个子 agent，分别用于只读 discovery、实现和独立审计。
- 验证预算：最多 4 轮。
- 超预算停止点：预计超过任一预算、扩大到用户级安装或真实非测试项目、或需要改变 ownership 规则时停止并重新确认。

## 已核实事实

- 当前 Template 已把 `### 1.1 架构红线`、`## 3 项目目录地图`、`### 4.2 快速命令` 标记为 project ownership，但项目内容分散，不是单一项目专区。
- 当前 Codex 原生指令只经根 / 嵌套 `AGENTS.md` 加载；Markdown `paths:` 不是指令加载机制。
- `.codex/hooks.json` 已使用 `codex-hooks` merge policy，能够保留非 BridgeForge dispatcher 的项目 handler；公共 dispatcher 冲突必须 fail-closed。
- 当前 retirement 依赖闸已保证 `root.agents` 存在 gap 时不会删除 8 个旧 rule。
- 两个指定 worktree 均为用户授权的测试副本；当前验收基线必须重新实时采集，历史收据不能代替本轮 before / after 证据。

## 已确认规则

### 双区域结构

根 `AGENTS.md` 必须包含以下精确边界：

```markdown
<!-- BRIDGEFORGE:PUBLIC:BEGIN -->
## BridgeForge 公共区
<!-- BRIDGEFORGE:PUBLIC:END -->

<!-- BRIDGEFORGE:PROJECT:BEGIN -->
## 项目级专区
<!-- BRIDGEFORGE:PROJECT:END -->
```

- 公共区由 BridgeForge 管理，下游禁止直接修改。
- 项目专区由项目完全所有，BridgeForge 禁止覆盖、删除、吸收或重新格式化。
- 项目专区可以补充或加强公共规则，禁止削弱公共红线；机器闸只执行结构与 ownership 校验，不声称能够自动证明自然语言语义无冲突。

### 项目专区内容

项目专区至少提供以下稳定子标题：

- `### 项目架构红线`
- `### 项目业务与安全红线`
- `### 项目目录地图`
- `### 项目快速命令`
- `### 目录级 AGENTS 索引`

前四项承接当前分散项目内容；目录级索引用于发现项目自有嵌套 `AGENTS.md`，不替代 Codex 原生层级加载。

### 约束分类

| 约束类型 | 唯一承载位置 | Ownership |
|---|---|---|
| BridgeForge 公共协作红线 | 根 AGENTS 公共区 | BridgeForge |
| 全项目业务 / 架构 / 数据 / 安全红线 | 根 AGENTS 项目专区 | 项目 |
| 目录专属行为约束 | 对应目录的嵌套 `AGENTS.md` | 项目 |
| 可机器判定约束 | 项目自有 hook + hooks.json handler | 项目 |
| 操作流程 | 项目 Skill | 项目 |
| 长说明、案例与事故复盘 | `doc/` | 项目 |
| 命令执行权限 | Codex 官方 `.codex/rules/*.rules` | 项目 |

### 更新与迁移

- 新项目只能在项目专区完成项目定制。
- 更新时只允许改动公共区；项目专区与嵌套 AGENTS 必须字节保持。
- 公共区被下游修改时，更新 planner 必须报 gap，逐项列出差异与迁移目标；禁止自动覆盖。
- 能精确识别的旧项目区内容迁入新项目专区；无法可靠分类的内容保留原文件并 fail-closed。
- 旧 Markdown rule 仅在替代语义已验证落地后才能退休；否则保留 rule 与旧版本戳。
- 任一结构歧义、验证失败、fingerprint 漂移或 apply 异常必须零写入或完整回滚。

## 数据映射

| 旧位置 | 新位置 |
|---|---|
| `### 1.1 架构红线` | `### 项目架构红线` |
| 项目业务、数据、风控与安全约束 | `### 项目业务与安全红线` |
| `## 3 项目目录地图` | `### 项目目录地图` |
| `### 4.2 快速命令` | `### 项目快速命令` |
| 路径限定行为规则 | 对应目录的嵌套 `AGENTS.md` |
| Markdown rule 长说明 | 项目 `doc/` 或 Skill |

## 拟修改范围

- `templates/AGENTS.md` 与根 `AGENTS.md` dogfood 结构。
- `templates/managed-skeleton.json`、`.codex/managed-skeleton.json` 与重建器 lineage。
- `scripts/bridgeforge_codex_project_sync.py` 的 AGENTS planner、apply、receipt、fingerprint 与 rollback。
- `templates/hooks/instruction_source_check.py`、dogfood 镜像、dispatcher / pre-commit 注册和相关测试。
- 原生指令架构、项目操作参考、README、CHANGELOG、VERSION / manifest（若发布规则要求）。
- `scripts/tests/**` 与下游 fixture。

## 验收标准

1. 新项目生成后公共区与项目专区边界唯一、完整、可机判。
2. 修改公共区会被 hook / pre-commit 阻断，并给出具体文件与迁移提示。
3. 修改项目专区、嵌套 AGENTS 或项目自有 hook 不触发公共区 drift。
4. BridgeForge 更新公共区时，项目专区、嵌套 AGENTS 与项目 hook 字节不变。
5. 旧项目三块 project-owned 内容无损进入项目专区；无法分类的内容保留为 gap。
6. 公共区漂移、边界损坏、fingerprint 漂移或注入失败时不写新版本戳并完整回滚。
7. 冲突清单在首次确认卡中完整列出，不要求用户第二次提问才看见文件。
8. 完整自动测试、fixture、manifest、instruction、mirror、metadata、structure 与 `git diff --check` 通过。
9. 两个高定制 worktree 完成 before hash、真实 apply、after hash、no-op / gap replan 验收：
   - `D:\Quant\CodexWorktree\test_bridgeforge`
   - `D:\Quant\CodexWorktree\test_bridgeforge_crs`
10. 两个样本不 commit、不 push；既有业务文件和项目约束无非预期变化。
11. 独立审计确认无公共区绕过、项目内容覆盖、错误 rule 退休或 stamp-last 回归。

## 合理假设与风险

- 精确 marker 与 heading 同时作为结构边界；重复、缺失、嵌套或顺序错误必须 fail-closed。
- 自然语言“项目规则是否削弱公共红线”无法由简单 hook 完全证明；本轮硬闸只保证公共区字节完整和项目内容落位，不虚构语义证明能力。
- 高定制样本可能包含既有 gap；兼容验收以保留项目资产、明确 gap、无误删和正确 stamp 为准，不以强制变成 `ready` 为目标。
- `test_bridgeforge_crs` 之前只能恢复到 Git 可见版本；本轮 before hash 是新的真实基线，不宣称还原更早未提交状态。

## 自动化边界

- 允许修改 BridgeForgeCodex 工作树内确认范围文件。
- 允许对两个指定测试 worktree 做计划、快照、apply 与复验；不得操作其分支、提交、远端或其他 worktree。
- 外部 worktree 写入必须使用精确路径、事务 fingerprint 与可回滚执行器；不得手工复制覆盖。
- 禁止自动 git add、commit 或 push。

## 实施计划

1. 只读 discovery：收敛 AGENTS section-layout、hook gate、schema lineage、迁移依赖和两个样本基线。
2. 实现 Template / dogfood 双区域结构、同步器 ownership 与硬闸，重建派生 contract / manifest。
3. 运行定向与完整测试、fixture、发布硬闸。
4. 对两个 worktree 记录 before → apply → after → replan 收据，最后独立审计。

## 实施记录

- Template 与工厂根 `AGENTS.md` 已改为唯一公共区 + 唯一项目专区；旧三块项目内容迁入专区，公共内容保持 Template 单一事实源。
- schema 新增 `agents_zones`：公共区 current/history exact hash、项目区稳定标题与旧章节迁移映射；旧 `section_layout` 仅保留为无 marker 项目迁移输入。
- 同步器对 marker 项目只替换可信公共区并逐字保留项目区；partial / duplicate / reversed / outside-content / public drift 均报 `root.agents` gap，继续阻断 8 个 rule 退休与版本戳。whole historical 快捷替换不再作用于 `root.agents`。
- `instruction_source_check.py` 已实现 PostEdit 提示、pre-commit 工作树 + staged blob 校验与旧无 marker 项目兼容；`version_release.py` 已区分 public / project / mixed。
- Template hook / release 脚本与工厂 `.codex` 三份镜像已逐字同步，contract / manifest 已重建并通过 current 检查。
- 产品版本已推进到 `1.2.0`，CHANGELOG、README、INSTALL 与原生指令 / 同步 / 操作指南已同步。
- 公共区的项目名归一化只作用于受管 `git clone … && cd …` 行；禁止用项目目录名全局替换公共文本，避免工厂目录名 `BridgeForge` 误伤品牌标题。

## 验证记录

- 定向修补复验：7/7 通过；覆盖旧 layout → 双区域迁移、渲染项目名保留、事务回滚、双版本戳、项目必填项、rule retirement 与 1.2.0 版本源。
- 完整自动测试：`.venv\\Scripts\\python.exe -B -m unittest discover -s scripts\\tests -p "test_*.py"`，227/227 通过。
- 下游 fixture：`.venv\\Scripts\\python.exe -B scripts\\tests\\run_downstream_fixture.py` 通过；初始化、legacy marker 与 19/19 个已发布版本迁移 / 二次 no-op 均为绿色。
- 发布硬闸：manifest `--check`、工作区 instruction、mirror、skill metadata、project structure 与 `git diff --check` 均 exit 0；structure 仅输出既有 archive advisory。暂存区 instruction gate 留待 `$git-sync` 精确暂存本轮文件后执行，本轮未擅自 `git add`。
- `test_bridgeforge` 真实 apply：共 6 个可信受管资产更新；首批 5 项更新时 2,342 个其他文件逐字哈希不变，项目 pre-commit extension、HEAD、分支不变；随后仅用精确 1.1.0 lineage 更新 `instruction_source_check.py`。旧戳 0.90.0 保留，风险戳迁移明确拒绝；最终稳定快照只读 replan 为 safe=0 / risk=1 / gaps=26 / root.gaps=1 / rule actions=0，样本 PATH Python 3.11 运行 hook exit 0。
- `test_bridgeforge_crs` 真实 apply：共 6 个可信受管资产更新；首批 5 项更新时 728 个其他文件逐字哈希不变，随后 instruction hook 单项更新时 732 个其他文件逐字哈希不变；项目 pre-commit extension、HEAD、分支不变。旧戳 1.0.0 保留；最终稳定快照只读 replan 为 safe=0 / risk=0 / gaps=17 / root.gaps=1 / rule actions=0，样本 PATH Python 3.11 运行 hook exit 0。
- 两个样本均为 `completed_with_gaps / degraded`，这是高定制旧结构 fail-closed 的预期兼容结果；没有 commit、push、分支切换或项目资产误删。
- 独立审计第一轮发现并已修复两项：带 marker 的 AGENTS 在 contract 缺失 / 损坏时曾 fail-open；无 marker 的高定制旧项目及未改 AGENTS 的普通提交曾被新 hook 误拦。现已分别改为 zoned 项目 fail-closed、legacy gap 项目兼容放行，并只在 staged AGENTS 与 HEAD 确实不同时检查 index。
- 独立审计第二轮发现并已修复两项：旧无 marker AGENTS 的文件前言或组标题下普通文字曾可能在迁移时丢失，现以 published residual hash 精确识别，未知内容整文件保留为 gap；项目专区代码围栏中的标题示例曾被误判为重复标题，现改用 fence-aware heading scanner。两项均有专门回归并包含在 227/227 完整测试中。
- 两个样本的旧 instruction hook 均由各自本地 managed contract 证明为同一官方 current hash；该精确哈希已作为 1.1.0 transition lineage 固化，未知 hook 仍保持 gap。
- 最终独立审计未发现剩余 Blocker、High 或 Medium；复核了 residual / fenced-heading 两项修复、两个样本 hook、最终 replan、branch / HEAD、Template / dogfood 镜像和需求卡收据，结论为可进入用户验收。审计未重复完整测试或真实 apply，复用了上列 227/227、fixture 19/19 与真实样本事务收据。
- 用户于 2026-08-17 明确调用 `$summary 同意验收`；本交付验收完成，后续仅作为 `$archive-scan` 候选，不在本轮自动归档。
