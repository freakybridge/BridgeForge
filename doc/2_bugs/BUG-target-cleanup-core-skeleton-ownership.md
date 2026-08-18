---
status: product-fixed-awaiting-downstream-migration
severity: high
scope: bridgeforge-codex core skeleton ownership and target_cleanup retirement
reported_at: 2026-08-18
downstream: D:\Quant\StratusAgent
factory_head: 5a6c5564e3d828358c850113b856bcd4f74e15e0
product_version: 1.4.7
---

# BUG：`target_cleanup.py` 不应作为 bridgeforge-codex 核心骨架默认 hook

## 结论

`target_cleanup.py` 应从 bridgeforge-codex 核心骨架退役。它治理的是 Rust/Cargo
`target/` 构建产物，不是 Codex 协作、指令加载、事务同步或安全边界的通用能力。

“非 Rust 项目自动 no-op”只能降低运行时干扰，不能消除产品复杂度和默认权限：当前所有
下游仍会安装、注册、升级和测试一个能够后台删除构建产物的 hook；所有 Rust 项目还会在
未显式启用的情况下接受固定阈值、固定保留策略和特定 Cargo 目录假设。

推荐终态：

1. 核心 Template、dogfood、dispatcher 和 managed contract 退役该 hook。
2. 精确匹配已发布哈希的下游副本只按 retirement 事务和用户确认删除。
3. 修改版、归属不明版和项目扩展版必须逐字保留并报告，禁止同步器自动移动或吸收。
4. 需要该能力的项目改用项目所有的显式 hook，例如 StratusAgent 的
   `.codex/hooks/stratus_target_cleanup.py`。
5. 若未来多个 Rust 项目确认有共同需求，应另做显式启用的 Rust 扩展，不得重新放回核心默认面。

## 已核实环境

- 工厂仓库：`D:\Quant\BridgeForge`
- 工厂 HEAD：`5a6c5564e3d828358c850113b856bcd4f74e15e0`
- 产品版本：`1.4.7`
- 真实下游：`D:\Quant\StratusAgent`
- 下游模式：legacy `0.90.0` 更新至 `1.4.7` 的只读 planner 与逐项人工审计
- 当前下游结论：本地 `target_cleanup.py` 被 planner 报为
  `whole-file target is modified or has no trusted historical hash`
- 本报告只记录退役需求；未修改 BridgeForge 产品代码、版本或 CHANGELOG。

## 产品来源与当前传播面

产品历史已经明确记录该能力来自 StratusAgent：

- `CHANGELOG.md` 记载初始 hook 源自下游 Rust workspace 的 `target/` 膨胀事故。
- 后续 L2 deps hash 变体裁剪同样标记为 `来源 StratusAgent harvest`。
- dogfood 在非 Rust 工厂仓库中的价值被描述为持续验证“无 Cargo.toml 静默跳过”。

当前核心传播面包括：

| 层级 | 当前目标 |
|---|---|
| Template 实现 | `templates/hooks/target_cleanup.py` |
| 工厂 dogfood | `.codex/hooks/target_cleanup.py` |
| Template 调度 | `templates/hooks/hook_dispatcher.py` 的 `session-after` route 与 handler audit |
| dogfood 调度 | `.codex/hooks/hook_dispatcher.py` 的对应镜像 |
| 旧 hook 合并器 | `templates/scripts/hooks_merge.py`、`.codex/scripts/hooks_merge.py` |
| ownership contract | 两份 `managed-skeleton.json` 的 `codex.hook.target-cleanup` whole-file asset |
| 产品测试 | `scripts/tests/test_codex_hook_single_source.py` 的 route、workspace 与 mirror 测试 |

这说明该能力不是一个孤立文件，而是核心产品的安装、调度、所有权、dogfood 和测试组成部分。

## 为什么不属于通用骨架

### 1. 只服务 Rust/Cargo 构建产物

实现依赖 `Cargo.toml`、`target/**/incremental`、`target/**/deps`、crate hash 文件名和 Cargo
重建语义。纯 Python、Node、文档、通用 Codex 配置仓库都不消费该能力。

### 2. 默认包含删除副作用

