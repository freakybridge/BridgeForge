# bridgeforge — 项目级 AGENTS.md

> ⚠️ **这不是普通项目**。bridgeforge 是个**"协作骨架工厂"**：它的产出（`templates/` + `skills/`）会被复印进每一个未来项目。
> 所以在这个 repo 里干活，第一红线不是"把功能做对"，而是**"把改动放对层、该传播的传播出去"**。

---

## §0.5 专业表达风格（always-on）

默认用工程判断口吻：先给结论，再给依据。能确定就直接说确定结论；不能确定就说明缺哪条证据，以及下一步怎么验证。

### 红线

- **禁止**空泛安抚句：不要用"没问题"、"当然可以"、"这是个好问题"这类无信息开场。
- **禁止**连续使用"可能 / 可以考虑 / 建议"这类弱判断来稀释结论；确实不确定时，明确标注"未验证 / 缺证据 / 只是推断"。
- **代码审查 / 方案判断 / 排障**时，优先说风险、根因、验证方式和文件证据；少说泛泛鼓励。
- **执行类任务**默认像可靠工程同事一样接管：读上下文、判断风险、动手、验证、交付结果；不要把明确任务包装成一串软建议。

### 默认工作姿态

- 用户给出明确执行目标时，默认直接推进到可交付结果：读上下文 → 判断风险 → 修改 / 执行 → 验证 → 汇报结果。
- **禁止**把明确任务退回成泛泛建议清单；只有缺少关键输入、存在高风险分叉、或会造成不可逆后果时才停下来问。
- 交付时优先报告"已做什么 / 验证了什么 / 还剩什么风险"，不要用"你可以……"作为主要收尾。

### 高价值场景输出结构

- **代码审查**：先列问题，按严重度排序；每条必须带文件 / 行号 / 行为风险；最后再给简短总结。
- **排障调试**：先给当前最可能根因；再给证据；再给下一步验证或修复动作。未验证的假说必须标明"未验证"。
- **架构 / 方案判断**：先给推荐结论；再给取舍理由；再列主要风险和触发条件。**禁止**只罗列选项不拍板。
- **验证通过**：交付中写"验证通过 / 测试通过 / 已验证"时，必须同时列出实际命令或收据、验证断言、覆盖路径 / 场景；缺任一项就标"未验证"或"已运行但验证有效性未确认"。

---

## §1 工厂红线：每个改动落地前，过一遍「传播四问」（always-on）

任何修改 / 新功能落地**之前**，必须显式回答这四问（写不出答案就别动手）：

1. **这属于哪一层？**
   - **产品层** `templates/` `skills/` → 会被复印给所有下游项目
   - **自身配置层** `.codex/` `AGENTS.md`（本文件）→ 只影响 bridgeforge 这个 repo 自己
   - **元文档** `docs/` `README.md` `SKILL.md` `CHANGELOG.md` → 描述产品，但不随产品下沉
2. **如果是通用改进，我写进 `templates/` / `skills/` 了吗？**
   - 最常见的事故：把一条通用规矩只写进了自身配置层或元文档，**忘了镜像进产品层** → 下游永远拿不到。
   - 反向也算事故：把项目特定的东西误塞进 `templates/` → 污染所有下游。判据见 [docs/design-rationale.md](docs/design-rationale.md) §6「模板 vs 占位」。
3. **传播出去要不要 bump 版本 + 记 CHANGELOG？**
   - 改动产品层 → 几乎一定要 bump（下游靠版本号判断该不该 sync）。
   - 记 CHANGELOG 时**按 §3 打层标签**。
4. **改的是 `templates/codex/hooks/` 或 `templates/codex/settings.json` 吗？那我吃狗粮了吗？（dogfood 镜像，红线）**
   - **凡确认要进产品层的 hook / settings 改动，必须当场镜像进自身 `.codex/`** —— 不能只发给下游、自己不装（§2 dogfood 约定的强制版）。
   - **现已机检硬拦**：`mirror_drift_check.py` 在 `.githooks/pre-commit` 对「缺文件」exit 2、正文差异（归一化 python 前缀后）软提示；漏镜像的 hook 提交时会被拦（细则 → `templates/codex/rules/portability.md §5.1`）。
   - 镜像时按 dev 仓库约定改 hook 命令：`templates/codex/` 用 `.venv/Scripts/python.exe`，自身 `.codex/settings.json` 用系统 `python`（dev 仓库无 `.venv`）。注意 hook `.py` 正文两侧应逐字一致——前缀差异只在 `settings.json` / `pre-commit` 的命令行，不在 `.py` 里。
   - 对 bridgeforge 不适用的 hook（如 Rust-only 的 `target_cleanup`）**也要挂上**——它的自门控 no-op 正好用来验证产品承诺，挂着 = 持续 dogfood 测试。
   - 例外：纯下游业务场景的 hook（本 repo 永远跑不到）可豁免，但要在 CHANGELOG 顶部当条加 `[dogfood-exempt: <hook> <因>]` 注明「不 dogfood + 原因」（这也是 `mirror_drift_check.py` 硬拦的豁免开关）。

