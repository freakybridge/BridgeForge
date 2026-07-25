# /summary / $summary 深档步骤 SOP

> 本文件是 `/summary`（Claude）/ `$summary`（Codex）主流程（`../SKILL.md`）里**低频条件触发**步骤的详细 SOP。
> 主模板只在命中时指示"先 Read 本文件对应节"——把这些不常用的长流程移出主模板，
> 是为了让每次 `/summary` / `$summary` 注入 context 的文本更短（避免顶爆触发 compact）。
> 触发了哪一步就只读哪一节，别整篇照搬进上下文。

---

## §对账 — rule 写入后连带 memory 对账（防 memory 膨胀）

> **仅当主流程步骤 3 真的新增 / 改写了 rule 才触发本节。**

rule 与 memory 是**互补不是替代**：meta_rule 范式要求 rule 把案例下沉到 memory、自己只留一行结论 + 链接。所以"内容上升成 rule"≠"删对应 memory"，必须分类判定，不可机械删。

**只对本次 rule 直接相关的 memory 对账**——不全量扫所有 memory（全局冷热区由
确定性索引重建脚本维护，summary 只做局部对账）。三类判定：

| memory 现状 | 处理 |
|---|---|
| 内容被新 rule **完整吸收**，且不再提供 rule 之外的 why / 案例细节（纯重复） | 候选**删除** |
| 是 rule 的案例 / why 支撑（rule 正链接或应链接它） | **保留**，并确保 rule 里有指向它的链接 |
| 被本次新经验**取代 / 升级**（旧版没清掉） | 候选删旧版 |

**禁止自动删**：列候选给用户、逐条 y/n 或整体显式确认后再动手。

**删一条 memory = 3 处同步**（缺一处即残留 / 悬空链接）：
1. 删分类目录或 topic 目录内的原文件。
2. 运行当前 agent 的 `memory_rebuild_index.py`，由脚本重建 `MEMORY.md`；
   禁止手改自动索引和计数。
3. **反向链接检查**：搜索其他 memory 的 `[[被删 name]]` + rules / doc 里指向它的链接 → 悬空的要处理。

> 第 3 步兼做**误删安全网**：删前若发现某条 rule 仍在链接这条 memory，恰证明它属上表第 2 类（案例支撑），**不该删**——回到判定，留下。

---

## §清理 — 清理已解决的 TODO 和 current 文档（防止无限膨胀）

扫描本轮关联的 `doc/1_delivery/` topic 与 `doc/2_bugs/` 记录，找出本次真正完成并经用户确认的条目。

**判定标准（严格，必须同时满足）**：
1. 代码已合并（本次对话中实际 edit 了文件并 build 通过）
2. 用户已**显式确认**解决（实操验证 / 看过 diff / 明确说"OK" / 测试通过）

**禁止**把"代码已写但未验证"的条目算作解决。例：今天刚改完几条 TODO 但用户没实操验证，不能算。

**执行流程（禁止自动批量删）**：

已完成或被取代的 topic memory 只把 `status` 改为 `completed` 或
`superseded`，并由索引降温；文件继续留在原 `memory/topics/<topic>/`。
禁止创建或使用 `memory/_archive/`。delivery 原始证据的归档不改变这条规则。

1. **列候选清单**给用户，分两类展示：

   ```
   候选归档（delivery / bugs → archive）:
   - [ ] doc/1_delivery/M1/foo/ — 已验收的需求包
   - [ ] doc/2_bugs/BUG-XX_foo.md — 已验证修复的 Bug
   ```

2. **等用户逐条 y/n 或整体确认**。用户说"都清"也行，但必须显式。

3. **执行清理**（按用户勾选）：
   - **delivery topic** → `git mv doc/1_delivery/... doc/4_archive/delivery/...`，保留完整确认、计划、验收与 debate trail
   - **Bug** → `git mv doc/2_bugs/XXX doc/4_archive/bugs/XXX`，禁止 `rm`
   - **doc/README.md** 索引 → 从 `## current/` 表格里删对应行，如归档则在 `## archive/` 表格加新行

**兜底**：若本次对话**没有**任何条目满足判定标准（常见情况），跳过本步，向用户说明"本次未达清理标准的条目"即可，不强行凑数。
