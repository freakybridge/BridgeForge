---
name: find-doc
model: sonnet
description: |
  **agent 主动调用**的文档定位 skill（用户极少手动 /find-doc 或 $find-doc）。当用户提问命中以下意图时，agent **应当无需用户提示主动调用**：

  **必触触发词**：
  - "帮我找一下 X 相关 / 关于 X 的文档"
  - "X 还有哪些问题没解决 / 哪些 bug 没修 / 还有什么 todo"
  - "X 进展如何 / 现状 / 当前状态"
  - "X 的设计 / 计划 / 验收方案在哪"
  - "X 涉及哪些文档 / 文件"
  - "查一下 X" / "搜一下 X"

  **跳过场景**：
  - 用户已给精确路径（直接 Read）
  - 问的是代码而非文档（用 Grep + `path: <source-dir>/`）
  - 单次对话已查过同一 topic

  实测 token 消耗约为 naive grep + read 的 30-50%（**省 50-70%**），主因避免 agent 进入"读完整文件理解上下文"循环。
user_invocable: true
argument: 主题关键词（中英混合，例 "auth oauth" / "数据库 schema"）
---

# 文档综合检索 skill

## 执行流程

### Step 0：意图分类 + 关键词分词

**意图分流**（决定走哪些 path）：

| 意图 | 触发词 | 走的 Path |
|------|--------|----------|
| **找东西**（默认）| "找/在哪/涉及/查/搜/设计/计划" | A + B + D + E（全集） |
| **看 TODO** | "还有什么没解决/没修/todo/bug/进展/现状" | C + D |
| **看远期功能** | "X 远期/以后做/backlog/未来计划" | C 仅 TODO-INDEX §远期 Backlog 索引 + Path A（`1_plan/<模块>/` 不带日期文件）|

> 边界模糊（如"X 进展"含混）→ 默认走"找东西"全集（容错）

**关键词分词**：
- 中文按 `/`、空格分词
- 英文 `_` **不拆**（`bucket_key` 保持原样）
- 多 token 用 `|` OR 连接，再额外加 1 路共现交集

### Step 1：并行 Grep（**同一 message 内多 tool call**）

**Path A — 文件名匹配**：Glob `pattern: "doc/**/*<token>*.md"`（每个 token 一次）。信号高（直接命中主题）。

**Path B — README 入口**：Grep `pattern: <topic-regex>` `glob: "doc/**/README.md"` `output_mode: content` `head_limit: 30` `-i: true`。命中 README 再读目标文件。

**Path C — TODO + Pending（"看 TODO"或"看远期功能"意图）**：
- Grep `pattern: <topic-regex>` `path: doc/0_architecture/TODO-INDEX.md` `output_mode: content` `-i: true`（**含主表 + §远期 Backlog 索引段**，单次 grep 扫全文）
- Grep `pattern: <topic-regex>` `glob: "doc/2_pending/*.md"` `output_mode: files_with_matches` `head_limit: 20` `-i: true`
- "看远期功能"时额外：Glob `pattern: "doc/1_plan/**/<topic>*.md"` 找不带日期前缀的 backlog 文件
- 信号极高（直接答 "X 还有什么没解决" / "X 远期计划"）

**Path D — Memory 索引**：先判当前 agent 目录（Claude `.claude`，Codex `.codex`），Grep `pattern: <topic-regex>` `path: <agent-dir>/memory/MEMORY.md` `output_mode: content` `head_limit: 25` `-i: true`。仅扫 MEMORY.md 不扫具体 memory 文件（省 token）。

**Path E — 共现交集（仅多 token 时）**：Grep `pattern: <token1>.*<token2>|<token2>.*<token1>` `path: doc/` `glob: "*.md"` `output_mode: files_with_matches` `multiline: true` `head_limit: 15`。信号极高（10× 降噪）。

### Step 2：Rules 字典查表（不 grep，读项目本地映射文件）

读项目本地映射文件（Claude `.claude/find-doc.map.md`，Codex `.codex/find-doc.map.md`；topic → 关联 rule 的静态字典），把命中的 topic 映射到 rule 文件，避免全量 grep rules 的 60% 噪音。

- **文件存在** → 按 `topic_to_rules` 字典查表：命中 topic 取对应 rule 列表；无 topic 命中取 `default`。
- **文件不存在**（新项目还没建）→ 跳过本步（不 grep rules），并在 Step 4 提醒用户创建。

> **为什么外置**：字典内容是**项目专属**的（引用本项目实际 rule 文件名）。**单一源拆分**：skill 本体「怎么查」归 bridgeforge 单一源（本文件）；字典「查什么」归当前 agent 的 `find-doc.map.md`。

### Step 3：聚合输出（结构化 markdown）

把各 Path 命中聚合成结构化 md（格式见 `references/output-format.md`，命中时先 Read）。空段不显示。

## 重要规则

1. **不读完整文件**：只 Grep 出匹配行
2. **优先 README**：命中 README 后再决定是否读目标文件
3. **限定范围**：只搜 `doc/` + 当前 agent 的 `{rules,memory}/`，**不扫源代码**
4. **意图分流**：默认"找东西"，看 TODO 意图时仅跑 Path C+D（省 token）
5. **去重逻辑**（聚合时）：Path A 文件名命中作 baseline，Path E 内容交集作优先列表，Path B/D 是次序信号
6. **空段不显示**

## 不适用场景

- **代码搜索**：源代码 → Grep `path: <source-dir>/`
- **新建文档**：用 `/todo` / `$todo` 或 `/collab` / `$collab`
- **跨会话状态**：用 `/resume` / `$resume`
- **总结当前对话**：用 `/summary` / `$summary`

### Step 4：映射文件检测与提醒（任务收尾，低频）

收尾若无当前 agent 的 `find-doc.map.md` 且本次有明确 topic → 按 `references/map-reminder-sop.md` 提醒（含凭空提醒 / 强制填 / 重复提醒三条禁止项）。否则跳过。

---

输入：$ARGUMENTS
