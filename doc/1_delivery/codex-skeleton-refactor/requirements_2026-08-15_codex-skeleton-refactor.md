# 需求确认：Codex 骨架系统性重构

> 日期：2026-08-15  
> 状态：completed（用户已验收）  
> 调用来源：用户直接调用 `$confirm`  
> 执行路径：`$develop` 已完成；用户于 2026-08-15 明确执行 `$summary 同意验收`

## 原始需求摘要

近期多个下游项目持续出现“按下葫芦浮起瓢”的 BridgeForge Bug。用户要求完整审计并重构 BridgeForge，重点治理 Codex 骨架，解决已知问题，复核已有报告，并把可复用教训提炼为 AGENTS、rule、hook 和测试防线。审计期间 BridgeForge 又从 `0.86.7` 升级到 `0.90.0`，新增 Codex-only `create-worktree` skill 和 safe/risk/gap 单次确认协议，因此本卡以 `0.90.0` 当前事实重新确认。

## 目标

1. 对 BridgeForge 的 Codex 产品链进行受控破坏性重构，降低活动部件数量、耦合、派生数据一致性成本和重复实现。
2. 全量审计 11 条 Bug、活跃报告和本轮新发现；逐条区分当前仍存在、已修复、文档过期、无法复现或真实下游未闭环。
3. 允许重新设计内部契约和目录；保留 `/bridgeforge` 以及 `init`、`update`、`adopt`、`switch` 的用户调用入口。
4. 把 `create-worktree` 作为 Codex 一级产品面，覆盖源码、Codex-only 分发、AGENTS/路由登记、权限协议、失败恢复、Desktop smoke 和测试。
5. 为 `0.86.0+` 下游提供确定性升级；成功前禁止写版本戳，失败必须回滚，证据不足时 fail closed。
6. 将工厂特有约束留在自身配置，将跨项目通用的防错机制下沉到 `templates/codex` 并由工厂 dogfood。

## 不做

- 不重构 Claude 骨架；只处理共享实现导致的必要兼容影响。
- 不为 `0.86.0` 以前的下游新增自动迁移分支；旧项目只做只读诊断后转 adopt 或重新铺设。
- 不长期保留新旧双轨实现。
- 不以本轮重构为由增加无关产品功能或监管所有下游项目。
- 不直接在真实下游原工作区试验；只使用用户指定的隔离 worktree。
- 不清理样本仓库中既有的 prunable worktree 登记。
- 不自动执行 `git add`、commit、push、worktree prune 或其他清理动作。

## 规模与预算

- 规模：L。
- 判定依据：跨产品层、自身配置层和元文档；涉及架构、受管资产所有权、自动迁移、回滚、用户级 skill、Windows/Codex runtime 和两个真实下游。
- 时间预算：10 小时。
- token 预算：约 120k 新增 token；平台无可靠计量器，标记为未实测估算。
- agent 预算：最多 5 个子 agent；确认阶段已使用 2 个只读 agent，剩余最多 3 个。
- 验证预算：最多 6 轮；确认阶段已完成 2 轮有效验证，剩余最多 4 轮。
- token 代理闸：以 agent 数、验证轮次和范围增长判断。预计超过任一预算时必须停止，只让用户选择扩大预算或缩小范围。

## 已核实事实

### 当前基线

- BridgeForge 当前提交为 `3ab876c0b2570d8f8a716c18d29542468fc91087`，版本为 `0.90.0`。
- 相对先前审计基线 `b1e117d`，新增 6 个相关提交，涉及 42 个文件，约 2926 行新增、294 行删除。
- 当前主仓库位于 `main`，工作树无已列出的修改；实施必须创建隔离分支/worktree，不在 `main` 直接开发。
- 最近升级新增 `create-worktree`、safe/risk/gap 单次确认协议和第 11 条 Bug；原 10 条 Bug 文档没有随升级更新状态。

### 已识别的系统性缺陷

