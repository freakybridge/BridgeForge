# Memory 索引设计（确定性事件驱动）

> 状态：现行设计（2026-06-27 改版落地）
> 前身：艾宾浩斯热度评分系统（2026-06-03 设计、已实现），**本次废弃**，原因见下。
> 改版辩论：[debates_2026-06-27_memory-untrack.md](debates_2026-06-27_memory-untrack.md)

---

## 为什么废弃热度评分（核心）

旧系统按「最近访问热度 + 艾宾浩斯时间衰减」自动重排 MEMORY.md 的 Top-40 热区。致命缺陷：

**热度分 = `exp(-days_since_last / S)` 含 `today` 变量 → 索引是时间的函数 → 每天自发变化。**
这与用户硬需求「`/git-sync` 后工作区必须干净、不自发变脏、多机不莫名冲突」**在数学上不兼容**：只要分数随日期漂，被 git 跟踪的 MEMORY.md/MEMORY_COLD.md 就会在没人改 memory 的情况下天天 dirty（外加 COLD 顶部 `rebuilt {date}` 日期戳跨天必变）。

辅证：实测 `_stats.json` 长期仅 1 条访问记录、17 个 memory 全进 Top-40 → 热度是「伪热度」，截断毫无作用，属当前规模（数十条）下的过早优化。

> 决定性技术事实：git 只比对**内容**、不看 mtime。所以脏的唯一来源是「内容自发变化」，而非「hook 每轮重写」。消除自发变化即根治。

---

## 新设计：确定性 + 事件驱动

**索引 = f(memory 文件集, created_at, pinned)，不含 `today`、不含访问热度。**
→ 不碰 memory 时，重建产出逐字不变 → 工作区永不自发变脏；多机用同规则同输入算出一致结果 → 不冲突。

```
.claude/memory/
├── MEMORY.md          # 主索引（派生，自动加载前 200 行）—— 勿手改
├── MEMORY_COLD.md     # 冷区索引（派生，不自动加载，/find-memory 的目录）
├── _stats.json        # 事实源：config(title/pinned) + 各文件 created_at（登记一次，固定）
└── *.md               # 各条 memory（事实源）
```

### 排序与容量
- **Pinned**（≤5，`config.pinned` 声明）置顶，永不滚出。
- 其余按 **created_at 倒序**（新增的在前），并列按文件名升序。
- 主索引（Active）保留 **ACTIVE_N=40** 条；超出的**自动滚入冷区**（MEMORY_COLD.md）。
- → 冷热维护全自动、不需人工决定；只在真增删 memory 时变（那本就该提交）。

### created_at
- 文件首次被 rebuild 看到时登记 `today`，此后**固定不变**（确定性的锚）。
- rebuild 同时清理 `_stats.json` 里已不存在的文件记录（单一事实源）。
- `_stats.json` 仅在「真增删 memory」时被追加/删除 → 与 MEMORY.md 同步变，不自发脏。

### 触发时机
- **PostToolUse(Write|Edit)** 调 `memory_rebuild_index.py --from-hook`：读 stdin，**仅当写入对象是 `.claude/memory/*.md`（非 MEMORY*.md、非 `_*`）时才重建**（防自触发循环 + 避免无谓执行）。
  → memory 写入的当下即同步索引；sync 时已最新；Stop 不再碰索引 → 不会「sync 后又被弄脏」。
- **SessionStart** 调 `memory_rebuild_index.py`（无参，无条件）：clone 新机 / pull 后首个 session 兜底对齐。

---

## 组件清单（现行）

| 组件 | 位置 | 触发 | 职责 |
|---|---|---|---|
| `memory_rebuild_index.py` | `scripts/` | PostToolUse(--from-hook) + SessionStart | 确定性生成 MEMORY.md + MEMORY_COLD.md |
| `memory_search.py` | `scripts/` | `/find-memory` 调用 | 关键词频率搜索全量 memory（召回冷区） |
| `find-memory` skill | `skills/find-memory/` | Claude 主动调用 | 包装 memory_search.py |
| `_stats.json` | `memory/` | rebuild 维护 | created_at + pinned/title（事实源，纳入 git） |

**已删除**（随热度系统废弃）：`memory_access_tracker.py`（PostToolUse/Read 访问追踪）、`memory_bootstrap_cold.py`（衰减冷启动工具）、`_stats.json` 的 `session_dates`、MEMORY_COLD.md 日期戳、艾宾浩斯评分。

---

## 关键不变量
- **确定性**：相同（memory 文件集 + created_at + pinned）→ 逐字相同的 MEMORY.md/COLD。可连跑 N 次验证 diff 为空。
- **git 边界**：MEMORY.md/COLD 留在 git（确定性 → 多机一致、可 diff 兜底），但内容只在真增删 memory 时变。
- **可删除性**：`rm MEMORY.md` 无后果，下个 PostToolUse/SessionStart 自动重生。
- **description 依赖**：索引每条描述取自该 memory 的 `description:` 字段；写 memory 时该字段必须是**纯文本**（勿用 YAML 引号/转义，否则提取出半截）。

---

## 多机协作走查
A 新增 memory `foo.md`（带 description）+ 可选置顶（`config.pinned` 加 `foo.md`）→ A 本地 PostToolUse 重建 MEMORY.md → `git-sync` 提交 `foo.md` + `_stats.json` + MEMORY.md/COLD（全部内容确定）→ B `pull` 拿到事实源 → B 的 SessionStart 重建，因规则与输入一致 → 算出与 A **逐字相同**的索引，不冲突。
