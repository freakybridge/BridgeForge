---
status: resolved-scope-clarified-project-remediation-pending
scope: downstream business version policy enforcement
source_project: D:\Quant\StratusAgent
incident_date: 2026-08-12
---

# 下游业务版本规则存在但提交链路未强制执行

## 结论

2026-08-12，StratusAgent 在完成资金与持仓面板展示修复后，通过 `$git-sync`
成功提交并推送了代码，但业务版本仍停留在 `1.4.3`。直到用户发现后，才补交
`1.4.4` 版本提交。

直接原因不是 `$git-sync` 失败，也不是 BridgeForge 覆盖了项目扩展，而是当前
StratusAgent 只有“提交前必须升级版本”的项目 Rule，没有对应的 pre-commit
硬闸。`version_check.py` 是 BridgeForge 提供的退役兼容空壳，`main()` 固定返回
成功；项目 `PROJECT_EXTENSION` 中也没有业务版本检查。因此 Rule 被漏执行时，
提交链路没有自动阻断。

本事件揭示的骨架问题不是“BridgeForge 应替所有项目自动升级版本”，而是下游
很容易把兼容空壳误认为有效保护，同时骨架没有清晰暴露“业务版本策略未安装强制
执行器”的状态。

## 2026-08-15 系统重构复核

- Codex `version_check.py` 未注册 no-op 已从模板与 dogfood 退役；已知受管历史副本只在单次 risk 确认后删除，人工修改副本保留为 gap。
- BridgeForge 只为 `version_release.py` 明确支持的版本源提供自动一致性；项目新增的自定义业务版本 Rule 必须同时提供项目自有 pre-commit/测试执行器。
- 删除误导空壳解决的是“虚假保护”；StratusAgent 是否已安装项目自有版本闸不属于通用模板自动写入范围，仍需项目侧补救收据。

## 事件经过

1. StratusAgent 修改了资金及持仓面板的美元字段名称、表头和数值格式。
2. 代码通过测试及 launcher 构建后，提交
   `b5d4959755dcd2c19ba8b137e094a9071c2317b2` 被推送到 `origin/master`。
3. 该提交没有修改 `stratus/Cargo.toml` 的 `[workspace.package].version`，版本仍为
   `1.4.3`，违反项目 `.codex/rules/workflow.md` 的提交前版本规则。
4. 用户发现版本未升级后，执行补救：版本改为 `1.4.4`，同步 `Cargo.lock` 和
   `CHANGELOG.md`，重新构建 launcher。
5. 补救提交 `29427c7273c8237e0f26af1be769075fab637ed7` 已推送到
   `origin/master`。

## 已核实证据

### StratusAgent 项目规则

`D:\Quant\StratusAgent\.codex\rules\workflow.md` 已明确规定：业务版本单一事实源是
`stratus/Cargo.toml` 的 `[workspace.package].version`；用户明确要求 commit 后，
必须在 commit 前按语义 bump 一次并重建受影响 binary；bump 时必须同步整理
`CHANGELOG.md`。因此规范本身已经存在，缺的是机器强制执行。

### 实际 Git pre-commit

`D:\Quant\StratusAgent\.githooks\pre-commit` 已具备
`BRIDGEFORGE_MANAGED` / `PROJECT_EXTENSION` 边界，但项目扩展目前只执行
`artifact_layout_check.py`，没有业务版本检查。

这说明 BridgeForge `0.82.2` 修复的“保留项目扩展”机制仍然存在且正常；本次不是
项目扩展再次被迁移删除，而是项目没有在扩展区安装版本闸。

### 兼容空壳

BridgeForge 模板和 StratusAgent 下游均包含 `.codex/hooks/version_check.py`，其
文档字符串明确标记为 `retired downstream version gate`，且 `main()` 固定返回
`0`。新模板也不注册该 Hook。该文件只用于避免旧配置在渐进升级时阻塞提交，不提供
任何业务版本保护。

### `$git-sync` 边界

`.codex/scripts/codex_git_sync.py` 负责 fetch、快进判断、暂存、commit、push 和最终
同步核验。它不负责理解 Rust workspace、选择 patch/minor/major 或修改业务版本。
这符合通用同步工具的职责边界，但也意味着项目必须在 commit 前另设版本策略闸。

## 根因分析

### 项目直接根因

