---
name: project-v040-state
description: v0.40.0（templates v0.11.0）全仓库 harness 体检 + P0 整批修复 + 07-01 欠账全部收口（2026-07-02）
metadata: 
  node_type: memory
  type: project
  originSessionId: 75ba2145-0b1a-452f-bdbb-f4c88670577c
---

2026-07-02 全仓库 harness 体检（4 个并行审计 agent：hook 可靠性 / token 重量 / agent 行为质量 / v0.39 落地+欠账核查，约 30 条 finding，高影响项人工核验后动手）。用户拍板「P0 全修 + 欠账收口」，落地为 v0.40.0：

**四组 P0 修复**：
1. **输入通道静默失效**：find_doc_reminder / memory_lint 只读 legacy env、rule_index/rule_size 的 PostToolUse 路径同病——CC 仅走 stdin 时挂着永不触发。统一补 stdin-first + env fallback（requirements_check 范式）。教训：**一个 hook 修了根因，要主动排查所有结构同胞**。
2. **出厂配置**：templates settings.json PostToolUse matcher 补 `MultiEdit`（mirror_drift_check 只查 .py，settings 漂移无闸）；context_warning WINDOW **保持 1M**（用户拍板），注释升级为显式陷阱警告。
3. **信号 hook 裸化**：clarify/focus/find_doc 每轮重发完整指令与常驻层双付/三付 → 改裸信号+指针；配套给 bridgeforge 自身 CLAUDE.md 新增 §5 信号速查表（自身此前无契约常驻，裸化后必须补）。
4. **软闸硬化铺全**：escalate/archive-scan/git-sync/plan/spinoff/summary 六个 skill 补「⛔硬契约:AskUserQuestion 结束回合」（此前只 debate/collab 有）；find-memory 幻影引用（已删的 memory_access_tracker + 升热区机制）、collab「2 次失败必停」错误阈值一并清理。

**欠账全清**：见 [[harness-trim-2026-07-01-deferred]]（已转历史档案）。另补记 v0.39.0 CHANGELOG 漏账（8 skill+2 rule 夹带瘦身）。

**未修遗留（P1/P2，报告在案待下批）**：CLAUDE.md 四反漂移段合表下沉（潜在 -40~50 行常驻）；find-doc description 449 字压缩；fallback_smell 覆盖远窄于 debugging §3（hook 名过度承诺）；version_check 漏 `git -c` 形式+缺 encoding；archive_scan.py 缺 .claude/scripts 镜像；show_state 每轮 3 git 子进程；「13 个 skill」计数过时（workflow.md:89、README:18/113）；debugging src/** 触发器与 meta_rule §4.2 反例的表述矛盾；已知三缝（幻觉读资源软-only / 方案替换无 hook / 非测试假验证无收据）。
