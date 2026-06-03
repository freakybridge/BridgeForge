# Memory 热度评分系统设计

> 来源：2026-06-03 debate（两轮双Agent辩论），详见下游项目 `doc/2_pending/debates_2026-06-03_*.md`
> 状态：设计已定稿，待实现

---

## 问题背景

`.claude/memory/` 随项目推进不断积累文件（数十到数百个）。但 Claude Code 只自动加载 `MEMORY.md` 前 200 行（约 40-50 条）。随时间推移索引必然溢出，导致重要知识被截断。

**根本解法**：把 MEMORY.md 从"全量摘要"变成"热点索引"，超出的靠按需搜索召回。

---

## 架构

```
.claude/memory/
├── MEMORY.md          # 热区索引（≤200行，Claude Code 自动加载）
├── MEMORY_COLD.md     # 冷区索引（不自动加载，/find-memory 的目录）
├── _stats.json        # 访问记录 + Pinned 配置（纳入 git）
├── archive/           # 归档（prune 后移入）
└── *.md               # 具体 memory 文件
```

---

## 评分公式（艾宾浩斯衰减）

```python
import math

def memory_score(session_count: int, days_since_last_session: int) -> float:
    """
    score ∈ [0, 1]，越高越热。
    
    S = 稳定性（天）：session 越多，衰减越慢
    score = e^(-t/S)：标准艾宾浩斯保留率
    """
    S = min(7 + session_count * 10, 90)   # 线性增长，上限90天（3个月）
    return math.exp(-days_since_last_session / S)
```

**参数解读**：

| session_count | 稳定性 S | 最后访问后多久 score < 0.1 |
|---|---|---|
| 1次 | 17天 | ~39天 |
| 3次 | 37天 | ~85天 |
| 5次 | 57天 | ~131天 |
| 9次（上限）| 90天 | ~207天 |

> **为什么不用访问次数（count）做乘数**：高历史次数会托底老文件的绝对分数，让已完结项目的 memory 永久占位。S 只做衰减参数（不做分数乘数），返回纯保留率 [0,1]，避免此问题。

---

## MEMORY.md 热区选取规则

```
Pinned（≤5条）：_stats.json config.pinned 声明，永不参与排名，置顶
Top-40：按 score 降序取前40，超出的进 MEMORY_COLD.md
```

**热区满时**：纯排名竞争，得分低的自动挤出（挤出 ≠ Cold，只是本轮未入选，下次被访问后重回竞争）。

---

## session_count 计数规则

- **粒度**：唯一访问日期（而非读取次数）
- **写入时机**：Stop hook（每轮 Claude 回复结束时）
- **同日去重**：同一天无论读多少次，只计 1 个 session
- **保留窗口**：最近 30 个日期（覆盖约 3 个月）

**防突发污染**：某天扫遍所有文件，每个文件只 +1 session，不会因为一次批量访问炸高所有文件热度。

---

## 五个组件

| 组件 | 位置 | 触发时机 | 职责 |
|---|---|---|---|
| `memory_access_tracker.py` | `templates/hooks/` | PostToolUse / Read | 检测读取的是否为 memory 文件，更新 `_stats.json` session_dates |
| `memory_rebuild_index.py` | `templates/scripts/` | Stop hook（由 session_snapshot.py 调用）| 计算所有文件 score，重写 MEMORY.md + MEMORY_COLD.md |
| `memory_search.py` | `templates/scripts/` | 按需（/find-memory skill 调用）| 关键词 grep 搜索所有 memory 文件，返回排名列表 |
| `find-memory` skill | `skills/find-memory/` | Claude 主动调用 | 包装 memory_search.py，Claude 读具体文件后自动升热度 |
| `_stats.json` | `templates/memory/` | — | 持久化访问记录 + pinned 配置，纳入 git |

---

## 设计决策记录

**为什么 score 不含 S 乘数**：debate Round 2 发现，`S × e^(-t/S)` 中 S 作为乘数会让高历史访问的文件得分虚高（60天前查过8次的文件得分远超最近查过的文件），违反艾宾浩斯"遗忘只跟时间有关"的核心前提。

**为什么上限 90 天而非 180 天**：高频开发项目（推进快、内容更新频繁），memory 应该更快老化。90天（3个月）是平衡"不过快清掉有用知识"和"不让完结项目内容永久占位"的合理上限。慢节奏项目可调整 `_stats.json` 中的上限参数。

**为什么 top-K 而非绝对阈值**：绝对阈值（如 score > 0.1）在活跃期可能产生 80+ 条 Warm 文件（MEMORY.md 溢出），在冷静期可能只有 5 条。top-40 硬截断保证 MEMORY.md 始终在容量限制内。

**为什么永久约束不放 memory**：架构红线、发单链路等永久约束放在 `.claude/rules/`（path-trigger 加载），与 memory 系统完全独立，不参与热度竞争。memory 只存时效性知识（feedback/project/reference）。

---

## 实现 Checklist（给 setup_agent session）

- [ ] `templates/hooks/memory_access_tracker.py` — PostToolUse/Read hook
- [ ] `templates/scripts/memory_rebuild_index.py` — Stop 时重建 MEMORY.md
- [ ] `templates/scripts/memory_search.py` — 关键词搜索
- [ ] `templates/memory/_stats.json` — 初始模板
- [ ] `skills/find-memory/SKILL.md` — /find-memory skill
- [ ] `templates/settings.json` — 注册 memory_access_tracker PostToolUse hook
- [ ] `templates/hooks/session_snapshot.py` — Stop 时追加调用 memory_rebuild_index.py
- [ ] `skills/prune-memory/SKILL.md` — 更新：集成 _stats.json 冷却判断
- [ ] 测试：验证 score 公式在各场景下的行为