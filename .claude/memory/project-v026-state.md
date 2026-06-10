---
name: project-v026-state
description: setup_agent v0.26.x 系列摘要（rule 约束 hook 化 + skill model 轻量化，2026-06-10）
metadata: 
  node_type: memory
  type: project
  originSessionId: 9c6e8492-ee13-489c-b8bd-36afd74c0ee0
---

## v0.26.0（2026-06-10）`[product]`

**支柱 B v0.26.0 — 3 条 rule 约束 hook 化 + 全面 dogfood 修复**（详见 CHANGELOG）
- 三条 rule 从"自觉"升级为 Stop hook 自动拦截
- 全面 dogfood 镜像修复（自身 .claude/ 与 templates/ 对齐）

## v0.26.1（2026-06-10）`[product]`

**rule_size_check 横切规则白名单**：消除框架规则触发器宽度永久误报。
- `rule_size_check.py` 新增白名单机制，跳过宽触发器的框架性规则文件（如 meta_rule_design.md）

## v0.26.2（2026-06-10）`[product]`

**`skills/git-sync/SKILL.md` frontmatter 加 `model: sonnet`**
- git-sync 是纯机械活（fetch diff / 生成提交消息 / push），不需要主模型推理强度
- `model` 字段语义（官方文档原文）：
  > "The override applies for the rest of the current turn and is not saved to settings; the session model resumes on your next prompt."
  — 即只管当轮，轮结束自动回原模型，不写 settings，不改会话
- 与 `summary` skill 已有的 `model: sonnet` 对齐
- **已建立模式**：高频低难度 skill → `model: sonnet`（省 token，无副作用）
- 用户级副本 `~/.claude/skills/git-sync/SKILL.md` 已同步

### 当前已用 `model: sonnet` 的 skill 清单

| skill | 原因 |
|-------|------|
| `summary` | 归档总结，结构化写入，无需强推理 |
| `git-sync` | 机械提交，无需强推理 |

**Why:** `model` frontmatter 是 Claude Code 官方支持的 per-skill 临时模型覆盖机制；记录哪些 skill 已用、模式何时建立，避免重复核实或漏加。

**How to apply:** 设计新 skill 时，若属于"高频、机械、低推理"类型，可加 `model: sonnet` 降低 token 消耗；加前不必再查文档，语义见本条引用。

[[project-v025-state]]
