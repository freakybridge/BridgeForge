---
title: Git Sync 延迟优化需求确认卡
status: confirmed
date: 2026-08-01
source: confirm
handoff: develop
---

# Git Sync 延迟优化需求确认卡

## 原始需求摘要

用户反馈一次 `$git-sync` 耗时超过三分钟，要求优化。事实核验显示主要延迟来自强制 `mechanical-sync-worker` 中转、版本闸发现过晚、memory 索引重复重建，以及脚本成功输出缺少完整收据。

## 目标

- 主 agent 在完成只读范围审查后，直接运行仓库唯一白名单脚本 `.codex/scripts/codex_git_sync.py`。
- 将无需暂存、无需运行 hooks 且无副作用的本地失败前置到网络操作和衍生产物刷新之前。
- 消除 git-sync 与 pre-commit 之间重复的 memory 索引重建。
- 脚本直接输出 commit ID、push 目标、最终工作区状态和 `ahead/behind=0/0`。
- 保持 dogfood 与 Codex 模板行为一致，并为下游发布。

## 非目标

- 不弱化或绕过 pre-commit 检查。
- 不自动 rebase、merge、force-push、`reset --hard` 或丢弃冲突现场。
- 不优化其他 skill 的 agent 调度。
- 不承诺固定网络耗时。

## 已核实事实

- `codex_git_sync.py` 当前按 `fetch → harness parity → 状态判断 → memory/manifest 刷新 → commit → push` 执行。
- `git-sync` 与 pre-commit 都会运行 memory rebuild，成功提交路径存在重复计算。
- pre-commit 会依次启动双宿主镜像、编码、规则、skill metadata 等检查及双宿主 memory rebuild。
- `skills/git-sync/SKILL.md`、两份 `skill-routing.json`、根/模板 `AGENTS.md` 当前强制使用 `mechanical-sync-worker`。
- 脚本成功时只输出工作区干净，不输出 commit ID、push 目标和最终 `0/0` 数值。

## 已确认规则

- 采用方案 A：取消 `mechanical-sync-worker` 的强制中转。
- 主 agent 仍只能运行唯一白名单脚本；失败、分叉、冲突和权限决策继续留在主对话。
- 保留现有 divergence、非快进、stash 冲突、pre-commit 和禁止 force-push 等安全边界。
- 缺 upstream、缺 push target、缺提交消息和产品版本未 bump 必须在 `fetch` 前完成；其余依赖暂存态的硬闸仍由 pre-commit 执行，禁止为前置校验而重复运行 hooks。
- runner 不再执行 memory rebuild；pre-commit 对每个存在的宿主各重建一次，不再对同一宿主重复计算。

## 数据与接口映射

本需求不引入业务数据结构。对外接口仍为：

```text
python .codex/scripts/codex_git_sync.py --message "<类型>: <描述>"
```

脚本 stdout 增加结构化的人类可读收据：commit、Git 实际配置的 push target、本次是否执行 push、working tree、ahead、behind。

## 拟修改

- `.codex/scripts/codex_git_sync.py` 与 `templates/codex/scripts/codex_git_sync.py`
- `skills/git-sync/SKILL.md`
- `.codex/skill-routing.json` 与 `templates/codex/skill-routing.json`
- `AGENTS.md` 与 `templates/codex/AGENTS.md`
- 相关 harness 测试、版本、根/模板 CHANGELOG
- 本需求卡及 `doc/README.md`

## 验收

- 正常 `$git-sync` 不启动 `mechanical-sync-worker`，只调用一次白名单脚本。
- 可本地判定的版本问题在 `fetch` 前失败。
- runner 中不存在 memory rebuild；pre-commit 对每个存在的宿主各执行一次，不重复同一宿主。
- 成功输出包含 commit ID、Git 实际配置的 push 目标、本次是否执行 push、工作区干净和 `ahead=0 behind=0`。
- dogfood/template 镜像一致，相关单测与下游 fixture 通过。
- 独立审计无发布阻断。

## 合理假设与风险

- 网络延迟不可控，因此验收以删除确定性冗余步骤为准，不设固定总秒数。
- 取消机械 agent 会减少一层角色隔离；白名单命令约束、脚本拒绝危险状态和 Git hooks 继续承担安全边界。
- 若现有测试把 named agent 清单视为固定集合，需要同步调整契约测试，但不删除该 agent 的通用定义文件，除非真实引用清点证明已无消费者。

## 自动化边界

- 允许脚本执行 fetch、必要的快进更新、衍生产物刷新、精确提交、push 和最终核验。
- 任何分叉、冲突、缺 upstream、权限失败或 push 竞态都必须停止并交回主对话。
- 禁止脚本自动改变历史或绕过 hooks。

## 实施计划

1. 调整主/模板 `codex_git_sync.py`：增加本地产品版本 preflight，移除脚本侧重复 memory rebuild，把 harness/manifest 刷新限制在有本地变更的提交路径，并输出完整同步收据。
2. 将 `$git-sync` 契约从 `mechanical-sync-worker` 改为主对话直跑唯一白名单脚本；同步两份路由、根/模板 AGENTS 与相关 fixture 断言。
3. 新增脚本级回归测试，覆盖 preflight 早于 fetch、成功收据和无重复 memory rebuild；同步版本、CHANGELOG、manifest，运行下游 fixture 与独立审计。

## 实施记录

2026-08-01：用户确认方案 A 并授权开发；已完成真实脚本、pre-commit、路由和 fixture 入口核验，进入实现阶段。

2026-08-01：已将 `$git-sync` 路由改为主对话直跑 repo-local 脚本；runner 增加缺 upstream、缺 push target、缺提交消息与产品版本 worktree preflight，移除主动 memory rebuild，补齐成功收据；dogfood/template、版本、CHANGELOG 与测试同步完成。

## 验证记录

- `.venv\Scripts\python.exe -m unittest tests.harness.test_downstream_version_sot`：10 项通过，覆盖 worktree 版本闸、主对话路由、runner 镜像与 memory rebuild 移除。
- `.venv\Scripts\python.exe tests\harness\run_downstream_fixture.py --case codex-git-sync`：通过，覆盖四个 fetch 前失败场景、真实本地 bare remote commit/push、完整收据与最终 `0/0`。
- `.venv\Scripts\python.exe -m unittest tests.harness.test_shared_skill_distribution`：14 项通过，覆盖 shared skill 分发与 manifest 一致性。
- `.venv\Scripts\python.exe -m unittest tests.harness.test_bridgeforge_root_skill`：5 项通过，覆盖根 skill 版本与入口契约。
- 独立审计：初审发现手工 Git 旁路、需求表述过宽与 push target 收据不精确；修复后二次审计结论为无发布阻断。
