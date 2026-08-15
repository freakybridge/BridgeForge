---
category: topic
topic: bridgeforge-upstream-absorption-modes
status: completed
description: BridgeForge 上游吸收采用 A/B/C 单次确认，并以稳定键合并索引表，吸收同键官方行时保留下游独有条目。
kind: delivery
tags: bridgeforge, upstream-absorption, managed-blocks, keyed-table, confirmation, transaction
related_paths:
  - doc/1_delivery/bridgeforge-upstream-absorption-modes/requirements_2026-08-15_bridgeforge-upstream-absorption-modes.md
  - doc/1_delivery/bridgeforge-keyed-index-merge/requirements_2026-08-16_bridgeforge-keyed-index-merge.md
  - scripts/bridgeforge_project_sync.py
  - templates/codex/managed-skeleton.json
  - shared-skill-manifest.json
  - skills/bridgeforge/SKILL.md
  - doc/0_architecture/design/codex-project-sync.md
  - tests/harness/test_bridgeforge_project_sync.py
  - tests/harness/test_git_sync_version_release.py
  - tests/harness/run_downstream_fixture.py
---

# BridgeForge 上游吸收模式

## 已验收契约

- 唯一业务确认卡提供 A 激进、B 温和、C 保守三种模式；每轮整体业务确认仍为 0 次或 1 次。
- A 在强风险提示和完整冲突清单后，一次确认执行全部推荐风险项并默认吸收所有可信上游受管区块；禁止整文件覆盖项目自有内容。
- B 支持稳定 `R/U` 编号及逐 U 自定义指令。每条指令必须确定表达 `absorb` 或 `preserve`；两种意图并存、缺少意图或试图在一个 U 内继续细分时零写入拒绝。
- C 保留已经完成的 safe 核心更新，不执行本轮进一步完善，也不保存永久拒绝偏好。
- 每个 `U` 对应一个显式登记的 Markdown 受管区块或 keyed-table 同键行；同一文件选择多个项目时合并为一次事务写入。无可信边界的变化只进入 manual/blocker。
- `.codex/memory/MEMORY.md` 使用 `seed` 策略；version-release 将 seed、受管标题区块之外的内容和 keyed-table 下游独有键视为项目所有。
- apply 受 aggregate fingerprint、事务快照、失败回滚和 stamp-last 保护；receipt 回显完整冲突卡及逐 U 的吸收/保留效果。
- `confirmation.options` 是不可改写的显示契约；冲突必须逐 U 展示完整项目相对路径、区块或稳定键、上游效果、本地影响与可恢复性，禁止压缩为编号范围或 basename。

## 稳定键索引合并

- schema v2 在 `managed_blocks` 下用 `keyed_tables` 显式登记索引表；普通 `headings` 仍保持整段替换语义。
- 索引表按稳定键合并：缺失官方键属于 safe insert；下游独有键始终保留；只有同一受管键内容不同才生成 `U`。
- A/B 只替换用户确认吸收的同键行，C 保留原样。激进模式不再因吸收上游索引区块而删除 `alerting.md`、`check_panel_ux.md` 等项目专有条目。
- keyed-table 重复键、表格歧义或契约与模板不一致时 fail closed 为 gap，禁止猜测合并。
- 合法 Markdown `\|` 作为同一单元格内容解析；仍以 `|` 开头但缺尾管道或结构损坏的行必须进入 gap，保持目标字节及旧版本戳不变。
- `version_release.py` 使用同一 keyed-table partition 识别 `skeleton`、`project` 与 `mixed` ownership，四份 Claude/Codex 模板及 dogfood 镜像同源。

## 0.94.0 下游格式回归修复

- 根因是缺失受管区块追加到文件末尾时复用了模板中间区块的分隔空行，导致 `AGENTS.md` 和 `workflow.md` 产生第二个末尾换行；旧比较逻辑又会归一化该边界，因此无法自愈。
- 受管区块改为按目标位置渲染：非末尾区块保留标题分隔空行，末尾区块只保留一个终止换行。既有 0.94.0 多余末尾空行被分类为 safe 边界修复，无需再次确认吸收。
- 写版本戳前对本轮受管路径执行 `git diff --check HEAD -- <targets>`；失败进入原事务回滚，禁止留下新版本戳。

## 独立审计与验证

- 上游吸收模式首轮独立审计发现的 B 自定义执行、managed-block ownership 和 receipt 对账三个阻断均已修复；独立复审通过。
- 0.94.0 格式回归修复已有 35 项相关 unittest、真实 CLI absorption-card fixture、manifest `--check` 与 `git diff --check` 通过收据。
- 稳定键合并的首次实现相关单测 48 项中 47 项通过；唯一失败来自测试样本未同时制造 project 变化，修正样本后该项定向复测 1/1 通过。
- 稳定键合并发布审计发现 parser 吞掉 `\|`/缺尾管道行及两条旧 skill 文案断言；修复后独立发布复审通过，核心 project-sync/version-release 39/39、root skill/actionable 13/13、完整下游 fixture 39/39。
- manifest `--check`、harness parity、mirror drift、skill metadata 与 `git diff --check` 均 exit 0；四份 `version_release.py` SHA-256 为 `87FB5E147B9EE0DB67DD372B498FBCB793F1AF433AE86BC6358906C61664C4CC`。
- 用户于 2026-08-16 明确调用 `$summary 同意验收`，稳定键索引合并验收成立，topic 保持 completed。

## 边界

- 真实下游 `ClaudeBridgeAssist` 的本次版本试用由用户后续执行，当前未验证。
- 当前会话未取得 Codex `/hooks` review/trust 或新会话 smoke 收据，runtime trust 未验证。
- VERSION、CHANGELOG、commit、push 和远端同步收据由紧随其后的受控 `$git-sync` 生成。
