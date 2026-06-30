# 终局共识：防 AI 幻觉资源打法 → bridgeforge 出厂态（两轮审计后对齐）

> 日期：2026-06-30
> 关联：`handoff_..._antifabrication-playbook.md`（原交接，含完整四层打法正文）→ `..._addendum.md`（来源侧对首轮审计的回应）→ 本文（对二轮审计的回应，**双方对齐，可据此落地**）。
> 状态：**意见已统一。** 两处开放分歧（C2 出厂态、C1 出厂态）来源侧均采纳 BridgeForge 侧裁决；其中一处修正了论证、结论不变。

---

## 0. 一句话

经两轮对抗式审计，最终出厂态：**C3 红线立刻进（口诀进常驻 + 完整进 rule）；C1、C2、Stop hook 三个 hook 都不进 `templates/hooks/` 强制层，四-gate / 超时哨兵 / 甩锅自检的完整设计与脚本进 `docs/`（或 `docs/examples/`）按需取；方法论框架进 `docs/`。**

> **核心收敛逻辑**：`templates/hooks/` 是「clone 即复印全下游 + 必须 dogfood 镜像」的强制层。只有「通用、低误伤、净收益清晰」的东西配进去。三个 hook 各自栽在不同一条上（C1 误伤是硬停 + 价值零件不能进 templates；C2 在 Claude Code 宿主下够不到诱因现场；Stop hook 贵 + 每轮 LLM judge）。**红线（C3）是纯文字、零代码、零误伤、堵最伤人的 L3 → 唯一进强制层的。**

---

## 1. 分歧 B（C1 出厂态）：来源侧**全采纳** BridgeForge 裁决

**裁决**：C1 四-gate deny hook **连休眠骨架都不进 `templates/hooks/`**；完整四-gate 判定逻辑（含三道防误伤保险）作为「已知设计」完整进 `docs/`（建议 `docs/examples/antifab-deny-hook.py` + 设计说明），哪个下游真撞上「幻觉读文件」痛点、又愿填 `REAL_SOURCE_HINT`+`EXEMPT_PREFIXES`，再照着落地一份。

**采纳理由**（BridgeForge 用来源侧自己毙 Stop hook 的标准反套，三条全成立）：
- 休眠代码照样 clone 即复印全下游；
- 「填俩配置就激活」就是那个危险开关，打开后果是**硬 deny 合法读取**；
- 休眠但存在 = 维护负担 + 误启用风险。
- 叠加来源侧自己挖的三条硬证据：§2 C1 唯一有价值的 `REAL_SOURCE_HINT` 在 templates 里恒为空 → 空 hint 的 C1 ≈ 更啰嗦的、模型已证明会无视的 `FileNotFoundError`；§4 C1 active 会先误伤 bridgeforge 自己的 touch-before-write / 读未创建占位；§3 C1 误伤是硬停且下游难自诊断。

**来源侧自认不自洽点**：原 addendum 给 C1「休眠出厂」、给 Stop hook「不进」，是同一把尺子两个待遇。统一后两者同级处置：**都不进 templates 代码，设计进 docs。**

**来源侧补一个零件（堵 docs 化后的发现性缺口）**：C3 红线条文里**挂一行指针**指向 `docs/examples/antifab-deny-hook.py`——下游撞上痛点时，常驻的 C3 规则能把人导到那个 example，不靠"记得去 bridgeforge 翻"。

---

## 2. 分歧 A（C2 出厂态）：来源侧**采纳结论**（C2 降级 docs），但**修正其论证**

**裁决（结论一致）**：C2 超时哨兵**不 active 出厂、不进 `templates/hooks/`**，降级为 `docs/` 方法论。

**但 BridgeForge 的论证有一处机制错误，须更正——否则共识建在错误前提上**：

> BridgeForge 原话：「agent 抄近路的决策早在那 8 分钟卡死里就做完了，事后补话太晚。」

- **错在**：模型在工具执行期间是**挂起的、没在生成**。抄近路的决策发生在工具**返回之后**那一刻。所以 PostToolUse 在软超时返回后注入降级提示，**时机是准的**——对本次真实事故（两次 Read 超时都返回了）甚至会有效。"事后补话太晚"不成立。

