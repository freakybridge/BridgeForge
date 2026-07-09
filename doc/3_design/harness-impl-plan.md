我已完整读取设计文档。这份设计文档本身就是"已核验的工单"来源(含 verify 修正)。现在我把它汇成一份供实施 agent 直接照做的开发计划文档。我已掌握全部工单(P0-1~5、P1-6~7、P2-8~11)、依赖、层标签、dogfood 要求、E-3/E-6 映射。

任务是"汇成一份开发计划文档"作为我的返回值。我直接输出该文档全文。

---

# BridgeForge Harness 九维方案 · 实施开发计划（供实施 agent 直接照做）

> 依据：`doc/3_design/harness-engineering-design.md`（v1，已融 verify 修正 + 对抗批评 11 项）。本计划把设计文档的 §4 路线图落成可逐条施工的工单，verify 打回/降级项已按结论修正后呈现，不含带病原稿。

---

## 【使用说明】给实施 agent 的话

1. **先读设计**：动手前 **Read `d:/Quant/BridgeForge/doc/3_design/harness-engineering-design.md`** 拿全上下文（尤其 §1 各维落地机制、§2 全局机制清单、§5 残余风险、§6 修订记录）。本计划是施工序，设计文档是判据源，冲突以设计文档为准。
2. **严守 dogfood 镜像红线（CLAUDE §1 第 4 问）**：凡改 `templates/hooks/` 或 `templates/settings.json`，**当场镜像进自身 `.claude/`**。命令前缀：`templates/` 用 `.venv/Scripts/python.exe`，自身 `.claude/settings.json` 用系统 `python`（dev 仓无 `.venv`）。对 bridgeforge 恒 no-op 的闸也要挂上（自门控 no-op = 持续验证产品承诺）。
3. **不 commit / 不 push**：只改文件，改完停下交还用户。提交与同步由用户亲自运行。
4. **逐工单自验再进下一个**：每完成一个工单，按该工单 **acceptance** 自验通过后才推进；不满足就修，别带病往下堆。
5. **产品层改动记账**：改 `templates/**` 或 `skills/**` → bump `templates/VERSION` + 写 `[product]` CHANGELOG（按 CLAUDE §3 打层标签，混合改动并列标）。对 bridgeforge no-op 的闸按 §1 第 4 问在 CHANGELOG 注明「不适用但仍挂上验证产品承诺」。
6. **检索走受控工具**：Glob/Grep/Read 找文件查内容，shell 只留给构建/git/进程。

---

## 【依赖序总览】

> 三轴排序：价值(机器判死/近零误伤) → 依赖 → **本机可验证性**。
> **P0 全是低风险**（dogfood 镜像补齐 + 纯文本改 + 阈值统一），无新代码，本机即验，先做。
> **P1 是硬闸升级**（复用现成 hook 共骑 pre-commit）：在 bridgeforge 自身**恒 no-op**（无 `.claude/rules/`、无双份下游结构），正确性**需下游模拟 dry-run 实测**，不能只看自身绿灯。
> **P2 是新建软信号 hook**（误伤近零、本机可立即自验），含新逻辑，依赖 P0 文本 + P1 骨架就位后做。

| id | 标题 | 层 | depends_on | 本机可验? |
|----|------|----|-----------|-----------|
| **P0-1** | 镜像补齐 `.claude/hooks/`（清 dogfood 欠账） | repo（自身配置层） | — | ✅ SessionStart 挂载无异常即验 |
| **P0-2** | D9 确认零改动 + 元数据标注订正 | meta | — | ✅ |
| **P0-3** | `templates/CLAUDE.md` + `debugging.md` 多处文本改 | product | — | ✅ 人眼审 |
| **P0-3b** | `context_warning.py` instruction 软化（配套 P0-3） | product(both) | — | ✅ hook 输出即验 |
| **P0-4** | 鬼打墙阈值统一 ≥3（**解 E-3**） | product + memory | — | ✅ 人眼审 |
| **P0-5** | `settings.json` deny/ask 查漏 + CHANGELOG 明示 | product(both) | — | ✅ 触发弹窗验 |
| **P1-6** | D6 规则闸升 pre-commit（size 读 staged blob / index 读工作树 + F3/F4） | product(both) | P0-1 | ⚠️ 自身 no-op，需下游实测 |
| **P1-7** | D8 新建 `mirror_drift_check.py` 镜像闸（缺文件 exit2 / 正文软提示） | product(both) | P0-1, P1-6 | 部分(缺文件段可自验) |
| **P2-8** | D5-M3 `memory_rebuild_index.py --from-hook` 加 `[memory-write]` 行 | product(both) | P0-1 | ✅ 当轮可见 |
| **P2-9** | D3-M1 新建 `fallback_smell_check.py`（仅裸吞异常） | product(both) | P0-1, P0-3 | ✅ 改一处 rule 即触发 |
| **P2-10** | D4-M4 新建 `stall_warning.py`（多特征合取 + 降级弱提醒） | product(both) | P0-1, P0-3 | ✅ 自身可触发观察 |
| **P2-11** | D1-M2 新建 `test_receipt.py`（先 dump payload 验 exit code 可取） | product(both) | P0-1 | ✅ 跑测试命令验 |

