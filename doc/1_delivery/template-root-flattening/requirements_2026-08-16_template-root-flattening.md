# BridgeForgeCodex 模板根目录扁平化需求卡

## 状态

- 阶段：已实施，待用户验收
- 调用来源：用户确认计划后由 `$develop` 接管
- 规模：M
- 日期：2026-08-16

## 原始需求

Claude 骨架退役后，`templates/codex/` 已无宿主分流价值。将其中的 Codex 模板资产提升到 `templates/`，删除多余中间层，再继续 BridgeForgeCodex 自收养闭环。

## 目标

1. 将当前 `templates/codex/**` 扁平化为 `templates/**`。
2. 下游安装目标保持 `AGENTS.md`、`.codex/**` 不变。
3. 同步器、schema、hooks、文档和测试统一使用新模板根。
4. 保留所有 `0.86.0+` 已发布版本中旧 `templates/codex/**` 的可信 lineage。
5. 验证新目录协议不会破坏下游更新、dogfood 镜像和用户级分发。

## 不做

- 本轮不执行 BridgeForgeCodex 自身 `adopt/apply`。
- 不改变任何下游目标路径或 ownership 策略。
- 不重写历史 CHANGELOG、Bug、归档、旧需求卡和历史 memory 中的旧路径。
- 不 commit、push，不修改 GitHub 仓库名、origin 或本地仓库目录。

## 规模与预算

- 判定：M。核心逻辑是单一模板根协议变更，但横跨同步器、schema 重建、dogfood hooks、文档与测试。
- 时间预算：45 分钟。
- Token 预算：约 20k 新增 token，平台无可靠计量器，未实测。
- Agent 预算：最多 1 个独立审计 agent。
- 验证预算：最多 2 轮；第一轮定向验证，第二轮完整单测、fixture 与发布门禁。
- 停止点：旧 lineage 丢失、脏工作树内容无法安全迁移、必须改变下游目标路径，或预计超过预算。

## 已核实事实

1. `templates/codex/` 当前有 71 个受 Git 跟踪的产品资产；目录中另有可再生的 `__pycache__`。
2. 活跃代码、hooks、skills、测试和架构文档约有 31 个文件引用 `templates/codex`。
3. `scripts/bridgeforge_codex_project_sync.py` 固定从 `templates/codex/managed-skeleton.json` 读取 contract。
4. `scripts/rebuild_shared_skill_manifest.py` 固定使用旧 contract 路径，并从 asset `source` 回溯历史 hash。
5. 当前 contract 已保存 `0.86.0+` 历史 hash；扁平化不得机械清空或重算丢失这些值。
6. 历史 fixture 会直接读取历史提交中的旧 contract 路径，当前发布树则应读取新路径。
7. 当前工作树包含大量已确认但未提交的 1.0.0 改动，移动必须保留全部修改、删除和未跟踪产品文件。

## 已确认规则

- 新模板根为 `templates/`：例如 `templates/AGENTS.md`、`templates/hooks/`、`templates/rules/`、`templates/scripts/` 和 `templates/managed-skeleton.json`。
- `templates/codex/` 在活跃产品树中必须消失。
- 当前 asset `source` 使用 `templates/**`；已发布旧路径仅作为历史 lineage 保留。
- dogfood 对照改为 `templates/hooks/** ↔ .codex/hooks/**`，其他镜像路径同步扁平化。
- 只更新活跃说明；历史材料保留当时事实。
- 当前未发布版本继续归入 BridgeForgeCodex 1.0.0，并补充 CHANGELOG。

## 拟修改

- 移动 `templates/codex/**` 到 `templates/**`。
- 更新项目同步器与 manifest/schema 重建器的 contract/template 根路径。
- 更新 managed contract 的当前 source 路径并保留历史 hash。
- 更新 mirror、metadata 等 factory hooks 及 dogfood 镜像。
- 更新根 skill、README、AGENTS、活跃架构文档和测试。
- 新增活跃路径硬闸，禁止重新引入 `templates/codex`。

## 验收

1. 活跃产品文件和代码不再依赖 `templates/codex`。
2. `templates/codex` 不存在；下游目标路径保持不变。
3. 完整 Codex-only 自动测试通过。
4. 19 个 `0.86.0+` fixture 全部完成真实 apply 与二次 no-op。
5. manifest `--check`、skill metadata、project structure、mirror drift 和 `git diff --check` 全部通过。
6. BridgeForgeCodex 自身及两个高定制样本的只读 planner 能从新模板根完成规划。
7. 独立审计确认历史兼容、路径单一事实源和文档没有遗漏。

## 合理假设与风险

- 文件移动本身不改变模板内容，但 contract source 路径变化会影响历史 hash 枚举。
- 不能对全仓历史文档做机械替换，否则会破坏历史事实。
- `git mv` 必须在当前脏工作树上保留已修改文件；已删除的退役资产继续保持删除状态。
- 忽略的 `__pycache__` 只属于可再生缓存，可在确认的旧模板目录内清理。

## 实施计划

1. 受控移动模板资产，更新同步器和重建器路径协议。
2. 更新 contract 当前 source、factory hooks、skill、活跃文档与测试。
3. 重建派生清单，执行两轮验证和独立审计。

## 实施记录

- 已将 `templates/codex/**` 物理提升到 `templates/**`，并移除旧中间目录及其中可再生的 `__pycache__`。
- 项目同步器、schema/manifest 重建器、factory hooks、dogfood 镜像、根 skill、活跃架构文档与自动测试均已切换到新模板根。
- managed contract 的当前 `source` 已迁移为 `templates/**`；`historical_source` 和历史 Git blob 查询继续保留旧 `templates/codex/**`，用于识别既有发布版本。
- 对已经下发到高定制样本、但尚未进入 Git 发布历史的 pre-flatten 1.0.0 状态，按 LF-normalized 精确登记 1 份 contract 与 5 个资产 hash；仅这些官方字节可安全前进，未知改动仍保持 gap。
- 新增活跃旧路径防复发硬闸，覆盖模板、skills、完整 scripts/tests、dogfood、根 pre-commit、活跃架构/参考文档和根文件；仅对精确历史 Git blob、schema `historical_source` 与迁移识别代码放行。
- 下游目标仍为 `AGENTS.md` 与 `.codex/**`，本轮未运行任何 apply、未写两个高定制样本、未 commit/push。

## 验证记录

- 聚焦回归：53/53 通过，覆盖 hook 单一来源、模板 pre-commit、metadata 分发契约、项目结构与版本发布分类。
- 完整单测：`python -m unittest discover -s scripts/tests`，208/208 通过。
- 完整 fixture：19/19 个 `0.86.0+` 发布基线逐版真实 apply 与 no-op 通过；Codex init stamp-last 与 legacy marker 迁移通过。
- 发布硬闸：manifest `--check`、skill metadata、project structure、mirror drift、`git diff --check` 均 exit 0；project structure 仅报告既有归档建议。
- 审计修复后项目同步模块：41/41 通过；活跃旧路径硬闸通过。
- 只读 planner：BridgeForgeCodex 自身与两个高定制样本均 exit 0 并从新模板根完成规划；`test_bridgeforge_crs` 恢复为 `ready / safe=6 / gap=0 / blocker=0`，`test_bridgeforge` 的既有高定制 gap 继续保留；未执行写入。
- 独立审计：最终复审无 blocker、无 high，确认路径扁平化、pre-flatten 1.0 精确兼容、下游 target 稳定及防回退硬闸闭环。