该 hook 在 SessionStart 后台执行，达到阈值后会重命名并删除 incremental 目录，还会删除
deps 中较旧的 hash 变体。这些目标可再生不等于它们适合由所有下游默认授权给骨架删除。

### 3. 固定策略无法代表所有 Rust 项目

当前策略内置：

- 24 小时节流；
- incremental 30 GiB 阈值；
- 每个 crate 保留两个 hash 变体；
- deps 可回收至少 5 GiB 才执行；
- 默认 Cargo workspace 与 target 目录发现方式。

真实 Rust 项目可能使用 `CARGO_TARGET_DIR`、共享 target、sccache、交叉编译、只读 checkout、
CI cache 或不同磁盘预算。核心骨架无法在没有项目配置的情况下替这些项目做正确选择。

### 4. no-op 仍有长期成本

即使非 Rust 项目每次只检查后退出，产品仍必须维护模板、dispatcher route、contract、历史
hash、迁移、dogfood、测试和发布兼容性。no-op 没有减少系统活动部件，只是隐藏了运行效果。

## StratusAgent 真实下游证据

StratusAgent 的版本已经发展出骨架没有的项目策略：

- 项目所在磁盘低于 20 GiB 时，在 Cargo 前同步清理可再生 target 产物；
- 清理后仍不足则阻断 Cargo；
- 使用 lock 防止多个构建入口并发清理；
- 区分 `session-start`、`pre-tool`、`pre-cargo` 和 worker；
- 六个项目入口显式调用 `pre-cargo`；
- `scripts/tests/test_target_cleanup_hook.py` 覆盖低空间、阻断、lock、dispatcher 和调用方。

六个当前调用方：

1. `start.bat`
2. `start_dev.bat`
3. `scripts/bench-ib-latency.bat`
4. `scripts/run_platform_snapshot_probe.ps1`
5. `.codex/hooks/cargo_check.py`
6. `scripts/tests/option_analytics/fixtures/m2_32_quantlib_cross_validate.py`

这些是 StratusAgent 的构建与磁盘安全策略，不应反向进入所有 BridgeForge 下游。当前 whole-file
ownership 既不能安全吸收这些差异，也不能让项目把同名文件声明为自己的，最终表现为每次更新
持续 gap。

## 推荐退休设计

### A. 产品核心退役

1. 删除 `templates/hooks/target_cleanup.py` 与 dogfood 镜像。
2. 从两份 dispatcher 的 `session-after` route 和 `HANDLER_AUDIT` 移除该 hook。
3. 从两份 `hooks_merge.py` 的受管 hook 集合移除该文件。
4. 将 `codex.hook.target-cleanup` 从 whole-file asset 改为 retirement asset，保留所有已发布
   历史 SHA-256；禁止直接从 contract 删除 lineage。
5. 更新 hook single-source、project-sync retirement、mirror 和 fixture 测试。
6. 产品版本 bump，并在 CHANGELOG 以 `[product]` 明确说明自动 Rust target 治理已退出核心。

### B. 下游安全迁移

1. 目标不存在：no-op。
2. 目标哈希精确匹配已发布副本：生成受控 retirement 风险项，只有用户确认后删除。
3. 目标已修改或哈希未知：逐字保留并报告项目所有权迁移建议，禁止删除、覆盖、复制或改名。
4. 项目确认需要保留时，由项目在 BridgeForge 事务之外改名为项目专属 hook，并同步调用方、测试和
   项目文档；后续 planner 只看到旧受管目标已不存在。
5. 项目拒绝迁移时允许保留 gap；禁止为了写新版本戳伪装成 ready。

### C. StratusAgent 项目终态

StratusAgent 应把现有扩展收敛为项目所有的 `stratus_target_cleanup.py`，保留 Cargo 前低空间
检查、紧急清理、二次检查、阻断和并发保护；删除已经失效的通用 shell PreTool 解析。六个显式
调用方和专项测试同步改名。该项目迁移不属于 BridgeForge 产品事务，也不得被公共 Template
吸收。

## 非目标