> P1-6 是 P1-7 的紧前置（P1-7 会追加 pre-commit 段，需 P1-6 的 rule 闸骨架已在）。P1-7 启 exit 2 前必须紧贴一道「提交前重验零缺文件」守卫（见工单）。

---

## 【逐工单全文】

---

### P0-1 · 镜像补齐 `.claude/hooks/`（清偿 dogfood 欠账）

- **目标**：把自身层缺失的 4 个 hook 从 `templates/hooks/` 镜像进 `.claude/hooks/`，让后续 D6/D8 pre-commit 闸调用时不空跑、承诺可验。
- **文件**：
  - 补入 `.claude/hooks/`：`show_state.py`、`rule_index_check.py`、`memory_lint.py`、`find_doc_reminder.py`
  - 对齐正文（如有漂移）：`.claude/hooks/clarify_reminder.py`、`context_warning.py`、`requirements_check.py`
  - `.claude/settings.json`：补注册上述 hook（SessionStart 挂 show_state.py，其余按 templates/settings.json 对应触发点）
- **步骤**：
  1. 逐个从 `templates/hooks/<name>.py` 复制到 `.claude/hooks/<name>.py`。
  2. **改命令前缀**：`.claude/settings.json` 用系统 `python`（非 `.venv/Scripts/python.exe`）。
  3. 核对已存在的 clarify/context_warning/requirements_check 正文与 templates 是否逐字一致（仅 python 前缀例外），有漂移就对齐。
- **dogfood**：本工单本身就是 dogfood 补齐动作。
- **preflight**：Grep/Glob 确认 `.claude/hooks/` 当前确实缺这 4 个（设计文档 D6-F1、D5-M4、§5.8 依据）。
- **验收**：`.claude/hooks/` 存在这 4 个文件；`.claude/settings.json` 已注册；SessionStart 触发时 hook 挂载无异常报错。`show_state.py` 能在开场吐 `[snapshot]` 提示（若有 snapshot）。
- **层与 bump**：改的是自身配置层 `.claude/` → `[repo]` 标签，**不 bump `templates/VERSION`**（产品层未变，只是自身补装）。
- **风险**：低。纯复制 + 前缀替换。注意 `rule_index_check.py` 在自身**恒 no-op**（无 `.claude/rules/`），其路径自门控须能干净 exit 0（P1-6 会依赖此点）。

---

### P0-2 · D9 确认零改动 + 元数据标注订正

- **目标**：确认 D9（人机沟通）维无需任何产品层改动；顺手订正设计内的 cosmetic 元数据标注。
- **文件**：无代码改动。若要落订正，仅涉设计文档自身元数据（三条统一标 `skill/advisory` + layer 标 `user-global`）。
- **步骤**：确认 D9 三条沟通 pref 归用户级全局 CLAUDE.md（软、自觉），不进 `templates/`。无 hook、无产品改动。
- **dogfood**：不适用。
- **验收**：确认无 `templates/` / `skills/` 变更即可。
- **层与 bump**：meta，无 bump。
- **风险**：无。

---

### P0-3 · `templates/CLAUDE.md` + `debugging.md` 多处文本改