1. 文档或 Rule 声明了要求，但真实运行链没有对应执行器或唯一生效入口。
2. 上游受管资产和下游项目资产的 ownership 粒度过粗，更新时曾误覆盖整文件或丢失项目扩展。
3. 版本戳、完成态或显式 switch 的短路判断曾早于完整事务成功。
4. 测试 fixture 过于理想化，曾漏掉 Windows ACL、CRLF/autocrlf、BOM、Git 沙箱、受保护目录和真实 Codex payload。
5. Codex 特有宿主契约曾被 Claude 或通用宿主假设替代。
6. “源码已修”“模板已传播”“dogfood 已同步”“fixture 已过”“真实下游已验收”经常被合并成一个不诚实的 Fixed 状态。

### 当前新增审计发现

- `create-worktree` 已进入 Codex-only shared-skill manifest，且明确不分发到 Claude。
- `create-worktree` 已成为第二个用户级全局入口，但根 `AGENTS.md`、`templates/codex/AGENTS.md` 与两份 `skill-routing.json` 仍只单列 `bridgeforge`。
- Codex harness parity 报告仍为 `REVIEW`：Claude 有而 Codex 缺失 1 项、未登记 Codex-only 9 项、同名差异中 4 项仍为 `needs-review`。
- `skill_metadata_check.py` 正是本次新增 skill 触碰的组件，但其 Codex/Claude 语义差异尚未在 parity 分类中结案。
- `create-worktree` 的自动化测试覆盖 Git 创建、零写入预检、Unicode、路径冲突、reparse point 和 Desktop 协议失败；真实 Codex Desktop deep link 成功打开仍缺清晰现场收据。
- `0.90.0` 的真实 `prefix_rule` 持久时序、权限弹窗和 `/hooks` trust 仍未现场验证。
- `.codex/find-doc.map.md` 不存在，新 topic 只能依赖 grep fallback。
- 模板和 dogfood 的 Python hook 源码一致，但工作目录曾发现双方不同的 `__pycache__/*.pyc` 运行产物；发布/复制链必须确认不会携带这些缓存。

### 已知 Bug 审计范围

1. `BUG-switch-codex-left-claude-live-dir.md`
2. `BUG-git-sync-sandbox-permission.md`
3. `BUG-shared-skill-manifest-line-endings.md`
4. `BUG-summary-writes-global-memory-instead-of-project-memory.md`
5. `BUG-migration-drops-project-pre-commit-extension.md`
6. `BUG-downstream-business-version-rule-without-enforcement.md`
7. `BUG-bridgeforge-references-omitted-from-user-skill.md`
8. `BUG-update-stamped-before-memory-migration.md`
9. `BUG-codex-native-memory-empty-snapshot-reconcile.md`
10. `BUG-finalizer-timeout-protected-host-tempfile.md`
11. `BUG-create-worktree-sandbox-half-created.md`

### 确认阶段验证收据

- `.venv\\Scripts\\python.exe --version`：Python `3.12.9`，满足项目 Python ≥3.11 红线。
- 首次尝试 `python -m pytest ...` 因 `.venv` 未安装 pytest 而未执行测试；未安装新依赖，改用测试文件自身采用的标准库 `unittest`。
- `.venv\\Scripts\\python.exe -m unittest tests.harness.test_create_worktree_skill tests.harness.test_bridgeforge_root_skill tests.harness.test_shared_skill_distribution tests.harness.test_skill_metadata_budget tests.harness.test_memory_native_sync`：89 项通过。
- `.venv\\Scripts\\python.exe tests\\harness\\run_downstream_fixture.py`：默认沙箱因 `.runtime/harness` 权限失败；经用户批准在沙箱外运行后，37 个完整下游场景通过。
- `.venv\\Scripts\\python.exe scripts\\rebuild_shared_skill_manifest.py --check`：manifest 当前。
- `.venv\\Scripts\\python.exe .codex\\hooks\\mirror_drift_check.py`：exit 0。
- `git diff --check`：exit 0。
- 上述测试后主仓库仍无已列出的 Git 修改。

