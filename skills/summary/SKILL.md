---
name: summary
description: 总结本次对话中的重要决策和经验，写入 memory/rules/docs。
user-invocable: true
argument: 可选的本次总结重点提示
model: sonnet
---

# 对话总结

把本次对话值得跨对话保留的内容同步进 memory / rules / docs。

> **步骤 3b·5 是低频条件触发**——多数收尾用不到。命中时**先 Read `references/deep-steps.md` 对应节**，按其 SOP 执行。详细流程刻意移出本文件，让每次 `/summary` 注入 context 的文本更短（避免顶爆触发 compact）。

## 步骤

### 1. 回顾本次对话
架构决策（为什么）/ 踩过的坑（根因）/ 已完成功能 / 遗留问题。

### 2. 更新 memory
跨对话有价值的内容 → 对应类型：架构=`project`、踩坑=`feedback`、外部资源=`reference`。
写入 `.claude/memory/`（junction 透明指向系统路径），**同步更新 `MEMORY.md` 索引**。先查重，再决定新建 or 更新。

### 3. 检查 rules（先过反膨胀闸，默认倾向"不加"）
- **分流**：只有"必须 X / 禁止 Y"硬约束进 rule；踩坑案例 → memory（rule 最多留一行结论 + 链接）；>20 行示例/教程 → doc。
- **去重**：与已有条目重叠 → 合并进原条目，不新开一段；同一约束只一处正文，余处放 pointer。
- **查体量**：被改 rule 超 ~500 行 / 50KB → 提示拆 path-specific 子文件；frontmatter `paths` 触发器越窄越好。
写入位置参见 `CLAUDE.md` 规则索引。**若本步真新增/改写了 rule → 触发步骤 3b。**

### 3b.（仅当步骤 3 改了 rule）连带 memory 对账
rule 与 memory **互补不替代**，"内容上升成 rule"≠"删对应 memory"，不可机械删。
**先 Read `references/deep-steps.md` §对账**，按其三类判定 + "删 memory = 4 处同步"清单执行（禁止自动删，列候选待用户确认）。

### 4. 检查相关文档是否需要同步
对照 `rules/workflow.md` §1 文档同步表；涉及架构红线 / 接口契约 / 新增数据对象 → 执行 `/sync-docs` 或直接更新对应文档。

### 5.（条件触发）清理已解决的 TODO / 归档 current 文档
仅当某条目**同时**满足：① 代码本次对话已合并 ② 用户**显式确认**解决（实操验证 / 看过 diff / 说"OK"）。
命中 → **先 Read `references/deep-steps.md` §清理**，按其流程列候选待确认（禁止自动批量删；归档用 `git mv` 不 `rm`）。无满足项（常见）→ 跳过并说明，不凑数。

### 6.（命中才做）反哺候选捕捉
本次 memory/rules 里有没有**换个项目也成立**的通用经验（协作流 / 调试法 / 可移植性坑 / agent 行为约定，非业务专属）？
有 → 向用户确认后，追加一行到 `.claude/harvest-inbox.md`：
`- [ ] <学到啥> | 来源 <file:line 或 本轮对话> | 通用性 <为啥跨项目成立> | <日期>`
只**捕捉不推送**（推送由 `/harvest` 另行做：读收件箱 → 脱敏 → 写上游 templates）。

### 7. 输出摘要
向用户列出：写了哪些 memory（类型 + 一句话）/ 改了哪些 rules / 连带清理了哪些 memory（文件 + 索引行 + 计数）/ 同步了哪些文档 / 清理归档了哪些 TODO·current doc / 记了哪些反哺候选 / 遗留问题。

## 规则
- 只写跨对话有价值的内容，当前对话的临时状态不写
- 先查重，不重复已有 memory（先检查再决定新建 or 更新）
- rules / docs 的检查以"是否影响其他模块开发者做决策"为判断标准

$ARGUMENTS