StratusAgent 把业务版本要求写进了 Rule，却没有把它实现为
`PROJECT_EXTENSION` 内的 pre-commit 检查。Rule 依赖执行者记忆，遗漏时不会
fail-closed。

### BridgeForge 产品层暴露缺口

BridgeForge 正确地退役了通用版本自动递增，因为不同项目的业务版本事实源和发布
语义不同；但当前骨架同时保留一个名为 `version_check.py` 的空壳，且没有显式的
“项目业务版本策略：未安装 / 已安装”能力声明或诊断结果。下游维护者容易看到文件名
后误以为版本已有 Hook 兜底。

### 非根因

- 不是 `$git-sync` 漏执行步骤：通用同步脚本不应擅自修改业务版本。
- 不是 Git hook 未启用：其他 pre-commit 检查正常运行。
- 不是 BridgeForge 再次覆盖扩展：`PROJECT_EXTENSION` 边界仍然存在。
- 不是用户未要求提交：用户已显式调用 `$git-sync` 并授权推送。

## 责任边界

### BridgeForge 负责

1. 提供并保留 `PROJECT_EXTENSION` 机器边界。
2. update、adopt、init、switch 时不得覆盖项目业务版本逻辑。
3. 清晰标注 `version_check.py` 仅为退役兼容空壳，不能被计入有效保护。
4. 在健康检查或文档中暴露业务版本策略的能力状态，但不得替项目选择版本文件或
   bump 语义。

### 下游项目负责

1. 定义自己的业务版本事实源、bump 规则和 CHANGELOG 规则。
2. 若要求“每次业务提交必须升版本”，必须在 `PROJECT_EXTENSION` 中安装项目专属
   pre-commit 硬闸。
3. 为项目版本闸提供 staged-blob 场景测试，确保手动 Git、IDE 和 `$git-sync` 均受
   同一约束。

## 建议修复

### BridgeForge 产品层

1. 将退役空壳改名或在文件头、运行输出及设计文档中明确标记
   `compatibility-no-op`；若兼容期允许，后续删除未注册空壳，避免名称误导。
2. 为下游提供“项目扩展能力声明”范式，例如仅声明
   `business_version_policy = project-owned` 和检查器路径；禁止模板内置 Cargo、
   `VERSION` 或其他具体版本逻辑。
3. `config_health_check` 或独立诊断可以报告：
   `business-version-enforcement: not-declared / declared / broken`。未声明默认只提示，
   由项目是否采用强制版本策略决定是否升级为硬错。
4. 在 BridgeForge 文档中把“版本规范 Rule”和“版本执行 Hook”明确列为两件事，避免
   把文字约束误报成自动保护。

### StratusAgent 项目层

1. 新增项目专属业务版本检查脚本，从 staged `stratus/Cargo.toml` 读取版本，并与
   `HEAD` 比较。
2. 当 staged 业务代码或用户可感知文档发生变更，而版本没有按项目规则变化时，
   pre-commit 必须退出 `2`。
3. 检查 `CHANGELOG.md` 是否包含对应版本章节；是否已重建 binary 需要使用现有构建
   receipt 机制核验，不能只凭时间戳猜测。
4. 将调用放入 `.githooks/pre-commit` 的 `PROJECT_EXTENSION` 区块，保证
   BridgeForge 更新时原样保留。

## 验收场景

1. 仅修改 StratusAgent 业务代码，不改 workspace 版本：普通 `git commit` 被阻断。
2. 同样变更通过 `$git-sync` 提交：在 commit 阶段被同一 pre-commit 阻断。
3. patch 版本与 CHANGELOG 同步更新：版本闸通过。
4. 只有 BridgeForge 受管骨架文件变化：项目版本闸按项目定义 no-op，不擅自 bump。
5. 执行 BridgeForge update 或双宿主 switch 后，`PROJECT_EXTENSION` 内容哈希不变。
6. `version_check.py` 兼容空壳存在时，健康检查不得把它报告为有效业务版本保护。

## 与既有 Bug 的关系

本报告关联
[`BUG-migration-drops-project-pre-commit-extension.md`](BUG-migration-drops-project-pre-commit-extension.md)，
但根因不同：既有 Bug 是项目版本扩展原本存在、迁移时被覆盖丢失；本次事件是扩展
边界存在并被保留，但项目尚未安装实际版本闸。

两者共同说明：BridgeForge 负责可靠承载和传播边界，下游项目负责业务版本策略与
具体执行器；两边都不能只靠 Rule 文本代替运行时检查。