- **目标**：一次性落齐所有零风险文本红线（保守权重、方案替换类、N7 大偏离必先说、顺手改必告知、上下文软化、收据红线含假验证澄清、lvl1 rules-based 优先、verbalized-uncertainty）。
- **文件**：`templates/CLAUDE.md`、`templates/rules/debugging.md`
- **步骤**（逐条，改完人眼审）：
  1. **§9.5（D2-M1）**：在中性正文前加保守权重一句——「**真·新的/大而模糊需求 → 默认先问（此处别做歪>别烦，拿不准就问）；仅琐碎/续接/已说全细节才免问**」。与「评估类只给结论收口」**分行强调**，不冲淡。`clarify_reminder.py` 文案**保持中性不动**。
  2. **§9.6（D1-M5）**：**增第五类「方案替换」**（定义：任务目标不变但实现路径/技术选型/数据结构被换掉），归入「大偏离」。
  3. **CLAUDE §9 落 N7 明文红线（D1-M5）**：换实现方案 / 扩缩范围前，先一句话告知「原打算 X，现改走 Y，因为 Z」，等确认或至少显式声明后再动手。focus 仅继续管话题漂移。
  4. **CLAUDE §9 顺手改必告知（D3-M2 质红线）**：任何非用户本次点名的顺手改动——哪怕只碰 1-2 文件、不触量阈值——都必须响应里一句话「顺带改了 X，因为 Y」，绝不静默夹带。
  5. **§10 软化（D5-M2）**：CRITICAL「立即拒绝/即使说快做也拒绝」→「开头告知用量 + 强烈建议先 `/snapshot` 换会话；决定权交用户」；HIGH「禁止启动」→「建议拆小，用户坚持则说明风险后继续」。（`anti_drift_hooks.md §3` 经核无硬措辞，**不改**。）
  6. **§2.5 收据红线（D1-M3）**：把收据口诀升为明文红线——「交付/危险处的结论（改了什么/验证通过/某资源存在）必须贴真实工具返回原文当证据；引不到=显式标未验证或说不知道；琐碎处免」。**补假验证澄清**：「测试 exit 0 ≠ 验证有效——声称『验证通过』须同时说清验了什么断言、覆盖哪条路径，不得拿一个绿色退出码冒充结论」。
  7. **§8 lvl1（D7-M2）**：加共性红线「rules-based 验证（lint/类型/单测）> LLM-judge（只作补充不作唯一裁决）」，让 debate 转 collab 后统一适用。
  8. **`debugging.md §3`（D3-M3）**：补 verbalized-uncertainty 措辞——根因未确认时须显式标假说置信度%（<50% 直说不确定），禁把低置信假说包装成结论下手。
  9. **`debugging.md §5`（D3-M2 量闸）**：加一条——交付前若单次改动 > N 文件或 > M 行，响应里必须贴 `git diff --stat` 并逐文件说明为何非改不可；并补 Q11 顺手改告知红线（与 CLAUDE §9 第 4 步呼应）。
- **dogfood**：`templates/CLAUDE.md` 是**纯下游产品层规则**；bridgeforge 自身 CLAUDE.md 在仓库根（是「工厂四问」文件，不携带 §9.5/§9.6）→ **豁免 dogfood**（无处可镜像，非「只管 hooks」）。`debugging.md` 同属 `templates/rules/`，自身无 `.claude/rules/`，同样无镜像目标。
- **preflight**：Read `templates/CLAUDE.md` 与 `templates/rules/debugging.md` 定位各 §；确认 §9.5/§9.6/§10/§2.5/§8 与 debugging §3/§5 现有措辞。
- **验收**：各 § 措辞按上述落地；`clarify_reminder.py` REMINDER 文案未动；`anti_drift_hooks.md` 未动。人眼审通过。
- **层与 bump**：product → bump `templates/VERSION` + `[product]` CHANGELOG。
- **风险**：低（纯文本）。注意别把保守权重写成硬拦口吻（D2 全维软，硬闸会误伤每轮）。

---

### P0-3b · `context_warning.py` instruction 软化（配套 P0-3，防 hook↔文档自相矛盾）

- **目标**：把 `context_warning.py` 注入的 instruction 字符串与 P0-3 的 CLAUDE §10 软化对齐。否则文档说“建议”、hook 仍注入“必须立即拒绝”，自相矛盾。（D5-M1；本条原独立工单在生成时失败被漏，此处补回。）
- **文件**：`templates/hooks/context_warning.py`（instruction 字符串，约 L118-137）+ dogfood 镜像 `.claude/hooks/context_warning.py`
- **步骤**：
  1. 改 instruction 字符串：CRITICAL「必须立即拒绝任务」→「强烈建议先 `/snapshot` 再 `/resume`；用户坚持可继续，提示状态可能被 compact 吞」；HIGH「拒绝任何复杂多文件改动」→「建议拆小或换会话」。**hook 判定逻辑/阈值一字不动**，只改注入文案。
  2. 与 P0-3 的 CLAUDE §10 文字保持措辞一致（都是“建议 + 决定权交用户”）。
- **dogfood**：改 `templates/hooks/context_warning.py` → 当场镜像 `.claude/hooks/context_warning.py`（前缀差异按约定；P0-1 已把两边正文对齐，改完两边仍须逐字一致，否则 P1-7 mirror 闸报漂移）。
- **preflight**：Read `context_warning.py` 定位 instruction 字符串（约 L118-137）。
- **验收**：hook 输出的 CRITICAL/HIGH 文案为“建议 / 交用户决定”口吻；与 CLAUDE §10 一致；hook 阈值逻辑未动；两处逐字一致。
- **层与 bump**：product(both) → bump `templates/VERSION` + `[product]` CHANGELOG。
- **风险**：低（纯文案）。坑：别动判定阈值；改完必镜像自身。

---

### P0-4 · 鬼打墙阈值统一 ≥3（**顺带解决 E-3**）

- **目标**：消除 §8(写3) 与 debugging §6 T1(写≥2) 的阈值冲突，统一到 ≥3；**T2 独立信号轴保持不动**。
- **文件**：`templates/rules/debugging.md`、memory `ghost-wall-threshold-conflict.md`
- **步骤**：
  1. 改 `debugging.md §6 T1`「连续改代码 ≥2 次」→「≥3 次（第 4 次禁动手，阈值以 CLAUDE §8 为准）」；加权威 pointer「计数唯一权威=CLAUDE §8」。**CLAUDE §8 不动**。
  2. **T2（用户回报还错的次数）是独立信号轴，绝不跟着抬**——否则「用户已说两次还错」却不触发升级，反放松更该敏感的信号。pointer 只对 T1/T6 写「以 §8 为准」。
  3. 更新 memory `ghost-wall-threshold-conflict.md` 为**已收口**状态。
