---
paths:
  - ".claude/rules/**"
  - "CLAUDE.md"
---

# Rule 设计规则（元规则）

> **加载条件**：编辑 `.claude/rules/**` 或 `CLAUDE.md` 时自动加载。
>
> **目的**：防止 rule 文件退化成"百科全书 + 踩坑案例集"。每次写新 rule / 改老 rule 前必读。

---

## 1. 三层强制力梯度（最核心）

```
Hooks (代码驱动，必定执行)  >  Rules (建议，Claude 概率遵守)  >  CLAUDE.md (越长越被忽略)
```

**判定**：

| 想达到的效果 | 该用哪层 |
|------------|---------|
| 改完代码必须跑 lint / build / test | **Hook**（`PostToolUse`） |
| 改完代码必须 bump 版本号 | **Hook**（`Stop` 提醒） |
| 编辑特定模块时必须按特定分支处理 | **Rule**（path-conditional） |
| 命名风格 / 术语 / 通用偏好 | **CLAUDE.md** 或 **Rule** |
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

**例子**（对比版）：

❌ **退化版**（rule 里塞案例）：

```
## 改 Module X 的 process_data

Module X 不应该自己重算 balance，因为 YYYY-MM-DD vX.Y.Z 那次出问题了。
当时 process_data 在 tick-driven 路径里又算了一次，导致和下游模块重复计算，
UI 显示跳动。具体表现是 ... （后面 30 行历史复盘）
```

✅ **normative 版**：

```
## Module X 数据重算红线

**禁止** Module X 做 tick-driven 数据重算，只 emit 原始字段。实时刷新归
下游 aggregator 统一接管。

**Why**: 双重计算导致 UI 跳动（memory `feedback_module_x_recompute_belongs_to_downstream`）。

**How to apply**: 写 `process_*` / `on_tick` 等接收推送的处理时，**不要**调
`recompute_*()` 类方法，只更新 raw 字段后 emit。
```

---

## 4. 加载策略红线

### 4.1 "始终加载"必须克制

只放每次开发都会用的内容。当 `architecture.md` + `modules.md` 总量已经过 3-5 KB 时就要警惕。**新增"始终加载" rule 必须用户同意**。

### 4.2 path 触发器越窄越好

| 反例 | 修正 |
|------|------|
| `编辑 src/** 或 tests/**` | 收成具体子目录，如 `src/risk/**` |
| `涉及架构 / 较大改动时` | 改成具体文件 path |
| `任何时候` | 拆成两条：常用部分 path-conditional 加载；真红线进 CLAUDE.md |

**判定**：触发条件覆盖 > 50% 的开发场景 → 太宽。

### 4.3 同一约束禁止多处重复

CLAUDE.md / 多个 rules / memory 之间，同一条约束**只在一处写正文**，其他位置只放 pointer。改一处忘改另一处会产生信息漂移。

### 4.4 入口文件"既当索引又当正文"会两者都失效

CLAUDE.md 是项目入口，**只放索引 + 必要红线**，正文细节放对应 rule。`MEMORY.md` 同理（索引 ≤ 200 行，详情子文件）。

---

## 5. 量化红线

| 文件类型 | 大小红线 | 行数红线 | 超了怎么办 |
|---------|---------|---------|----------|
| 单个 rule | 50 KB | 500 行 | 拆 path-specific（如 `gateway.md` → `gateway_<vendor>.md`） |
| CLAUDE.md | 25 KB | 200 行 | 段落正文移到对应 rule，只留 pointer |
| MEMORY.md 索引 | 25 KB | 200 行 | 详细信息搬子文件，索引只一行 |
| 单条 memory 索引行 | — | 150 字符 | 压缩描述 |

---

## 6. 维护节奏（增量演化）

### 6.1 从空开始

官方推荐的 CLAUDE.md 起步是 100 行 / 2500 tokens。**禁止**一上来写满百科全书，只在 Claude 实际犯错时增量加规则。

### 6.2 案例增多 → 拆 path-specific rule

当某个 topic（如外部 SDK / 某个 feature）的案例累积到一定量，从公共 rule 拆成专属 path-rule。

### 6.3 rule 越来越胖 → 案例下沉

发现某个 rule 行数 > 500 时，先 audit 内容：

1. 哪些段是 normative？ → 留
2. 哪些段是案例 / 历史？ → 搬 memory
3. 哪些段是示例 / 教程？ → 搬 doc

**禁止**等到一个 rule 超过 1000 行还不拆。

### 6.4 自动护栏