**C2 仍应降级的、站得住的真实理由**（替换上面那条）：
1. 原 playbook 的 C2「包一层超时哨兵」靠「记录起止时刻」算 delta，**本就是边界式（PreToolUse 打点 + PostToolUse 算差）**，不是「卡死中途开火」——Claude Code 确无工具执行中途钩子，但 C2 本来也没需要它。
2. 这个可实现版本对**真·永不返回的硬卡死完全失明**（PostToolUse 不触发）——而硬卡死才是最毒的诱因。
3. 对软超时，C2-b 的注入**与 C3 常驻红线高度重叠**（模型已经看到超时错误），边际增益薄。
4. 阈值式 delta 检测会在 bridgeforge 大量慢-成功操作上**误刷"疑似超时"噪声**（BridgeForge 第 4 问的担心，此处成立）；改成「按超时错误签名触发」可消除误报，但那已退化成「软超时后再喊一句 C3」，更不值一个强制层 hook。

**净判**：C2 有**薄而真**的价值（软超时返回后重注入、对冲 C3 长会话衰减），但够不上 `templates/hooks/`+dogfood 的门槛 → **降级 `docs/` 方法论**。落点与 BridgeForge 一致，理由更硬。

---

## 3. 其余三项：来源侧**全同意** BridgeForge（其有 bridgeforge 内部可见性，方案更省更对）

| 项 | 终局 |
|----|------|
| **C3 红线落点** | **口诀一行进 `templates/CLAUDE.md` 常驻正文（始终在场）+ 完整 R1–R5 与四层框架进 `templates/rules/anti_fabrication.md`（详情库，按需查）。** 复用 bridgeforge 已验证的 redline-placement 两档范式，**不新造「SessionStart 注入完整红线」第三种机制**，不撞 meta_rule ≤200 行。 |
| **不加 `[anti-fab]` 轻信号 hook** | 同意。幻觉是低频事件，每轮注入信号是噪声。一行口诀常驻已够本；真发现长会话衰减，再仿 focus「攒够轮数才注入」的节流式补，不迟。 |
| **Stop hook** | 不进 templates 代码，只在 `docs/` 留「唯一能机检纯文字嫁祸但贵」的备选设计。 |
| **方法论框架 + 切分判据** | 进 `docs/`。 |

---

## 4. 终局出厂态总表（可据此落地）

| # | 内容 | 出厂态 | 落点 |
|---|------|--------|------|
| 1 | R1–R5 口诀 | **进常驻强制层** | `templates/CLAUDE.md` 正文一行 |
| 2 | R1–R5 完整 + 四层框架 + 切分判据 | 进详情库 | `templates/rules/anti_fabrication.md` |
| 3 | C1 四-gate deny 脚本 + 设计 | **不进 templates** | `docs/examples/antifab-deny-hook.py` + docs 说明；C3 规则挂指针 |
| 4 | C2 超时哨兵设计 | **不进 templates** | `docs/` 方法论 |
| 5 | Stop hook 甩锅自检设计 | **不进 templates** | `docs/` 备选 |

**强制配套**：本轮结论下，`templates/hooks/` **不新增任何文件** → 无需动 dogfood 镜像、无需注册 settings.json hook。只动 `templates/CLAUDE.md`（一行）+ 新增 `templates/rules/anti_fabrication.md` + `docs/`。bump VERSION（新增产品层红线规则 → 视 bridgeforge 约定 patch/minor）+ CHANGELOG `[product]`。

---

## 5. 残余风险（诚实保留，落地时随附）

- **纯文字逃逸仍无事中拦截**：L3 嫁祸是 0 工具调用，C1 都进 docs 了、更无任何 hook 看得见 → **完全靠 C3 口诀 + R5 反激励（认错不扣分、掩盖才扣分）压低概率**。这是本方案最薄弱、最依赖模型自觉的一环。本轮把三个 hook 全收进 docs 后，强制层只剩 C3 一道——**接受这个取舍**：宁可少装会误伤/够不到的 hook，也不在复印工厂强推半残防御。
- **C3 概率遵守、长会话衰减**：一行口诀常驻对冲一部分；衰减严重再上节流式信号 hook（暂不做）。
- **C1/C2 下游自取**：撞上痛点的下游需自行从 docs 落地并填项目数据——这是「不污染全下游」换来的代价，可接受。

---

> 双方意见至此统一。落地动作仅在 `templates/CLAUDE.md` / `templates/rules/anti_fabrication.md` / `docs/`，不碰 `templates/hooks/` 与 dogfood 镜像。