- **dogfood**：`debugging.md` 属 `templates/rules/`，无自身镜像目标。
- **preflight**：Read `debugging.md §6` 确认 T1/T2/T6 现措辞；确认 CLAUDE §8 写的是 3。
- **验收**：debugging §6 T1 = ≥3 且带 pointer；T2 未改；CLAUDE §8 未改；memory 标已收口。
- **层与 bump**：product（debugging）+ memory → bump `templates/VERSION` + `[product]` CHANGELOG；memory 更新属 `[repo]`。
- **风险**：低。**唯一坑**是误把 T2 一起抬（设计文档批评③明确禁止）。

---

### P0-5 · `settings.json` deny/ask 查漏补齐 + CHANGELOG 明示（**顺带解决 E-3 相关的危险动作硬闸承诺**）

> 说明：E-3 的核心（阈值统一）在 P0-4；本工单落 D1-M1 的危险动作 PreToolUse 硬闸清单，属同批低风险文本/配置。

- **目标**：把 `settings.json` permissions.deny/ask 三段式查漏补齐，并在 CHANGELOG 明示这套 deny 清单是产品层承诺。
- **文件**：`templates/settings.json`、`.claude/settings.json`（dogfood 镜像）、`CHANGELOG.md`
- **步骤**：
  1. 核对 deny 段硬拦覆盖：`rm -rf/-r`、`git reset --hard/clean`、`push --force/--delete`、`npm/cargo publish`、`twine upload`、`gh release`、`docker push`、`Remove-Item`。缺项补齐。
  2. 核对 ask 段拦 push/rebase/reset/checkout/merge。缺项补齐。
  3. CHANGELOG 明示：这套 deny/ask 清单是**产品层承诺**（下游继承的危险动作 PreToolUse 硬闸）。
- **dogfood**：改 `templates/settings.json` → **当场镜像 `.claude/settings.json`**（permissions 段逐字对齐；此段无 python 前缀差异）。
- **preflight**：Read 两处 settings.json 的 permissions 块，比对缺漏。
- **验收**：deny/ask 清单齐全且两处一致；CHANGELOG 有条目明示产品层承诺。可选：本机触发一条 deny 命令确认弹窗/拦截生效。
- **层与 bump**：product(both) → bump `templates/VERSION` + `[product]` CHANGELOG。
- **风险**：低。permissions 是纯声明式配置。

---

### P1-6 · D6 规则闸升 pre-commit（**自身 no-op，需下游实测**）

- **目标**：把 `rule_size_check`/`rule_index_check` 从 PostToolUse advisory 升级为 pre-commit 硬拦（exit 2），并按读法分治 + 修 F3/F4。
- **文件**：`templates/hooks/rule_size_check.py`、`templates/hooks/rule_index_check.py`、`templates/.githooks/pre-commit`、`.githooks/pre-commit`（镜像）、`templates/rules/meta_rule_design.md`；对应 `.claude/hooks/` 镜像。
- **步骤**：
  1. **rule_size_check.py**：抽检测为 `check_rule(content, name)->violations`；pre-commit 分支对 `git diff --cached --name-only` 命中 `.claude/rules/*.md`（**排除 meta_rule_design.md**）的 staged 文件，用 **`git show :path` 读 staged blob** 跑 `check_rule`（单文件自洽、staged 精确、把「工作树脏改没 stage」误伤降到零）。违规→stderr 列清单 + **exit 2**。保留 PostToolUse 版做编辑瞬间软提醒（双层同一 `check_rule`）。
  2. **rule_index_check.py（F3 读法分治）**：**读工作树**（非 staged）——本检查是「CLAUDE.md 索引 ↔ 整个 rules 目录」的跨文件集合一致性比对，纯 staged 会漏「只 stage CLAUDE.md、rule 文件工作树增删没 stage」的死链。**注释显式声明局限**「按工作树判断、部分暂存可能误报」。missing/unlisted 非空→exit 2，错误信息给「去 CLAUDE.md §2 增/删哪一行」。
  3. **F4 正则放宽**：索引正则 `rules/([a-z_]+\.md)` → `rules/([\w-]+\.md)`（两侧同规则），避免 `gateway-v2.md` 恒判 unlisted 误伤。
  4. **F2 自门控 no-op**：`rule_index_check` 在自身无 `.claude/rules/` 时**直接 exit 0**（不空跑不误报）。
  5. **pre-commit 分支（M1+M2 共用扫描分支）**：`rule_size` 读 staged blob、`rule_index` 读工作树；**try 兜底**——只有明确判出违规才 exit 2，脚本自身异常（python 缺失/读失败/编码错）一律 exit 0 放行（宁漏不误伤）。豁免走 **CHANGELOG 顶部 `[skip-rule-size]`**（脚本读 `git show :CHANGELOG.md` 顶部当条判断，**非** commit message——pre-commit 在 message 生成前触发）。
  6. **执行序**：rule 闸段置于 memory 段之前（见 §2.1）。两处 pre-commit（`templates/.githooks/` + 自身 `.githooks/`）**逐字镜像**。
  7. **文档同步（M4）**：改 `meta_rule_design.md §5/§6.4/§8`——「只提醒不阻塞」→「PostToolUse 软提醒 + pre-commit 硬拦（`[skip-rule-size]` 可豁免）」；§8 self-check「【hook 已自动查】」→「【pre-commit 硬拦】」。
