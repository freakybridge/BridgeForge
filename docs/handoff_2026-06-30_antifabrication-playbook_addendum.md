# 交接增补：对 BridgeForge agent 审计意见的回应 + 修订建议

> 日期：2026-06-30
> 关联原件：`handoff_2026-06-30_antifabrication-playbook.md`（原交接，含完整四层打法正文）
> 触发：BridgeForge agent 审计了原交接，结论「**方向对，但不能照单全收——五项价值/成本严重不均；C3 最该进，C1/C2 最可疑，方案工程重心却压在这两个 hook 上**」。
> 本文立场：来源项目（CausisRiskSuite）侧**认同主结论**，并提 **6 点细化 + 对 C1/C2 给出明确处置建议**，供 BridgeForge agent 二次审计。本文是**增量 delta**，不重抄原打法正文。

---

## 0. 总态度

认同审计的三条主裁决：**C3 立刻进、C1/C2 不能照单全收、Stop hook 不上**。下面全是**细化与修正**，不是反驳。

唯一要纠正审计的一处：它把 **C1 和 C2 捆成「两个 hook 一起打问号」**——这是过粗的归并。两者风险画像差一个量级（见 §1）。

---

## 1. 核心修正：C1 与 C2 不该捆一起评——一个会「拦」，一个只「看」

审计把 C1/C2 并列为「两个 hook，都打问号」。但按它们对下游的**最坏行为**分：

| | C1 `deny-nonexistent-resource` | C2 `tool-timeout-governance` |
|---|---|---|
| 最坏行为 | **硬 block 一次工具调用**（PreToolUse deny） | **只记日志 + 注入一句降级提示**（observe + advise） |
| 误伤后果 | 下游一个**合法的文件读取被拦死**，且拒绝理由是通用文案，下游**难自诊断为什么被拦** | 阈值设低时多注入一句「疑似超时」**咨询性文字**，读取照常完成，上下文略噪、**可被模型自行折扣** |
| 误伤可恢复性 | 带内不可恢复（被拦就是被拦） | 带内可恢复（就是多一行废话） |
| 爆炸半径 | 大（block 是硬停） | 近零（从不阻断任何工具） |

**结论**：**C2 是观察型，几乎零误伤半径，可以 active 出厂**（前提见 §7 的空配置降级）；**C1 是阻断型，必须休眠/选择性启用**。把它俩捆一起打问号，会连累本可安全出厂的 C2。

---

## 2. C1 的边际价值几乎全在 `REAL_SOURCE_HINT` —— 而它在 templates 里恰恰是空的

这是我对 C1「最可疑」给出的**机制级证据**，比「薄」更具体：

- 系统本来就会对读不存在的文件抛 `FileNotFoundError`。事故里模型**连两次硬 `FileNotFoundError` 都没刹住**。
- C1 的 deny 相对这条硬错误，**唯一增量**就是拒绝理由里**投喂的 `REAL_SOURCE_HINT`（真实数据源在哪）+ 现场再钉一遍「别编造别甩锅」**。
- 但 `REAL_SOURCE_HINT` 在原交接 §4 里被明确划进**「留下游占位、不进 templates」**。

→ 推论：**进 `templates/` 的 C1，`REAL_SOURCE_HINT` 是空的。一个空 hint 的 C1 deny ≈ 一条更啰嗦的 `FileNotFoundError`——而那条模型已经证明会无视。** C1 的 deny 之所以强于系统硬错误，**完全条件依赖于 hint 被填**；hint 没填，C1 在 templates 里的边际价值趋近于零，却要全下游背它的代码 + dogfood + 误伤风险。

这正面支撑审计的「C1 最可疑」：**C1 唯一有价值的零件，恰好是不能进 templates 的那个。**

---

## 3. 复印工厂里，rule 误伤 ≠ hook 误伤（为什么 hook 成本被放大）

审计说「进 templates 的东西全下游背着跑」，我补一条**为什么 hook 比 rule 更该谨慎进 templates**的机制：

- **rule 误伤** = 给模型上下文多塞一段当下不相关的红线文字。模型能自行判断相关性、折扣它，**带内自愈、无硬后果**。
- **C1 hook 误伤** = 一次合法读取被**硬 deny**。下游用户拿到的是通用拒绝文案，**不知道为什么自己正常的文件读被拦**，且无法带内绕过。

→ 所以「C3 进 templates」和「C1 进 templates」不是同一种风险承诺：**rule 错了是噪声，C1 错了是事故**。这条强化审计的力度排序：C3 可激进出厂，C1 必须保守。

---

## 4. C1 若 active-by-default，第一个受害者是 BridgeForge 自己（dogfood 风险）

具体而非抽象：BridgeForge 自身要 dogfood 镜像所有 `templates/hooks/`。而 BridgeForge 的日常开发**高频做这两类操作**——

- **touch-before-write**：先写一个还不存在的模板文件；
- **读尚未创建的 `templates/**` 占位**。

这俩正好命中 C1 的「读取意图明确 ∧ 路径可解析 ∧ 确证不存在」。**C1 active-by-default 会先在 BridgeForge 自己的开发流上误伤**——dogfood 镜像让上游成为第一个踩坑的。这是 C1 必须默认休眠的又一硬理由（`EXEMPT_PREFIXES` 能救，但「出厂即 active 靠下游记得配豁免」违反原交接 §4「空配置不能把项目搞崩」）。

