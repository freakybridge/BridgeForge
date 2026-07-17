---
name: find-doc
model: sonnet
description: 定位主题相关文档、TODO、当前进展、设计计划、验收方案及关联 memory/rules；用户询问“相关文档在哪、还有什么未解决、现状如何、查一下某主题”时主动使用。精确路径、纯代码搜索或本轮已查过同一主题时跳过。
user_invocable: true
argument: 主题关键词（中英混合，例 "auth oauth" / "数据库 schema"）
---

# 文档综合检索

## 定位与边界

只检索 `doc/`、当前 agent 的 memory 索引和项目专属 rule 映射，不扫描源代码，不先读取完整文档。目标是用少量高信号命中回答“在哪、现状、TODO、设计和计划”。

## 输入

从 `$ARGUMENTS` 或用户问题提取主题：中文按 `/` 和空格分词；英文 `_` 不拆。多关键词用 OR 检索，并增加一路共现交集。

## 核心流程

### 1. 分流意图

| 意图 | 典型问题 | 执行路径 |
|------|----------|----------|
| 找东西（默认） | 找、在哪、涉及、查、搜、设计、计划 | A + B + D + E |
| 看 TODO | 未解决、没修、bug、todo、进展、现状 | C + D |
| 看远期功能 | 远期、以后、backlog、未来计划 | C 的远期索引 + A 的无日期计划 |

边界含混时按“找东西”执行。

### 2. 并行检索

在同一批工具调用中运行所需路径：

- **Path A—文件名**：每个 token 执行 Glob `doc/**/*<token>*.md`。
- **Path B—README 入口**：在 `doc/**/README.md` 中大小写不敏感 Grep topic regex，返回内容，最多 30 条；命中后再判断是否读取目标文件。
- **Path C—TODO + Pending**：
  - Grep `doc/0_architecture/TODO-INDEX.md` 全文；
  - Grep `doc/2_pending/*.md`，只返回命中文件，最多 20 个；
  - 远期意图再 Glob `doc/1_plan/**/<topic>*.md`，定位无日期 backlog 文件。
- **Path D—Memory 索引**：判断 Claude `.claude` 或 Codex `.codex`，只 Grep其 `memory/MEMORY.md`，最多 25 条；不扫描具体 memory 文件。
- **Path E—多词共现**：仅多 token 时，在 `doc/**/*.md` 中按正反顺序做 multiline 共现 Grep，只返回文件，最多 15 个。

### 3. 查项目 rule 映射

读取当前 agent 的 `.claude/find-doc.map.md` 或 `.codex/find-doc.map.md`，按 `topic_to_rules` 查表：命中主题取对应 rules，未命中取 `default`。映射不存在时跳过，不全量 grep rules。

### 4. 聚合与收尾

1. 聚合去重：A 作基线，E 作高优先级，B/D 调整次序，空段不显示。
2. 命中后读取 [references/output-format.md](references/output-format.md)，按其格式输出。
3. 收尾读取 [references/map-reminder-sop.md](references/map-reminder-sop.md)，只在满足条件时提醒维护映射。

## 输出与验证

标明每项命中来自文件名、README、TODO、memory 还是规则映射；区分进行中、待解决与已归档文档。需要正文结论时，只读用户选定或最高信号的目标文件。

## 停止条件

- 用户已给精确路径：直接读取该路径，不执行本 skill。
- 用户问的是源代码：转为限定源码目录的代码搜索。
- 本轮已检索同一主题：复用结果，除非用户明确要求刷新。
- 所有路径无命中：说明检索范围和关键词，不编造文档。

## 禁止事项

- 禁止先读完整文件理解上下文；先检索，再按需读。
- 禁止扫描源代码、全量 memory 文件或全量 rules。
- 禁止在无明确 topic 时提醒创建映射，或在同一会话重复提醒同一 topic。
- 禁止用 `todo`、`resume`、`summary` 的能力替代本 skill；新建文档、跨会话接续和对话总结应转交对应 skill。

输入：`$ARGUMENTS`
