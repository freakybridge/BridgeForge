---
status: product-fixed-awaiting-independent-audit
severity: high
scope: bridgeforge-codex native memories permission classification and maintenance transaction
reported_at: 2026-08-18
downstream: D:\Quant\StratusAgent
factory_head: 442bfc4c57a42d07d30d5c9a0a6b05286c9a7ef8
product_version: 1.4.11
fixed_in: 1.4.12
---

# BUG：native-memory `maintain` 被误分类为 safe，但实际包含远端数据同步

## 结论

`$bridgeforge-codex` 当前把 `approved + enabled` 状态下的 native-memory 漂移修复归为
safe；但 `codex_memory_sync.py maintain` 不只是修复用户 hook，还会检查或创建 GitHub
远端、写入远端配置并立即 `reconcile` 用户级 `~/.codex/memories/`。

这使计划分类、用户授权和真实副作用不一致：用户确认项目骨架 A 更新后，编排器认为可以
自动执行 maintain；平台安全层则正确识别到潜在数据外发并拒绝执行。最终项目骨架显示 ready，
但用户级 hook 仍为 `hookInstalled=false`，维护闭环没有完成。

推荐终态：把“恢复本地 hook”和“立即远端同步”拆开；缺失同步 hook 必须作为明确的用户级
权限项进入本轮唯一风险卡，列明数据范围、远端身份和未来自动同步行为。项目骨架更新不得
顺手执行远端 reconcile。

## 2026-08-19 产品裁决

用户进一步明确：native Memory 是首次授权后无感运行的双向自动同步能力，不应在每次 hook
漂移时重复询问。因此 1.4.12 采用长期授权契约：首次确认必须完整披露用户级 Memory 范围、
private 远端、本地较新上传、远端较新恢复以及生命周期自动 hook；范围与目标未变化时，
`repair-hook` 可以基于该长期授权自动修复。旧 `approved` 只有在本地远端仍为原受管仓库时才
无感迁移。内部仍严格拆开本地 hook repair 与完整 reconcile，项目更新不顺手执行同步。

这一裁决替代下文“每次 hook 缺失都生成新的 P1 权限项”的初始建议；下文作为原始下游报告
和事故分析保留。

## 用户可见症状

真实下游 `D:\Quant\StratusAgent` 完成 bridgeforge-codex `1.4.11` 项目更新后，项目 planner
已经满足：

- `safe=[]`
- `risk=[]`
- `gaps=[]`
- `blockers=[]`
- `target_readiness=ready`

但用户级 native-memory status 同时返回：

```json
{
  "enabled": true,
  "hookInstalled": false,
  "pending": false,
  "remoteConfigured": true,
  "consent": "approved"
}
```