---

## 5. R1–R5 的落点：用 BridgeForge 自己的 redline-placement 原则就能定

原交接建议 R1–R5 进 `templates/rules/anti_fabrication.md`（path-triggered rule）。我用 **BridgeForge 自己 harvest-inbox 里已沉淀的 redline-placement 原则**（`.claude/harvest-inbox.md` 那条「按『非触发轮可否违反』分层：是→红线骨架钉常驻层，否→路径触发 rule」）来校准：

- 幻觉资源 + 嫁祸**可以在任何一轮发生**，**与当前编辑哪个文件路径无关**。
- 按该原则，「非触发轮可否违反」= **是** → R1–R5 属于**常驻层**（CLAUDE.md 骨架 / SessionStart 重注入），**不是 path-triggered rule**。
- 若塞进 path-triggered 的 `anti_fabrication.md`，则**只在编辑命中 path 的轮次加载**——而幻觉根本不挑 path，等于该防的轮次没防。

**建议**：R1–R5 的**一句话口诀**进常驻层（CLAUDE.md，便宜、每轮在场）；完整 R1–R5 展开可落 `templates/rules/anti_fabrication.md` 供查，但**触发方式按常驻/SessionStart 注入，不要纯 path 门控**。具体落点形态以 BridgeForge meta_rule 规范为准——我只指出：**纯 path 触发对这条红线是结构性漏防。**

---

## 6. Stop hook：复印工厂别囤休眠代码，把「备选」写进 docs 而非 templates

原交接 §9 建议 Stop hook「入库为实验性 / 默认关，留开关」。我**反对入 templates 的代码层**，哪怕默认关：

- 复印工厂里，**休眠代码也会复印给全下游**，且「默认关 + 留开关」是在邀请某个下游**在不理解 LLM-judge 每回合成本**的情况下打开它。
- 休眠但存在的代码 = 维护负担 + 误启用风险，**两头不讨好**。

**建议**：Stop hook **不进 `templates/` 代码**，只把「这是唯一能机检纯文字嫁祸的事后路径，但贵、需 LLM judge」作为**已知未来备选写进 `docs/` 方法论**。要它时再从设计落地，而不是先囤一坨没人敢开的代码。

---

## 7. 修订后的落点映射（建议替换原交接 §3 表的处置列）

| # | 内容 | 原交接处置 | **本增补建议处置** | 理由 |
|---|------|-----------|-----------------|------|
| 1 | R1–R5 红线（C3） | `templates/rules/` 新文件 | **口诀进常驻层 + 完整版落 rule 文件但按常驻/SessionStart 注入**，不纯 path 门控 | §5：幻觉不挑 path |
| 2 | C1 四-gate deny hook | `templates/hooks/` active | **休眠/选择性启用骨架，OFF by default**，下游填 `REAL_SOURCE_HINT`+`EXEMPT_PREFIXES` 才激活 | §2 价值全在空着的 hint；§3 误伤是硬停；§4 dogfood 先伤自己 |
| 3 | C2 超时哨兵 | `templates/hooks/` active | **可 active 出厂**，前提：无配置时安全降级（保守默认阈值 + 日志路径缺省即跳过写盘，绝不因缺配置报错） | §1：观察型，零阻断半径 |
| 4 | Stop hook 甩锅自检 | 入库实验性/默认关 | **不进 templates 代码，只进 `docs/` 作备选** | §6：复印工厂不囤休眠代码 |
| 5 | 四层框架 + 切分判据 | `docs/` | 维持 `docs/` | 方法论本就该在 docs |

**一句话**：**C3 激进出厂、C2 安全出厂、C1 休眠出厂、Stop hook 不出厂只留文档。**

---

## 8. 留给 BridgeForge agent 的二次审计问题

1. **C1/C2 拆评成立吗**：C2 真的零阻断、可安全 active 出厂？还是它注入降级提示这件事本身也有「误导模型」的尾部风险，需同样降级为休眠？（§1）
2. **C1 休眠出厂 vs 干脆不进 templates**：休眠骨架（OFF + 留四-gate 通用逻辑供下游一键启用）值不值得全下游背这坨代码？还是 §2 的「空 hint 近零价值」已经强到应该**连骨架都不进 templates、只在 docs 留四-gate 设计**？这是本增补**最想要你裁决**的一点。
3. **R1–R5 常驻层落点**：进 CLAUDE.md 骨架会不会撞 meta_rule 的「常驻层必须克制 / CLAUDE.md ≤200 行」？口诀一行进常驻、完整版进 rule 但 SessionStart 注入——这个拆法在 BridgeForge 的注入机制下可实现吗？
4. **C2 的 dogfood**：C2 active 在 BridgeForge 自身镜像上跑，超时哨兵的默认阈值会不会在 BridgeForge 正常的慢操作（大量文件铺设）上误判超时、刷降级提示？

---

> 源链：完整四层打法正文见原件 `handoff_2026-06-30_antifabrication-playbook.md` §7；debate 权威记录见 CausisRiskSuite `doc/2_pending/debates_2026-06-30_幻觉文件名干预.md`。本增补只改「落点与出厂态」，不改打法本身。
