---
status: regression-fixed-awaiting-real-downstream
severity: high
scope: downstream git-sync version classification after bridgeforge-codex contract migration
reported_at: 2026-08-17
downstream: D:\Quant\ClaudeBridgeAssist
factory_head: f82e0b6accaeaece4bf5565125655c2a30022fda
product_version: 1.4.35
fix_target: 1.4.37
---

# BUG：`$git-sync` 无法分类跨 ownership contract 的骨架更新

## 开发预算与授权

- 规模：M。
- 预算：45 分钟 / 20k 新增 token 估算（平台无可靠计量器）/ 最多 1 个独立审计 agent / 最多 2 轮验证。
- 规模依据：修改跨版本 ownership 分类、Template/dogfood、回归 fixture 与真实下游预检，但不改变项目同步协议。
- 开工授权：用户于 2026-08-17 明确要求“开始修复”，按本报告既定范围实施。
- 超预算停止点：若需要改变 schema v2、项目同步事务、持久化戳格式或扩大到下游自动提交，必须停止并重新确认。

## 结论

BridgeForgeCodex `1.4.3` 可以把旧下游从无分区 `AGENTS.md` 和旧受管文件结构升级到新的
公共区 / 项目专区与 managed-region contract，但升级后的第一次 `$git-sync` 会在创建
commit 前被 `version_release.py` 阻断。

根因不是新版 marker 损坏，而是版本分类器只读取工作树中的新
`.codex/managed-skeleton.json`，随后用这份新 contract 同时解析 HEAD 里的旧文件与工作树里的
新文件。HEAD 本来没有新 marker，因此合法的 contract 迁移被误判为 marker 缺失。

这是产品级兼容缺口。当前 fail-closed 避免了错误提交和推送，但也让正常完成骨架更新的
下游进入“更新成功、无法提交”的死路。

## 用户可见影响

- 下游通过 `$bridgeforge-codex` 从旧 contract 更新成功后，无法用标准 `$git-sync` 提交该次更新。
- 用户会看到 `AGENTS zone markers are missing or duplicated`，或先看到其他受管文件的
  `managed region markers are missing or ambiguous`；首个报错取决于 changed paths 的遍历顺序。
- 重复升级 BridgeForgeCodex不能解决问题，因为当前项目脚本与工厂 `1.4.3` 模板完全一致。
- 直接绕过版本分类、手工 commit 或弱化 marker 校验会破坏版本域与 ownership 安全边界，不能作为修复。
- 当前故障发生在 commit 前；没有证据表明它会删除工作区修改或产生远端副作用。

## 真实下游证据

### 环境

- 工厂仓库：`D:\Quant\BridgeForge`
- 工厂 HEAD：`f82e0b6accaeaece4bf5565125655c2a30022fda`
- BridgeForgeCodex 产品版本：`1.4.3`
- 真实下游：`D:\Quant\ClaudeBridgeAssist`
- 下游 HEAD：`c33125b1a00571edc0429728e1469f097d9f3d3b`
- 下游 HEAD 旧骨架戳：`0.94.2`，路径 `.codex/.bridgeforge_version`
- 下游工作树新骨架戳：`1.4.3`，路径 `.codex/.bridgeforge_codex_version`
- 下游分支 / upstream：`master` / `origin/master`
- 工厂模板与下游 `.codex/scripts/version_release.py` SHA-256 均为
  `96352E5E1F6ABF5E2481ACE5D3756F30C17AAB3183A18A8A6E89B4FE8E8B0D02`

HEAD 的旧 `managed-skeleton.json` 中，`root.agents` 没有 `agents_zones`；工作树新 contract
已经要求唯一公共区和项目专区。这是受支持的 `0.94.2 -> 1.4.3` 升级状态，不是用户手工
删除 marker。

### 最小复现

在已完成骨架更新、尚未提交的真实下游运行只读分类探针：

```powershell
.venv\Scripts\python.exe -B -c "import sys; from pathlib import Path; root=Path.cwd(); sys.path.insert(0,str(root/'.codex/scripts')); import version_release as v; print(v.classify_changes(root,{'AGENTS.md'}))"
```

实际结果：

```text
version_release.ReleaseError: AGENTS zone markers are missing or duplicated
```

