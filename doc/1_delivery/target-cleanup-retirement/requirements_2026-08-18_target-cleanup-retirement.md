---
status: implemented-awaiting-user-acceptance
next: user_acceptance
size: M
confirmed_at: 2026-08-18
source_bug: doc/2_bugs/BUG-target-cleanup-core-skeleton-ownership.md
---

# bridgeforge-codex 核心 `target_cleanup.py` 退役

## 原始需求摘要

根据下游退役报告，将只服务 Rust/Cargo 构建缓存治理且包含删除副作用的
`target_cleanup.py` 从 bridgeforge-codex 核心默认骨架退役；官方旧副本通过统一
retirement 事务受控删除，修改版和项目扩展版逐字保留，由项目另行接管。

调用来源：用户审阅
`doc/2_bugs/BUG-target-cleanup-core-skeleton-ownership.md` 后要求先出计划，再明确选择开始实施。
后续交接目标：主对话实现、最多两轮验证和一次独立审计。

## 目标

1. 新 init/update 不再安装、注册、调度或测试核心 `target_cleanup.py`。
2. contract 保留 `0.86.0+` 已发布官方副本的可信 lineage，不把旧副本变成孤儿资产。
3. 精确匹配可信历史摘要的旧副本只生成一次 risk retirement 动作，经用户确认后删除。
4. 修改版、未知版和项目扩展版逐字保留并报告 gap，禁止自动覆盖、改名、移动或写新骨架版本戳。
5. 项目仍需该能力时，必须在 BridgeForge 产品事务之外改用项目专属 hook 名称和调用链。

## 不做

- 不自动修改、重命名、提交或推送 `D:\Quant\StratusAgent`。
- 不把 StratusAgent 的 20 GiB 阈值、Cargo 前阻断、lock 或六个调用入口吸收到公共 Template。
- 不设计新的全语言构建缓存清理器。
- 不把修改版 `target_cleanup.py` 视作可安全删除的官方副本。
- 不执行 Git commit 或 push。

## 规模与预算

- 规模：M。
- 判定依据：跨 ownership contract、dispatcher、旧 hook 合并器、同步器提示、测试和发布传播；
  Template/dogfood 镜像、版本、CHANGELOG 和 manifest 属机械传播，不单独抬高规模。
- 时间上限：45 分钟。
- Token 上限：20k 估算，平台无法实测。
- 子 agent：最多 1 个独立审计 agent。
- 验证：最多 2 轮。
- 超预算停止点：需要修改真实下游、引入新扩展架构、重构通用 retirement 协议，或第二轮修复后
  仍存在 blocker/high 时停止。

## 已核实事实

- 当前版本为 `1.4.7`。
- Template 与 dogfood 均包含 `target_cleanup.py`，dispatcher 的 `session-after` route 和
  `HANDLER_AUDIT` 均主动调度该文件。
- `templates/scripts/hooks_merge.py` 将该文件列为 active managed hook；已有
  `RETIRED_MANAGED_HOOK_NAMES` 可继续识别旧直接注册而不重新安装。
- `codex.hook.target-cleanup` 当前是 `whole` asset，current SHA-256 为已发布官方摘要，历史至少覆盖
  `0.86.0` 与 `0.90.0`。
- 统一同步器已有 fail-closed retirement：目标不存在 no-op；可信历史副本生成 risk；未知摘要生成
  gap；apply 前重算 fingerprint；ready 后最后写戳。
- 当前工作树已有用户新增的 Bug 报告和 `doc/README.md` 索引修改，本轮必须保留。

## 已确认规则

### 产品核心退役

- 必须先冻结当前官方摘要和历史 source，再删除 Template 与 dogfood 实现。
- dispatcher 必须同时移除 route 与 handler audit，禁止留下死路由。
- `hooks_merge.py` 必须把文件名从 active 集合移动到 retired 集合；禁止完全遗忘旧直接注册。
- contract 必须使用 retirement strategy、显式 target、historical source 和可信历史摘要；禁止删除 lineage。

### 下游安全迁移

- 文件不存在：no-op。
- 文件摘要精确命中可信历史：生成一个 risk retirement 项；未确认时零写入。
- 文件摘要未知、目标不是普通文件或 ownership 不明确：逐字保留并报告 gap。
- decline 或任一 gap 存在时不得写新 `.codex/.bridgeforge_codex_version`。
- 项目自行改成专属 hook 且旧目标消失后，BridgeForge replan 对该资产 no-op。

### 用户可见反馈

- 修改版 gap 必须明确显示目标文件、无法自动删除的原因、原样保留事实和项目专属改名建议。
- 可信官方副本必须与本轮其他 risk 合并到既有唯一确认卡，不增加第二次确认。

## 拟修改

- `templates/hooks/target_cleanup.py` 与 `.codex/hooks/target_cleanup.py`
- `templates/hooks/hook_dispatcher.py` 与 `.codex/hooks/hook_dispatcher.py`
- `templates/scripts/hooks_merge.py` 与 `.codex/scripts/hooks_merge.py`
- `templates/managed-skeleton.json` 与 `.codex/managed-skeleton.json`
- `scripts/bridgeforge_codex_project_sync.py`
- `scripts/tests/test_codex_hook_single_source.py`
- `scripts/tests/test_bridgeforge_codex_project_sync.py`
- `scripts/tests/run_downstream_fixture.py`（仅在 fixture 需要显式退休场景时修改）
- `scripts/rebuild_shared_skill_manifest.py`（仅在现有 historical source 重建能力不足时修改）
- `doc/0_architecture/design/skill-distribution-gaps.md`
- 本需求卡、源 Bug 报告、`VERSION`、`CHANGELOG.md` 和派生 manifests

