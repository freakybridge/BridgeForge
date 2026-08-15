---
status: bridgeforge-resolved-downstream-business-recovery-pending
scope: bridgeforge migration and downstream pre-commit extension preservation
---

# BridgeForge 迁移遗漏项目专属 pre-commit 扩展

## 结论

BridgeForge 从 Claude 骨架切换到 Codex 骨架时，重写了下游项目的
`.githooks/pre-commit`，但没有保留其中明确标注为“项目专属、非
BridgeForge 模板管理”的版本递增步骤。结果是后续 `$git-sync` 能正常提交和
推送，却不再调用项目自己的 `scripts/bump_version.py`，项目发布版本停止递增。

这是迁移合并策略的缺陷，不是 Git hook 未安装，也不是 `$git-sync` 的运行失败。

## 影响

- 下游项目在成功提交功能或修复后，根 `VERSION` 可能保持旧值。
- 提交记录与程序实际版本失去对应关系，排查“已部署的是哪个版本”会得到错误答案。
- 项目专属 hook 扩展只要不在 BridgeForge 模板中，就可能在宿主切换或受管文件重写时被静默丢失。

## 已核实证据

1. 迁移前的 `.githooks/pre-commit` 同时包含 BridgeForge 的规则与 memory
   检查，以及项目专属的版本递增段：读取 `COMMIT_EDITMSG`，执行
   `scripts/bump_version.py`，随后 `git add VERSION`。
2. 该段的原有注释明确说明：它不属于 BridgeForge 模板管理范围，同步骨架时必须保留。
3. Claude 到 Codex 的迁移提交删除了整个版本递增段；迁移后的 hook 仅保留
   BridgeForge 管理的检查和 memory 索引重建。
4. 当前 `core.hooksPath` 仍指向 `.githooks`，其他 pre-commit 检查正常运行。
   因此问题不是 hook 没有被 Git 调用，而是被调用的脚本中已没有该项目扩展。
5. 当前 `$git-sync` 只做版本一致性检查、fetch、提交和 push；它不负责递增项目
   `VERSION`，所以无法弥补该遗漏。

## 2026-08-15 系统重构复核

- Codex 项目事务把 `.githooks/pre-commit` 定义为唯一显式 region ownership，只替换受管 marker 区域，`PROJECT_EXTENSION` 区域外字节保持不变。
- planner/apply/rollback fixture 已覆盖项目扩展保留与失败恢复。
- 低/高定制真实样本均已完成回滚演练和正式 apply；两份 `.githooks/pre-commit` 的 managed region 外归一化字节与各自 HEAD 一致，证明本次更新没有再次覆盖项目扩展。
- CausisRiskSuite 在旧事故中已经丢失的业务版本递增段不能由 BridgeForge 猜测恢复；BridgeForge 防复发已闭环，下游业务恢复仍需项目自身单独确认。

## 根因

现有迁移逻辑把 `.githooks/pre-commit` 当作可整体替换的受管文件，但该文件实际是
“BridgeForge 通用段 + 下游项目专属扩展”的组合面。迁移没有定义项目专属扩展的
保留边界、锚点或冲突处理，因此模板更新覆盖了本应保留的后缀。

白话说：BridgeForge 更换了下游的总闸门，但没有把门后面项目自己加装的编号器
一起迁过去；闸门仍在工作，编号器却不再接电。

## 已实施的源码修复（2026-08-03）

BridgeForge `0.82.2` 已在 Codex 与 Claude 两套模板的
`scripts/precommit_merge.py` 中实现受限的历史迁移：仅当无标记旧 hook 同时具备
以下证据时，才允许一次性转换为 `BRIDGEFORGE_MANAGED` /
`PROJECT_EXTENSION` 边界格式。

1. 历史段以 `Step 2: VERSION bump` 开始。
2. 段内调用 `scripts/bump_version.py`。
3. 段末为 `git add VERSION`。
4. `Step 2` 之前的完整受管前缀 SHA-256 逐字匹配冻结的 0.81 Codex 或 Claude 模板。

转换时，项目版本递增段按字节原样保留；新模板只替换受管通用段。任何前缀多出、
缺少或改写一个字节的无标记 hook，以及损坏标记或区块外自定义代码，仍会 `exit 2`
且零写入，避免把未知项目逻辑误认成可迁移内容。

同时已更新根产品版本 `0.82.2`、Codex/Claude 模板版本、CHANGELOG、BridgeForge
技能运行手册和回归夹具。

## 验证收据

- 两份 `precommit_merge.py` 均通过内存编译检查，且 SHA-256 完全相同。
- `tests/harness/run_downstream_fixture.py --case precommit-merge` 通过：带显式边界的
  扩展与受管前缀逐字匹配的历史版本递增段均逐字保留；未知无标记 hook 和历史段前
  插入项目命令的混合 hook 都被阻断；switch 不改根 hook。
- `tests/harness/run_downstream_fixture.py --case skill-refs` 通过：技能引用没有高置信
  缺失。
- `git diff --check` 通过。

## 仍待下游处理

该源码修复只能迁移“仍存在”的历史版本递增段，不能凭空还原已被旧迁移删除的项目
逻辑。CausisRiskSuite 当前 `.githooks/pre-commit` 不含旧段，也不含新边界标记，因此
不能自动恢复其版本递增行为。需要在该项目另行确认并恢复项目专属
`PROJECT_EXTENSION` 后，才可验证真实提交是否再次递增 `VERSION`。

## 修复要求

1. 已完成：为 `pre-commit` 定义机器可识别的项目扩展区，例如
   `PROJECT_EXTENSION_BEGIN` / `PROJECT_EXTENSION_END`。
2. 已完成：init、adopt、update 和 Claude/Codex switch 都必须保留该扩展区原文；没有可识别
   边界时，停止并报告冲突，禁止静默覆盖。
3. 已完成：BridgeForge 模板只维护通用段，不得把下游的版本策略、发布策略或其他业务 hook
   逻辑收编进通用模板。
4. 已完成：为迁移脚本补回归测试：输入带项目扩展的 pre-commit，迁移后必须逐字保留扩展；
   输入无法识别的自定义内容时必须阻断。
5. 已完成：在 CHANGELOG 中将该修复标为 `[product]`，并提升 BridgeForge 产品版本，使下游
   能识别到需要更新。

## 验收场景

1. 下游已有项目扩展的 pre-commit，从 Claude 切换到 Codex 后扩展仍存在且可执行。
2. 下游已有项目扩展的 pre-commit，执行普通 BridgeForge update 后扩展仍存在且可执行。
3. 下游 pre-commit 存在未标记的自定义内容时，迁移停止并显示冲突文件，不覆盖。
4. 只有 BridgeForge 通用段变化时，迁移后项目扩展的内容哈希保持不变。
5. 完成迁移后，分别运行一次普通 `git commit` 和 `$git-sync`，确认项目专属版本策略
   仍按其自身约定生效。

## 范围与非目标

本报告仅记录 BridgeForge 对下游项目 hook 扩展的保留责任。它不规定下游项目应当
采用自动版本递增、手动版本递增，还是完全不使用版本号；这些仍属于项目自己的
发布策略。