对完整 changed paths 调用同一分类入口时，本轮首先命中：

```text
version_release.ReleaseError: managed region markers are missing or ambiguous:
# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN / # <<< BRIDGEFORGE_CODEX_MANAGED_END
```

`templates/scripts/codex_git_sync.py` 在 `build_release_plan()` 中调用同一
`classify_changes()`，因此标准 `$git-sync` 会在暂存和 commit 前走到相同阻断路径。本报告
没有执行 commit 或 push。

## 源码根因

### 1. before 与 current 共用工作树 contract

`templates/scripts/version_release.py::_change_ownership()` 分别读取：

- `before = _head_bytes(repo, path)`：HEAD 旧文件；
- `current = current_path.read_bytes()`：工作树新文件。

但 `_load_managed_configs()` 只从工作树读取当前 contract。随后 `_change_ownership()` 对
`before` 和 `current` 都调用当前 contract 的 `_region_parts()` 或
`_agents_zone_release_parts()`。

这在 contract 不变的普通开发提交中成立，在 `$bridgeforge-codex` 同一批次改变 ownership
边界、marker 和版本戳时不成立。

### 2. AGENTS 专区迁移测试缺少提交阶段

现有 `test_agents_zones_distinguish_public_project_and_mixed_changes` 使用“HEAD 已有 zone、工作树
仍有 zone”的基线，覆盖了稳定 contract 下的 public / project / mixed 分类和损坏 marker
阻断。

它没有覆盖以下真实生命周期：

```text
HEAD 旧 contract、无 zone
  -> $bridgeforge-codex 合法迁移
  -> 工作树新 contract、有 zone
  -> $git-sync 版本分类
```

因此项目同步器的迁移验收通过，但下一个正式提交阶段仍会失败。

### 3. 报错语义混淆“损坏”与“版本迁移”

当前解析器看到旧文件缺新 marker 就直接抛错，没有先判断 contract 是否在本次受管骨架更新中
发生了可信迁移。相同错误既表示“当前 marker 真损坏”，也表示“HEAD 属于旧发布格式”，用户
无法从提示中判断实际风险和正确动作。

## 推荐修复

把“ownership contract 迁移”作为版本分类器的一等场景，禁止用异常兜底或跳过版本自动化。

1. 分别加载 HEAD contract 与工作树 contract；不能再用工作树 contract 解析两侧文件。
2. contract 未变化时保持现有分类逻辑，避免扩大普通提交路径。
3. contract 或骨架戳变化时进入 transition classifier：
   - 以稳定 asset id 对齐新旧资产；
   - 用 HEAD contract 解析 before，用工作树 contract 解析 current；
   - 结合已发布历史 hash、legacy section 映射和 stamp 变化证明迁移来源可信；
   - 证明只有受管资产变化时返回 `skeleton-only`，使 `build_release_plan()` 不 bump 下游业务版本；
   - 同批存在项目自有变化时返回 `mixed`，继续按现有规则 bump 项目版本；
   - 无法证明旧资产可信、项目内容无损或当前 marker 完整时继续 fail-closed。
4. 错误消息应区分当前工作树损坏、HEAD 属于不受支持的旧 contract、transition 缺少可信 lineage
   和项目内容无法映射四类原因。

该方案保持单一版本分类入口和 fail-closed 语义，不引入手工 Git 旁路，也不要求下游永久保存
一次性运行时收据。

## 修复要求

1. `version_release.py` 必须支持“HEAD contract 与工作树 contract 不同”的合法骨架事务。
2. 不得仅捕获并忽略 marker 异常；当前工作树 marker 缺失、重复、逆序或区块外有内容仍必须阻断。
3. 只有可信旧 contract / 历史 hash、当前新 contract、骨架戳变化和资产映射共同成立时，才可
   把 marker 变化判为骨架迁移。
4. 旧 project-owned 内容到新项目专区的映射必须按已登记 legacy section 契约核对；无法映射时
   必须阻断，禁止把项目语义误判为受管变化。
5. changed paths 的遍历顺序不得改变最终分类或用户看到的主要根因；建议先完成 transition
   预判，再逐资产分类并聚合全部冲突。