## 已确认规则

### 兼容与接口

- 采用受控破坏性重构：内部契约可重写，但必须提供迁移、回滚和真实下游验证。
- `/bridgeforge`、`init`、`update`、`adopt`、`switch` 的用户入口保持不变。
- 自动迁移只保证理解 `0.86.0+`；版本戳只是候选证据，不能替代真实资产审计。
- `create-worktree` 保持 Codex-only 和 Windows-only，不扩展到 Claude、macOS 或 Linux。

### safe / risk / gap

- `safe`：所有权、目标和结果均可机器证明，幂等且无需业务判断；零业务确认自动执行。
- `risk`：删除、移动、首次外部授权等影响明确、可恢复且需要用户决定的动作；全轮只生成一张汇总卡并确认一次。
- `gap`：人工修改、低置信 ownership、冲突、损坏账本或来源不可信；原样保留，不转成 risk，不开启第二轮逐项追问。
- apply 前必须重跑 planner 并核对 aggregate fingerprint；漂移时风险动作零写入。
- 任一步失败必须回滚本事务拥有的写入；未完成所有验证前禁止更新版本戳。

### 精简原则

- 允许删除、合并重复、失效或低价值的 hook、rule、script 和派生状态。
- 删除前必须证明替代链路、迁移结果、可观察性和回滚边界。
- 默认选择活动部件更少、单一事实源更清晰、下游定制保护更强的方案；不以最快实现为标准。

## 数据与证据映射

每个已知或新发现问题必须记录以下独立状态，禁止用一个 `Fixed` 覆盖全部层次：

| 维度 | 必须记录的证据 |
|---|---|
| 当前状态 | 可复现、已修复、文档过期、无法复现或阻塞原因 |
| 根因 | 真实入口、ownership、事务或宿主契约证据 |
| 源码 | 修改文件和行为断言 |
| 产品传播 | `templates/codex` / `skills` 的下沉状态 |
| dogfood | `.codex` 镜像与工厂自身运行状态 |
| 迁移 | `0.86.0+` planner、fingerprint、apply 和回滚 |
| fixture | 单元/集成场景及退出码 |
| 真实下游 | 低/高定制样本的资产保留、runtime 和 Git diff |
| 文档 | Bug、需求、设计、验收和 README 状态同步 |

## 真实下游样本

### 低定制样本

- 路径：`D:\Quant\CodexWorktree\testBridgeForgeCausisRiskSuite`
- 分支：`codex/testBridgeForgeCausisRiskSuite`
- 骨架版本：`0.90.0`
- 初始 `git status --short`：无已列出的修改。
- 源仓库另有 `D:/Quant/CodexWorktree/causis_risk_suite_2` 的 detached/prunable 登记；不属于本测试事务，禁止 prune 或删除。

### 高定制样本

- 路径：`D:\Quant\CodexWorktree\testBridgeForgeStratusAgent`
- 分支：`codex/testBridgeForgeStratusAgent`
- 骨架版本：`0.90.0`
- 初始 `git status --short`：无已列出的修改。
- 源仓库另有 `D:/Quant/CodexWorktree/7f86/StratusAgent` 的 detached/prunable 登记；不属于本测试事务，禁止 prune 或删除。

### 样本操作边界

- 开始任何写入前重新运行 `git branch --show-current`、`git status --short`、`git worktree list --porcelain` 和版本戳检查。
- 只修改两个已确认的测试 worktree；禁止修改原项目工作区、其他 worktree 或用户级 Git 状态。
- 不自动 commit、push、prune、remove、delete 或 reset。
- 每轮结束核对 branch、HEAD、status 和 diff；失败时按本事务明确记录的恢复边界回滚。

## 拟修改范围

### 产品层

- `templates/codex/**`
- `skills/bridgeforge/**`
- `skills/create-worktree/**`
- shared-skill manifest 及其确定性生成/分发入口
- 与 Codex 更新、迁移、finalization 和 harness 直接相关的共享脚本

