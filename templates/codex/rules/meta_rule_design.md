---
paths:
  - ".codex/rules/**"
  - "AGENTS.md"
---

# Rule 设计规则（元规则）

> **加载条件**：编辑 `.codex/rules/**` 或 `AGENTS.md` 时自动加载。
>
> **目的**：防止 rule 文件退化成"百科全书 + 踩坑案例集"。每次写新 rule / 改老 rule 前必读。

---

## 1. 三层强制力梯度（最核心）

```
Hooks (代码驱动，必定执行)  >  Rules (建议，Codex 概率遵守)  >  AGENTS.md (越长越被忽略)
```

**判定**：

| 想达到的效果 | 该用哪层 |
|------------|---------|
| 改完代码必须跑 lint / build / test | **Hook**（`PostToolUse`） |
| 改完代码必须 bump 版本号 | **Hook**（`Stop` 提醒） |
| 编辑特定模块时必须按特定分支处理 | **Rule**（path-conditional） |
| 命名风格 / 术语 / 通用偏好 | **AGENTS.md** 或 **Rule** |
| 这一次性的临时偏好 | **Prompt** |

**核心反模式**：用 rule 当强制（长会话失效）。**真正必须**的写 hook；**建议性**的写 rule。

---

## 2. Rule 的定性（是什么 / 不是什么）

### Rule 是

- **代码库约束**：必须 X / 禁止 Y / 范式定义（数据流方向、职责边界）
- **决策红线**：架构级"不能跨越"的边界
- **path 触发**：相关代码改动时自动加载

### Rule 不是

| 内容类型 | 该放哪 | 在 rule 里出现就是退化 |
|---------|--------|---------------------|
| 完整事故案例（YYYY-MM-DD 那次踩坑） | `memory/` | ❌ |
| 长 code 示例（> 20 行） | `doc/3_design/` 或子文件 | ❌ |
| 决策过程 / 方案对比 | `doc/3_design/` 或 `doc/2_pending/debates_*` | ❌ |
| 教程 / 入门指南 | `doc/9_reference/` 或 `doc/4_archive/` | ❌ |
| 临时偏好 / 一次性约定 | prompt | ❌ |

**判定问句**：写完一段问自己 —

> "这是'必须 X / 禁止 Y'吗？"
> - 是 → 留 rule
> - 不是，是"YYYY 年 X 月 Y 日那次踩了 Z" → 搬 memory
> - 不是，是"方案 A vs B 怎么选" → 搬 doc

---

## 3. Rule 的最小骨架

```markdown
## <红线标题>（简短，可索引）

<一句话约束：必须 X / 禁止 Y>

**Why**: <一行，说明动因。引用 memory 案例名，不要把案例搬进来>

**How to apply**: <什么场景该想起这条；edge case 怎么处理>

详见 [memory/feedback_xxx.md](...) / [doc/3_design/yyy.md](...)
```

**最小骨架范例**（normative，≤10 行）：

```
## Module X 数据重算红线

**禁止** Module X 做 tick-driven 数据重算，只 emit 原始字段；实时刷新归下游 aggregator。

**Why**: 双重计算致 UI 跳动（memory `feedback_module_x_recompute`）。

**How to apply**: 写 `process_*` / `on_tick` 时不调 `recompute_*()`，只更 raw 字段后 emit。
```

> 完整正反例（退化版 30 行历史复盘 vs normative 版）略 — 按本节判据自写：凡看到"某年某月那次踩了 X + 长复盘"就是退化版，搬 memory 留一行 Why。

---

## 4. 加载策略红线

### 4.1 "始终加载"必须克制

只放每次开发都会用的内容。当 `architecture.md` + `modules.md` 总量已经过 3-5 KB 时就要警惕。**新增"始终加载" rule 必须用户同意**。

### 4.2 path 触发器越窄越好

| 反例 | 修正 |
|------|------|
| `编辑 src/** 或 tests/**` | 收成具体子目录，如 `src/risk/**` |
| `涉及架构 / 较大改动时` | 改成具体文件 path |
| `任何时候` | 拆成两条：常用部分 path-conditional 加载；真红线进 AGENTS.md |

**判定**：触发条件覆盖 > 50% 的开发场景 → 太宽。

### 4.3 同一约束禁止多处重复

AGENTS.md / 多个 rules / memory 之间，同一条约束**只在一处写正文**，其他位置只放 pointer。改一处忘改另一处会产生信息漂移。

### 4.4 入口文件"既当索引又当正文"会两者都失效

AGENTS.md 是项目入口，**只放索引 + 必要红线**，正文细节放对应 rule。`MEMORY.md` 同理（索引 ≤ 200 行，详情子文件）。

---

## 5. 量化红线

