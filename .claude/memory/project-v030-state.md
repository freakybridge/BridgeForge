---
name: project-v030-state
description: v0.29.2 summary trim + v0.30.0 产品层全面瘦身：skill/CLAUDE.md/rules 总减 250+ 行，建立 redline-placement 原则 + external-references 模式
metadata: 
  node_type: memory
  type: project
  originSessionId: bcafccde-dc6d-4f9c-8e5e-d2ca0cee57d9
---

## v0.29.2（2026-06-25）
- **summary skill trim**：135→55 行。触发原因：`/summary` 注入 context 把已近满的 ctx 顶爆 compact，在关键时刻丢失信息。修法：低频步骤 3b/5 外置到 `references/deep-steps.md`，主文件只留 7 步骨架 + pointer。dogfood 同步至 `~/.claude/skills/summary/`。

## v0.30.0 产品层瘦身（2026-06-25）

### 改动一览

| 文件 | 变化 | 手法 |
|---|---|---|
| `templates/CLAUDE.md` | 325→251（-74） | hook 机制/配置细节外置到 anti_drift_hooks.md；§11 删论述留骨架 |
| `skills/find-doc/SKILL.md` | 170→97（-73） | 输出模板+映射 SOP 外置 references/ |
| `templates/rules/workflow.md` | 243→210（-33） | §9 SemVer 教程压缩；§5.5 删与 §11 重叠强制项表 |
| `templates/rules/portability.md` | 244→192（-52） | §4 包安装示例压缩 |
| `templates/rules/meta_rule_design.md` | 227→206（-21） | §3 自打脸示例压缩（rule 自身违 §7 修正） |
| `templates/rules/anti_drift_hooks.md` | 新建 64 行 | 承接 CLAUDE.md 外置的 hook 机制/配置细节 |

所有护栏（鬼打墙 4 禁止、漂移四类、doc 六层 + 5 禁止）逐条 grep 确认在位。

### 建立的两条新原则

**①  redline-placement 原则**（debate `docs/debates_2026-06-25_redline-placement.md`）：
- 骨架（粗粒度红线断言）→ 常驻层（CLAUDE.md）；场景操作细节 → path-triggered rule。
- 机械判据："这条约束在『不触发该 rule 的轮次』也可能被违反吗？是→骨架常驻 / 否→细节下沉"。
- §4.3 禁的是「逐字复制同一正文」，不禁分工式骨架+细节共存。

**② external-references 模式**（summary/find-doc skill 落地）：
- 低频/大段内容外置到 `references/` 子目录。
- 主 SKILL.md 留指针"命中时先 Read references/xxx"。
- 效果：每次 `/skill` 注入 context 的字节数大幅缩减，compact 风险降低。

### 遗留（待独立决策）

- **鬼打墙阈值冲突**：CLAUDE.md §8（第 4 次硬停）↔ debugging.md §6 T1（≥2 次升级）数字不一致。属行为变更，用户本次选「不修改」，与 §6 结构去重打包待单独决策。详见 [[ghost-wall-threshold-conflict]]。
- CLAUDE.md 251 行超 meta_rule §5 软红线（≤200）——剩余超额主要在 §8 鬼打墙组；阈值统一后一并压缩。
