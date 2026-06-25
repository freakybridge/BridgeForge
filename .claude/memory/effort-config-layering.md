---
name: effort-config-layering
description: Claude Code effortLevel 多层覆盖关系 + bridgeforge v0.31.0「项目层禁写 effortLevel、全局统一管 + SessionEnd 自动还原 medium」反转决策
metadata: 
  node_type: memory
  type: project
  originSessionId: 18992951-df51-47c9-910b-1f37d200374e
---

Claude Code `effortLevel` 多层合并优先级（高→低）：Managed > 命令行/env(`CLAUDE_CODE_EFFORT_LEVEL`) > 项目 `.claude/settings.local.json` > 项目 `.claude/settings.json` > 用户级 `~/.claude/settings.json`。**项目级覆盖全局**（实测 + 文档 code.claude.com/docs settings/configuration/model-config）。

关键事实（踩坑根源）：
- `/config` 的 Effort slider 和普通 `/effort <level>` **都落盘到用户级全局** `~/.claude/settings.json`（普通 `/effort` 本该会话级却落盘 = 已知 bug #53331）。**唯一真·会话级、自动还原的是 `ultracode`**（= xhigh + 自动 workflow）。
- 平台**无**"对话结束自动还原 effort"内建行为；Opus 4.8 默认 effort = `high`（项目+全局都删光不设 → fallback 到 high，更糟）。
- effortLevel 大概率开机读一次（非实时重读）→ `SessionEnd` hook 改、**下次会话**生效。

**反转决策（v0.31.0 / 2026-06-26）**：原 `portability.md §1` 红线"项目级**应当**写 effortLevel 覆盖全局（按项目定档 + 可移植）"被证明是坑——它把顺手的 slider/`/effort` 顶掉，用户"调了不生效、被锁在 high 难降"，而 high effort 是 token 空转无回复的放大器（根因：高 effort 下"拿到信息不收口"，每点工具结果就思考到 64k `max_tokens` 截断）。改为：
1. 项目层（含 `templates/settings.json`）**一律不写 effortLevel**，effort 由用户级全局统一管（一个 slider 控全舰）。**由 `SessionStart` hook `enforce_no_effortlevel.py` 机检强制剔除**（不靠散文 rule——本骨架特征：能机检的红线一律 hook 化）。
2. 用户级全局 baseline = `medium`；要深想 → 会话内 `/effort high` 或 ultracode 临时顶。
3. 全局 `SessionEnd` hook `~/.claude/reset_effort.py` 关对话把 effortLevel 原子还原回 medium（json 读改写 + temp+os.replace + `.bak`）。**个人全局，刻意不进 `templates/`**（否则 N 个下游抢改同一全局文件打架）。

**Why**：项目级 effortLevel 优先级 > 全局，顶掉唯一顺手的调节入口，造成"锁死高档 + 难降 + 持续烧 token"。
**How to apply**：① 新项目骨架不带 effortLevel；② 项目级 effortLevel 由 `enforce_no_effortlevel` SessionStart hook **自动剔除，无需手删**（流入会架空全局机制，故机检）；③ 想永久改基线 → 改 `reset_effort.py` 的 `BASELINE` 或全局文件；④ 临时提效用 `/effort`/ultracode，别写进任何项目文件。关联 [[utf8-garble-rootcause]]（同属"配置/环境层悄悄改变 agent 行为"）。
