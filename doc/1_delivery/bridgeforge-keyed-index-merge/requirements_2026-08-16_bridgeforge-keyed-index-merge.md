---
title: BridgeForge 索引稳定键合并需求确认卡
status: implemented
date: 2026-08-16
source: confirm
handoff: develop
---

# BridgeForge 索引稳定键合并需求确认卡

## 原始需求摘要

下游选择 A 激进吸收后，`AGENTS.md` 的“规则文件索引”整段被上游替换，导致
`alerting.md`、`check_panel_ux.md` 等项目专属索引消失。用户要求上游与下游真正合并，
激进模式只能让上游赢得同一索引键的冲突，不能删除无冲突的项目条目。

## 目标

- 为规则索引、目录索引提供显式 keyed-table ownership。
- 上游新增受管键可安全加入；下游独有键逐字保留；同键差异才生成 U 冲突。
- A/B/C 继续保持全轮 0 次或 1 次业务确认，并准确说明影响范围。
- version-release 能区分官方索引行、项目索引行和两者混合修改。

## 不做

- 不实现任意 Markdown 的通用语义合并或完整 AST。
- 不自动恢复已被旧版本删除且当前文件、Git 均无证据的内容。
- 不自动删除上游不再出现的历史键；退役需未来显式 `retired_keys` 与历史证据。
- 不改变普通规范正文的上游区块覆盖语义，不增加第四个确认选项。
- 不自动 commit 或 push。

## 任务规模与预算

- 规模：M。
- 判定依据：跨 schema ownership、project-sync、四份 version-release 镜像、收据、文档和测试，
  但保持现有 schema v2、事务执行器和 A/B/C 命令面。
- 时间预算：45 分钟。
- token 预算：约 20k 新增 token；平台无可靠计量器，标记为未实测。
- agent 预算：最多 1 个独立审计 agent；实现阶段默认 0 个。
- 验证预算：最多两轮。
- 超预算停止点：若必须升级 schema v3、引入完整 Markdown AST、恢复无证据历史内容，或
  超过两轮验证，停止并由用户决定扩大预算或缩小范围。

## 已核实事实

- schema v2 的 `whole + managed_blocks` 只登记 Markdown 标题，未登记标题内数据身份。
- `_plan_managed_markdown_blocks()` 对差异标题生成整段 replacement；A 会覆盖该标题全部内容。
- `version_release.py` 同样把整个登记标题视为 BridgeForge 所有，无法识别项目独有表格行。
- `AGENTS.md` 的规则索引和 `doc/README.md` 的目录/文件索引均使用首列稳定身份表格。
- `AGENTS.md` 的架构红线、快速命令和项目结构速查是明确的项目填充区，不应成为上游覆盖区。

## 已确认业务规则与数据映射

- schema v2 保持兼容：原 `headings` 继续表示 replace；新增 `keyed_tables` 显式登记表格。
- 每个 keyed table 以精确标题定位，以第一列规范化值作为稳定键，并在 contract 中显式登记
  BridgeForge 管理的 `managed_keys`。
- 上游键缺失于下游时作为 safe insert；下游非 managed key 永远保留。
- managed key 同值为 no-op；同键异值生成一个 U。A 吸收上游行，B 逐 U 选择，C 保留本地行。
- 输出顺序为上游 managed keys 的模板顺序，随后是下游独有键的原相对顺序。
- 重复键、多个候选表格、损坏表头、列数不一致或解析歧义必须零写入并进入 gap/blocker。
- 上游当前未列出的旧键保守视为项目内容；没有显式退役证据时禁止删除。

## 拟修改

- `scripts/bridgeforge_project_sync.py`：schema 校验、keyed-table parser、planner/apply、receipt。
- `templates/codex/managed-skeleton.json` 与 `.codex` dogfood：ownership 分类。
- 四份 `version_release.py`：按键拆分 managed/project ownership。
- `scripts/rebuild_shared_skill_manifest.py`：contract keyed-table 硬校验。
- `skills/bridgeforge/SKILL.md`、同步设计与本需求卡：产品契约。
- project-sync、version-release、fixture 与镜像测试；重建 shared manifest。

## 验收标准

- 下游索引含 `alerting.md`、`check_panel_ux.md` 时，A/B/C 后两项均保留。
- 上游新增 managed key 无冲突时 safe 加入，不展示空确认卡。
- 同一 managed key 双方内容不同才生成 U；A/B/C 的最终行与 receipt 一致。
- project-owned 标题不进入 U，不被 A 修改。
- `doc/README.md` 下游独有目录/文件行同样保留。
- version-release 对项目行、受管行、混合修改分别判定正确，旁路官方行仍被阻断。
- 解析歧义、fingerprint 漂移、验证失败均零风险写入或完整回滚，版本戳保持旧值。
- 目标单测、真实 CLI fixture、manifest check、四镜像一致性和 `git diff --check` 通过。

## 合理假设与风险

- 首列路径/名称在现有表格中具有稳定身份；规范化只去 Markdown code/link 包装与首尾空白，
  不做模糊匹配。
- 合法但复杂的转义管道若不能确定解析，宁可 gap，不猜测。
- 已被旧版本删除的项目行只能从 Git 或用户持有的事实恢复；本修复保证未来更新不再删除。

## 自动化边界

- 只修改当前 BridgeForge 工厂工作区及其产品/dogfood 镜像。
- 不修改 `ClaudeBridgeAssist` 或其他下游；真实下游试用由用户完成。
- VERSION、CHANGELOG、commit 和 push 仅在后续显式 `$git-sync` 中执行。

## 实施 / 验证记录

- 已在 schema v2 的 `managed_blocks` 中新增 `keyed_tables` 契约；`headings` 继续保持整段替换语义，索引表改为按稳定键合并。
- `AGENTS.md`、`doc/README.md` 的官方索引行由 BridgeForge 管理；下游独有键始终保留，缺失官方键安全插入，同键内容差异才生成逐项 `U` 冲突。
- A/B/C 均不再因吸收上游而删除下游独有索引；A/B 只替换用户确认的同键行，C 保留原样。
- 独立审计发现 parser 曾把合法 `\|` 或缺尾管道的损坏行当作表格结束；现已支持合法转义竖线，并让仍以 `|` 开头的损坏行 fail-closed 为 gap，禁止写新版本戳。
- `version_release.py` 已同步识别 keyed-table 的 `skeleton`、`project` 与 `mixed` ownership，四份宿主/模板镜像保持同源。
- 自动化验证：相关单测首轮 48 项中 47 项通过，唯一失败为测试样本未同时制造 project 变化；修正样本后定向复测 1/1 通过。
- parser 修复后，新增 escaped-pipe、malformed-tail 与 version-release 定向回归 3/3 通过；相关测试 50 项中 49 项直接通过，唯一 ACL 环境错误提升权限复跑后 1/1 通过；root skill/actionable 文案契约 13/13 通过。
- 真实 CLI fixture：`project-sync-absorption-card`、`project-sync-keyed-index` 均通过，覆盖单次确认、同键吸收及下游独有行保留。
- 完整 downstream fixture 全部通过。
- 静态硬闸：manifest `--check`、harness parity、mirror drift、skill metadata、`git diff --check` 全部 exit 0；四份 `version_release.py` SHA-256 一致。
- 独立发布审计通过：核心 project-sync/version-release 39/39、root skill/actionable 13/13、完整下游 fixture 39/39，未发现剩余发布阻断。
- 本轮未修改真实下游 `ClaudeBridgeAssist`，未执行 VERSION/CHANGELOG 发布、commit 或 push。