| 文件类型 | 大小红线 | 行数红线 | 超了怎么办 |
|---------|---------|---------|----------|
| 单个 rule | 50 KB | 500 行 | 拆 path-specific（如 `gateway.md` → `gateway_<vendor>.md`） |
| AGENTS.md | 25 KB | 200 行 | 段落正文移到对应 rule，只留 pointer |
| MEMORY.md 索引 | 25 KB | 200 行 | 详细信息搬子文件，索引只一行 |
| 单条 memory 索引行 | — | 150 字符 | 压缩描述 |

> 单 rule 的体积 / 行数 / 戳数 / 长 code 块红线由 `rule_size_check.py` **双层护栏**执行：PostToolUse 编辑时软提醒 + **pre-commit 硬拦**（对 staged `.codex/rules/*.md` 读 staged blob，超标 exit 2；CHANGELOG.md 顶部当条加 `[skip-rule-size]` 可豁免本次）。

---

## 6. 维护节奏（增量演化）

### 6.1 从空开始

官方推荐的 AGENTS.md 起步是 100 行 / 2500 tokens。**禁止**一上来写满百科全书，只在 Codex 实际犯错时增量加规则。

### 6.2 案例增多 → 拆 path-specific rule

当某个 topic（如外部 SDK / 某个 feature）的案例累积到一定量，从公共 rule 拆成专属 path-rule。

### 6.3 rule 越来越胖 → 案例下沉

某 rule > 500 行先 audit：① normative → 留；② 案例 / 历史 → 搬 memory；③ 示例 / 教程 → 搬 doc。**禁止**超 1000 行还不拆。

### 6.4 自动护栏

机械可判定的退化用 hook 自动查（**PostToolUse 软提醒 + pre-commit 硬拦**，`[skip-rule-size]` 可豁免；见到信号后按 §5/§6 处置）；**normative 比例**（案例 vs 红线）需语义判断，hook 做不了 → 留人工 self-check（§8 前两项）。本骨架附带两道护栏（项目有 `.venv` 时由 bridgeforge 复制 + settings.json 注册），二者均双层挂载（PostToolUse 编辑瞬间软提醒 + `.githooks/pre-commit` 提交期硬拦 exit 2）：

- `.codex/hooks/rule_index_check.py` — AGENTS.md 规则索引 ↔ `rules/*.md` 一致性（死链接 / 未索引）。pre-commit 读**工作树**判定（跨目录集合一致性比对；局限：部分暂存可能误报，`[skip-rule-size]` 兜底）。
- `.codex/hooks/rule_size_check.py` — 量化红线：大小 / 行数 / 版本戳 / 日期戳 / 长 code 块 / **触发器宽度**（单段目录通配 `a/**` 或裸 `**` = 伪常驻）。pre-commit 读 **staged blob**（`git show :path`，单文件自洽、近零误伤）。

---

## 7. 反模式速查

| 反模式 | 后果 | 修正 |
|--------|------|------|
| 用 `@` 引用整目录 / 大文件 | context 爆炸 | 精确到文件 + 章节锚点 |
| rule 标题写得长 / 不可索引 | 引用时拗口 | 标题 ≤ 20 字，可作 anchor |
| 在 rule 末尾写"详见 X / Y / Z"长清单 | 维护成本高，经常过时 | 只链 1-2 个权威来源 |

> 另 7 类（塞完整案例 / 塞 >20 行 code / 触发器过宽 / rule 当强制 / 一上来写满 / 多处重复正文 / 入口既索引又正文）已在 §1/§2/§4/§6 各处成条，此处不重列。

---

## 8. 现状评估清单（self-check）

每次写新 rule / 改老 rule 前，过一遍：

- [ ] 这条约束真的需要 rule 吗？（不是 prompt 一次性？不是 hook 能强制？）
- [ ] 内容里有没有完整事故案例？（有 → 抽 memory）
- [ ] 内容里有没有 > 20 行的 code 示例？（有 → 抽 doc/3_design）【pre-commit 硬拦】
- [ ] 内容里有没有版本号 > 5 处 / 日期 > 8 处？（有 → 信号：案例越界；阈值以 `rule_size_check.py` 为准）【pre-commit 硬拦】
- [ ] 触发器 path 是否单段目录通配（`a/**`）或裸 `**`？（是 → 伪常驻，收紧到 ≥2 段前缀）【pre-commit 硬拦；横切框架规则在 `rule_size_check.py` 白名单豁免】
- [ ] 跟现有哪条 rule 有重叠？（有 → 合并 / pointer）
- [ ] 单 rule 改完后总大小 / 行数？（超 50KB / 500 行 → 拆）
- [ ] 标题能不能 ≤ 20 字 + 作 anchor？

全部通过 → 可以提交。

---

## 9. 与其他 rule 的关系

**冲突优先级**：具体 rule > meta_rule > AGENTS.md（meta_rule 是元规则，不覆盖具体业务红线）。