- 本报告不要求立即删除任何下游修改版 hook。
- 本报告不把 StratusAgent 的 20 GiB 阈值、磁盘策略或调用入口上升为公共配置。
- 本报告不要求 BridgeForge 为所有语言设计统一构建缓存清理器。
- 本报告不把 `scripts/clean-target.bat` 当作现有自动保护的等价替代。
- 本报告不授权修改、提交或推送 BridgeForge 产品代码。

## 回归与验收场景

1. 新 init 的非 Rust 项目不再安装或注册 `target_cleanup.py`。
2. 新 init 的 Rust 项目同样不默认安装；除非项目显式提供自己的 hook，否则无自动删除行为。
3. update 遇到精确发布副本时生成 retirement 动作，未确认时零写入，确认后删除并在终态验证缺失。
4. update 遇到修改版时保持文件字节不变、报告 gap，且不写新版本戳。
5. 修改版经项目自行改名并更新调用方后，replan 不再报告旧受管目标。
6. dispatcher、hooks config、hooks merge、managed contract、Template 和 dogfood 不再引用该 hook。
7. contract 仍保留所有历史 hash，旧 `0.86.0+` 项目可证明合法退休来源。
8. StratusAgent 的低空间允许、清理后允许、清理后阻断、并发 lock 和六调用方测试全部通过。
9. factory dogfood、manifest `--check`、mirror drift、instruction source、project structure、完整
   fixture 和完整 unittest 通过。
10. 至少一个无修改受管副本和一个真实修改版下游完成 plan/apply/replan 验收。
11. 独立审计确认退休不会删除未知项目能力，也不会遗留 dispatcher 死路由。

## 六类关闭证据

| 证据类别 | 当前状态 | 关闭要求 |
|---|---|---|
| 源码 | 已验证 | Template/dogfood 文件删除，dispatcher route/audit 退役，hooks merge 保留 retired marker，contract 保存 retirement lineage |
| 产品传播 | 已验证本地发布树 | VERSION 1.4.8、CHANGELOG、两份 contract 与 active/compat manifests 已同步；尚未 commit/push 或刷新用户 product home |
| dogfood | 已验证 | 工厂不再携带或调度该 hook；mirror、instruction、metadata、structure 与 diff 硬闸通过 |
| fixture | 已验证 | 官方副本确认退休、修改副本保留及 `0.86.0+` 24/24 可执行迁移通过 |
| 真实下游 | 只读 planner 已验证，项目迁移未完成 | StratusAgent 修改版为 M1 gap、原样保留且无退休动作；仍需项目 hook 改名与六调用方验收 |
| runtime | 核心模拟已验证，真实项目未验证 | SessionStart dispatcher 测试证明核心不再启动 worker；StratusAgent 项目显式入口 runtime smoke 待完成 |

六类证据全部满足前，本报告不得标记 resolved。

## 当前恢复与回滚边界

- BridgeForge 仓库在报告前为干净工作树；本轮只新增本报告并同步文档索引。
- StratusAgent 当前修改版 `target_cleanup.py` 保持原样，本报告不触碰其代码或 target 目录。
- 正式修复必须由独立产品改动完成；失败时回滚 Template、dogfood、dispatcher、contract、测试、
  VERSION 和 CHANGELOG 的同轮修改。
- 任何真实下游验证必须在用户授权的工作树中进行，禁止对未知项目自动迁移项目 hook。

## 传播四问

1. 层级：这是产品层核心骨架 ownership 修复；StratusAgent 改名属于下游项目层。
2. 通用性：退役行为影响所有已安装该受管 hook 的下游，但 Rust 清理策略本身不具通用性。
3. 发布：修复需要 bump 根 VERSION，并在 CHANGELOG 标记 `[product]`。
4. dogfood：必须同步 Template 与 `.codex` 镜像、dispatcher、contract、hook merge 和测试。

## 关联记录

- `CHANGELOG.md`：初始 Rust target hook、L2 deps 裁剪及 StratusAgent harvest 历史。
- `doc/1_delivery/codex-project-zone-ownership/requirements_2026-08-17_codex-project-zone-ownership.md`
- `doc/1_delivery/codex-rule-runtime-simplification/`
