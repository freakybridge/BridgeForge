# Memory Index — setup_agent

> Active: 12 | Cold: 0

## Pinned
- [project-rename-bridgeforge](project-rename-bridgeforge.md) — v0.29.0 起 setup_agent 更名 bridgeforge；活文档=bridgeforge，历史流水账故意保留旧名（双名共存非 bug）

## Active
- [project-v032-state](project-v032-state.md) — v0.32.0 反漂移红线补强：4条文本红线进 templates/CLAUDE.md，16-agent debate 定案，focus 结构盲点指针
- [tool-result-corruption-triggers](tool-result-corruption-triggers.md) — 工具传结果线腐蚀的两类触发器：shell for+pipe 批处理大输出 + AskUserQuestion 大段中文参数；dry-run ≠ 已改
- [project-v031-state](project-v031-state.md) — v0.31.0 effortLevel 治理反转：空转根因分析（Opus 4.8 高 effort 不收口）+ enforce_no_effortlevel hook 机检替代散文 rule + 全局 SessionEnd 自动还原 medium
- [effort-config-layering](effort-config-layering.md) — effortLevel 多层覆盖（项目级盖全局）+ v0.31.0 反转决策：项目层禁写 effortLevel、全局统一管 + SessionEnd 自动还原 medium；slider/`/effort` 落盘全局、唯一会话级是 ultracode（空转根因的可调旋钮）
- [project-v030-state](project-v030-state.md) — v0.29.2 summary trim + v0.30.0 产品层全面瘦身；建立 redline-placement 原则 + external-references 模式；鬼打墙阈值冲突遗留
- [project-v026-state](project-v026-state.md) — v0.26.x：rule hook 化 + skill model 轻量化（git-sync/summary → sonnet），官方 model 字段语义
- [project-v025-state](project-v025-state.md) — v0.25.0 支柱 B：开机自检 + 退役检测，退役三步 SOP，诚实边界
- [project-v024-state](project-v024-state.md) — v0.24.0 主要变更摘要（context_warning 升级/map 外置/memory 治理废弃）
- [feedback-review-technique](feedback-review-technique.md) — review 红线：收尾前重拉 status + 删 hook 后 grep 当前内容（非 diff）
- [utf8-garble-rootcause](utf8-garble-rootcause.md) — 中文 hook 在 GBK Windows 糊成 � 注入 context 曾高频致漂；治本=PYTHONUTF8（已修），剩余=模型流式抽风（不可防）；护栏=utf8_mode 自检，反过度加固
- [ghost-wall-threshold-conflict](ghost-wall-threshold-conflict.md) — 鬼打墙阈值 CLAUDE.md §8(3) ↔ debugging §6 T1(2) 冲突待统一；属行为变更不混进瘦身，与 §6 去重打包待单独决策

<!-- AUTO-HOT-START -->

## 🔥 Hot（Top-40，按访问时效自动维护）
- [effort-config-layering.md](effort-config-layering.md) — Claude Code effortLevel 多层覆盖关系 + bridgeforge v0.31.0「项目层禁写 effortLevel、全局统一管 + SessionEnd 自动还原 medium」反转决策
- [feedback-review-technique.md](feedback-review-technique.md) — setup_agent review 时的两条操作红线（并行编辑 + hook 删除安全检查）
- [ghost-wall-threshold-conflict.md](ghost-wall-threshold-conflict.md) — 鬼打墙计数阈值在 CLAUDE.md §8(3) 与 debugging §6 T1(2) 不一致，待统一；属行为变更不混进瘦身，用户暂选不改
- [project-v024-state.md](project-v024-state.md) — setup_agent v0.24.0 主要变更摘要（2026-06-09）
- [project-v025-state.md](project-v025-state.md) — setup_agent v0.25.0 支柱 B 实现摘要（开机自检 + 退役检测，2026-06-09）
- [project-v026-state.md](project-v026-state.md) — setup_agent v0.26.x 系列摘要（rule 约束 hook 化 + skill model 轻量化，2026-06-10）
- [project-v030-state.md](project-v030-state.md) — v0.29.2 summary trim + v0.30.0 产品层全面瘦身：skill/CLAUDE.md/rules 总减 250+ 行，建立 redline-placement 原则 + external-references 模式
- [project-v031-state.md](project-v031-state.md) — v0.31.0 effortLevel 治理反转：空转根因分析 + 机检 hook 替代散文 rule + 全局 SessionEnd 自动还原
- [project-v032-state.md](project-v032-state.md) — v0.32.0 反漂移红线补强：4条文本红线进 templates/CLAUDE.md，16-agent debate 定案，focus 结构盲点指针进 design-rationale
- [tool-result-corruption-triggers.md](tool-result-corruption-triggers.md) — 工具传结果线腐蚀的两类触发器：shell for+pipe 批处理大输出 + AskUserQuestion 大段中文参数；区别于 hook 编码腐蚀（utf8-garble）
- [utf8-garble-rootcause.md](utf8-garble-rootcause.md) — 中文 hook 输出在 GBK Windows 上糊成 U+FFFD 注入 context、曾高频致 agent 跑偏；根因/已修手段/残留/为何不过度加固的完整地图
- [project-rename-bridgeforge.md](project-rename-bridgeforge.md) — v0.29.0 起项目/skill 由 setup_agent 更名为 bridgeforge；历史流水账故意保留旧名

<!-- AUTO-HOT-END -->