> 写在 AGENTS.md 而非 rules/：任何任务常驻、不按 path 触发（理由 → design-rationale §5）。

---

## §1.5 自改审计独立性（always-on）

当审计对象包含本轮 agent 自己刚做的改动，且用户要求"审计 / 复核是否达成需求 / 找遗漏"时，必须启动独立 agent 做二次审计。

普通解释、轻量自查、用户未要求审计时不强制启动独立 agent。

---

## §2 分层地图（哪个目录 = 哪一层）

| 目录 / 文件 | 层 | 改动会不会传到下游 |
|------------|----|------------------|
| `templates/**` | 产品层 | ✅ 下游复印时全量继承 |
| `skills/**` | 产品层 | ✅ 下游 `$bridgeforge` Step 0 自检补齐到 `~/.agents/skills/` |
| `.codex/**` `AGENTS.md` | 自身配置层 | ❌ 只管 bridgeforge 自己（自产自用：理论上应与 `templates/` 同款，见下） |
| `docs/**` `README.md` `SKILL.md` | 元文档 | ❌ 描述产品 |
| `CHANGELOG.md` `VERSION` | 元文档（流水账 / SoT） | ❌ 自己的版本号；模板版本号是 `templates/<agent>/VERSION` |

**自产自用（dogfood）约定**：bridgeforge 自己也按自己的手册活——`.codex/hooks/*.py` 理论上应与 `templates/codex/hooks/*.py` **逐字一致**（仅 hook 命令前缀按 dev 仓库无 `.venv` 改用系统 `python`）。改了一边就该同步另一边（已提升为 §1 第 4 问红线）。

---

## §3 CHANGELOG 层标签约定

每条 CHANGELOG entry 前缀打一个标签，让下游一眼看懂"这次该不该拉"：

| 标签 | 含义 | 下游动作 |
|------|------|---------|
| `[product]` | 改了 `templates/` / `skills/`，会下沉 | sync-from-upstream 时**应当**拉取 |
| `[repo]` | 只改了 bridgeforge 自身配置 / 工具，不下沉 | 无关，跳过 |
| `[meta]` | 只改了 `docs/` / `README` / `SKILL.md` 等说明 | 一般无关（除非想了解设计） |

混合改动就并列标，如 `[product][meta]`。这是让"下游同步收益"最直接的抓手——下游 `grep "\[product\]" CHANGELOG.md` 即知增量。

---

## §4 跨项目传播机制（详见 docs/）

- **上游 → 下游**（拉新手册回老房子）：[docs/sync-from-upstream-playbook.md](docs/sync-from-upstream-playbook.md)
- **下游 → 上游**（把老房子攒的通用经验脱敏反哺回手册）：[docs/reverse-sync-playbook.md](docs/reverse-sync-playbook.md)
- **整体设计 / 双重身份论述**：[docs/design-rationale.md](docs/design-rationale.md) §9

两条 playbook 都**靠人脑判断、手动触发**——§1 四问是它们的"前门闸"（改动进门即分层 + 产品层 hook 当场 dogfood）。

---

## §5 hook 信号速查（dogfood 配套：镜像 hook 只发裸信号，响应契约在此）

| 信号 | 响应 |
|------|------|
| `[clarify]` | 大而模糊需求 → 先 `AskUserQuestion` 问 2-4 个背景问题对齐再动手；琐碎 / 续接 / 已说全细节 → 忽略 |
| `[focus] 任务锚:…` | 判断是否**不知不觉**偏离锚任务；正常转新任务 → 忽略；真偏离 → 先一句话说明再动（前置阻塞大的走 `/spinoff`） |
| `[ctx-budget] MEDIUM/HIGH/CRITICAL` | MEDIUM：完成后建议 `/snapshot`；HIGH/CRITICAL：响应开头报用量 + 强烈建议 `/snapshot` 换会话，决定权交用户 |
| `[stall]` | 本轮尽快收口——给结论或落一个具体动作，别继续纯 thinking 空耗 |
| `[find-doc]` | 定位文档优先 `/find-doc <topic>`；已知精确路径 / 代码搜索 → 忽略 |

> 完整契约（下游版全文）→ `templates/codex/AGENTS.md` §9.5-§10.5。
