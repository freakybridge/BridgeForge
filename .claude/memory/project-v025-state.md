---
name: project-v025-state
description: setup_agent v0.25.0 支柱 B 实现摘要（开机自检 + 退役检测，2026-06-09）
metadata: 
  node_type: memory
  type: project
  originSessionId: 0e54f5a5-13d9-45e9-bdcf-67d584475678
---

## v0.25.0（待发版，[Unreleased] 状态）

### 核心目标：关掉 skill 分发机制的洞 2–3（漂移 + 删除不传播）

设计文档：[docs/skill-distribution-gaps.md](../../../d:/Quant/setup_agent/docs/skill-distribution-gaps.md)

### 产品层改动（[product]）

**第一块 — 开机自检（SessionStart hook）**
- `templates/hooks/skill_sync_check.py`（新增）+ dogfood `.claude/hooks/skill_sync_check.py`（字节一致）
- 两份 `settings.json` 注册 `SessionStart`
- 机制：离线比对 `~/.claude/skills/<skill>` 副本与上游 `~/.claude/skills/setup_agent/skills/` 的内容哈希
  - 上游有、架子没 → 报"缺失"；内容不一致 → 报"漂移"
  - 只通知，绝不改文件；自门控（没 setup_agent 静默 no-op）
- 哈希跳过：`__pycache__` / `.git` / `.` 开头隐藏文件（保证 mtime 不误报、为 provenance 标记预留）

**第二块 — 退役检测（轻量墓碑）**
- `RETIRED.md`（新增，repo 根）：机器可读墓碑名单，格式 `- <name> | <版本> | <日期> | <原因>`，机器取第一列
  - 首条：`prune-memory | v0.24.0 | 2026-06-09 | 手动 MEMORY.md 治理整代废弃，改由 memory_rebuild 自动评分`
- `skill_sync_check.py` 扩展：读 RETIRED.md，赖在架子上的 → 报"已退役待删"
- `SKILL.md` Step 0：新增退役清理 bash 片段，列出来问用户删，**绝不静默删**

### 工程取舍（重要）

原设想"version-stamped manifest"被**有意砍掉**：内容哈希自检已覆盖"漂移/落后"，
再叠 manifest 是冗余。真正缺的只有退役检测，RETIRED.md 最轻量。

### 退役一个 skill 的三步 SOP

1. 删 `skills/<name>/` 目录（并从用户级 `~/.claude/skills/<name>/` 手动删，如果已安装）
2. 追加一行到 `RETIRED.md`（格式：`- <name> | <版本> | <日期> | <原因>`）
3. CHANGELOG 加 `Removed` 条目（[product] 标签）

### 诚实边界（未关闭的洞）

- **洞 4（开发机特例）**：junction 指向工作区，脏文件也会参与哈希 → 可能误报"漂移"。真解法是干净 clone / CI，归 future work。
- **退役 hook（项目级）**：`.claude/hooks/` + settings 改动是项目级，仍靠手动删 + CHANGELOG 提示。
- **GitHub 新鲜度**：比的是本机 clone，不联网；SKILL.md Step 0 有手动 `git pull` 指引。

**Why:** 支柱 B 设计取舍跨会话容易忘，特别是"为什么没做 manifest"和"退役三步 SOP"。

**How to apply:** 退役 skill 时对照"退役三步 SOP"。遇到"为什么没有版本号/manifest"质疑时，看本条。

[[project-v024-state]]
