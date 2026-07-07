# Step 4 映射文件检测与提醒（任务收尾，低频）

仅当**无当前 agent 映射表（Claude `.claude/find-doc.map.md`，Codex `.codex/find-doc.map.md`）且本次有明确 topic**时触发。聚合输出已呈现给用户后，**额外**做一件事：

1. 检查项目根是否存在当前 agent 映射表
2. **不存在 且** 本次任务实际接触到了 **≥ 1 个明确的 topic / 关联到具体 rule 文件** → 在回复末尾追加提醒，附带可直接落盘的模板：

   ```
   💡 映射提醒：本项目还没有当前 agent 的 find-doc.map.md，find-doc 只能走 grep fallback。
   本次涉及 <topic_a> / <topic_b>，要不要我建这个文件？初始内容候选：

   # find-doc 项目映射表（topic → 关联 rules）
   topic_to_rules:
     <topic_a>:
      - <agent-dir>/rules/<guessed_rule_a>.md
     <topic_b>:
      - <agent-dir>/rules/<guessed_rule_b>.md
     default (无 topic 命中):
      - <agent-dir>/rules/architecture.md
   ```

3. **已存在但本次 topic 不在表里** → 提醒"要不要顺手给当前 agent 的 find-doc.map.md 加 `<topic>` 这几行"。
4. **禁止**（护栏，不可丢）：
   - 凭空提醒（本次没接触到具体 topic 时不提醒，符合"宁缺毋滥"）
   - 强制要求用户填（用户说"不用"就立刻闭嘴）
   - 同一会话内对同一 topic 重复提醒

**Why this exists**：字典是项目演进中自然沉淀的（StratusAgent 演了很久才填出 14+ topic）。外置成当前 agent 的 `find-doc.map.md` 后，skill 本体保持通用单一源，项目只维护这一个数据文件。早期项目没有该文件 agent 走 grep fallback 也能跑，本段保证用户在 doc/ 结构稳定后顺手建表。
