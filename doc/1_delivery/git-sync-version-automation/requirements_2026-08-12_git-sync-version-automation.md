---
status: implemented
date: 2026-08-12
source: direct user confirmation via $confirm
scope: git-sync automatic version bump for BridgeForge and downstream projects
---

# `$git-sync` 双版本域自动升级确认卡

## 原始需求摘要

BridgeForge 体系存在两个彼此独立的版本域：BridgeForge 骨架版本与下游项目业务
版本。用户要求 `$git-sync` 在创建新提交时自动升级当前仓库所属版本域，并保持
版本文件、原生项目版本字段与 CHANGELOG 一致。

## 目标

1. 下游项目执行 `$git-sync` 并创建项目提交时，自动升级项目版本。
2. BridgeForge 自身执行 `$git-sync` 并创建提交时，自动升级统一的骨架版本。
3. 严格分离下游项目版本与 BridgeForge 骨架版本，禁止互相推导或误改。
4. 自动维护本次版本对应的 `CHANGELOG.md` 记录。

## 不做

- `$git-sync` 不负责在下游更新 BridgeForge 受管骨架；骨架更新只允许通过
  `/bridgeforge` 流程完成。
- 不从冲突版本、模糊文件或任意搜索结果中猜测正确版本。
- 工作区没有需要创建的新提交时，不制造版本提交。
- BridgeForge 不再维护根、Codex 模板、Claude 模板三套独立版本与 CHANGELOG。

## 任务规模与预算

- **规模：M**。
- **判定依据**：逻辑改动横跨 `$git-sync`、版本发现与结构化同步、CHANGELOG
  生成、模板传播、既有版本迁移和回归验证；机械镜像、版本文件删除及 manifest
  更新不单独抬高规模。
- **时间预算**：45 分钟。
- **token 预算**：约 20k 新增 token，平台无可靠计量器，标记为未实测。
- **agent 预算**：0 个子 agent。
- **验证预算**：最多两轮验证。
- **超预算停止点**：若实施发现需要新的数据迁移契约、无法结构化同步某类原生版本
  文件，或预计超过两轮验证，停止并重新确认扩大预算或缩小范围。

## 已核实事实

1. 当前 BridgeForge `$git-sync` 不自动 bump；产品层变化缺少根 `VERSION` 改动时，
   `factory_version_check.py` 只会阻断。
2. 当前 BridgeForge 存在根 `VERSION`、`templates/codex/VERSION` 和
   `templates/claude/VERSION` 三个版本文件，并有三份 CHANGELOG。
3. 当前下游模板明确允许项目自行选择根 `VERSION`、`Cargo.toml`、
   `package.json`、`pyproject.toml` 或其他业务版本来源。
4. 当前下游通用 `version_check.py` 是未注册的退役兼容 no-op，不提供自动升级。
5. `/bridgeforge` 与 `$git-sync` 是不同流程：前者管理下游骨架，后者提交并同步当前
   仓库变更。

## 已确认业务规则

### 通用 bump 级别

- `fix`、`docs`、`refactor`、`chore` 提交自动 bump `patch`。
- `feat` 提交自动 bump `minor`。
- `feat!`、`fix!` 或提交正文包含 `BREAKING CHANGE:` 时自动 bump `major`。
- 调用 `$git-sync` 前即使人工修改过版本，本次仍按提交类型再自动 bump 一次。
- 只有本次 `$git-sync` 将创建新提交时才 bump；仅推送已有提交或检查干净同步状态时
  不 bump。

### 下游项目版本域

- 所有下游项目必须以仓库根 `VERSION` 作为项目版本唯一事实源。
- 下游可以在原生项目文件中保留版本字段，但必须与根 `VERSION` 同步。
- 自动识别常见原生版本字段，例如 `Cargo.toml`、`package.json`、
  `pyproject.toml` 及其锁文件；项目允许配置额外同步位置。
- 自动识别出现歧义、多个版本不一致或无法安全结构化修改时必须阻断。
- 既有下游首次没有根 `VERSION` 时，从唯一且明确的现有版本配置创建；找不到版本或
  存在冲突时阻断。
- 任何项目提交，包括纯项目文档提交，都必须 bump 项目版本。
- `$git-sync` 根据提交消息自动新增对应版本的项目 `CHANGELOG.md` 记录；文件不存在
  时自动创建。
- 下游日常开发和 `$git-sync` 禁止自行修改或更新 BridgeForge 受管骨架；只有
  `/bridgeforge` 可以更新受管骨架。
- 只有 `/bridgeforge` 骨架更新时，`$git-sync` 可以正常提交，但不得 bump 项目
  `VERSION` 或写项目 CHANGELOG。
- 骨架更新与项目改动混合存在时允许一起提交，并按项目改动 bump 项目版本；骨架
  版本戳仍只由 `/bridgeforge` 管理。

### BridgeForge 骨架版本域

- BridgeForge 全仓只保留根 `VERSION` 这一套骨架版本。
- 删除 `templates/codex/VERSION` 与 `templates/claude/VERSION`。
- `$git-sync` 只要在 BridgeForge 创建新提交，无论是产品层、元文档还是自身配置
  变化，都按提交类型自动 bump 根 `VERSION`。
- BridgeForge 只维护根 `CHANGELOG.md`。
- 删除 `templates/codex/CHANGELOG.md` 与 `templates/claude/CHANGELOG.md` 前，必须将
  根 CHANGELOG 缺失且仍有价值的历史记录去重合并到根 CHANGELOG。