- **dogfood**：改 `templates/hooks/*.py` 与 `templates/.githooks/pre-commit` → 镜像 `.claude/hooks/` + `.githooks/pre-commit`（templates 用 `.venv/Scripts/python.exe`，自身用系统 `python`）。**F1 前置**：P0-1 已把 `rule_index_check.py` 镜像进 `.claude/hooks/`，否则自身 pre-commit 调不存在文件、闸永久空跑。
- **preflight**：
  - 确认 `.claude/hooks/rule_index_check.py` 已在（P0-1 产物）。
  - 实测 `git show :path` / `git ls-files -s` 本机可行（设计 F3 已核可行）。
  - **下游模拟 dry-run**：临时造一个 `.claude/rules/` 目录 + 一条超标 rule + CLAUDE.md 索引，stage 后跑 pre-commit，**确认真能 exit 2**；再验 `[skip-rule-size]` 豁免真放行。验完清理临时目录。
- **验收**：
  - 自身跑 pre-commit：无 `.claude/rules/` → rule 闸 no-op exit 0，脚本无异常。
  - 下游模拟：超标/死链/漏索引 → exit 2 且 stderr 给可执行修复信息；`[skip-rule-size]` → 放行；脚本异常 → exit 0。
  - 两处 pre-commit 逐字一致（仅 python 前缀例外）。
  - `meta_rule_design.md` 文档硬度描述已同步。
- **层与 bump**：product(both) → bump `templates/VERSION` + `[product]` CHANGELOG（`[product]`）；按 §1 第 4 问注明「D6 闸在 bridgeforge 自身 no-op（无 `.claude/rules/`），仍挂上验证产品承诺」。
- **风险**：中。**本机不可自验真实拦截**（自身 no-op），F3/F4 正确性**只能人眼审 + 下游模拟 dry-run**。坑点：豁免语法必须走 CHANGELOG 顶部（commit message 在 pre-commit 阶段还没写）；rule 闸段必须在末行 exit 0 之前。

---

### P1-7 · D8 新建 `mirror_drift_check.py` 镜像闸（缺文件 exit2 / 正文差异软提示）