### 自身配置层

- `.codex/**`
- `AGENTS.md`
- 必要的 `.githooks/pre-commit` 或工厂专属检查

### 元文档与发布

- `doc/1_delivery/codex-skeleton-refactor/**`
- `doc/2_bugs/**` 的事实状态和验收记录
- `doc/0_architecture/design/codex-harness-parity.md` 及直接关联设计
- `doc/README.md`
- `CHANGELOG.md`、根 `VERSION`

具体源码文件必须以实施前代码审计为准；本卡不授权把 Claude 骨架扩大为重构对象。

## 传播四问

1. 层级：本需求同时涉及产品层、自身配置层和元文档，必须逐项区分 ownership。
2. 通用改进：必须写入 `templates/codex` 或共享 `skills`；工厂专属约束不得污染下游模板。
3. 发布：产品层变化必须 bump 根 `VERSION`，并在 `CHANGELOG.md` 使用 `[product]` / `[repo]` / `[meta]` 标签。
4. dogfood：任何确认进入产品层的 Codex hook/settings 变化必须同步 `.codex`；两侧 Python 正文逐字一致，命令使用项目 `.venv/Scripts/python.exe`。

## 验收标准

1. 11 条 Bug、活跃报告和新发现全部有明确、可追溯的最终分类。
2. Codex harness parity 中缺失、未登记和 `needs-review` 项全部说明为补齐、明确豁免或已分类，最终报告不保留无解释的 `REVIEW`。
3. 每项核心职责只有一个事实源、一个受管 ownership 契约和一个真实生效入口。
4. `0.86.0+` 升级具备幂等 planner、fingerprint 重检、失败回滚和延迟写版本戳。
5. 两个真实样本均完成升级、重复运行和失败回滚；业务资产、第三方 hook、项目版本及人工定制保持不变。
6. Windows ACL、受保护目录、CRLF/autocrlf、BOM、Git 沙箱、reparse point、路径逃逸和真实 hook payload 均有对应场景。
7. `create-worktree` 补齐 AGENTS/路由登记、Codex-only 分发、权限提升前置、半成功语义和真实 Desktop deep-link smoke。
8. `/bridgeforge` 的 safe/risk/gap 契约在 init、adopt、update、switch 四模式均有零确认安全路径、单次 risk 卡和 gap 保留测试。
9. `/hooks` trust、真实 Codex 新会话和权限时序不能完成现场验证时，必须明确标记未验证，禁止用静态测试冒充。
10. 新增 AGENTS/rule/hook 只写机器可执行红线；rule frontmatter 带机器可解析 `paths:`；事故叙事留在 Bug/设计文档。
11. 所有“验证通过”收据必须同时列出真实命令、退出码、断言和覆盖场景。
12. 实施结束后主仓库和两个样本分别提供 `git status`、`git diff` 与未提交变更清单；不自动 commit 或 push。

## 合理假设与风险

- 历史 Bug 状态可能过期，必须以当前源码、当前文档和复现结果交叉验证。
- `0.86.0+` 版本戳可能与资产真实状态不一致；ownership 不能只靠版本字符串推断。
- 用户指定的样本当前干净且为 `0.90.0`；后续若发生外部修改，必须重新确认基线。
- 真实 Codex Desktop、hook trust 和用户级权限可能需要用户现场操作或窄权限批准。
- 两个源仓库已有的 prunable 登记是外部既存状态，不得将其误判为本轮失败成果或自动清理对象。
- `create-worktree` 对任一 reparse ancestor fail closed 可能拒绝部分合法路径；重构必须明确保留、收窄或替代该契约。
- 若审计证明必须自动兼容 `0.86.0` 以前结构、重构 Claude 骨架或增加第三个真实样本，视为范围增长并触发预算硬闸。

## 自动化与权限边界

