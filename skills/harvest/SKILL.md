---
name: harvest
description: 将当前下游项目积累的通用经验脱敏后反哺 BridgeForge 上游模板或 skills；用户调用 /harvest、$harvest，处理 harvest inbox，或提供单条经验要求 reverse-sync 时使用。
user_invocable: true
argument: 可选的单条经验描述；有参走快车道，无参批量处理当前项目收件箱
---

# harvest — 反哺通用经验

## 定位与边界

把当前下游项目的可移植经验写回 BridgeForge `templates/` 或 `skills/`。`summary` 只捕捉候选，`harvest` 负责通用性判断、脱敏和上游写入。

## 输入

- 无参：当前项目 `.claude/harvest-inbox.md` 或 `.codex/harvest-inbox.md` 的未处理项。
- 有参：`$ARGUMENTS` 指定的单条经验。
- 上游 `doc/3_design/reverse-sync-playbook.md` 与 `design-rationale.md`。

## 核心流程

1. 定位通常位于 `~/.bridgeforge/` 的上游 Git 仓库；找不到时停止。
2. 把 candidate-and-target discovery 显式分派给 `light-explorer`：无参时只读当前项目收件箱全部未处理项，有参时只研究该条，并提出上游候选落点。
3. 主 agent 按 reverse-sync playbook 将每条候选判为：通用增量、可抽象后通用、业务专属。业务专属项不反哺。
4. 对可反哺内容逐项检查并移除项目名、内部包名、凭证、内部 URL、提交哈希、绝对路径和业务术语；任一项拿不准就询问用户。
5. 主 agent 按“模板 vs 占位”规则批准 `templates/<agent>/`、入口规则或 `skills/` 等产品层落点；禁止依赖特定业务领域。
6. 把已批准的 sanitized product change 显式分派给 `implementation-worker`。修改产品层后 bump 上游版本，并在 CHANGELOG 写 `[product]` 条目；在 reverse-sync playbook 的反哺日志追加日期、源项目、目标文件、摘要和操作人。
7. 把 product-change review 显式分派给 `review-auditor`，要求它独立检查真实 diff、产品层归属和七项脱敏结果；主 agent 决定接受或修复。
8. 只有成功写入且复核通过的收件箱条目才可勾选或移除。
9. 展示上游 diff 和敏感词扫描结果，交给用户 review；不要提交或推送。

## 输出与收据

- 每条候选的通用性判定及理由。
- 修改的上游文件、版本、CHANGELOG 和反哺日志。
- 脱敏检查结果与上游 `git diff` 摘要。
- 已回收及保留的收件箱条目。

## 停止条件

- 找不到上游 clone 时，提示用户先准备仓库并停止。
- 脱敏结果、落点或通用性不确定时，暂停该条并等待用户决定。
- 写入、版本更新或敏感词扫描失败时，不回收对应收件箱条目。

## 禁止事项

- 禁止跳过脱敏检查，即使用户走单条快车道。
- 禁止把业务专属内容写入产品层。
- 禁止一次处理多个下游来源。
- 禁止自动 `git add`、commit 或 push 上游。

$ARGUMENTS
