# 讨论：MEMORY.md 每轮变脏 — 是否移出 git 跟踪

> 日期：2026-06-27
> 相关文件：`.claude/scripts/memory_rebuild_index.py`、`.claude/hooks/memory_access_tracker.py`、`.claude/hooks/session_snapshot.py`、`.claude/memory/MEMORY.md`、`.claude/memory/MEMORY_COLD.md`、`.claude/memory/_stats.json`、`docs/memory-scoring-design.md`、`.claude/settings.json`
> 用户硬需求：**每次 `/git-sync` 动作结束后，工作区必须没有未提交文件；下次打开、多机协作也不应莫名变脏。**
> 用户取向：低系统复杂度 > 高度解耦 > 单一事实源 > 可删除性，不以开发效率为选型标准。

## 候选方向

把派生索引 `MEMORY.md` / `MEMORY_COLD.md` 移出 git 跟踪（`git rm --cached` + `.gitignore`），git 只跟踪事实源 `_stats.json` + 各 memory `*.md`，由 rebuild hook 在每台机器本地动态生成 MEMORY.md。

## 决定性实测（裁判，Round1 后）

1. `touch MEMORY_COLD.md`（只改 mtime 不改内容）后 `git status` 为空 → **git 只比对内容，不看 mtime**。
   推论：rebuild 每轮无条件 `write_text`，只要写入内容逐字相同，**git 根本不会 dirty**。"每轮强制重写=脏永动机"的前提被削弱。
2. MEMORY_COLD.md 第一行实测带 `rebuilt 2026-06-27` 日期戳 → **跨天内容必变 → 必 dirty**，每天第一次 sync 必遇。
3. `_stats.json` 实测仅 1 条记录，memory 目录 17 个 `.md` → 访问追踪极少触发，当前热区是**伪热度**。
4. `memory_access_tracker.py` L81 同日去重，`_stats.json` 非每轮变。

**真正的 git 脏源收窄为四类**：①COLD 日期戳（跨天必变）；②热区排序真翻转（当前伪热度下几乎不发生）；③真实 memory 增删（本就该提交，非噪声）；④人为 git add 漏文件（操作纪律）。

## Round 1

### 🔵 提议者（正方：移出 git）
- 派生数据进 git = 同一事实存两份，必付一致性成本；移出 = 拉回"git 只存事实源、派生本地现生"的单一事实源形状，正中用户取向。
- 移出后 `git status` 永远看不见这两个文件 → 脏概率**定性归零**，而非定量改善；硬需求要"必须没有"，定量改善给不了。
- 可删除性拉满：`rm MEMORY.md` 无后果，下个 Stop hook 自愈（rebuild 已有"不存在则新建"分支）。
- `_stats.json` 继续跟踪：同日去重 + 当前仅 1 条 → 低频**信号** diff（真实访问历史），本就该入库，不是把脏转移。
- 多机：事实（memory 内容 + pinned + 访问记录）走 git，派生两端本地各生；两机 MEMORY.md 字节可不同，因热区本就是 per-machine。
- 冷启动：SessionStart 加第 5 个 hook 跑 rebuild 兜底。
- 诚实弱点：①SessionStart 首启"鸡生蛋"窗口；②消解手写区是一次性迁移工 + rebuild 要改整文件生成；③`description:` 成硬依赖。

### 🔴 审阅者（反方：幂等 + 去日期戳，别动结构）
- **脏的转移而非消除**：移出 MEMORY.md 后 `_stats.json` 仍跟踪、仍被 hook 写（跨天/读新 memory），且 MEMORY_COLD.md 也得一起移出，否则照样 dirty。
- **真假 dirty 混淆**：本会话 MEMORY.md 反复脏，主因是"真实 memory 增删 + 人为漏 add"，不是系统抖动；用结构手术治操作纪律问题=杀鸡用牛刀。
- **信息丢失（对方没算到）**：手写 Active 区的人工编排措辞比 `description:` 更精炼，移出 git 后 B 机 clone 看不到，`_stats.json` 只存文件名 → 真·悄悄丢失。
- **产品层成本**：rebuild 从"填空机"升级"全权生成"，失败模式翻倍（崩了还无 diff 兜底），且下沉给所有下游一个未验证必要性的契约。
- **更优替代**：(a) rebuild 写前比对（内容相同不写）+ (b) 去掉 COLD 日期戳 → 稳态零写盘、零结构改动、零信息丢失、MEMORY.md 留 git；(c) 进一步砍掉伪热度系统（17 条 + 伪热度下 Top-40 截断毫无作用，属过早优化）。
- **边界问题**：多机 `_stats.json` 的 `session_dates` 是 append-only 并发写，易 merge conflict，而移出 MEMORY.md 后失去对账载体，让"多机莫名变脏"更难诊断。