- 用户已在确认卡完成后选择 `$develop`；产品实现与仓库内验证已获授权，外部样本 risk 仍按唯一汇总卡确认。
- 确定性、项目内、幂等 safe 动作可零业务确认；外部用户目录、首次授权及 destructive risk 遵循平台和项目安全确认要求。
- 未取得对应授权时禁止修改用户级 config、rules、native memories、hook trust 或其他项目。
- 实施测试优先使用临时目录、隔离 fixture 和用户指定 worktree；禁止把测试残留清理扩大到其他 worktree。
- 不自动 `git add`、commit 或 push。

## Discovery 结论与目标架构

当前结构性根因不是某个单独 hook，而是 `init/adopt/update` 仍由 agent 按多份 Markdown 手册人工串联复制、merge、memory 审计和 finalizer。safe/risk/gap 与 aggregate fingerprint 只存在于自然语言契约，没有单一程序负责逐资产 ownership、统一计划、跨步骤回滚和延迟写戳。

目标架构只保留五个执行域：

1. 用户级分发事务：`bridgeforge_shared_update.ps1` + `shared-skill-manifest.json`。
2. 项目骨架事务：新增唯一 `bridgeforge_project_sync.py`，统一 Codex `init/adopt/update`。
3. 双宿主投影：唯一 canonical `scripts/bridgeforge_switch.py`。
4. 用户级 native memories：`scripts/codex_memory_sync.py`。
5. 永久 worktree：`skills/create-worktree/scripts/create_worktree.ps1`。

项目骨架事务固定为：

```text
detect -> load asset contract -> plan safe/risk/gap
       -> aggregate fingerprint -> optional single risk confirmation
       -> replan/recheck -> stage/apply owned writes
       -> validate hooks/config/memory/ownership
       -> ready 时 write stamp last；degraded 保留旧戳/无戳 -> receipt
       -> caught failure restores every owned pre-state
```

`templates/codex/managed-skeleton.json` 升级为逐资产 schema v2，记录 stable id、source、target、ownership strategy、当前 hash、`0.86.0+` 可识别历史 hash和 retirement 策略；禁止继续用 `hooks/*.py`、`scripts/*.py` 等 glob 代表 ownership。

高置信精简项：

- 退役 Codex `model_policy_check.py` 与 `version_check.py` 两组未注册 no-op，并以历史受管 hash 安全迁移存量下游。
- 删除 `run_downstream_fixture.py` 中未进入 `CHECKS` 的旧 model/subscription routing 死测试。
- 修正 `hooks_merge.py` 关于写版本戳的过期说明。
- 将 create-worktree 登记为第二个 `global_entries` 主对话 skill，并反转“不得出现在 routing”的旧测试。
- 将 harness parity 的 1 个预期缺失、8 个有效 Codex-only、1 个应删除 no-op 和 4 个差异逐项结案。
- `skill_metadata_check.py` 的通用治理逻辑不得只存在于 Codex；共享语义同步到 Claude，宿主差异单独保留。

## 实施计划

- [x] 建立 `codex/codex-skeleton-refactor` 独立开发分支并复核预算。
- [x] 完成 Codex 产品链、11 条 Bug、harness parity 与 create-worktree 的只读源码审计。
- [x] 确定五执行域目标架构、schema v2 ownership 合约和删除/合并清单。
- [x] 实现 `bridgeforge_project_sync.py`、schema v2 planner/apply/rollback/receipt 和 `0.86.0+` 迁移。
- [x] 压缩 `bridgeforge` Codex 路径为薄编排，统一 init/adopt/update 的真实入口。
- [x] 登记 create-worktree 全局入口并结案 harness parity 差异。
- [x] 退役 no-op/死代码并同步 Codex 模板与 dogfood；Claude 仅同步通用 hook 语义。
- [x] 更新 11 条 Bug 状态、架构设计、版本、CHANGELOG、manifest 和 README。
- [x] 完成仓库测试、双真实样本与独立审计；Codex runtime smoke 独立保留为未验证边界。

