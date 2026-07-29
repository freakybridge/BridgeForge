---
status: confirmed
topic: memory-rule-organization
date: 2026-07-29
source: $confirm
handoff: develop
---

# 项目 memory 写入边界与遗留 note 迁移

## 原始需求摘要

下游项目调用 `$summary` 时，项目经验必须写入项目内受 Git 管理的
`.codex/memory/`，不能隐式回退到 `~/.codex/memories`。同时应在无参数
`/bridgeforge` 的既有项目维护分支中，安全迁移可明确归属当前项目的历史 note，
并清理无引用的空 `~/.codex/memory` 孤儿目录。

## 已核实事实

- 现有 `skills/summary/SKILL.md` 使用“当前 agent memory”表述，未将下游项目
  `$summary` 的目标路径锁定为 `<repo>/.codex/memory/`。
- `~/.codex/memories` 已由用户级 `config.toml` 的 `memories`、
  `generate_memories`、`use_memories` 启用，是用户级 memory 存储；不得整体删除。
- `~/.codex/memory` 是普通目录、非 junction，只含空的 `MEMORY.md`、
  `MEMORY_COLD.md` 与 `_stats.json`；当前用户级配置、hook 与 BridgeForge
  junction 逻辑均不引用它。
- BridgeForge 对外命令只有 `/bridgeforge` 与 `/bridgeforge switch <claude|codex>`；
  `update` 只是无参数 `/bridgeforge` 的内部判场，禁止作为公开命令或提示文字。
- 现有遗留 note 中只有含 `项目：<绝对路径>` 的记录可机器判定归属；标题或正文
  推断不能作为自动迁移依据。
- `cross_project_write_guard.py` 已注册为模板和 dogfood 的跨项目写入边界，但它只
  拦截项目外写入，不足以将 `$summary` 的项目内目标精确限制到 `.codex/memory/`。

## 已确认业务规则

1. 受 BridgeForge 管理的下游项目调用 `$summary` 时，唯一写入目标是
   `<repo>/.codex/memory/`；同主题记录优先合并。
2. `$summary` 必须通过确定性项目 memory 写入器：验证项目标记、目标解析路径与
   可写性，执行写入或合并并重建索引。任一校验失败即停止。
3. 用户级 `~/.codex/memories/extensions/ad_hoc/notes` 仅在用户明确要求跨项目或
   全局经验时允许写入；不得作为项目写入失败的回退。
4. 项目 memory 不可写、junction 异常或分类无法确认时，必须报告阻塞；全局目录
   保持未写入。
5. 无参数 `/bridgeforge` 进入既有项目维护分支时，仅扫描
   `~/.codex/memories/extensions/ad_hoc/notes/`。候选 note 必须同时满足：
   `项目：<绝对路径>` 严格等于当前项目，且当前项目已受 BridgeForge 管理。
6. 命中候选后先展示迁移计划；用户确认后才允许合并到项目 memory、重建并验证
   索引、删除原 note。未分类 note 不迁移、不删除。
7. `~/.codex/memory` 只有在它是非 junction 普通目录、仅含空索引与空
   `_stats.json` 时才可作为清理候选展示；用户确认后才删除。任何正文、子目录、
   链接或异常都必须阻断删除。
8. `~/.codex/memories` 禁止整体迁移或删除。
9. 所有用户可见命令提示统一为 `/bridgeforge`；不得出现 `/bridgeforge update`。

## 双层强制边界

- 运行时边界：保留并验证 `cross_project_write_guard.py`，对隐式用户级 memory
  写入进行阻断。
- 确定性边界：新增 `$summary` 专用写入器，唯一接受已验证的
  `<repo>/.codex/memory/` 目标，并负责合并和索引重建。
- 静态配置与 harness 不等同于运行时 trust。下游安装后必须在 `/hooks` review/trust
  并开启新会话完成 smoke；此前状态只能标记为 `runtime trust 未验证`。

## 拟修改范围

| 层级 | 路径 / 责任 |
|---|---|
| 产品 skill | `skills/summary/`、`skills/bridgeforge/` |
| 产品模板与 dogfood | 确定性项目 memory 写入器、必要的迁移逻辑与对应 `.codex/` 验证资产 |
| 测试 | 迁移与写入器的单元 / downstream harness |
| 元文档 | 本需求卡、BUG 记录关联、版本与 `[product]` CHANGELOG |

产品层变更必须按 BridgeForge 传播规则同步下游，bump 根 `VERSION` 并记录
`[product]`。若实现涉及 `templates/codex/hooks/` 或 `settings.json`，必须同步
BridgeForge 自身 `.codex/` 并通过 mirror 校验。

## 不做

- 不删除或批量迁移 `~/.codex/memories`。
- 不按标题、正文关键词或模型推断自动决定 note 的项目归属。
- 不在用户确认前删除任何遗留 note 或 `~/.codex/memory`。
- 不新增 `/bridgeforge update` 公开命令。
- 不自动 commit 或 push。

## 验收标准

1. fixture 下游项目调用 `$summary` 后，新增或更新文件只位于
   `<repo>/.codex/memory/`，且 `MEMORY.md` 含对应索引；不产生用户级 note。
2. 明确请求跨项目 / 全局经验时才允许用户级写入。
3. 模拟项目 memory 不可写、junction 异常或分类未决时，写入失败且用户级目录
   保持未写入。
4. `/bridgeforge` 只迁移严格匹配当前项目的 note；项目索引验证成功后才删除原件。
5. 未分类 note 始终原样保留。
6. 空孤儿 `~/.codex/memory` 仅在用户确认且严格空条件成立时删除；任一异常条件
   必须零删除。
7. harness 覆盖上述路径，并验证 guard 对用户级 memory 路径的阻断。
8. 下游真实 `/hooks` review/trust 与新会话 smoke 未完成前，不得宣称运行时 guard
   已验证。

## 实施与验证记录

### 实施计划

1. 在 Codex 模板和 BridgeForge dogfood 增加项目 memory 写入器与遗留恢复器；两者都以
   解析后的项目根和路径边界 fail-closed。
2. 将 `$summary` 改为只通过写入器写受管 Codex 项目 memory；无可用写入器时停止并
   提示无参数运行 `/bridgeforge`，不回退用户级 note。
3. 扩展无参数 `/bridgeforge` 的既有项目维护手册：先展示严格归属 note / 空孤儿目录
   计划，用户确认后再调用恢复器 apply。
4. 统一 junction 迁移的公开提示为 `/bridgeforge`，同步 Codex/Claude 模板和 Codex
   dogfood hook。
5. 用 focused harness 验证写入、索引、严格归属、来源 hash 变化不删、空目录确认门和
   dogfood 镜像。

### 已执行

- 已新增 Codex 项目 memory 写入器和恢复器，并镜像到 BridgeForge `.codex/scripts/`。
- 已更新 `$summary`、无参数 `/bridgeforge` 维护手册及 junction 命令提示。
- 已运行：`python tests\\harness\\test_project_memory_recovery.py`（6 tests）、
  `python tests\\harness\\test_memory_junction_check.py`（15 tests）、`python -m py_compile`
  （4 个新增/镜像脚本）与 `git diff --check`；均通过。
- 独立交付复审：首次发现孤儿目录索引正文未纳入资格和 fingerprint；已修复并补充
  3 条回归。复审确认索引含条目拒绝、计划后索引变化阻断、严格空目录经确认后删除和
  模板 / dogfood 镜像均无阻断。
- 下游 `/hooks` trust / 新会话 smoke：待真实下游安装后执行；当前为未验证。