## 验收

1. 新 init 的 Rust 与非 Rust 项目均不包含或调度核心 `target_cleanup.py`。
2. 可信官方副本生成 risk；decline 零写，confirm 删除，replan 不再出现动作。
3. 修改版保持文件字节不变、生成可操作 gap 且旧版本戳保持。
4. 项目专属改名后的文件、调用方和第三方 hook 不被 BridgeForge 接管。
5. dispatcher、hooks config、hooks merge、contract、Template 与 dogfood 无 active 引用。
6. contract 明确保留 `0.86.0+` 发布谱系，manifest 重建后 `--check` 为 current。
7. 定向单测、完整 fixture、完整 unittest、mirror、instruction、structure、metadata 与
   `git diff --check` 通过。
8. 至少一个可信旧副本 fixture 和一个修改版 fixture 完成 plan/apply/replan 验收。
9. 真实 StratusAgent 只读 planner 证明修改版仍为 gap、原字节和旧戳未变；若未获授权则明确未验证。
10. 独立审计确认未知项目能力不会被删除，且无 dispatcher 死路由。

## 合理假设与风险

- 将该能力移出核心是修正错误 ownership，不代表 Rust 项目不再需要磁盘治理。
- 若完全从 `hooks_merge.py` 忘记旧名字，历史直接注册可能残留；因此必须保留 retired marker。
- 若先删除 source 再重建 contract，可能丢失当前发布摘要；实施顺序必须先冻结 lineage。
- 项目修改版持续 gap 是预期安全结果，不能为了 ready 强行删除或伪造可信摘要。
- 产品发布建议为 `1.4.8 [product]`；若版本工具按仓库规则得出不同合法 patch 版本，以工具收据为准。

## 自动化边界

- 自动：冻结可信摘要、移除核心分发与调度、生成 retirement plan、事务删除官方副本、重建派生数据。
- 需用户唯一确认：可信官方副本的删除，与本轮其他 risk 合并展示。
- 禁止自动：修改版删除或改名、StratusAgent 业务迁移、未知 project hook 接管、commit/push。

## 实施记录

- `templates/hooks/target_cleanup.py` 与 `.codex/hooks/target_cleanup.py` 已删除；新 Template 与
  dogfood 均不再携带该实现。
- 两份 dispatcher 已从 `session-after` route 与 `HANDLER_AUDIT` 删除该 hook，审计编号收敛为
  连续 1-36。
- 两份 `hooks_merge.py` 已把 `target_cleanup.py` 从 active managed 集合移动到 retired 集合，
  保留历史直接注册清理能力但不再安装或调度。
- `codex.hook.target-cleanup` 已改为 retirement asset：无 current source/hash，保留
  `historical_source`、可信历史摘要和项目专属 hook 迁移提示。
- project sync 的通用 retirement 文案不再把所有资产误称为 no-op；修改版 gap 会显示
  “逐字保留并迁移为项目专属 hook”。
- 产品版本更新为 `1.4.8`，CHANGELOG 增加 `[product][repo][meta]` 退役说明；两份 contract 与
  active/compat manifests 已重建。
- 未写入、提交或推送 StratusAgent；其项目 hook 改名与六调用方迁移仍属于下游独立任务。

## 验证记录

- 退役定向回归：7/7 通过，覆盖 dispatcher、SessionStart、legacy hooks merge、contract、
  官方副本确认退休和修改版保留。
- 完整自动测试：`.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`
  为 245/245 通过。
- 完整 fixture：`.venv\Scripts\python.exe -B scripts/tests/run_downstream_fixture.py` 通过；
  `0.86.0+` 可执行迁移 24/24，其中 `1.4.7` 官方来源通过，published_count=29。
- `rebuild_shared_skill_manifest.py --check`、mirror drift、instruction source、skill metadata、
  project structure 与 `git diff --check` 均 exit 0；structure 仅输出既有 archive advisory。
- 真实 `D:\Quant\StratusAgent` 只读 planner：`target_cleanup.py` 仅产生 M1 gap，原因包含
  “preserve verbatim”和项目专属 hook 建议；无该资产 risk/action，旧版本为 `0.90.0`，未执行 apply。
- 第 1 轮验证暴露一处新增测试把 receipt asset-id 字符串当 Action，以及四个测试类名调用错误；
  修正后第 2 轮定向、全量与全部硬闸通过，未超过预算。
- 独立只读审计通过，blocker/high 为 0；另行验证 24 个 `0.86.0+` baseline 的该 hook
  摘要均精确命中可信历史，并确认 StratusAgent planner 前后目标哈希、legacy stamp 与 Git 状态不变。
- 真实 StratusAgent 项目改名、六调用方测试与 Codex Desktop runtime smoke 仍未验证，因此源 Bug
  继续保持 `product-fixed-awaiting-downstream-migration`，不得标记 resolved。
