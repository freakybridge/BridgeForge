---
name: project-skill-junction-single-source
description: C盘 skills/bridgeforge 是指向 D:\Quant\BridgeForge 的 junction，单一源在 D 盘，别被 Glob 穿透骗成「两份」
metadata:
  node_type: memory
  type: project
  originSessionId: 6045254e-37d9-4527-ab51-00254fb4fa5c
---

`C:\Users\bridg\.claude\skills\bridgeforge` 不是独立副本，而是一个 NTFS **junction（LinkType: Junction, Target: D:\Quant\BridgeForge）**。物理文件**只有 D 盘一份**，C 盘只是 Claude Code 发现 skill（`~/.claude/skills/<name>/SKILL.md`）用的透明跳板。

> 历史：框架 v0.29.0 由 `setup_agent` 更名 `bridgeforge`，旧 junction `setup_agent → D:\Quant\setup_agent` 一度悬空，已重建为 `bridgeforge → D:\Quant\BridgeForge`（旧 D 盘路径同步改名 BridgeForge）。

**单一真相源 = `D:\Quant\BridgeForge`。** 所有编辑、版本 bump、下游 harvest（反哺）都只改 D 盘；C 盘 junction 实时"看到"，无需任何同步。以后所有操作（含 git）都直接在 D 盘做，别去 C 盘那个路径操作，免得自己产生"两份"的错觉。

**坑：Glob/文件列举会穿透 junction**，把 C 盘和 D 盘列成两份一模一样的内容（连 `.git/objects` 哈希都对应），看起来像两个独立副本。**判定真伪**：`Get-Item <path> -Force` 看 `LinkType`/`Target`，是 Junction 就是同一份。参见 [[feedback-glob-search-gotchas]]。

**注**：junction 单一源模式现已在 `INSTALL.md` 正式集中说明（区分"只用不改"直接 clone 一份真实副本 vs "又用又维护"用 junction 物理只留一份），不再是文档缺口。