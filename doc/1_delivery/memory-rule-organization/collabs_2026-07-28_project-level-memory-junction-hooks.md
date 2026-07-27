---
status: complete
topic: memory-rule-organization
created: 2026-07-28
confirmation_card: requirements_2026-07-28_project-level-memory-junction-hooks.md
---

# Collab：项目级双宿主 memory junction hook

## 接口契约

- 两侧 `memory_junction_check.py` 保持同一状态机，仅由 `.codex` / `.claude` 路径分支不同。
- 同路径冲突绝不覆盖；合并完整性校验通过后才删除系统 memory 并建 junction。
- Codex 唯一有效注册为 `.codex/hooks.json` 的 SessionStart；Claude 保持 `.claude/settings.json`。
- 自动 hook 不执行删除迁移；下游 update 仅在用户确认的迁移步骤中执行删除。

## 拆分计划

| 组 | 负责人 | 文件边界 | 依赖 |
|---|---|---|---|
| 1A | implementation-worker | 两侧模板及 Codex dogfood 的 junction 脚本；专项状态机测试 | 无 |
| 1B | implementation-worker | Codex/Claude 模板及 Codex dogfood 的 hook 注册承载面 | 无；消费既有脚本名 |
| 1C | implementation-worker | `/bridgeforge` init/update 迁移契约与相关 portability 文档 | 无；消费确认卡的迁移规则 |
| 2A | implementation-worker | 版本、CHANGELOG、README 和最终文档索引 | 依赖组 1 实际改动 |
| 3 | main + review-auditor | dogfood 串联、测试、独立审计和修复 | 依赖组 1/2 完成 |

## 执行收据

- 组 1A：`/root/project_junction_core`（完成：`--mode check|plan|migrate --confirmed`、15 项专项测试通过；ignored __pycache__ 保留未删）
- 组 1B：`/root/project_hook_carriers`（完成：Codex hooks.json 承载面与 dogfood 镜像，JSON 断言通过）
- 组 1C：`/root/project_migration_contract`（完成：迁移契约、三类合并规则与 `--mode migrate --confirmed` 接口）
- 组 2A：`/root/project_codex_versioning`（完成：根仓与 Codex 模板版本/CHANGELOG 校验通过）
- 组 2B：`/root/project_claude_versioning`（完成：Claude 模板版本/CHANGELOG 校验通过）

## 验收

- 正确/错误/断裂 junction，新 clone，独有文件合并，内容一致，内容冲突，校验失败与删除顺序均有测试。
- Codex hook 配置由真实有效承载面发现；Claude 注册不回归。
- 双模板、dogfood、版本与 `[product]` CHANGELOG 一致。

## 最终收据

- `.venv\\Scripts\\python.exe -B tests\\harness\\test_memory_junction_check.py -v`：15/15，通过正确/错误/断裂 junction、确认门、冲突、Windows 大小写冲突、完整性校验与删除顺序。
- `.venv\\Scripts\\python.exe -B tests\\harness\\test_shared_skill_distribution.py`：14/14，通过 manifest 清单和哈希分发回归。
- `.venv\\Scripts\\python.exe -B tests\\harness\\run_downstream_fixture.py`：33 checks 通过。
- `git diff --check`：通过。
- 独立审计：无 P0/P1；真实 Codex/Claude trust/new-session smoke 未在本线程执行，交付状态为 trust 未验证。
- 审计修复后复验：状态机专项 15/15、shared-skill 分发 14/14、manifest inventory 1/1、`git diff --check` 均通过；独立审计最终为 READY，无 P0/P1/P2。