## Round 2

### 🔵 提议者（正方 Round2 — 有原则的让步）
- **认错**：Round1 把"每轮 write_text"当结构脏源是错的——git 只看内容，相同内容不 dirty。真正自发脏源只剩①日期戳。
- 去日期戳后，"移出 git"相比"留在 git + 幂等 + 去日期戳"的增量收益只剩"教条意义的单一事实源"，而幂等下 MEMORY.md 稳态零 diff，占 git 名额的成本≈0 → 这张王牌缩水成普通牌。
- 冷启动一栏移出 git 反而**负收益**（要新增 SessionStart hook + 鸡生蛋窗口）；留在 git 则 clone 即有。
- 指控(a)手写措辞丢失：解法是把措辞回灌进各 memory 的 `description:` 字段——但这对两个方案**对称**，不是移出 git 的独有收益/代价。
- **最终推荐：撤回"移出 git"，收敛到反方"幂等+去日期戳"。** 因为用户取向里"低系统复杂度"压在"单一事实源"之前，两行改动 vs 踹翻 rebuild 架构+下沉，低复杂度反方碾压。
- 保留"移出 git"作为**规模触发的二期方案**：当 `_stats.json` 长到几十上百条、热区**真实跨天翻转**时，其收益才由负转正。

### 🔴 审阅者（反方 Round2 — 给硬主张）
- **认账**：决定性事实让"写前比对"那条**冗余**（git 本就不看 mtime）。唯一每天必遇脏源 = COLD 日期戳，删它即消。
- **但轻修在规模上去后必破**：memory 涨到几十上百条、`_stats.json` 有真信号后，`score=exp(-days/S)` 每天变 → 跨天某些条目穿越 Top-40 边界 → 名单翻转 → MEMORY.md 内容真变 → **纯系统抖动的 dirty**，且多机各自不同步。
- **核心论断**：只要分数含 `today` 变量，派生文件就是时间的函数，与"不自发变脏"**数学上不兼容**。修不好，因为需求本身排斥这个机制。
- **主张：砍掉热度系统**（非轻修）。删三件套：`memory_access_tracker.py` + PostToolUse hook、`memory_rebuild_index.py`、`session_snapshot.py` 的 rebuild 调用、`_stats.json`、`MEMORY_COLD.md`/冷区概念、产品层镜像 + 退役 `docs/memory-scoring-design.md`。
- 删后 memory 系统剩干净三件套：**各 memory 文件（事实源）+ 纯人工 MEMORY.md 索引 + `/find-memory` 搜索召回**。MEMORY.md 只在人真改 memory 时变（该变），零自发抖动、零信息丢失、人工措辞天然保留。
- 新 memory 进索引靠 `/summary` skill checklist 手动加一行（不引入"防漏脚本"——那本身是新脏源）。

## ✅ 共识结论

- **决定性事实**：git 只比对内容、不看 mtime；唯一每天必遇的自发脏源是 `MEMORY_COLD.md` 的 `rebuilt {today_str}` 日期戳。"移出 git"和"写前比对"都因此失去主要价值。
- **两方收敛**：当前规模下都**不推荐"移出 git"**（信息丢失 + 产品成本 + 冷启动负收益，不值）。
- **分歧精准收窄到一个产品决策**（非技术）：**用户还要不要"按时效自动重排热度"这个功能？**
  - 要 → 该功能与"不自发变脏"不兼容，只能走正方"移出 git"（接受信息丢失 + 多机本地各异 + 产品成本）。
  - 不要 → 走反方"砍掉热度系统"，MEMORY.md 转纯人工，永久干净（最符合低复杂度/可删除性）。
- **无争议的止血动作（任何路线都先做）**：删掉 `memory_rebuild_index.py` 的 COLD 日期戳（`rebuilt {today_str}`），立即消除每天必遇的脏源。

### 实施要点
- **Step 1（止血，立即）**：删 `memory_rebuild_index.py` L146 日期戳 + 产品层同款。bump + `[product]`。
- **Step 2（取决于用户决策）**：砍热度系统（删三件套，MEMORY.md 转纯人工，/summary 加索引 checklist）/ 或移出 git（保功能）/ 或暂不动（先止血观察）。

### 风险
- 砍热度系统是产品层大改 + 退役文档，影响所有下游；但当前 17 条伪热度下该机制零作用，YAGNI。
- 现实证据强烈倾向"砍"：`_stats.json` 仅 1 条记录、用户从不知道有此功能、一直当 MEMORY.md 是手写索引。
