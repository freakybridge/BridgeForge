---
name: utf8-garble-rootcause
description: 中文 hook 输出在 GBK Windows 上糊成 U+FFFD 注入 context、曾高频致 agent 跑偏；根因/已修手段/残留/为何不过度加固的完整地图
metadata: 
  node_type: memory
  type: project
  originSessionId: bcafccde-dc6d-4f9c-8e5e-d2ca0cee57d9
---

2026-06-25 调查：一次会话（评估 GitHub 公开风险）跑偏，顺藤摸出一个**系统性**编码问题。

## 根因（一个根，四处症状）
中文文本 + **中文版 Windows 默认 GBK** + 工具按 UTF-8 读 = 乱码 U+FFFD（�）。全部 transcript 扫出 **8.5 万个 �**、横跨所有下游项目（StratusAgent / CausisRiskSuite / ClaudeBridgeAssist）。
- 直接源：Python hook（最大头是每条 prompt 都触发的 `context_warning.py` `[ctx-budget]` 等 UserPromptSubmit hook，2.2 万）往 stdout 打中文 → 糊。
- 次生源：糊掉的字节被写进 snapshot/memory 文件，后来被 Read / Bash `cat` 读出 → 再现乱码（Read 1.2 万 / Bash 1.7 万其实多是读到已写坏的文件，**不是独立病**）。
- 溯源最早一条：2026-06-01 StratusAgent 的 `target_cleanup.py` `[target-cleanup]` 开机中文提示。但本质不是某个 hook 的错——"中文 hook + GBK Windows"组合下第一个触发的中文 hook 必中招。

## 已修手段（6-24, v0.28.1）
1. **全局 `env.PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`**（用户级 `~/.claude/settings.json`）——UTF-8 Mode 让 Python 的 print + `open()` + subprocess text **一锅端**走 UTF-8。这是真治本，也是为何修复后**所有工具类型一起归零**。
2. 16/16 hook 各带 `sys.stdout.reconfigure(encoding="utf-8")`——**与 PYTHONUTF8 功能重叠的冗余 belt**（env 生效时它无关紧要）。
修复后真实会话乱码 ≈ 0；用户体感"修复前每天多次数不过来 → 后明显降低"印证因果。

## 残留（低频，且多不可在 harness 修）
- 模型自己跑的**非 Python 原生程序**（.exe/未配 git）吐中文，PYTHONUTF8 管不到（控制台代码页 GBK）。已配 git UTF-8 三件套堵 git 那块。
- **模型自身流式解码抽风**（junction 那次的 �，在 assistant 输出、客户端层）——harness 够不着，任何大模型都有小概率，**不可防**。见 [[feedback-review-technique]] 式的"看到跑偏就打断纠偏"。

## 落地的护栏（右尺寸，反过度加固）
经两轮 debate（docs/debates_2026-06-25_encoding-fix-scope.md）砍掉镀金项：**不**新增守卫 hook、**不**加 portability rule 红线（env 透明兜底 → 新 hook 作者无需记任何事 → 红线无可执行内容）。最终只做：
- `memory_junction_check.py`（SessionStart，templates+.claude 双份）加 `_utf8_mode_guard()`：查 `sys.flags.utf8_mode`（**事实**，不被 reconfigure 掩盖），OFF 才打**纯 ASCII** 告警。守的是唯一承重柱（PYTHONUTF8 是否生效），不巡逻冗余的 per-hook reconfigure。
- git UTF-8 三件套（本仓库 --local + 写进 templates/CLAUDE.md §6 可选 checklist）。
- 本条 memory。

**Why**：n=1 偶发 / 0 复发问题动产品层会把"安慰剂式加固/坏惯例"复印进所有下游（幸存者偏差陷阱）。真病 env 层已治本，剩下只值得"记账 + 在承重柱贴勿拆标签"。

**How to apply**：① 写任何会输出文本的 hook/脚本——靠 PYTHONUTF8 全局兜底即可，中文可放心用，别为它单独加 ASCII-only 约束（区别于 [[此处可链 portability §4.4.1]] 双击入口脚本那种无兜底场景）。② 见到 `[utf8-guard] WARNING` = 某机 PYTHONUTF8 没生效，去补 `~/.claude/settings.json` 的 env 块。③ 别再提议"hook 改英文"——那是冗余避害且只覆盖 hook 一处，PYTHONUTF8 更全。
