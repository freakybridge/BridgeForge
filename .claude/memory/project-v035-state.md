---
name: project-v035-state
description: v0.35.0 debate/collab 六步重构 L1 审计 + 闸硬度修补（2026-06-27）
metadata:
  node_type: memory
  type: project
  originSessionId: 3768f027-d44b-4f5e-aeb3-804ca7e4229b
---

## 背景

debate/collab 两个重型 skill 在一个工具传结果线抽风的会话里完成了六步重构（渐进对齐、三道闸开在烧 token 之前）。本轮是新会话独立审计 + L1 静态修补。

## 版本登记问题

0.34.0 被 memory 索引重写（确定性事件驱动）抢先占用并提交，debate/collab 重构原来没有版本号。本轮 bump 到 **0.35.0**，补 CHANGELOG entry。

## L1 审计发现的主要问题（已修）

**🔴 致命：闸的硬度**（最重要）
- 三道闸原来只写"停下等用户"（描述性），无工具级回合终止契约
- agent 会把三道闸一口气连贯跑完，彻底破坏重构目的
- 修法：每道闸加 `⛔ 硬契约`，明确"必须以 AskUserQuestion 结束回合，用户未回复禁止任何后续动作"；闸②③点名工具；明说闸①②绝不可合并

**🟡 A（debate SendMessage 续接）**
- id 取法、存哪、怎么传全没说；续接失败无降级路径，且 MD 被剥夺上下文职责后退路被堵死
- 修法：写清从 spawn 返回取 id → 记 MD 头部 → SendMessage to: id；补降级（失败则回读 MD 新 spawn 同角色）

**🟡 D（collab 独立 review）**
- review agent 输入未定义；"复查结论"措辞诱导审文字而非审代码
- 修法：定义三项输入（目标/接口约定/文件清单）+ 硬性要求独立 Read 代码/跑 diff

**🟡 G（轻量出口）**
- 判据主观无锚；collab 研读后才发现不可拆，但 Step3 没出口检查点
- 修法：给粗判据（≤2 文件）；collab Step3 补研读后出口

**🟢 E**：措辞"对齐全局红线" → "比全局更严"

**🟢 agentId 字段**：硬编码 `agentId` → 改为描述性措辞，避免 harness 演化后下游失效

## 审计方法（本轮验证有效）

独立 agent（不带本会话预判）逐字读全文 + git diff 复核，三道验证：母版内容 → 修补后内容 → 独立复审。见 [[tool-result-corruption-triggers]]。

## 文件

- `skills/debate/SKILL.md` + `~/.claude/skills/debate/SKILL.md`
- `skills/collab/SKILL.md` + `~/.claude/skills/collab/SKILL.md`

**Why:** 记录版本号撞车根因 + 审计发现的硬伤，防止后续再把"停下等用户"当成可用的闸设计。

**How to apply:** 写任何 skill 的"等用户确认"步骤时，直接参考 [[feedback-skill-gate-hardness]]。