机械可判定的退化用 hook 自动查（只提醒不阻塞，见到信号后按 §5/§6 处置）；**normative 比例**（案例 vs 红线）需语义判断，hook 做不了 → 留人工 self-check（§8 前两项）。本骨架附带两道护栏（项目有 `.venv` 时由 setup_agent 复制 + settings.json 注册）：

- `.claude/hooks/rule_index_check.py`（PostToolUse）— CLAUDE.md 规则索引 ↔ `rules/*.md` 一致性（死链接 / 未索引）
- `.claude/hooks/rule_size_check.py`（PostToolUse）— 量化红线：大小 / 行数 / 版本戳 / 日期戳 / 长 code 块 / **触发器宽度**（单段目录通配 `a/**` 或裸 `**` = 伪常驻）

---

## 7. 反模式速查

| 反模式 | 后果 | 修正 |
|--------|------|------|
| rule 里塞完整事故案例 | rule 爆胖，真红线被淹 | 案例搬 memory，rule 只 1 行 Why + 链接 |
| rule 里塞 code 示例（> 20 行） | 同上 | 示例搬 `doc/3_design/`，rule 留 1-2 行片段 + 链接 |
| 触发器写得太宽（`src/**` 等） | 等同始终加载，context 浪费 | path 收紧到具体子目录 |
| 用 rule 当强制（"必须每次跑 X"） | 长会话失效 | 改用 hook |
| 把 rule 当百科全书一上来写满 | 维护负担，大多数永远用不到 | 从空开始增量加 |
| 同一约束多处重复正文 | 改一处忘另一处，信息漂移 | 单一事实源 + 其他位置 pointer |
| CLAUDE.md 既当索引又当正文 | 两者都失效 | CLAUDE.md ≤ 200 行，只索引 |
| 用 `@` 引用整目录 / 大文件 | context 爆炸 | 精确到文件 + 章节锚点 |
| rule 标题写得长 / 不可索引 | 引用时拗口 | 标题 ≤ 20 字，可作 anchor |
| 在 rule 末尾写"详见 X / Y / Z"长清单 | 维护成本高，经常过时 | 只链 1-2 个权威来源 |

---

## 8. 现状评估清单（self-check）

每次写新 rule / 改老 rule 前，过一遍：

- [ ] 这条约束真的需要 rule 吗？（不是 prompt 一次性？不是 hook 能强制？）
- [ ] 内容里有没有完整事故案例？（有 → 抽 memory）
- [ ] 内容里有没有 > 20 行的 code 示例？（有 → 抽 doc/3_design）【hook 已自动查】
- [ ] 内容里有没有版本号 > 5 处 / 日期 > 8 处？（有 → 信号：案例越界；阈值以 `rule_size_check.py` 为准）【hook 已自动查】
- [ ] 触发器 path 是否单段目录通配（`a/**`）或裸 `**`？（是 → 伪常驻，收紧到 ≥2 段前缀）【hook 已自动查；横切框架规则在 `rule_size_check.py` 白名单豁免】
- [ ] 跟现有哪条 rule 有重叠？（有 → 合并 / pointer）
- [ ] 单 rule 改完后总大小 / 行数？（超 50KB / 500 行 → 拆）
- [ ] 标题能不能 ≤ 20 字 + 作 anchor？

全部通过 → 可以提交。

---

## 9. 与其他 rule 的关系

| Rule | 关系 |
|------|------|
| `workflow.md` | 工作流（怎么开发），meta_rule（怎么写规则）— 互补不重叠 |
| `portability.md` | 跨机器可移植性，meta_rule 不管这层 |
| `architecture.md` | 架构红线本身，meta_rule 管的是"红线该长什么样" |

**冲突优先级**：具体 rule > meta_rule > CLAUDE.md（meta_rule 是元规则，不覆盖具体业务红线）。

---

## 10. 反模式案例库（本项目实测）

<!-- TODO: 当本项目发现 rule 退化样本时登记进来，作为反例教材
示例（请按本项目实际情况填）：

| 文件 | 当前状态 | 问题 | 处理 |
|------|---------|------|------|
| `<rule>.md` | 48 KB / 829 行 | 塞了 N+ 个完整事故案例和 code 示例，远超 50KB / 500 行红线 | 阶段 X 拆分 + 案例下沉 |
| `<rule>.md` | 触发器 `**/* tests/**` 等同始终加载 | 阶段 Y 收紧 |

**本表实时更新**：每次发现新的退化样本登记进来。
-->
