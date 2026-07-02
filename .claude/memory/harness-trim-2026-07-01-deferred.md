---
name: harness-trim-2026-07-01-deferred
description: 2026-07-01 全 harness 精简会：28 叙述瘦身+2 整删已落地；6 争议点中 E-3/E-6 已随 v0.39.0 九维方案解决，E-1/E-2/E-4/E-5+2 行为变更+git-sync 过时 Why 仍搁置待议
metadata: 
  node_type: memory
  type: project
  originSessionId: 916e4c2c-bb29-40d5-8ee0-b649d9d5c115
---

2026-07-01 一次「全 harness 精简」会（宁缺毋滥、中间档尺子）。已落地：**28 条叙述瘦身**（meta_rule/anti_fab/modules/portability/templates·CLAUDE §9/4 个 hook docstring/7 个 skill）+ **2 条整删**（escalate `/coordinator`→`/collab`；meta_rule_design §10 空案例库）+ **1 处修错**（`.claude/settings.json` Stop 注释误写"重建 MEMORY.md"，代码实锤重建早移出 Stop 链路→改由 PostToolUse+SessionStart，已修）。

**以下全部按用户指示「跳过、待议」，不是否决**：

6 争议点：
- **E-1** 机械改动是否免走项目 CLAUDE §1「传播四问」（防空转诉求）——复核否决豁免（任务深浅 vs 改动分层正交，绕四问会在漏镜像事故上开口），仅修了"三句话→四问"笔误。**仍搁置**，是否仍探索豁免待议。
- **E-2** workflow §4 收尾自查 → 复核判 KEEP（非 Python 项目退化兜底锚点）。
- **E-3**（✅ **已解决**，2026-07-02 harness 九维方案 P0-4）鬼打墙阈值 CLAUDE §8「第4次硬停」vs debugging §6「≥2次升级」冲突——统一到 ≥3（T2 独立轴不动），见 [[ghost-wall-threshold-conflict]]、[[project-v039-state]]。
- **E-4** architecture/modules 占位模板 6 处 → 复核 KEEP（design-rationale §6「占位骨架 AI 不代填」）。**双语言示例是否冗余仍待议**。
- **E-5** rule_size_check.py 白名单注释 → 复核 KEEP（含全库唯一"禁通配/只豁免触发器宽度"红线）。
- **E-6**（✅ **已解决**，2026-07-02 harness 九维方案 P0-1+P1-7）dogfood 缺口：`.claude/hooks` 比 `templates/hooks` 少 4 个——P0-1 已补齐 4 个镜像；P1-7 新建 `mirror_drift_check.py` pre-commit 硬闸（缺文件 exit2、豁免走 CHANGELOG `[dogfood-exempt]`），根治「以后再漏」而非只补一次性欠账。见 [[feedback-dogfood-hook-gap]]、[[project-v039-state]]。

2 条搁置的行为变更（非纯叙述，故未混进瘦身批，本轮九维实施**未触碰**，仍原样搁置）：
- debugging §11「根因预测」收紧为「列待验证假设、禁止据此改代码」。
- B-6 项目 CLAUDE §1 Q4「也要挂上」→「适用才镜像」——动 dogfood 政策。**注**：本轮 E-6 落地时**未采纳** B-6 这条替代方案，走的仍是原「也要挂上 + 不适用需 CHANGELOG 注明豁免」路线（与 mirror_drift_check 的 `[dogfood-exempt]` 机制天然吻合），B-6 本身仍是未拍板的搁置提案。

新发现未处理：**skills/git-sync SKILL.md L20 的 Why** 栽在同一过时说法（"这俩文件由 Stop hook 每轮重建"，实际早移到 PostToolUse），动作没错、解释过时，待修。

**下一步**：用户提出「先访谈式一问一答摸清 harness 偏好，再结合外部资料打造 harness 工程」，专注优化 bridgeforge 自身 harness（此前从未系统讨论过的新方向）。
