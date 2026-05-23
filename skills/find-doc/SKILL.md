---
name: find-doc
description: |
  **agent 主动调用**的文档定位 skill（用户极少手动 /find-doc）。当用户提问命中以下意图时，agent **应当无需用户提示主动调用**：

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
user-invocable: true
argument: 主题关键词（中英混合，例 "auth oauth" / "数据库 schema"）
---

# 文档综合检索 skill

---

## 执行流程

### Step 0：意图分类 + 关键词分词

**意图分流**（决定走哪些 path）：

| 意图 | 触发词 | 走的 Path |
|------|--------|----------|
| **找东西**（默认）| "找/在哪/涉及/查/搜/设计/计划" | A + B + D + E（含交集，全集） |
| **看 TODO**（聚焦未决） | "还有什么没解决/没修/todo/bug/进展/现状" | C only（TODO + 远期 backlog + pending） + D（memory）|
| **看远期功能**（聚焦未排期）| "X 远期/以后做/backlog/未来计划" | C 仅 TODO-INDEX §远期 Backlog 索引 + Path A（`1_plan/<模块>/` 不带日期文件）|

> 边界模糊时（如"X 进展" 含混 ）→ 默认走"找东西"全集（容错）

**关键词分词**：
- 中文按 `/`、空格分词
- 英文 `_` **不拆**（`bucket_key` 保持原样）
- 多 token 用 `|` OR 连接，再额外加 1 路共现交集

### Step 1：并行 Grep（**同一 message 内多 tool call**）

**Path A — 文件名匹配**：Glob `pattern: "doc/**/*<token>*.md"`（每个 token 一次）
- 输出：精准文件名命中
- 信号：高（直接命中主题）

**Path B — README 入口**：Grep `pattern: <topic-regex>` `glob: "doc/**/README.md"` `output_mode: content` `head_limit: 30` `-i: true`
- 输出：README 索引段提到的位置
- 信号：高（README 是入口，命中 README 再读目标文件）

**Path C — TODO + Pending（"看 TODO"或"看远期功能"意图）**：
- Grep `pattern: <topic-regex>` `path: doc/0_architecture/TODO-INDEX.md` `output_mode: content` `-i: true`（**含主表 + §远期 Backlog 索引段**，单次 grep 扫全文）
- Grep `pattern: <topic-regex>` `glob: "doc/2_pending/*.md"` `output_mode: files_with_matches` `head_limit: 20` `-i: true`
- "看远期功能"时额外：Glob `pattern: "doc/1_plan/**/<topic>*.md"` 找不带日期前缀的 backlog 文件
- 输出：短期 TODO + 远期 backlog 入口 + 未决 debates
- 信号：极高（直接答 "X 还有什么没解决" / "X 远期计划是什么"）

**Path D — Memory 索引**：Grep `pattern: <topic-regex>` `path: .claude/memory/MEMORY.md` `output_mode: content` `head_limit: 25` `-i: true`
- 输出：memory 索引中的相关条目（仅扫 MEMORY.md，不扫具体 memory 文件，省 token）
- 信号：高（踩坑经验 + 项目状态）

**Path E — 共现交集（仅多 token 时）**：Grep `pattern: <token1>.*<token2>|<token2>.*<token1>` `path: doc/` `glob: "*.md"` `output_mode: files_with_matches` `multiline: true` `head_limit: 15`
- 输出：同时含两关键词的文件
- 信号：极高（10× 降噪，相比 Path A 单关键词扩散）

### Step 2：Rules 字典查表（不 grep）

**项目接入时**，在下方维护本项目的 `topic → rule` 静态映射字典（避免 grep rules 全量产生的噪音）。模板格式：

```yaml
# <!-- TODO: 按本项目实际 rule 文件填写。例: -->
topic_to_rules:
  <topic_keyword_a> / <topic_keyword_b>:
    - .claude/rules/<rule_file_1>.md
    - .claude/rules/<rule_file_2>.md
  <another_topic>:
    - .claude/rules/<rule_file_3>.md
  default (无 topic 命中):
    - .claude/rules/architecture.md
    - .claude/rules/workflow.md
```

每个项目自行维护本字典，目的是"agent 不用 grep 也能定位关联 rule"。字典稳定，rule 改动时同步维护即可。

### Step 3：聚合输出（结构化 markdown）

```markdown
# 关于 "<topic>" 的检索结果

## 📍 直达位置（文件名 + 共现交集）
- `<paths from Path A + E, 去重后>`

## 📚 README 入口（agent 推荐先读）
- `<paths from Path B>`

## 🟢 活跃 / 进行中（如 "找东西" 意图）
- 从 Path A 命中里挑 `1_plan/<topic>/` 下的活跃文件

## 🔴 待解决问题（仅 "看 TODO" 意图，或主动列出）
- TODO #N（P0/P1/P2）— <description>（来自 Path C）
- 未决 debates: <files from Path C>

## ⚠️ 关联 rules（字典查表，无 grep）
- `<rules from Step 2 字典>`

## 🧠 相关 memory
- `<entries from Path D>`

## 🗂 已归档（仅作历史参考）
- 从 Path A 命中里挑 `4_archive/` 下的文件

---

**建议下一步**：
- 改代码 → 先读 [README + 关联 rules]
- 看进展 → 读 [活跃] 段
- 修问题 → 读 [待解决问题] 段
```

---

## 重要规则

1. **不读完整文件**：只 Grep 出匹配行，避免 Read 完整文件
2. **优先 README**：命中 README 后再决定是否读目标文件
3. **限定范围**：只搜 `doc/` + `.claude/{rules,memory}/`，**不扫源代码**（源代码用 Grep 单独查）
4. **意图分流**：默认"找东西"，看 TODO 意图时仅跑 Path C+D（省 token）
5. **去重逻辑**（聚合时）：Path A 文件名命中作为 baseline，Path E 内容交集作为优先列表，Path B/D 是次序信号
6. **空段不显示**：避免输出冗余空段

---

## 不适用场景

- **代码搜索**：源代码 → Grep `path: <source-dir>/`
- **新建文档**：用 `/todo` 或 `/collab` skill
- **跨会话状态**：用 `/resume` 读 snapshot
- **总结当前对话**：用 `/summary`

---

## Step 4：placeholder 检测与提醒（任务收尾）

聚合输出已呈现给用户后，**额外**做一件事：

1. 检查 Step 2 的 `topic_to_rules` 字典是否仍含 `<!-- TODO:` 占位
2. 如仍是占位 **且** 本次任务实际接触到了 **≥ 1 个明确的 topic / 关联到具体 rule 文件** → 在回复末尾追加提醒：

   ```
   💡 字典提醒：本次涉及 <topic_a> / <topic_b>，find-doc Step 2 字典还是 placeholder。
   要不要顺手加这几行？候选：
     <topic_a>:
       - .claude/rules/<guessed_rule_a>.md
     <topic_b>:
       - .claude/rules/<guessed_rule_b>.md
   ```

3. **禁止**：
   - 凭空提醒（本次没接触到具体 topic 时不提醒，符合"宁缺毋滥"）
   - 强制要求用户填（用户说"不用"就立刻闭嘴）
   - 同一会话内对同一 topic 重复提醒

**Why this exists**：字典是项目演进中自然沉淀的（StratusAgent 演了很久才填出 11+ topic）。早期项目字典空着 agent 走 grep fallback 也能跑，但永远空着 agent 跑得慢。本段保证用户在 doc/ 结构稳定后顺手填表，不依赖用户自觉。

---

输入：$ARGUMENTS