6. 产品修复必须同步 Template、工厂 dogfood 镜像、manifest / contract、VERSION 与
   CHANGELOG，并标记 `[product]`。

## 回归与验收场景

1. fixture 从已发布 `0.94.2` HEAD contract 更新到当前 contract，随后以完整 changed paths
   调用 `build_release_plan()`：纯骨架更新返回 `None`，不 bump 下游 `VERSION` 或 CHANGELOG。
2. 同一迁移同时修改项目文档：分类为 `mixed`，按提交类型生成业务版本计划。
3. HEAD 与工作树都已是新 zone contract，只修改项目专区：分类为 `project`。
4. HEAD 与工作树都已是新 zone contract，只修改公共区且没有合法骨架戳变化：继续阻断旁路修改。
5. 当前 AGENTS 缺失、重复、逆序 marker 或存在区块外正文：继续 fail-closed。
6. HEAD 旧 AGENTS 不匹配任何可信历史 hash，或 legacy project section 无法映射：零写入并报告
   明确 transition blocker。
7. 新 contract 已写入但新骨架戳缺失，或 stamp / contract 来源不一致：继续阻断。
8. 真实下游 `D:\Quant\ClaudeBridgeAssist` 在修复版更新后重新运行只读 preflight，再由用户显式
   调用 `$git-sync` 验证 commit、push、clean 和 ahead / behind 收据。
9. 完整自动测试、downstream fixture、factory dogfood、manifest、mirror、instruction、structure
   与 `git diff --check` 全部通过，并由独立审计复核 contract transition 没有扩大 ownership。

## 范围与非目标

- 本报告只要求修复版本分类与 `$git-sync` 提交衔接，不重新设计 AGENTS 公共区 / 项目专区。
- 不要求 BridgeForge 上游直接修改真实下游工作区；真实下游只在修复发布后按用户授权更新。
- 不允许用手工 commit、`--skip-version`、删除 contract 或修改 marker 绕过故障。
- 不宣称当前下游已完成 `$git-sync`；本轮只修复并验证工厂产品，真实下游仍须在修复版发布后按用户授权更新和清理其既有内容异常。

## 实施记录

- `version_release.py` 已分离读取 HEAD 与工作树 contract；contract 未变化时继续走原稳定分类路径，发生可信迁移时才进入 transition classifier。
- transition classifier 以稳定 asset id 对齐新旧资产，并校验 contract 历史摘要、`release_version`、新旧版本戳、whole / region / retirement 资产摘要以及 AGENTS legacy section 映射。
- 同 id、同 target 但受管内容摘要变化也必须出现在 changed paths；漏报时 fail-closed，禁止误判为 `skeleton-only`。
- AGENTS 自定义项目内容只有在 legacy section、residual 内容与新项目专区逐项可证明无损时才归类 `mixed`；未知内容、未闭合 fence、marker 损坏或不可信历史均阻断。
- Template 与 `.codex` dogfood 镜像、两份 managed contract、发布 manifest、`VERSION=1.4.4` 与 CHANGELOG 已同步。

## 验证记录

- 定向回归：`.venv\Scripts\python.exe -B -m unittest scripts.tests.test_git_sync_version_release scripts.tests.test_bridgeforge_codex_project_sync -q`，63/63 通过。
- 完整自动测试：`.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"`，242/242 通过。
- 下游迁移 fixture：`.venv\Scripts\python.exe -B scripts/tests/run_downstream_fixture.py`，22/22 个可执行发布基线通过。
- 发布硬闸：manifest `--check`、mirror drift、skill metadata、project structure、instruction source 与 `git diff --check` 全部 exit 0；structure 仅输出既有归档 advisory。
- 独立审计复核了双 contract、stable asset-id、legacy AGENTS 语义保留、region / whole 摘要、stamp / release 绑定与同路径摘要变化漏报场景；最终未发现 Blocker 或 High。
- 真实下游 `D:\Quant\ClaudeBridgeAssist` 仅做只读诊断，未被本轮写入。当前旧现场还包含未闭合 AGENTS fenced code block 和部分无法命中可信历史的受管资产，因此修复版会正确 fail-closed；这属于该下游既有内容恢复问题，不能宣称其 `$git-sync` 已通过。

## 关联记录

