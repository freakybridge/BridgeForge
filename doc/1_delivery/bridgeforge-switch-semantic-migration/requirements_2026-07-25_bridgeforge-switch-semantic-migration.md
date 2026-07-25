# BridgeForge switch 项目级资产语义保全需求卡

> 状态：`implemented`
> 确认日期：2026-07-25
> 来源：用户在 BridgeForge switch 行为复核后调用 `$confirm` 的逐项确认
> 后续交接目标：实现 Claude / Codex 之间的项目级资产语义迁移，保证硬约束不会在 switch 后失效。

## 原始需求摘要

用户确认：`/bridgeforge switch claude|codex` 不能只把旧项目资产归档后停用。Claude 与 Codex 的 memory、rules、hooks、项目私有 skill、入口文件不能直接互拷，但其中承载的项目级约束不得丢失。

## 已核实事实

- 当前 `scripts/bridgeforge_switch.py` 会合并 memory，并按用户决策迁移部分 settings。
- 当前 hooks、rules、项目私有 skill、入口文件只归档，不写入目标骨架。
- Claude 与 Codex 的 hook 生命周期、输入通道、skill 格式、入口文件和配置格式不同，不能把来源文件直接复制给目标 agent。
- 当前旧 agent 骨架会归档到项目 `.bridgeforge/archive/<agent>/<timestamp>/`；目标骨架优先从项目归档恢复，没有归档才从目标模板安装。

## 已确认规则

1. 不直接复制 Claude / Codex 项目资产；逐项做“来源语义 → 目标平台原生实现”的转译。
2. 每个项目资产都先分析其语义，并分类为：可等价转译、纯平台细节不适用、或承载无法等价转译的项目硬约束。
3. 可转译项必须展示来源、目标位置和 diff；每一条都由用户确认后才写入目标骨架。
4. 项目硬约束无法获得可验证的目标等价实现时，阻断 switch。
5. 纯平台细节可保留在 archive，并在收据中标记“不适用”；不要求作为活跃目标约束迁移。
6. 每条硬约束必须有验证收据：可执行项运行测试或 hook smoke；纯文本项展示来源、目标位置与 diff，由用户确认。
7. 在全部硬约束转译、逐项确认、目标验证通过之前，旧 agent live 骨架保持原状；不得归档或删除。
8. 只有上述条件全部满足，才归档旧骨架、启用目标骨架并输出完整迁移收据。

## 拟修改范围

- `scripts/bridgeforge_switch.py` 与 Claude / Codex 模板镜像；
- `skills/bridgeforge/SKILL.md`、`skills/bridgeforge/references/switch.md`；
- switch harness 与迁移验证；
- 版本、CHANGELOG、需求卡与文档索引。

## 非目标

- 不把平台专属文件原样复制到另一端。
- 不跨项目扫描或迁移。
- 不自动 commit、push。
- 不把无法等价的硬约束静默降级成 archive。

## 验收标准

1. Claude→Codex、Codex→Claude 都生成逐项语义迁移计划。
2. 任一硬约束未确认、无法转译或验证失败时，旧 live 骨架内容不变。
3. 切换成功时，每项硬约束都有目标实现与验证收据。
4. 纯平台不适用项保留在 archive 并在收据中列出。
5. 切换成功后，目标骨架只包含目标平台原生文件，不含来源平台格式残留。

## 风险与约束

- “语义等价”不能由文件名或目录位置推断，必须逐项展示来源、目标实现与验证方式。
- hook 若承载项目硬约束但目标平台没有可验证等价实现，必须阻断，不能静默跳过。
- 每项用户确认前不得写入目标；任何阻断发生前，旧 live 骨架必须保持原状。
- archive 是恢复与审计资料，不是对活跃约束迁移失败的替代。

## 自动化边界

- switch 只作用于当前项目。
- 不读取或修改其他项目、用户级共享 skill 或运行时来源。
- 不执行 git add、commit、push、stash、merge 或 reset。

## 实施与验证记录

- 已实现 schema v2 proposal → approved manifest → stage / verify → transactional commit；当前目标模板为基线，archive 只机械重放 proven user-owned delta，旧 receipt、legacy archive、无 adapter 的 constraint-generated archive 与未满足 hard constraint 均 fail-closed。
- 已补齐 source / target ownership 分离、approved source-state backup/restore、detached/stage/live/archive exact-tree、target move journal、archive 排他 claim / rollback ownership（含预建空父目录保留）、Windows 路径/link/junction 硬闸和 `.bridgeforge_version` 完整安装。
- 当前无 trusted sandbox runner；任何 `evidence.command` 都直接阻断，`contract-smoke` / `native-host` 为 `sandbox-unavailable`，因此本版本只完成纯文本约束迁移。
- `python tests\harness\run_downstream_fixture.py`：43 项全部通过。
- `python tests\harness\test_shared_skill_distribution.py`：13 项全部通过；共享 manifest inventory / hash 与 JSON 解析通过。
- `git diff --check`：通过。
