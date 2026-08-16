---
category: topic
topic: codex-project-zone-ownership
status: completed
description: BridgeForgeCodex 通过公共只读区与项目专区分离根 AGENTS ownership，并对旧项目执行零损失、fail-closed 迁移。
kind: delivery
tags: bridgeforge-codex, agents, ownership, project-zone, migration, fail-closed
related_paths:
  - doc/1_delivery/codex-project-zone-ownership/requirements_2026-08-17_codex-project-zone-ownership.md
  - templates/AGENTS.md
  - templates/managed-skeleton.json
  - scripts/bridgeforge_codex_project_sync.py
  - templates/hooks/instruction_source_check.py
  - templates/hooks/mirror_drift_check.py
  - templates/scripts/version_release.py
  - scripts/rebuild_shared_skill_manifest.py
  - scripts/tests/test_bridgeforge_codex_project_sync.py
  - scripts/tests/test_instruction_source_check.py
---

# Codex 项目专区与公共区 Ownership

## 已验收契约

- 根 `AGENTS.md` 使用精确 marker 分为 BridgeForge 公共区与项目专区；公共区由产品管理，项目专区由下游完全所有并逐字保留。
- 项目级通用约束写入根项目专区；目录专属约束写入嵌套 `AGENTS.md`；可机器判定约束使用项目自有 hook 与 `hooks.json` handler。
- 带 marker 项目仅允许可信公共区迁移；公共区漂移、marker 缺失/重复/逆序或 contract 无法验证时 fail closed。
- 旧无 marker 项目只有在受管章节与 residual 内容均命中发布谱系时才自动迁移；无法分类的前言、分组普通文本、自定义标题或其他内容保留整份原文件并报告 gap。
- `root.agents` 存在 gap 时禁止退休 8 个旧 Markdown rule，也禁止推进 BridgeForgeCodex 版本戳。
- 项目专区标题扫描必须识别 fenced code，示例代码中的 Markdown 标题不得造成重复标题误拦。

## 验证与真实样本

- 完整 unittest 227/227、已发布版本迁移 fixture 19/19 通过；manifest、instruction、mirror、skill metadata、project structure 与 `git diff --check` 均 exit 0。
- `test_bridgeforge` 最终只读计划为 safe=0、risk=1、gaps=26、rule actions=0，旧戳保持 0.90.0。
- `test_bridgeforge_crs` 最终只读计划为 safe=0、risk=0、gaps=17、rule actions=0，旧戳保持 1.0.0。
- 两个样本的项目约束、branch 与 HEAD 均保持；本交付未对样本 commit 或 push。
- 最终独立审计未发现 Blocker、High 或 Medium。

## 边界

- 高定制旧项目允许保持 `completed_with_gaps / degraded`；兼容的判据是项目资产零损失、gap 清晰、旧 rule 不误删、版本戳不前移，而不是强制达到 ready。
- 自然语言项目规则是否削弱公共红线无法由简单 hook 自动证明；机器闸只保证公共区字节完整、结构有效和 ownership 边界。
- 暂存区 instruction gate 留待 `$git-sync` 精确暂存后执行；当前会话没有独立的新会话 runtime trust 收据，runtime trust 未验证。
- 用户于 2026-08-17 明确调用 `$summary 同意验收`，本 topic 状态为 completed。