## 验证记录

- [x] 单元与静态检查。
- [x] 完整下游 fixture。
- [x] 低定制样本升级/回滚/重复运行。
- [x] 高定制样本升级/回滚/重复运行。
- [ ] Codex Desktop、hook trust 和新会话 smoke。
- [x] 独立 review-auditor 复审。

## 2026-08-15 实施记录

### 已落地架构

- `scripts/bridgeforge_project_sync.py` 成为 Codex `init/adopt/update` 唯一 apply 入口。
- `templates/codex/managed-skeleton.json` 与 dogfood 使用 schema v2：68 个显式资产、62 whole、2 merge、1 region、3 retirement，无 glob ownership。
- memory canonical auditor 的明确/高置信迁移进入统一 risk 决策；ambiguous 结果保留为 gap；memory tree 在验证/写戳失败时恢复原路径与字节。
- switch 调用收敛到 command bundle 根 `scripts/bridgeforge_switch.py`；Codex template/dogfood 项目副本退役。
- manifest 重建器保留历史 lineage，并从 Git 的 `VERSION` 变更提交枚举全部实际 `0.86.0+` 发布版本；`--check` 零写入。
- `skill_metadata_check.py` 硬拦 Codex 分发集合、routing 集合、routing 双镜像和 global entry 的双 AGENTS 登记漂移；工厂 SoT 缺失或 hook 自身异常均 fail closed。
- 新增工厂专属 `.codex/rules/bridgeforge-product-change.md`；通用资产仍只进入产品层，工厂规则未下沉。
- 版本升至 `0.91.0`；11 条 Bug 分别标记源码、传播、fixture、真实下游与 runtime 状态。

### 仓库验证收据

- 主验证组运行 112 项：全部通过；覆盖 schema v2、历史 lineage、planner/apply/rollback、memory risk、reparse/path escape、skill 分发、routing、版本域和 hook 单一事实源。
- git-sync/schema v2 修复组运行 20 项：全部通过；完整 downstream fixture 首轮除 `codex_git_sync_runner` 外全部通过，修复 `version_release.py` 的 schema v2 兼容后该 case 与完整 fixture 复跑通过。
- harness parity：`OK`，缺失 0、未登记 Codex-only 0、未分类 0。
- manifest `--check`、parity `--check`、mirror drift、skill metadata 和 `git diff --check` 均通过。
- 独立 auditor 发现并推动修复：发布 lineage 漏版本、memory move 误列 safe、root reparse 检查失效、memory validator 错误码放行过宽、metadata gate fail-open；对应回归均已加入。

### 真实样本事务收据

| 样本 | branch / HEAD | apply | gap / 版本戳 | 重复运行 |
|---|---|---:|---|---|
| CausisRiskSuite 低定制 | `codex/testBridgeForgeCausisRiskSuite` / `9b8bdc3` | 8 safe、3 risk、0 blocker | 2 gap 全部 hash 不变；degraded，保留 `0.90.0` | safe 0、risk 0 |
| StratusAgent 高定制 | `codex/testBridgeForgeStratusAgent` / `33d2f1f` | 7 safe、3 risk、0 blocker | 18 gap 全部 hash 不变；degraded，保留 `0.90.0` | safe 0、risk 0 |

两份事务的 risk 都只删除 hash 命中的旧 Codex `bridgeforge_switch.py`、`model_policy_check.py`、`version_check.py`。正式 apply 前均注入 `before-validate` 故障；Git clean、原 HEAD、原版本戳和 aggregate fingerprint 全部恢复。正式 apply 后 `.githooks/pre-commit` 的 managed region 外归一化字节与各自 HEAD 一致。未 commit、push 或 prune。

## 当前交接边界

源码、传播、dogfood、fixture、双真实样本事务和独立审计已经闭环。Codex Desktop deep-link 实际显示、`/hooks` trust 与新会话 lifecycle 没有现场收据，保持未验证，禁止由静态测试代替。
