---
category: topic
topic: create-worktree-skill
status: completed
description: Codex-only create-worktree 已验收：支持斜杠位置调用、安全创建永久 worktree，并通过 Windows 协议激活 Codex Desktop。
kind: delivery
tags:
  - codex-skill
  - git-worktree
  - windows
  - shared-skill
related_paths:
  - doc/1_delivery/create-worktree-skill/requirements_2026-08-15_create-worktree-skill.md
  - doc/2_bugs/BUG-create-worktree-sandbox-half-created.md
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
- 新分支固定补 `codex/` 前缀，worktree 直接创建在 `desktop.git-worktree-root` 下，不插入槽位目录；创建后验证 Git 成果，并通过 Windows Shell 打开 `codex://threads/new?path=<encoded-path>` 激活 Codex Desktop。
- 整条创建脚本必须在首次运行前申请沙箱外执行；未批准时零写入停止，禁止先在默认沙箱试跑，避免 Git 登记持久而仓库外目录消失的半创建状态。
- 禁止解析或直接执行 WindowsApps 内的 `codex.exe`；执行器可能因此收到 `Access is denied`。协议激活异常时保留有效 Git 成果、输出原始错误和重试命令，统一返回部分成功码 `3`。
- 所有输入、脏工作区、冲突、Windows 保留名和 reparse point 风险在 Git 写入前 fail closed。
- BridgeForge metadata 门卫向后兼容 `user_invocable` / `argument`，用于斜杠菜单调用；OpenAI 当前 `quick_validate.py` 不接受这两个扩展字段，该已知差异不伪报为通过。

## 验收收据

- 用户再次明确执行 `$summary 同意验收`，验收范围包含协议启动补丁和试用成果清理。
- `test_create_worktree_skill.py`：13/13 通过，覆盖位置调用、`main`/`master` 缺省、零写入硬闸、安全边界、UI metadata、deep link 路径编码及协议激活异常。
- `test_skill_metadata_budget.py`：7/7 通过；`test_shared_skill_distribution.py`：19/19 通过。
- PowerShell AST、metadata 门卫、版本门卫、mirror drift、manifest current 和 `git diff --check` 均通过。
- 用户级 `SKILL.md`、`agents/openai.yaml` 与 PowerShell 脚本均已同步，SHA-256 与仓库源文件一致。
- 删除前确认 `D:\Quant\CodexWorktree\aaa` 工作树干净，`codex/bbb` 与 `main` 同指向 `bf0da61`；标准移除后只剩主工作树，目标目录与分支引用均不存在。

## 未验证边界

- 本轮没有 `/hooks` review/trust 或新会话 lifecycle smoke 收据，`runtime trust 未验证`。
- 自动化测试没有实际打开 Codex Desktop GUI；协议调用由可控 `Start-Process` 替身验证。用户明确验收后不作为 blocker。