- **目标**：新建 dogfood 镜像漂移比对脚本，pre-commit 追加调用。**缺文件 → exit 2 硬拦**（二值确定、近零误伤）；**正文差异 → 只 stderr 软提示不拦**（避免合法差异误伤，踩 framework 否 C1 坑）。
- **文件**：新建 `templates/hooks/mirror_drift_check.py` + 镜像 `.claude/hooks/mirror_drift_check.py`；改 `templates/.githooks/pre-commit` + `.githooks/pre-commit`；改 `templates/rules/portability.md §5`、`templates/CLAUDE.md §1.4`、`templates/hooks/config_health_check.py`、`templates/hooks/githooks_path_check.py`（均含 dogfood 镜像）。
- **步骤**：
  1. **新建 `mirror_drift_check.py`**，三态判据：
     - **无 `templates/hooks/` 目录（下游）→ 自门控 no-op exit 0**。
     - **缺文件**（templates/hooks/ 有某 `.py` 但 `.claude/hooks/` 无对应）→ **exit 2**（列缺失清单到 stderr）。
     - **正文差异**（把 `.venv/Scripts/python.exe ↔ python/python3` 前缀归一化后逐字比对，不一致）→ 只 stderr 报「hook 正文疑似漂移，请核对」，**放行**（用 `skill_sync_check.py` 的 `dir_content_hash` 仅生成软提示）。
     - **豁免**：读 `git show :CHANGELOG.md` 顶部当条是否含 `[dogfood-exempt: <hook> <因>]`（CHANGELOG 提交时已 staged，可靠可得；**非** commit message）。
  2. **pre-commit（硬伤2 约束）**：mirror 段**置最前**（先于任何 exit 0），写成 `python mirror_drift_check.py; rc=$?; [ "$rc" = 2 ] && exit 2`；正文差异段只回显 stderr 不改 rc，落下去继续跑 rule 闸(P1-6)与 memory 段。
  3. **★ 紧前置守卫（批评⑪，启 exit 2 前必做）**：**紧贴一道现场 dry-run「提交前重验零缺文件」**——现场再跑一遍比对确认此刻无缺文件漂移，**不依赖「P0-1 早已补齐、中间隔了 P1-6 若干次提交仍无新漂移」的假设**。若 dry-run 报缺文件，**先补齐再启闸**。
  4. **M2 换机自愈**：微调 `githooks_path_check.py` 提示文案从「重建 memory 索引的闸」泛化为「提交前闸（含 memory 索引 + dogfood 镜像）」。mirror 闸挂进 pre-commit 后天然继承 SessionStart 的 core.hooksPath 自愈。
  5. **M3 开机知晓**：在 `config_health_check.py`（SessionStart 只读体检）DELEGATED 表登记一行 `hooks-mirror-intact → mirror_drift_check.py (pre-commit)`。**不在 SessionStart 亲测**（避免与 pre-commit 双重刷屏）。
  6. **M4 红线文本**：`portability.md §5` 加红线——templates/hooks/*.py 与 .claude/hooks/*.py 必须**文件齐全**（仅 python 前缀例外的正文差异属软提示），缺失由 mirror_drift_check 机检硬拦，硬拦豁免须 CHANGELOG 顶部 `[dogfood-exempt: <hook> <因>]` + 一行 Why 指针（memory `feedback-dogfood-hook-gap`）。**订正2**：本 repo 无 `.claude/rules/`，portability.md 改动只落 templates 一处，删掉「本 repo .claude/rules/ 同步」的空指针注记。CLAUDE §1.4 补一句指向硬闸。
- **dogfood**：新建 hook + 改 pre-commit + 改 config_health_check/githooks_path_check → 全部镜像 `.claude/`（缺文件段自身可验、正文差异段自身可验；**订正1**：下沉目录是 `templates/.githooks/` 点开头隐藏，pre-commit 文件已存在，改的是「追加 mirror 段」非新建）。
- **preflight**：
  - 确认 P0-1 已补齐 4 个缺失 hook（否则本闸第一次提交自拦）。
  - dump/核对 `skill_sync_check.py` 的 `dir_content_hash` 可复用。
  - **紧前置守卫 dry-run**：现场跑一遍确认零缺文件漂移。
- **验收**：
  - 无 `templates/hooks/` → no-op exit 0。
  - 人为删一个 `.claude/hooks/*.py` 制造缺文件 → pre-commit exit 2 且 stderr 列清单；`[dogfood-exempt]` → 放行。
  - 人为改一处正文（非 python 前缀）→ stderr 软提示但放行（exit 0）。
  - mirror 段在末行 exit 0 之前、且在 rule 闸之前；两处 pre-commit 逐字一致。
  - config_health_check DELEGATED 表有登记行；githooks_path_check 文案已泛化。
- **层与 bump**：product(both) → bump `templates/VERSION` + `[product]` CHANGELOG（`[product]`）。
- **风险**：中。硬伤点：豁免走 CHANGELOG 顶部（非 commit message）；exit 2 必须置于末行 exit 0 之前防被吞；启 exit 2 前的紧前置 dry-run 不可省（否则自拦窗口）。正文差异降软后的漏防已知（残余风险9，靠 config_health_check 软登记兜底）。

---

### P2-8 · D5-M3 `memory_rebuild_index.py --from-hook` 追加 `[memory-write]` 行

- **目标**：memory 写入后**当轮可见**地报一行提醒，兑现「memory 主动写 + 当场报」透明承诺。
- **文件**：`templates/hooks/memory_rebuild_index.py`（或其在 `.claude/scripts/` 的对应）+ dogfood 镜像；确认 `templates/settings.json` / `.claude/settings.json` 的 PostToolUse(Edit|Write) 注册已在（settings 178-186 / 189-197）。
- **步骤**：
  1. 在 **`--from-hook` 分支**里、`hook_should_run()` 判定为 memory 写入且重建完成处，向 stdout **追加一行纯 ASCII** `[memory-write] wrote <file>; revert via git`（**纯 ASCII 防 GBK 上 utf8-garble 糊成 U+FFFD**）。
  2. **绝不接** `allow_memory_write.py`（PreToolUse 放行闸、只吐 permissionDecision、回注不进 context）；**更不接** pre-commit 的 `memory_rebuild_index.py`（commit 时才跑、当轮 LLM 已结束、看不到）。只有 **PostToolUse `--from-hook` 当轮可见**。
- **dogfood**：改 `templates/` 侧脚本 → 镜像自身（前缀差异按约定）。
- **preflight**：Read `memory_rebuild_index.py` 的 `--from-hook` 分支与 `hook_should_run()`；确认 PostToolUse 注册在 settings.json 已存在。
- **验收**：在自身 repo 触发一次 memory 写入（Edit/Write memory 文件），当轮 context 出现纯 ASCII `[memory-write]` 行，无乱码。
- **层与 bump**：product(both) → bump + `[product]` CHANGELOG。
- **风险**：低（追加一行）。坑：必须纯 ASCII；必须在 `--from-hook` 分支而非其他触发路径。

---

### P2-9 · D3-M1 新建 `fallback_smell_check.py`（仅裸吞异常）

- **目标**：PostToolUse 软 hook，只抓「裸吞异常」这一类近零合法用途的坏味道，命中吐 `[fallback-smell]` 提醒（exit 0 非阻塞）。
- **文件**：新建 `templates/hooks/fallback_smell_check.py` + 镜像 `.claude/hooks/`；两处 settings.json PostToolUse(Edit|Write) 块各加一行注册。
- **步骤**：
  1. 复用 `requirements_check.py` 的 stdin/env 双兜底 + 自门控骨架。
  2. 只扫 `tool_input.new_string` 的**新增行**，正则**只命中「裸 `except: pass` / `except Exception: pass` 吞异常」**（语言无关、跨 Python/JS `catch{}` 通用、几乎无正当用途）。
  3. **首版明确删掉**：`.get(k,default)` / `or []` / `?? x` / Rust `unwrap_or` / `?`（合法默认值/惯用法，误报源）与「显式 `#兜底` 注释」（自证诚实、不该罚）。
  4. 命中打印 `[fallback-smell]` 提醒，**exit 0 非阻塞**。非 Edit/Write 或无命中自门控 no-op。
- **dogfood**：新建 hook → 镜像 `.claude/hooks/` + 两处 settings.json 各加注册行 + bump + `[product]` CHANGELOG（D3-M4 明列）。
- **preflight**：Read `requirements_check.py` 借骨架；确认 settings.json PostToolUse 块格式。
- **验收**：改一处 rule/代码文件写入含 `except: pass` → 触发 `[fallback-smell]`；写入合法 `.get(k, default)` → 不触发（无误报）；exit 0 不阻塞写入。
- **层与 bump**：product(both) → bump + `[product]` CHANGELOG。
- **风险**：低。残余风险6：即便收窄仍可能脱敏刷屏 → 后续可再收窄或撤下。坑：别把合法默认值/惯用法/诚实注释纳入正则（设计批评③明列）。

---

### P2-10 · D4-M4 新建 `stall_warning.py`（多特征合取 + 降级弱提醒）

- **目标**：UserPromptSubmit 软 hook，检测空转（长 thinking 无产出），吐 `[stall]` **弱事后提醒**（非实时刹车）。兑现 framework §7 残余风险2「长会话衰减→节流信号 hook」预留。
- **文件**：新建 `templates/hooks/stall_warning.py` + 镜像；两处 settings.json UserPromptSubmit 注册；`templates/CLAUDE.md §10` 加 `[stall]` 响应节。
- **步骤**：
  1. 复用 `context_warning.py` 的 transcript 倒查 + tail-read 骨架，**新增多轮遍历 + `message.content[]` 里 `type=='tool_use'` block 扫描**（这是新逻辑，非「仅换判据」——诚实标注实现量）。
  2. **判据 = 多特征合取**（批评⑧，去抖救不了主力误报）：须同时满足
     - (a) 最近 ≥2 轮高 output_tokens 且**零 tool_use**；
     - (b) 这几轮之间**用户未插入任何新指令**（纯模型自驱空转，排除「用户连发几条让它连写几轮」的合法场景）；
     - (c) thinking token 占 output 比例偏高（**有 reasoning 元数据时取；取不到则跳过此特征、只用 a+b**）。
  3. **定位降级为「只在明显场景弱提醒」**——达不到全部可得特征就不 fire，宁漏不烦。
  4. **CLAUDE §10 邻位加 `[stall]` 响应节**，**写明**：本信号是**事后代理提醒（非实时刹车）**——空转发生在单个 assistant 轮内（thinking 期 LLM 被 SUSPENDED），UserPromptSubmit 只在下一轮触发，作用是让下一轮尽快收口；**已知对合法长思考轮（连续写 rule/doc）无区分力**；Opus 4.8 无硬开关、概率遵守、不保证根治（Q5 已知情）。
  5. **T2 轴不受影响**（本 hook 与 debugging T2 独立）。
- **dogfood**：新建 hook → 镜像 + 两处 settings.json 注册 + CLAUDE §10（§10 是产品层文本，随 templates 下沉；bridgeforge 自身根 CLAUDE.md 不携带 §10 → 该文本改豁免 dogfood，hook 本身照常镜像）。
- **preflight**：Read `context_warning.py` 的 transcript 倒查 / `read_last_usage` 骨架，确认需改遍历多条 + 加 content-block 扫描；确认 transcript 里 reasoning 元数据是否可得（不可得则 (c) 跳过）。
- **验收**：自身 repo 连续几轮纯写文档无 tool_use 且无用户插指令 → 观察是否 fire（应保守、明显才 fire）；用户连发指令让连写几轮 → 不 fire（特征 b 排除）；CLAUDE §10 有 `[stall]` 节且写明事后代理/无区分力/不保证根治。
- **层与 bump**：product(both) → bump + `[product]` CHANGELOG。
- **风险**：中（新逻辑 + 高误报领域）。残余风险4：结构性滞后（事后非实时）+ 对合法长思考无区分力已诚实放弃「去抖解决误报」。坑：别宣称「仅复用换判据」（实为新逻辑）；(c) 特征取不到时必须优雅降级只用 a+b。

---

### P2-11 · D1-M2 新建 `test_receipt.py`（先 dump payload 验 exit code 可取）

- **目标**：PostToolUse(Bash) 软 hook，测试类命令跑完抓真实 exit 码 + 命令指纹 + 时间戳写收据，声称「测试通过」时可对账。
- **文件**：新建 `templates/hooks/test_receipt.py` + 镜像；两处 settings.json PostToolUse(Bash) 注册。收据落 `.runtime/test_receipts/`。
- **步骤**：
  1. **落地前先 dump 一次 PostToolUse payload**，确认 Bash exit code 在 `tool_response` 里**可取**（拿不到则从文本反解，脆——需评估是否降级整条 M2）。**这一步是本工单的硬前置，不确认不写主体**。
  2. 命令匹配 `pytest\|cargo test\|npm test\|go test\|tsc\|make` 时，抓真实 exit 码 + **命令指纹 + 时间戳**写入 `.runtime/test_receipts/` 一行收据；非测试命令自门控 no-op。
  3. 配 CLAUDE 红线（已在 P0-3 §2.5 落）：声称「测试通过」须指到**命令签名匹配且在本轮时间窗内**的 exit==0 收据（**防旧收据钓鱼**），指不到=按编造处理。
  4. **明确覆盖边界（写进注释/CHANGELOG）**：收据只证「命令真跑了且退出码为 0」，**不证「验证内容本身有效」**——exit 0 但断言写错/漏断言的假验证收据照样盖章，属残余风险（§5.2）。
- **dogfood**：新建 hook → 镜像 + 两处 settings.json 注册。
- **preflight**：**dump PostToolUse payload 确认 exit code 可取**（残余风险7 明列硬前置）；确认 `.runtime/test_receipts/` 目录策略。
- **验收**：跑一条 `pytest`（或 `make`）→ `.runtime/test_receipts/` 生成一行含 exit 码/指纹/时间戳的收据；非测试命令 → 无收据(no-op)；旧收据不落在本轮时间窗内 → 声称对账查不到。
- **层与 bump**：product(both) → bump + `[product]` CHANGELOG。
- **风险**：中。**继承 C2「硬卡死失明」缺陷**（残余风险7）——命令真卡死不返回则 PostToolUse 不触发、收据不写，此时声称「测试通过」反被判编造（误伤方向）或模型放弃声称（漏防方向），已记账。payload 可取性是硬前置，拿不到需改文本反解或降级。

---

## 【顺带解决映射】

- **P0-4 → 解 E-3**：鬼打墙计数阈值统一到 ≥3（debugging §6 T1 的 ≥2 抬齐 CLAUDE §8 的 3，T2 独立轴保持不动），收口 `ghost-wall-threshold-conflict` memory 记录的冲突。
- **P1-7 → 解 E-6**：enforce dogfood 镜像——CLAUDE §2 承诺的镜像漂移检查做成 pre-commit 硬闸（缺文件 exit 2、正文差异软提示），缺的补装或走 CHANGELOG 顶部 `[dogfood-exempt]` 注明豁免。

---

相关文件锚点（全绝对路径）：
- 设计源（先读）：`d:/Quant/BridgeForge/doc/3_design/harness-engineering-design.md`
- 权威偏好：`d:/Quant/BridgeForge/.claude/memory/harness-preferences.md`
- 既有框架：`d:/Quant/BridgeForge/doc/3_design/antifabrication-framework.md`
- pre-commit 底座：`d:/Quant/BridgeForge/.githooks/pre-commit`、`d:/Quant/BridgeForge/templates/.githooks/pre-commit`
- 待镜像补齐（P0-1）：`d:/Quant/BridgeForge/.claude/hooks/`（缺 show_state.py / rule_index_check.py / memory_lint.py / find_doc_reminder.py）
- 复用骨架：`templates/hooks/context_warning.py`（stall）、`requirements_check.py`（fallback_smell）、`skill_sync_check.py`（mirror_drift 的 dir_content_hash）、`version_check.py`（exit2+skip 逃生舱范式）、`show_state.py`（snapshot 提示已实现）
- rule 读法：`templates/hooks/rule_size_check.py`（改读 staged blob）、`templates/hooks/rule_index_check.py`（保留工作树；正则 `[a-z_]`→`[\w-]`）