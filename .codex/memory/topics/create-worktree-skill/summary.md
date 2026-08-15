---
category: topic
topic: create-worktree-skill
status: completed
description: Codex-only create-worktree 交付已验收：支持斜杠显式调用、位置参数、main/master 基准缺省和用户级分发。
kind: delivery
tags:
  - codex-skill
  - git-worktree
  - windows
  - shared-skill
related_paths:
  - doc/1_delivery/create-worktree-skill/requirements_2026-08-15_create-worktree-skill.md
  - skills/create-worktree/SKILL.md
  - skills/create-worktree/agents/openai.yaml
  - skills/create-worktree/scripts/create_worktree.ps1
  - tests/harness/test_create_worktree_skill.py
  - shared-skill-manifest.json
---

# create-worktree Skill

## 已验收结论

- `create-worktree` 是 Codex-only 用户级 Skill，同时支持 `/create-worktree` 与 `$create-worktree` 显式调用，UI 展示名精确为 `create-worktree`。
- 用户只输入两个必填位置参数：工作树名、分支名；禁止要求输入 `worktree_name=` 等变量名。第三个基准分支可选，缺省时优先本地 `main`，其次本地 `master`，两者均无时零写入停止。
- 新分支固定补 `codex/` 前缀，worktree 直接创建在 `desktop.git-worktree-root` 下，不插入槽位目录；创建后验证 Git 成果并调用 `codex app`。
- 所有输入、脏工作区、冲突、Windows 保留名和 reparse point 风险在 Git 写入前 fail closed；Codex 打开失败时保留有效 Git 成果。
- BridgeForge metadata 门卫向后兼容 `user_invocable` / `argument`，用于斜杠菜单调用；OpenAI 当前 `quick_validate.py` 不接受这两个扩展字段，该已知差异不伪报为通过。

## 验收收据

- 用户已明确执行 `$summary 同意验收`。
- `test_create_worktree_skill.py`：13/13 通过，覆盖位置调用、`main`/`master` 缺省、零写入硬闸、安全边界和 UI metadata 契约。
- `test_skill_metadata_budget.py`：7/7 通过；`test_shared_skill_distribution.py`：19/19 通过，确认 Codex-only 分发。
- PowerShell AST、metadata 门卫、镜像检查、版本门卫、manifest current 检查和 `git diff --check` 均有通过收据。
- 用户级 `SKILL.md`、`agents/openai.yaml` 与 PowerShell 脚本已与仓库源文件逐一 SHA-256 一致。

## 未验证边界

- 本轮没有 `/hooks` review/trust 或新会话 lifecycle smoke 收据，`runtime trust 未验证`。
- 自动化使用假 `codex` CLI，未以自动化方式捕获 Codex Desktop GUI 刷新；用户明确验收后不作为交付 blocker。