## 数据映射

| 场景 | 唯一事实源 | 同步目标 | CHANGELOG |
|---|---|---|---|
| BridgeForge 新提交 | 根 `VERSION` | 无独立模板版本文件 | 根 `CHANGELOG.md` |
| 下游项目新提交 | 根 `VERSION` | 已识别原生版本字段及项目额外配置 | 项目根 `CHANGELOG.md` |
| 下游纯骨架更新 | `.codex/.bridgeforge_version` 或对应宿主戳由 `/bridgeforge` 管理 | 不改项目版本 | 不写项目 CHANGELOG |
| 无新提交 | 不变 | 不变 | 不变 |

## 拟修改范围

- BridgeForge 自身与 Codex 下游模板的 `.codex/scripts/codex_git_sync.py`。
- Claude 对应同步入口或共享实现，保证双宿主行为一致。
- 新增或重构可测试的版本发现、SemVer bump、原生字段同步及 CHANGELOG 生成逻辑。
- BridgeForge 根 `VERSION`、根 `CHANGELOG.md`、模板版本/CHANGELOG 文件及所有引用。
- 相关 init、update、switch、分发 manifest、规则、设计说明和回归测试。
- 根据工厂传播红线，同步产品模板、BridgeForge dogfood 与必要版本元数据。

## 验收标准

1. 下游 `fix` 项目提交自动将根 `VERSION` patch +1，并同步已识别原生版本字段和
   CHANGELOG。
2. 下游 `feat` 与 breaking change 分别正确执行 minor、major bump。
3. 人工预先 bump 后，`$git-sync` 仍按本次提交类型再 bump 一次。
4. 下游无根 `VERSION` 且只有一个明确现有版本时自动迁移；无候选或冲突候选时零
   提交并显示阻断原因。
5. 纯项目文档提交会 bump；纯 `/bridgeforge` 骨架更新不会 bump；混合提交会 bump
   项目版本。
6. 仅推送已有本地提交或干净 no-op 时不修改任何版本或 CHANGELOG。
7. BridgeForge 任意新提交按提交类型 bump 唯一根 `VERSION`，且仅写根
   `CHANGELOG.md`。
8. `templates/codex/VERSION`、`templates/claude/VERSION` 及两份模板 CHANGELOG 被
   删除，所有运行时、测试、manifest 和文档引用完成迁移。
9. 两份模板 CHANGELOG 中根 CHANGELOG 缺失的有效历史已去重合并，历史可追溯。
10. fetch / pull / stash 恢复发生在自动改版本之前；自动写入或 commit 失败时只精确
    回滚自动生成的版本、原生 manifest/lock 与 CHANGELOG，保留用户原始修改；push
    失败时保留已经创建的本地提交。
11. 完整 `$git-sync` 成功收据仍要求干净工作区及 `HEAD...@{u}=0 0`。

## 合理假设与风险

- 提交消息遵循已确认的 Conventional Commits 类型；未知类型的处理规则须在实现时
  采取安全阻断，不能静默猜测 bump 级别。
- 原生版本字段必须结构化解析；禁止无边界全文字符串替换。
- 自动同步锁文件可能需要调用项目原生工具；若无法确定安全、确定性的更新方式，
  必须阻断并报告缺少的项目配置。
- 人工 bump 后仍再次自动 bump 会产生连续跳号，这是用户明确选择的预期行为。
- 将现有下游迁移到根 `VERSION` 会改变 2026-07-30 确认的版本域契约，相关旧规则、
  设计和测试必须一起更新，禁止并存互相矛盾的说明。

## 自动化边界

- 自动化只能修改当前仓库内已确认的版本与 CHANGELOG 表面。
- 不自动运行 `/bridgeforge`，不把 `$git-sync` 扩张成骨架更新器。
- 歧义、解析失败、未知提交类型或同步失败必须 fail closed。
- 不自动 commit 或 push 本需求卡；后续提交同步仍由用户明确调用 `$git-sync`。

## 调用来源与后续交接

- **调用来源**：用户直接调用 `$confirm`。
- **后续交接目标**：待用户选择 `$develop`、`$debate` 或 `$collab` 后继续。

## 实施记录

- 新增双宿主共享的 `version_release.py` 与 `managed-skeleton.json`。
- `codex_git_sync.py` 在 fetch / pull / stash 恢复后、暂存前执行版本计划；只有新提交
  才 bump，纯骨架提交跳过项目版本，失败时精确恢复自动版本文件。
- BridgeForge 统一为根 `VERSION` / `CHANGELOG.md`，删除两套模板独立版本文件。
- 初始化、更新、workflow、git-sync skill、分发清单和回归测试已同步。

## 验证记录

- `python -m unittest tests.harness.test_downstream_version_sot tests.harness.test_bridgeforge_root_skill tests.harness.test_shared_skill_distribution tests.harness.test_git_sync_version_release`：36 tests，全部通过。
- `python tests/harness/run_downstream_fixture.py --case codex-git-sync`：通过；实际完成 `0.1.0 -> 0.1.1`、commit、push、clean、ahead/behind `0/0`。
- `test_git_sync_version_release` 追加 Rust workspace / Cargo.lock、人工预 bump 与混合骨架/项目变更覆盖后：6 tests，全部通过。
