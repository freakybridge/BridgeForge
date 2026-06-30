# Memory Index — bridgeforge

<!-- 自动生成索引，勿手改（改动会被下次重建覆盖）。新增 memory：在 .claude/memory/ 下新建 .md 文件，本索引会自动收录；写法见 ~/.claude/CLAUDE.md「auto memory」段。满 40 条自动滚入冷区，用 /find-memory 搜。 -->

> Active: 21 | Cold: 0

## 📌 Pinned
- [project-rename-bridgeforge](project-rename-bridgeforge.md) — v0.29.0 起项目/skill 由 setup_agent 更名为 bridgeforge；历史流水账故意保留旧名

## Active（按新增时间，新在前；满 40 自动滚入 Cold）
- [feedback-llm-suspended-during-tool-exec](feedback-llm-suspended-during-tool-exec.md) — LLM 在 Claude Code 工具执行期间被 SUSPENDED——PostToolUse 才是最早干预窗口，而非「边等边想」
- [project-v037-state](project-v037-state.md) — v0.37.0（templates v0.8.0）防 AI 幻觉资源四层框架落地 + CLAUDE.md 瘦身 275→193 行（2026-06-30）
- [effort-config-layering](effort-config-layering.md) — Claude Code effortLevel 多层覆盖关系 + bridgeforge v0.31.0「项目层禁写 effortLevel、全局统一管 + SessionEnd 自动还原 medium」反转决策
- [feedback-bash-cwd-persistence](feedback-bash-cwd-persistence.md) — Bash 工具的 cwd 在会话内持久——cd 进子目录后所有后续调用都从那里执行，导致相对路径 hook 全部失效
- [feedback-dogfood-hook-gap](feedback-dogfood-hook-gap.md) — 改 templates/hooks 时漏了同步 .claude/hooks 的事故模式及已有修复
- [feedback-glob-search-gotchas](feedback-glob-search-gotchas.md) — 用户机器上用 Glob/Grep 查文件的首选方式与三个坑（范围、文件非目录、跳过点目录）
- [feedback-review-technique](feedback-review-technique.md) — setup_agent review 时的两条操作红线（并行编辑 + hook 删除安全检查）
- [feedback-skill-gate-hardness](feedback-skill-gate-hardness.md) — skill 指令里"等用户确认"闸的正确写法——描述性措辞拦不住 agent，必须用 AskUserQuestion 工具级回合终止契约
- [ghost-wall-threshold-conflict](ghost-wall-threshold-conflict.md) — 鬼打墙计数阈值在 CLAUDE.md §8(3) 与 debugging §6 T1(2) 不一致，待统一；属行为变更不混进瘦身，用户暂选不改
- [project-skill-junction-single-source](project-skill-junction-single-source.md) — C盘 skills/bridgeforge 是指向 D:\Quant\BridgeForge 的 junction，单一源在 D 盘，别被 Glob 穿透骗成「两份」
- [project-target-cleanup-design](project-target-cleanup-design.md) — target_cleanup.py 的核心设计决策（体积而非 atime、自门控、全深度扫描）
- [project-v024-state](project-v024-state.md) — setup_agent v0.24.0 主要变更摘要（2026-06-09）
- [project-v025-state](project-v025-state.md) — setup_agent v0.25.0 支柱 B 实现摘要（开机自检 + 退役检测，2026-06-09）
- [project-v026-state](project-v026-state.md) — setup_agent v0.26.x 系列摘要（rule 约束 hook 化 + skill model 轻量化，2026-06-10）
- [project-v030-state](project-v030-state.md) — v0.29.2 summary trim + v0.30.0 产品层全面瘦身：skill/CLAUDE.md/rules 总减 250+ 行，建立 redline-placement 原则 + external-references 模式
- [project-v031-state](project-v031-state.md) — v0.31.0 effortLevel 治理反转：空转根因分析 + 机检 hook 替代散文 rule + 全局 SessionEnd 自动还原
- [project-v032-state](project-v032-state.md) — v0.32.0 反漂移红线补强：4条文本红线进 templates/CLAUDE.md，16-agent debate 定案，focus 结构盲点指针进 design-rationale
- [project-v035-state](project-v035-state.md) — v0.35.0 debate/collab 六步重构 L1 审计 + 闸硬度修补（2026-06-27）
- [tool-result-corruption-triggers](tool-result-corruption-triggers.md) — 工具传结果线腐蚀的两类触发器：shell for+pipe 批处理大输出 + AskUserQuestion 大段中文参数；区别于 hook 编码腐蚀（utf8-garble）
- [utf8-garble-rootcause](utf8-garble-rootcause.md) — 中文 hook 输出在 GBK Windows 上糊成 U+FFFD 注入 context、曾高频致 agent 跑偏；根因/已修手段/残留/为何不过度加固的完整地图