- `doc/1_delivery/codex-project-zone-ownership/requirements_2026-08-17_codex-project-zone-ownership.md`
- `doc/1_delivery/git-sync-version-automation/requirements_2026-08-12_git-sync-version-automation.md`

## 2026-08-21 current-only 重构回归与修复

### 真实回归

CausisRiskSuite 已通过 BridgeForgeCodex 1.4.35 完成受治理重建并达到 no-op，但随后执行标准
`$git-sync` 时在自动版本发布阶段再次被阻断：

```text
ownership contract transition is blocked: codex.precommit:
managed markers are missing or duplicated:
# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN / # <<< BRIDGEFORGE_CODEX_MANAGED_END
```

现场证明工作树与 index 都各有一组合法新 marker，HEAD 则各有一组合法旧 marker；HEAD、stash
和远端均未变化，失败发生在 commit/push 前。1.4.31 current-only 重构删除旧 transition
classifier 后，`evaluate_release_transition()` 又用当前 asset 同时投影 HEAD 与工作树，重新引入
本卡原始根因。

### 1.4.37 修复

- 只有 HEAD contract 与当前 contract 不同时，发布器才读取 HEAD contract；普通同合同提交继续
  使用当前快速路径。
- HEAD payload 使用 HEAD asset 的 marker / ownership strategy，工作树 payload 使用当前 asset；
  stable asset id 用于同 target 或 target 迁移时对齐；当前合同存在重复 id/target、坏 JSON 或
  非对象资产时继续 fail-closed。
- 同合同下，旧基线损坏仍然 fail-closed。跨合同升级时，无法用旧合同证明的 HEAD 内容不再成为
  永久历史卡点，而是保守分类为 `mixed`；这样会触发正常业务版本升级，但绝不会被洗成
  `skeleton-only`。
- contract target 与新旧 stamp 归入骨架变化；两侧 managed/project projection 分别比较。纯 marker
  迁移分类为 `skeleton-only`，叠加业务文件分类为 `mixed`。
- 当前工作树仍先通过 `verify_current_baseline()`；缺失、重复或漂移的新 marker 没有放宽。
- `$git-sync` 仍识别 `.runtime/bridgeforge-codex/explicit-adaptation.json`，但旧收据不再参与或覆盖
  ownership 分类。独立审计证明旧 schema-2 fingerprint 只是自洽校验、不是不可伪造的信任根；继续
  用它放行会允许项目修改被洗成 `skeleton-only`。
- 发布器只使用当前合同与真实 HEAD/工作树内容给出结果。当前规则独立通过并成功 commit 后，
  `$git-sync` 才删除过期收据；当前规则阻断或 commit 失败时收据原样保留。
- 这保留一套 current-only 规则：旧收据既不能放宽 fail-closed，也不会让已经能由当前规则安全
  分类为 `mixed` 的 Causis 永久卡住。

### 当前验证

- 精确回归与 parser 反例覆盖旧 marker、跨合同 HEAD 漂移保守转 `mixed`、stable-id target rename、
  同 target 换 id、无 HEAD contract 的首次安装，以及伪造旧收据不能进入正式 evaluator。
- Git 事务回归证明过期收据不会传给发布 evaluator，只在 current-only commit 成功后清理；commit
  失败时保留且自动写入回滚。
- 使用修复后的 Template 模块只读分类真实 `D:\Quant\causis_risk_suite`：返回 `mixed`，不再报告
  marker 缺失；未 stage、commit 或 push。
- 完整 unittest `266/266` 通过；downstream fixture 三场景通过；manifest、mirror、structure、
  instruction、skill metadata 与 `git diff --check` 全部 exit 0。最终独立审计为
  Blocker / High / Medium / Low = `0/0/0/0`。
- 真实 Causis `$git-sync` 须在 1.4.37 发布并重新更新后复验，复验前不得关闭本回归。

### 历史边界

本轮不恢复 schema-v1 `whole_files` / `managed_regions` 历史兼容包，也不恢复一套长期并存的旧
transition classifier。当前 contract 始终是唯一安装标准；跨合同旧侧无法证明时统一降级为
`mixed`，同合同当前基线损坏仍 fail-closed。旧显式适配收据仅作为待退休运行时产物，不再是
ownership 证明或骨架事实源。