这不是项目 `.codex/memory/` 结构缺失，而是用户级
`C:\Users\bridg\.codex\memories\` 的自动同步 hook 漂移。

## 已核实环境

- 工厂仓库：`D:\Quant\BridgeForge`
- 工厂 HEAD：`442bfc4c57a42d07d30d5c9a0a6b05286c9a7ef8`
- 产品版本：`1.4.11`
- 真实下游：`D:\Quant\StratusAgent`
- 下游项目骨架：`1.4.11`，post-plan no-op，项目 ready
- 用户级 consent：`approved`
- 原生 memories：`enabled=true`
- 远端：`remoteConfigured=true`，具体远端身份本报告未读取
- hook：`hookInstalled=false`
- 本报告只记录产品缺陷；不执行 maintain，不读取用户 memories，不修改产品代码、VERSION
  或 CHANGELOG。

## 根因证据

### 1. Skill 把漂移 maintain 归为 safe

`skills/bridgeforge-codex/SKILL.md` 的 native memories planner 规定：

- `approved + enabled + healthy`：no-op；
- 有漂移时把 `maintain` 归为 safe。

这隐含假设 maintain 只是已授权能力的本地幂等维护，不需要新的外部副作用授权。

### 2. `maintain` 实际同时承担本地与远端职责

`scripts/codex_memory_sync.py` 的 maintain 路径依次执行：

1. 校验 consent 为 `approved`；
2. 校验 native memories 已启用；
3. 迁移用户级 state dir；
4. 选择稳定 hook Python；
5. 调用 `ensure_github_repository(...)`；
6. 调用 `merge_user_hooks(...)`；
7. 写入 `remote.txt`；
8. 调用 `reconcile(memories, state_dir, remote)`。

因此 maintain 同时具备用户配置写入、远端检查或配置以及用户数据同步三类副作用，不能等同
于普通 safe 文件修复。

### 3. 平台安全层拒绝项目授权扩张为数据外发授权

真实执行中，用户已对 bridgeforge-codex 项目计划选择 A。项目事务成功应用 4 项 safe 与
R1 版本戳迁移后，编排器按 Skill 尝试执行 native-memory maintain。平台安全层拒绝该命令，
理由是维护可能持久化用户 hook、配置或同步远端，而用户只明确批准了项目骨架更新。

拒绝后没有绕过或手工补 hook；复查仍为 `hookInstalled=false`。这证明问题不是单纯文案不清，
而是当前权限分类无法通过真实执行边界。

## 影响

### 1. safe 分类失真

用户看到的 A/B/C 卡没有单列用户数据外发影响，却可能触发远端 reconcile。safe 不再代表
“无需新增授权的确定性本地动作”。

### 2. 项目 ready 与用户功能未闭环混在同一收据

项目骨架可以完全 ready，但用户级自动同步仍损坏。若只报告项目 planner，容易给用户造成
“全部升级完成”的错觉。

### 3. 本地修复被网络和远端状态绑架

恢复一个缺失 hook 依赖 GitHub 可达性、仓库状态和 reconcile 成功，增加活动部件、失败面与
排障成本。

### 4. 未来自动外发边界不透明

即使 repair 当下不立即 reconcile，安装 SessionStart/Stop 等同步 hook 也会启用未来自动
外发。该影响必须进入权限卡，不能仅依赖内部 ledger 字段对用户静默推定。

## 推荐修复设计

### A. 拆分本地 hook 修复与远端 reconcile

新增明确的本地修复入口，例如：

```text
codex_memory_sync.py repair-hook --confirmed
```

该入口只允许：

- 校验现有 `approved` consent 与 enabled 状态；
- 使用稳定的用户级 Python；
- 合并或恢复用户级 hooks；
- 验证 hook 注册与解释器路径；
- 输出结构化收据。

该入口禁止：

- 调用 `ensure_github_repository`；
- 创建、修改或探测远端仓库；
- 写入新的 remote identity；
- 调用 `reconcile`；
- 读取、提交、推送或覆盖用户 memories。

远端数据同步继续由独立 `reconcile` 入口负责，不得在项目骨架更新事务中顺手执行。

### B. 缺失自动同步 hook 必须进入唯一风险卡

当状态为 `approved + enabled + hookInstalled=false` 时，不再归为隐式 safe。planner 应生成
用户级权限项，例如 `P1`：

| 字段 | 必须展示的内容 |
|---|---|
| 目标 | 用户级 hooks 配置，不是当前项目 |
| 数据范围 | `~/.codex/memories/` |
| 远端 | 当前已配置远端的可识别名称；无法确认时标为未验证 |
| 当下动作 | 只恢复 hook，不立即同步 |
| 未来行为 | SessionStart/Stop 等生命周期可能自动同步用户 memories |
| 拒绝影响 | 项目更新仍可 ready；用户级自动同步保持 gap |
| 回滚 | 恢复原用户 hooks 配置，不改用户 memories 内容 |

用户选择 A 或 `B: P1` 后才能安装；选择 C 时不写用户配置，并在收据中保留独立用户级 gap。

### C. 项目与用户级 readiness 分离

收据必须分别报告：

- `project_readiness`
- `user_native_memory_readiness`
- `hook_repair_applied/declined`
- `remote_reconcile_applied/declined/not_requested`

用户级功能缺失不得伪装成项目骨架 gap，也不得因项目 ready 而被折叠消失。

### D. 保持单一确认但扩大证据面

本修复不要求新增第二次零散确认。正确做法是在执行前的唯一风险卡中完整列出 P1；用户的
A/B/C 选择只有在卡片已经说明用户级目标、数据范围、远端和未来自动行为时，才能覆盖该动作。

## 最小可接受修复

若暂不拆命令，至少必须完成：

1. 把 `approved + enabled + drift` 下的 maintain 从 safe 改为 risk；
2. 在唯一风险卡中逐项列出远端 reconcile 与用户数据范围；
3. 只有用户选中对应 ID 后才能调用现有 maintain；
4. 项目 A 选择不得自动解释为 native-memory 外发授权；
5. maintain 拒绝或失败时，收据必须明确保留用户级 gap。

该最小修复能纠正授权错误，但仍保留本地 hook 修复与网络同步的耦合；推荐终态仍是职责拆分。

## 非目标

- 不把项目 `.codex/memory/` 与用户级 `~/.codex/memories/` 合并。
- 不取消 native-memory 远端同步能力。
- 不把用户以前的 approved consent 擅自改成 declined。
- 不删除或重写现有用户 memories。
- 不要求项目骨架为用户级 hook 保存副本。
- 不允许以手工编辑 `~/.codex/hooks.json` 代替受控产品修复。
- 不授权本报告提交、推送或实施产品代码。

## 回归与验收场景

1. `approved + enabled + hook healthy`：完全 no-op，不访问网络。
2. `approved + enabled + hook missing`：计划生成 P1，不归为 safe，plan 阶段零写入、零网络。
3. 用户选择 C：项目 safe 正常执行，用户 hooks 字节不变，收据保留用户级 gap。
4. 用户选择 A 或 `B: P1`：只恢复 hook，使用稳定用户级 Python，不持久化项目 `.venv`。
5. hook repair 测试对 GitHub、Git 和 reconcile 设置 fail-if-called，证明本地修复零网络、零数据同步。
6. repair 后 status 返回 `hookInstalled=true`；第二次 repair 为幂等 no-op。
7. 独立 reconcile 在缺少有效 consent、remote 或显式运行条件时 fail closed。
8. reconcile 成功收据列出远端、触发来源、数据范围和结果；不得只返回笼统 completed。
9. 项目 planner 在用户级 repair 拒绝时仍可准确报告项目 ready，不写错误版本戳。
10. 真实下游从 `hookInstalled=false` 经 P1 修复到 true；期间项目文件和项目 memory 字节不变。
11. 平台安全审查能够从命令参数和前置风险卡确认授权范围，不再因数据外发范围不明而拒绝。
12. 完整 factory unittest、manifest、dogfood、fixture 与独立审计通过。

## 六类关闭证据

| 证据类别 | 当前状态 | 关闭要求 |
|---|---|---|
| 源码 | 已验证 | 本地 repair 与远端 reconcile 已解耦；长期授权结构化；完整 unittest `252/252` 通过 |
| 产品传播 | 已验证 | 根 Skill、用户级 updater/migrator、manifest、VERSION `1.4.12` 与 CHANGELOG 已同步，manifest check exit 0 |
| dogfood | 已验证 | Template/dogfood contract、skill metadata、mirror drift、instruction source 与 project structure gate 均通过 |
| fixture | 已验证 | 完整 downstream fixture 状态 `passed`，已发布 lineage `26/26` 可执行迁移通过 |
| 真实下游 | 失败路径已验证，修复后未验证 | 既有 StratusAgent 报告证明原缺陷；本轮未写真实下游或真实用户 Memory |
| runtime | 未验证 | 新会话 hook 实际加载，明确触发或不触发 reconcile，平台审批通过 |

六类证据全部满足前，本报告不得标记 resolved。

## 恢复与回滚边界

- 报告前 BridgeForge 仓库为干净工作树。
- 本轮只新增本报告并同步 `doc/README.md`；不修改产品代码、VERSION 或 CHANGELOG。
- 正式修复必须备份并事务恢复用户 hooks；任何失败不得改变用户 memories 或 remote 配置。
- 真实下游验证只能在用户明确授权的环境中执行，禁止借项目骨架 A 更新静默取得外发权限。

## 传播四问

1. 层级：这是 bridgeforge-codex 用户级产品维护与权限模型缺陷，不属于下游项目层。
2. 通用性：影响所有启用 native memories 且 hook 漂移的用户。
3. 发布：正式修复需要 bump 根 VERSION，并在 CHANGELOG 标记 `[product]`。
4. dogfood：Skill、脚本、用户级分发、factory dogfood、fixture 和真实下游必须同步验证。

## 关联记录

- `skills/bridgeforge-codex/SKILL.md`：native memories planner 与 safe/risk/gap 分类。
- `scripts/codex_memory_sync.py`：status、maintain、setup、reconcile 与用户 hook 合并。
- `scripts/tests/test_memory_native_sync.py`：用户级 native-memory 回归入口。
- `doc/2_bugs/BUG-update-stamped-before-memory-migration.md`
- `doc/2_bugs/BUG-codex-native-memory-empty-snapshot-reconcile.md`
