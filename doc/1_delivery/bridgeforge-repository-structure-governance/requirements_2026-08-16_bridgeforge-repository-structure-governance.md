---
status: completed
size: M
---

# BridgeForge 文档与测试目录治理需求卡

## 原始需求摘要

整理 BridgeForge 仓库：解释并修复 `doc/` 未严格执行自身五层红线的问题；将工厂测试从 `tests/harness/**` 迁入 `scripts/tests/**`，并把测试目录规范下沉为所有 BridgeForge 项目的产品级约束。

## 目标

1. `doc/README.md` 继续作为文档目录唯一总索引，并由机器检查五层结构、delivery 布局、索引覆盖、非法散落文件和归档候选。
2. BridgeForge 自身测试统一迁入 `scripts/tests/**`。
3. 新项目禁止创建顶层 `test/`、`tests/`；测试代码统一放入 `scripts/tests/**`。
4. 既有下游检测到旧测试目录时只输出项目迁移行动，不自动移动、删除或改写任何文件。

## 不做

- 不在本轮批量归档 `doc/1_delivery/`、`doc/2_bugs/` 或 `doc/4_archive/` 历史材料。
- 不为每个 topic 生成重复、低价值的局部 README。
- 不改写历史需求卡、CHANGELOG 或 memory 中已经发生过的旧测试路径。
- 不继续处理高定制 AGENTS 自动迁移问题。
- 不自动 commit 或 push。

## 规模与预算

- 规模：M；跨越仓库结构、产品模板、同步器、受管 schema 和测试入口。
- 时间预算：45 分钟。
- Token 预算：约 20k，平台无可靠计量器，未实测。
- Agent 预算：0。
- 验证预算：最多 2 轮完整验收；同一验收集中的多条命令按一轮计算。
- 停止点：出现需要自动移动既有下游文件的新要求、第二轮修复后仍失败或范围升级为新的语言生态适配。

## 已核实事实

1. `doc/` 已有五个顶层目录，但没有 pre-commit 结构硬闸。
2. `doc/README.md` 的 topic 索引存在漏项，`4_archive/` 仍有旧式散放历史材料。
3. 归档扫描器需要用户确认，当前至少能识别一个候选；本轮只报告不移动。
4. 所有 BridgeForge 测试当前位于 `tests/harness/**`，该层由早期 harness fixture 演进形成。
5. 测试文件和 fixture 与仓库根目录保持两层相对深度；迁入 `scripts/tests/**` 后多数 `parents[2]` 定位不变。
6. shared manifest 逐文件登记产品脚本，不会因为新增 `scripts/tests/` 自动分发测试代码。

## 已确认规则

1. 产品级目标目录为 `scripts/tests/**`，禁止把 `test_*.py` 散放到 `scripts/` 根目录。
2. 约束下沉所有新项目和既有下游。
3. BridgeForge 仓库立即迁移；既有下游只收到迁移清单，不自动迁移。
4. `doc/README.md` 是唯一总索引；结构检查只读、fail-closed，不顺手修复或归档。
5. 历史验证收据保留原路径，只有当前运行入口、产品规则和可执行引用改为新路径。

## 拟修改范围

- `tests/harness/**` -> `scripts/tests/**`。
- `scripts/bridgeforge_project_sync.py` 的项目行动清单。
- Codex/Claude 模板入口、`rules/debugging.md`、`rules/modules.md`、`rules/meta_rule_design.md`。
- 产品级项目结构检查 hook、pre-commit 注册、managed schema、manifest 和 dogfood 镜像。
- `doc/README.md`、本需求卡、`CHANGELOG.md` 与相关当前运行手册。

## 自动化边界

- 结构检查不得移动、删除、改写目标文件。
- 下游旧目录只影响 `project_readiness`，不得伪装为骨架文件冲突或取得 ownership。
- symlink、junction、解析异常或无法确认的路径必须只报告，不递归进入外部目录。
- `--check`、dry-run 和 planner 必须零写入。

## 验收

1. 迁移后的原测试集通过，完整 downstream fixture 通过。
2. 新项目顶层 `test/`、`tests/` 被结构硬闸拦截。
3. 既有下游 planner 输出明确迁移行动，旧目录及内容逐字不变。
4. doc 结构检查能发现漏索引、非法顶层结构和归档候选，并在正常仓库通过。
5. manifest `--check`、mirror drift、harness parity、skill metadata 与 `git diff --check` 通过。
6. 当前 AGENTS 重构及 shared-skill model inheritance 既有改动不丢失。

## 实施记录

- 将原 `tests/harness/**` 整体迁入 `scripts/tests/**`，并更新所有当前执行入口；历史 CHANGELOG 与 memory 收据保持原样。
- 新增 Codex/Claude `project_structure_check.py` 产品 hook 和 BridgeForge dogfood 镜像，pre-commit 硬拦顶层 `test/`、`tests/`、doc 五层非法结构、漏索引与 reparse/path-escape；归档候选仅 advisory。
- `bridgeforge_project_sync.py` 对既有下游旧测试目录生成 `project_layout_migration` 行动，进入 `project_readiness=needs_user_action`，不取得 ownership、不自动移动或改写。
- 测试目录红线已写入 Codex/Claude 产品规则；Codex schema v2、共享 manifest、harness parity 与 0.95.0 CHANGELOG 已同步。
- 删除了两个已核实为空且不属于五层结构的目录 `doc/2_pending/`、`doc/3_design/`；未移动任何历史文档或归档候选。

## 验证记录

- `.venv\\Scripts\\python.exe -B -m unittest ...`：迁移后 `scripts/tests` 共 246 项，按模块/用例分批运行，246/246 通过；分批是为规避执行宿主对长 stdout 会话的中断，不是跳过用例。
- `.venv\\Scripts\\python.exe -B scripts\\tests\\run_downstream_fixture.py`：39/39 通过；同时修正 fixture 只信任冻结历史 pre-commit 字节，不扩大 legacy hash 白名单。
- `rebuild_shared_skill_manifest.py --check`、`harness_parity_check.py --check`、`mirror_drift_check.py`、`skill_metadata_check.py`：全部 exit 0。
- `project_structure_check.py --root . --json`：errors 为空；仅报告 4 个已关闭 delivery 和 16 个旧式 archive 文件，均未自动移动。
- 四份 `project_structure_check.py` SHA-256 一致；顶层 `test/`、`tests/` 均不存在；`git diff --check` exit 0。
