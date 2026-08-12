---
status: reported
date: 2026-08-12
source: StratusAgent M2-43 downstream git-sync failure
scope: managed-skeleton ownership boundary for downstream project rules
---

# 下游项目 Rule 被误判为受管骨架的所有权缺口报告

## 结论

当前 Codex 下游模板把 `.codex/rules/*.md` 全部登记为 `whole_files`。这会把项目在
日常开发中维护的架构、模块、数据库和时间等项目约束，误判为只能由
`/bridgeforge` 修改的骨架资产，并导致正规的 `$git-sync` 无法提交。

这不是 stamp 内容错误，也不应通过放宽或绕过 `$git-sync` 守卫解决。根因是
`managed-skeleton.json` 的所有权粒度与 BridgeForge 已定义的 rule 维护语义不一致：
rule 是下游项目约束面，BridgeForge 更新流程对 rules 采用“只 diff、由用户逐段决定”，
但机器清单却把每个 rule 整文件判定为 BridgeForge 独占所有。

## 真实复现

### 下游与版本

- 下游仓库：`D:\Quant\CodexWorktree\4d74\StratusAgent`
- BridgeForge 版本戳：`0.84.0`
- 分支：`codex/m2`
- 触发场景：M2-43 完成后，项目按真实实现同步自身规则约束

### 合理的项目规则改动

本次修改并要求保留的文件是：

- `.codex/rules/app_layer.md`
- `.codex/rules/database.md`
- `.codex/rules/modules.md`
- `.codex/rules/time.md`

这些内容记录 StratusAgent 新增 `replayer`、`backtester`、Dataset Catalog 和回测 UTC
边界等项目事实，不是对 BridgeForge 通用模板的更新。

### 失败输出

下游按契约只运行项目自带脚本：

```text
.venv\Scripts\python.exe .codex/scripts/codex_git_sync.py \
  --message "feat: 完成 M2-43 确定性回放与缓存收口"
```

脚本在版本规划阶段失败：

```text
[git-sync] automatic version release blocked: managed skeleton files changed
outside /bridgeforge; missing updated skeleton stamp for
.codex\managed-skeleton.json
```

未产生 commit 或 push，原项目改动被保留。

## 代码证据

模板当前把整个 rules 目录纳入整文件管理：

```json
{
  "whole_files": [
    ".codex/rules/*.md"
  ]
}
```

来源：`templates/codex/managed-skeleton.json`。

`templates/codex/scripts/version_release.py` 的 `_managed_owner()` 对命中
`whole_files` 的文件直接返回 `whole-file`。`classify_changes()` 随后要求每个发生变化
的 managed owner 必须同时出现对应 stamp 变化，否则抛出上述错误。

因此当前机器判断只有路径信息：

```text
.codex/rules/*.md 发生变化
=> BridgeForge whole-file 发生变化
=> stamp 未变化
=> 阻断
```

它无法表达“这个 rule 文件由模板首次提供，但其业务内容由下游项目持续维护”。

## 与已确认设计的冲突

`git-sync-version-automation` 的边界辩论已明确：

> 所有权清单不能只是路径列表；混合文件必须有 marker 或结构化成员边界。

BridgeForge `$bridgeforge` 入口同时明确：

- hooks/scripts 可作为上游受管资产比对后覆盖；
- rules、入口文件只 diff，由用户逐段决定；
- 禁止静默覆盖已有 rules；
- 禁止代编项目架构红线、快速命令和项目结构。

但最终 `managed-skeleton.json` 用 `.codex/rules/*.md` 的整文件通配符覆盖了上述边界。
也就是说，人工维护契约承认 rule 中存在下游所有权，自动分类器却把它当作上游整文件
所有权。

## 影响

1. 下游完成真实模块或架构变更后，无法把对应 rule 与代码放在同一正常提交中。
2. 用户只能在以下错误选择中三选一：伪造/推进 stamp、绕过 `$git-sync`、或不提交
   必要的项目规则；三者都破坏现有安全模型。
3. `/bridgeforge` 版本已经与上游一致时，普通 update 不会自然产生新 stamp，因而不能
   用“再跑一次 `/bridgeforge`”修复。
4. 误判范围覆盖所有 `.codex/rules/*.md`，不是 StratusAgent 单项目特例。

## 期望语义

所有权判断应区分三类内容：

| 类型 | 日常项目修改 | 是否要求 stamp | `$git-sync` 分类 |
|---|---:|---:|---|
| BridgeForge 独占整文件 | 禁止 | 是 | skeleton-only / mixed |
| 项目拥有整文件 | 允许 | 否 | project |
| 混合文件的 BridgeForge managed region | region 外允许 | 仅 region 内变化要求 | project / skeleton-only / mixed |

关键判据不是文件位于 `.codex/rules/`，而是该文件或该区域的真实所有权。

## 推荐修复方向

### 推荐：把 rule 所有权显式化

1. 从 `whole_files` 删除 `.codex/rules/*.md` 通配符。
2. `managed-skeleton.json` 只显式列出确实禁止下游修改的 rule 整文件；不存在这种
   文件时，不应为了方便分类而整目录纳管。
3. 同一 rule 同时包含通用底座和项目扩展时，用稳定 marker 声明 managed region；
   marker 外归项目所有。
4. `/bridgeforge` init/adopt/update 根据实际采用的所有权决定生成或迁移下游清单，
   禁止重新退化为目录通配符。
5. Claude 模板若存在同构问题，应按相同语义修复，不按文件名机械复制。

### 可接受的最小止血

若本期不实现 rule managed region，先将 rules 全部视为“模板提供初始内容、下游接管
维护”的项目文件，并从 `whole_files` 排除。这个方案会让 `/bridgeforge` 用户确认后
合入的 rule 更新被视为项目变更，可能触发项目版本 bump；它不完美，但不会错误阻止
项目维护自身约束，也不会削弱 hooks/scripts 等真正受管资产的守卫。

不推荐以“stamp 变化即可允许所有 rules 变化”作为修复。stamp 只能证明运行过
`/bridgeforge`，不能解决单个 rule 内上游区域与项目区域的所有权混淆。

## 必要回归测试

1. 下游只修改项目拥有的 rule，stamp 不变：不得报 unauthorized managed skeleton，
   应分类为 `project`。
2. 下游修改受管 hook/script，stamp 不变：继续 fail closed。
3. `/bridgeforge` 修改 stamp 与纯受管资产：分类为 `skeleton-only`，不 bump 项目版本。
4. 受管资产与业务代码同时变化：分类为 `mixed`，按项目提交 bump。
5. mixed rule 只改 marker 外内容：分类为 `project`；只改 marker 内内容但 stamp 不变：
   fail closed。
6. 使用 StratusAgent 四个 rule 的复现 fixture，证明 M2-43 同类提交可以正常进入版本
   规划，同时真正的骨架旁路仍被拦截。
7. Codex/Claude 两侧 ownership schema 与分类行为保持语义一致。

## 非目标

- 不删除 managed-skeleton 安全机制。
- 不允许 `$git-sync` 自动更新 BridgeForge 骨架。
- 不允许普通项目流程修改真正由 BridgeForge 独占的 hooks/scripts。
- 不要求为本次 StratusAgent 提交手工伪造 stamp 或提供绕过参数。

## 下游当前状态

StratusAgent 的 M2-43 代码、文档、memory 与四个项目 rule 仍保留在工作区；由于该守卫
缺口，尚未 commit/push。下游已明确选择保留规则改动，并暂不手工处理 stamp，等待
BridgeForge 上游修复所有权边界后再重跑正规的 `$git-sync`。
