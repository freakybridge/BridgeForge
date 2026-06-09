# 已退役的通用 skill（tombstone / 退役清单）

> setup_agent 出品过、但已**退役下架**的通用 skill 名单。
>
> **为什么存在**：正向同步（`/setup_agent` Step 0）只增不减——上游删掉一个 skill，
> 下游用户级架子 `~/.claude/skills/` 上的旧副本会**赖着不走**（「删除不传播」洞）。
> 本清单是机器可读的"墓碑"，让两处认出"下架的 skill 还在架上"：
> - `templates/hooks/skill_sync_check.py`（SessionStart 自检）→ 报 "N 个已退役待删"
> - `/setup_agent` Step 0 退役清理 → 列出来**问用户**删（绝不静默删）
>
> **格式**：每行 `- <skill 名> | <退役版本> | <日期> | <原因>`。
> 机器**只取第一列**（skill 名，到第一个 `|` 或空白为止），其余列给人看。
>
> **退役一个 skill 的完整动作**（缺一不全）：
> 1. 删 `skills/<name>/`
> 2. 在本文件追加一行
> 3. CHANGELOG 记 `[product]` Removed
>
> **范围**：本清单只管**用户级 skill**。退役的 **hook**（如 `memory_guard.py`，活在下游
> 项目 `.claude/hooks/` + 项目 settings 注册里）是项目级、需另一套机制，暂仍靠手动删
> （见 CHANGELOG v0.24.0 Removed 条 + `docs/skill-distribution-gaps.md` 支柱 B 待办）。

- prune-memory | v0.24.0 | 2026-06-09 | 手动 MEMORY.md 治理整代废弃，改由 memory_rebuild 自动评分（封顶活跃 40 + >45 天冷区化）
