# bridgeforge harness 正式设计文档 · 九维系统方案（v1）

> 版本：v1（2026-07-01）｜依据：`harness-preferences.md`（19 问 + 宪法原则，权威）+ 9 维已复核设计（含 verify 修正）+ `docs/antifabrication-framework.md`（既有四层框架）+ 对抗式批评 11 项 + 事实核查结论
> 定位：本文是**可直接照着开工**的实现蓝图。所有 verify 打回/降级项与对抗式批评项均已按结论修正并融进正文，凡与仓库现状对不上的地方均已订正。v0.1→v1 的逐条修订记录见 §6。

---

## 0. 北极星 + 宪法原则（立纲）

**北极星 N1 = 可靠**：输出敢信、不用逐条核。其余（省心/合心意/扛大活）排后但不弃。

**贯穿宪法（用户 19 问自证一致，本文所有取舍的唯一裁决基准）**：

> **硬闸只给「机器能一眼判死的事实」——真相 / 危险动作 / 产品健康，且近零误伤；软的留给「用户自己的判断」——上下文预算 / 沟通 / 节奏。总体看轻重：大事/危险/交付处严（甚至硬拦），琐碎处放手别烦。唯「澄清」与「根因」两处比纯看轻重更严（质量>速度）。**

由此推出三条工程铁律，贯穿全文：
1. **只认铁证**：硬闸判据只能是 `git diff --cached` / 文件存在性 / exit 码 / 字节数行数正则计数这类确定性事实，**绝不引入 LLM-judge**。凡「可能误伤」的判据不得当 exit-2 硬闸（这正是 framework 否 C1 的坑）。这一条也是解开「Q2 硬闸优先 × Q3 下沉全下游」张力的钥匙（确定性对账既硬又近零误伤 → 可安全下沉）。
2. **少而精、复用优先**：硬闸尽量共骑 `.githooks/pre-commit`（version_check 同款范式），软信号复用现有 reminder hook 家族（context_warning 骨架）。非必要不新建。
3. **下沉即 dogfood**：产品层 `templates/` 改动必须当场镜像自身 `.claude/`（CLAUDE.md §1 第 4 问红线），命令前缀 templates 用 `.venv/Scripts/python.exe`、自身用系统 `python`。

---

## 1. 九维设计（逐维：偏好 → 命中方法 → 落地机制）

### D1 · 可靠交付真实（谎报 / 编造 / 假验证 / 危险动作）

**用户偏好**：N2 四类信任杀手全防；谎报→交付时确定性对账（铁证）；编造/假验证→结论必附证据（分级）；危险动作→分级（不可逆必停确认、碰核心看影响面即放行）；跑偏→大偏离才报，且**方向性/换方案必须先说**（N7）。Q4「只认铁证」。

**命中的外部方法**：B 类 state/outcome-based grading（查 git 终态不信「已完成」）、require-evidence-not-assertion、tool receipts（运行时收据）、PreToolUse deny 不可绕过；A 类带引证核验 + 无引证撤回 + 逃生舱 + verbalized uncertainty。

**落地机制（硬闸留 PreToolUse 层 + 提交期对账留 D8；本维不往 pre-commit 加对账段）**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 | 层 |
|---|--------|------|------|-----------|----|
| M1 | 不可逆危险动作（删/覆盖/外发上线） | **复用** `settings.json` permissions.deny/ask 三段式（已 dogfood）：deny 段硬拦 `rm -rf/-r`、`git reset --hard/clean`、`push --force/--delete`、`npm/cargo publish`、`twine upload`、`gh release`、`docker push`、`Remove-Item`；ask 段拦 push/rebase/reset/checkout/merge。本维只**查漏补齐** + CHANGELOG 明示这套 deny 清单是产品层承诺 | **hard-gate**（PreToolUse 层真硬闸） | reuse-existing | both |
| M2 | 谎称「测试/命令跑通」 | **新建**软 hook `test_receipt.py`（PostToolUse on Bash）：命令匹配 `pytest\|cargo test\|npm test\|go test\|tsc\|make` 时抓真实 exit 码 + **命令指纹 + 时间戳**写入 `.runtime/test_receipts/` 一行收据；非测试命令自门控 no-op。配 CLAUDE 红线：声称「测试通过」须指到**命令签名匹配且在本轮时间窗内**的 exit==0 收据（防旧收据钓鱼），指不到=按编造处理。**明确覆盖边界（见 M3 与 §5.2）**：收据只证「命令真跑了且退出码为 0」，**不证「验证内容本身有效」**——exit 0 但断言写错/漏断言的假验证，收据照样盖章，属残余风险 | soft-signal | new-build | both |
| M3 | 编造(A 类) + 假验证 + 谎称「已改/已删/已同步」 | **不新建 hook**。复用常驻 rule `anti_fabrication.md` R1–R5，在 `templates/CLAUDE.md §2.5` 收据口诀升为明文红线：**交付/危险处的结论（改了什么/验证通过/某资源存在）必须贴真实工具返回原文当证据；引不到=显式标未验证或说不知道；琐碎处免**。特别补一句针对**假验证**：「测试 exit 0 ≠ 验证有效——声称『验证通过』须同时说清验了什么断言、覆盖哪条路径，不得拿一个绿色退出码冒充结论」 | rule | reuse-existing | both |
| M4 | 碰核心（改架构/核心 path） | **不硬拦**（合 N5「看影响面即放行」）。复用 `clarify_reminder`/`focus_reminder` 软信号 + CLAUDE 红线：改核心 path 前先摆影响面。version_check 已硬拦「改产品层不 bump」，碰核心的「先摆影响面」保持软 | soft-signal | reuse-existing | both |
| M5 | 悄悄跑偏（**擅自换实现方案** / 扩范围） | **落明文红线，不再挂空 focus**。`focus_reminder.py` 的锚是「本会话首条实质 prompt」、四分类判的是**话题漂移**，**同一任务内换实现方案不改话题、锚不动、focus 永不 fire**——旧设计挂 focus 是空指针。改法两步：① `templates/CLAUDE.md §9.6` **增第五类「方案替换」**（定义：任务目标不变但实现路径/技术选型/数据结构被换掉），归入「大偏离」；② 落一条 CLAUDE 明文红线 **N7「大偏离必先说」**：换实现方案 / 扩缩范围前，先一句话告知用户「原打算 X，现改走 Y，因为 Z」，等确认或至少显式声明后再动手。focus 仅继续管话题漂移，不再假装能抓方案替换 | rule | modify-existing（§9.6 加类 + N7 红线） | both |

> **★ 设计要点（P1/P4 + 批评①②）**：原设计想把「dogfood 镜像漂移对账 + CHANGELOG 未同 staged」塞进 pre-commit 并 exit 2，**已否决**——这两条都不是「机器一眼判死」（分两次提交是合法节奏、补 typo 不动 CHANGELOG 合法），升 exit 2 会误伤，正踩 framework 否 C1 的覆辙。pre-commit 保持纯卫生闸；D1 的谎报硬闸能力实际由 **D8 的 dogfood 镜像闸**（真机检项）+ **M3 收据红线**（软兜）承接，D1 自身不再往 pre-commit 加对账段。CHANGELOG 对账整条**砍掉**（与 `version_check.py` 覆盖重叠）。**假验证盲区**（M2 收据对「exit 0 但验证无效」失明）已在 M2 边界 + M3 红线 + §5.2 三处显式点破，不把收据吹成防假验证。

---

### D2 · 澄清与范围（接活前）

**用户偏好**：Q8 大而模糊的新活「尽量先问」（比看轻重更保守，别做歪>别烦），限真·新的/大而模糊，琐碎/续接不问；Q9 岔路分类处理。宪法：澄清属「用户判断（沟通/节奏）」→ **全维软、无硬闸**（「大不大/该不该问」是纯语义，硬闸会误伤每轮）。

**命中的外部方法**：逃生舱（允许说「需求不清」）、verbalized uncertainty；poka-yoke（gate 词表调到难误触）。

**落地机制（全软，核心工程结论=D2 不新建任何 hook）**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | 大而模糊需求零思考直接开干 | **改 `templates/CLAUDE.md §9.5` 措辞**（hook 逻辑一字不改）：在中性正文前加保守权重一句——「**真·新的/大而模糊需求 → 默认先问（此处别做歪>别烦，拿不准就问）；仅琐碎/续接/已说全细节才免问**」。与「评估类只给结论收口」**分行强调**，不冲淡 | soft-signal | modify-existing（仅 §9.5 正文） |
| M2 | clarify 提醒准头（该出没出/乱出） | 沿用 `clarify_reminder.py` 三层负向 gate，仅 `CONTINUATION_TOKENS` 词表按需增删（调参入口，非结构改） | soft-signal | reuse-existing |
| M3 | 干活中岔路不分类闷头展开 | 沿用 `focus_reminder.py` + CLAUDE §9.6 四分类（现扩为含「方案替换」五分类，见 D1-M5）+ `/spinoff` `/todo` `/focus`。Q9 = 现有 focus 模型 | soft-signal | reuse-existing |
| M4 | 防第三个 UserPromptSubmit 探针叠成噪声墙 | **显式否决**为 D2 新建 hook，全部诉求靠已注册的 clarify+focus 承接 | — | reuse-existing |

> **★ 设计要点（F1/F3）**：① `.claude/CLAUDE.md` **不存在**（bridgeforge 自身 CLAUDE.md 在仓库根，是「工厂四问」文件，不携带 §9.5/§9.6）——§9.5 是纯下游产品层规则，上游自用无镜像目标，故此改**豁免 dogfood**（理由是「无处可镜像」，非「§1 第 4 问只管 hooks」）。② `clarify_reminder.py` 的 REMINDER 文案**保持中性不动**，保守权重只落 §9.5 正文，避免双头维护漂移。

---

### D3 · 方法纪律（根因优先 + 改动克制）

**用户偏好**：Q10 修 bug 必先找根因、禁先加兜底/fallback/模糊匹配掩盖（比看轻重更严，质量>速度）；Q11 改动克制看情况（危险/核心处外科手术、**边角顺手理但必须告诉用户**）。宪法：方法纪律本质是 thinking 质量→无铁证→主体软，只有极少留下文本痕迹的坏味道可机检。

**命中的外部方法**：可执行错误信息（兜底=把真报错吞成假成功的反面靶）、PostToolUse 事后校验注回 context、rules-based verification > LLM-judge；Chain-of-Verification、verbalized uncertainty。

**落地机制（只抓「裸吞异常」这一类近零合法用途的坏味道 + 补齐 Q11 顺手改告知红线）**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | 兜底/fallback 掩盖根因 | **新建**软 hook `fallback_smell_check.py`（PostToolUse on Edit\|Write，复用 `requirements_check.py` 的 stdin/env 双兜底 + 自门控骨架）：只扫 `tool_input.new_string` 的**新增行**，正则**只命中「裸 `except: pass` / `except Exception: pass` 吞异常」**这一类语言无关、近零合法用途的高置信坏味道。**首版明确删掉** `.get(k,default)`/`or []`/`?? x`/Rust `unwrap_or`/`?`（合法默认值/惯用法，误报源）与「显式 `#兜底` 注释」（自证诚实、不该罚）。命中打印 `[fallback-smell]` 提醒。**exit 0 非阻塞** | soft-signal | **new-build** |
| M2 | 改动克制·外科手术（改动面过大 + **边角顺手改告知**） | **不新建 hook**。① `debugging.md §5` 加一条：交付前若单次改动 > N 文件或 > M 行，响应里必须贴 `git diff --stat` 并逐文件说明为何非改不可；② **补 Q11 顺手改红线**（`debugging.md §5` 与 `templates/CLAUDE.md §9`）：**任何顺手改动——哪怕只碰 1-2 文件、不触发上面的量阈值——只要不是用户本次点名要改的，就必须在响应里主动一句话告知「顺带改了 X，因为 Y」**，绝不静默夹带；③ `.githooks/pre-commit` 加一段**纯 stderr 提示给用户看**（非注回 context——pre-commit 阶段 LLM 已结束），默认阈值 **>8 文件 或 >400 行**（对齐 rule_size 量级感），注明「大重构正当超标可无视」。用纯 git+shell 计数，无需 python | soft-signal | reuse-existing |
| M3 | 根因本身（追踪调用链→确认再动手） | **纯 rule 强化**，不加机关（诚实标注此层无机检抓手，硬做=假验证 AUROC<0.65）。`debugging.md §3` 补 verbalized-uncertainty 措辞：根因未确认时须显式标假说置信度%（<50% 直说不确定），禁把低置信假说包装成结论下手 | rule | modify-existing |
| M4 | dogfood 一致性 | 落 `fallback_smell_check.py` 时同步镜像 `.claude/hooks/`、两处 settings.json PostToolUse 块各加一行、bump `templates/VERSION` + `[product]` CHANGELOG | rule | reuse-existing |

> **★ 设计要点（F1/F2/F3 + 批评③）**：原设计正则同时扫「显式 `#兜底` 注释 + `or None`/`??`」——**抓错人**（罚诚实作者、漏静默兜底），且 `or default` 是高误报源却仍写进清单（自相矛盾）。已收窄到**仅裸吞异常**（跨 Python/JS `catch{}` 通用、几乎无正当用途），天然规避 Rust 惯用法与合法默认值。M2 补齐了 Q11「边角顺手改必须主动告知」这个**质**的红线——旧设计只有「>N 文件贴 diff」的量闸，漏了小范围顺手改（不触阈值却正是该告知的场景）。M2 的 scope-reminder 受众是**人**不是模型，措辞不蹭 PostToolUse「注回 context」论述。

---

### D4 · 失败处置（鬼打墙 / 停手先问 / 空转）

**用户偏好**：Q12 试 3 次再停、第 4 次硬停（★ 解 E-3：阈值统一到 3，debugging §6 的 ≥2 改齐）；Q13 停手先问（停+列已试方案+问用户，> 自动派外援）；Q5 空转找代理信号做软提醒（非硬闸，复用 context_warning 读 usage 机制）。

**命中的外部方法**：verification hierarchy 先停再验、require-evidence-not-assertion（列已试方案=贴证据）、PostToolUse 注回 context（受 SUSPENDED 约束退化到 UserPromptSubmit）。此外 **D4-M4 stall 直接兑现 `antifabrication-framework.md §7 残余风险 2` 早已预留的「长会话衰减 → 仿 focus 上『攒够轮数才注入』的节流信号 hook」**，非凭空新增（对齐见 §3）。

**落地机制**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | 鬼打墙阈值两处冲突（§8 写 3、debugging §6 T1 写 ≥2） | **改 `debugging.md §6 T1`**「连续改代码 ≥2 次」→「≥3 次（第 4 次禁动手，阈值以 CLAUDE §8 为准）」；加权威 pointer「计数唯一权威=CLAUDE §8」。CLAUDE §8 不动。更新 `ghost-wall-threshold-conflict` memory 为已收口 | rule | modify-existing |
| M2 | 第 4 次硬停 | **维持软红线不新建 hook**（计数无 file/git/exit 铁证、内部状态、硬 hook 无法区分「第 4 次真失败」vs「正当新子步骤」→ 宪法判留软）。CLAUDE §8「禁用新思路豁免第 4 次」保持 | soft-signal | reuse-existing |
| M3 | 停手后动作（列已试 N 方案 + 问用户） | **不新建**。`escalate` skill 已实现「选 A 优先/停手先问/列已试方案表」（Step1-2）。仅确认阈值统一后 debugging §6 Step2 触发口径（≥3）与之一致 | skill | reuse-existing |
| M4 | 空转（长 thinking 无产出） | **新建**软 hook `stall_warning.py`（挂 UserPromptSubmit，与 context_warning 同触发点，兑现 framework §7 预留）：**复用 context_warning 的 transcript 倒查 + tail-read 骨架，新增多轮遍历 + content-block 扫描**（检测最近 N 条 assistant 高 output_tokens 且无 tool_use block）→ 输出 `[stall]` 软提醒。**判据加强 + 降级弱提醒，见下方要点**。CLAUDE §10 邻位加 `[stall]` 响应节 | soft-signal | **new-build** |

> **★ 设计要点（②③④ + 批评④⑧）**：
> - **② 复用被夸大**：`read_last_usage` 返回单 int、遇首条 assistant 即 return——检测「多轮高 output 且无 tool_use」需**改遍历多条 + 新增 `message.content[]` 里 `type=='tool_use'` block 扫描**，是新逻辑，实现量诚实标注，别宣称「仅换判据」。
> - **③ 阈值轴混淆（必修）**：T1（同一 bug 连续改代码次数）与 §8 是同一计数轴，抬到 ≥3 正确；但 **T2（用户回报还错的次数）是独立信号轴，不要跟着抬**——否则「用户已说两次还错」却不触发升级，反而放松了更该敏感的信号。pointer 只对 T1/T6 写「以 §8 为准」。
> - **④ stall 时机滞后（必写进文案）**：空转发生在单个 assistant 轮内（thinking 期 LLM 被 SUSPENDED），UserPromptSubmit 只在下一轮触发 → 本信号是**事后代理提醒（非实时刹车）**，作用是让下一轮尽快收口。CLAUDE §10 那节须写明，避免用户误以为能当轮刹住。
> - **⑧ 去抖救不了主力误报（诚实改判据 + 降级）**：本 repo「连续多轮写 rule/doc 无 tool_use」是**最常见的合法长思考**，「≥2 轮去抖」对这个主力误报场景**几乎不设防**——去抖并不能分开真假空转，旧设计把它当解法是乐观断言。**改法**：① 判据从「单看高 output+无 tool_use」加强为**多特征合取**——须同时满足 (a) 最近 ≥2 轮高 output_tokens 且零 tool_use、**(b) 这几轮之间用户未插入任何新指令**（纯模型自驱空转，排除「用户连发几条让它连写几轮」的合法场景）、(c) thinking token 占 output 比例偏高（有 reasoning 元数据时取；取不到则跳过此特征、只用 a+b）；② **定位降级为「只在明显场景弱提醒」**——达不到全部可得特征就不 fire，宁漏不烦。文案明确标注：本信号是**弱事后提醒、已知对合法长思考轮无区分力**，Opus 4.8 无硬开关、概率遵守、不保证根治（Q5 已知情）。

---

### D5 · 跨会话状态 & 知识

**用户偏好**：Q14 memory 主动写+当场报（高自主+透明）；Q15 上下文预算只提醒不拦（★ 反着硬闸偏好，软化现 §10 CRITICAL）；snapshot 自动。宪法：三件事全落「用户判断」侧 → **整维软、无新硬闸**。

**落地机制**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | 上下文将满时现行为过硬 | **改 `context_warning.py`**（instruction 字符串，约 L118-137）：CRITICAL「必须立即拒绝任务」→「强烈建议先 `/snapshot` 再 `/resume`；用户坚持可继续，提示状态可能被 compact 吞」；HIGH「拒绝任何复杂多文件改动」→「建议拆小或换会话」。信号仍每轮注入，只是不再命令拒活 | soft-signal | modify-existing |
| M2 | CLAUDE.md §10 散文层同样硬 | **改 `templates/CLAUDE.md §10`**：「立即拒绝/即使说快做也拒绝」→「开头告知用量+强烈建议先 `/snapshot` 换会话；决定权交用户」；HIGH「禁止启动」→「建议拆小，用户坚持则说明风险后继续」。`anti_drift_hooks.md §3` 经核**无硬措辞，无需改** | soft-signal | modify-existing |
| M3 | memory「当场报」无信号承载 | **接正确 hook = PostToolUse 的 `memory_rebuild_index.py --from-hook`**（`settings.json` PostToolUse / matcher=Edit\|Write，脚本在 `.claude/scripts/`，写入**之后**触发、LLM 恢复时注回当轮 context）。在其 `--from-hook` 分支里、`hook_should_run()` 判定为 memory 写入且重建完成处，向 stdout **追加一行纯 ASCII 提醒** `[memory-write] wrote <file>; revert via git`（纯 ASCII 防 GBK 上 utf8-garble 糊成 U+FFFD）。**绝不接 `allow_memory_write.py`**（那是 PreToolUse 放行闸、写入前触发、只能吐 `permissionDecision`、回注不进 context），**更不接 pre-commit 的 `memory_rebuild_index.py`**（commit 时才跑、当轮 LLM 早已结束、看不到）| soft-signal | modify-existing（在既有 PostToolUse hook 的 --from-hook 分支加一行） |
| M4 | snapshot 存了但开场无感知 | **降级为纯 dogfood 补齐，零新代码**：`templates/hooks/show_state.py`（L61-70 `_latest_snapshot()`）**已完整实现** `[snapshot]` 提示且已在 `templates/settings.json` SessionStart 注册——产品层早已兑现 resume/SKILL.md L104 承诺。真正 gap 只在自身：`.claude/hooks/` **缺 show_state.py**。改法=把它镜像进 `.claude/hooks/` + `.claude/settings.json` SessionStart 注册（dev 仓用系统 python） | soft-signal | **reuse-existing（dogfood 补齐）** |

> **★ 设计要点（致命 + 批评⑤ + 事实核查）**：① 原设计称 snapshot 提示 hook「尚未实现、需 new-build 约 25 行」——**已证伪**，产品层早有 `show_state.py`，new-build 是重复造轮子（违少而精），M4 降级为一次 dogfood 镜像。② memory「当场报」的落点经三处证据交叉确认是 **PostToolUse 的 `memory_rebuild_index.py --from-hook`**：该脚本挂三处（PostToolUse --from-hook 当轮可见 / SessionStart 无参兜底下个 session / pre-commit 提交时），**只有 PostToolUse --from-hook 当轮可见**。旧设计把提醒并入「pre-commit 的 rebuild 脚本」技术上跑不通（当轮看不到）；批评③曾建议改接 `allow_memory_write.py`，但核查证实那是 **PreToolUse 放行闸、只能吐 permissionDecision、回注不进 context**，同样不行——故本 v1 采信核查的第三选项：直接在已挂 PostToolUse 且门控精确的 `memory_rebuild_index.py --from-hook` 里追加一行 ASCII 提醒，改动最小。落地按工厂红线双镜像（templates 用 `.venv/Scripts/python.exe`、自身 `.claude` 用系统 python，逐字对齐）。③ **顺带核对**：`memory_lint.py`/`rule_index_check.py`/`find_doc_reminder.py` 同样只在 templates 不在 `.claude/`（经典 dogfood 欠账），落地时一并补齐。

---

### D6 · 知识治理（规则肿 / 死链 / 漂移）

**用户偏好**：Q16 自动盯+硬拦——规则超标 pre-commit 阻断（规则肿/死链/漂移是「机器可判死的事实（产品健康）」→ 硬闸安全，不与 Q15 矛盾）。现有 `rule_size_check`（当前只提醒非阻塞）应升级为 pre-commit 硬拦。

**命中的外部方法**：PreToolUse deny 不可绕过、rules-based verification（lint/schema，最可靠层）、state/outcome-based grading（查 staged 终态）、ground truth from environment、可执行错误信息（报应改什么而非裸报错）。

**落地机制（本维含真硬闸，但须先补 dogfood 欠账 + 加固误伤面；两条 hook 的 staged 读法按各自耦合度分治）**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | 规则肿（超 50KB/500 行/戳数/长 code 块/伪常驻触发器） | 抽 `rule_size_check.py` 检测为 `check_rule(content, name)->violations`，`.githooks/pre-commit` 新增分支：对 `git diff --cached --name-only` 命中 `.claude/rules/*.md`（排除 meta_rule_design.md）的 staged 文件，**用 `git show :path` 读 staged blob 内容**跑 check_rule（单文件自洽检查、无跨文件耦合，staged 版精确命中「这次真要提交的内容」、把「工作树脏改没 stage」的误伤降到零）。违规→stderr 列清单 + **exit 2**。保留 PostToolUse 版做编辑瞬间软提醒（双层同一 check_rule）。commit message 通道不可行（见 D8 硬伤 1），豁免走 **CHANGELOG 顶部 `[skip-rule-size]`** | **hard-gate** | modify-existing |
| M2 | 死链/漂移（索引列了文件不存在 / 文件有索引没列） | 同款升级 `rule_index_check.py` 走 pre-commit，但**读法取「以工作树为准 + 注释显式声明局限 + `[skip-rule-size]` 兜底」，不纯 staged**：本检查本质是「CLAUDE.md 索引 ↔ 整个 rules 目录」的**集合一致性比对（跨多文件）**，纯 staged 只能看到 diff 子集，会漏「只 stage 了 CLAUDE.md、rule 文件在工作树已增删但没 stage」的死链/未索引；严谨 staged 版要对 CLAUDE.md 用 `git show :CLAUDE.md`、对 rules 用 `git ls-files -s` 枚举 index 全量，复杂度陡增收益有限。故以工作树为准（部分暂存少见，死链/漏索引本就该拦），注释声明「按工作树判断、部分暂存可能误报」。missing/unlisted 非空→exit 2，错误信息给「去 CLAUDE.md §2 增/删哪一行」。与 M1 共用同一 pre-commit rules 扫描分支 | **hard-gate** | modify-existing |
| M3 | pre-commit 多闸并存健壮性 | rule 闸段**包 try 兜底**：只有明确判出违规才 exit 2；脚本自身异常（python 缺失/读失败/编码错）一律 exit 0 放行（宁漏不误伤）。顺序见 §2.1 | **hard-gate** | modify-existing |
| M4 | meta_rule_design.md 文档与新硬度同步 | 改 §5/§6.4/§8：「只提醒不阻塞」→「PostToolUse 软提醒 + pre-commit 硬拦（[skip-rule-size] 可豁免）」；§8 self-check「【hook 已自动查】」→「【pre-commit 硬拦】」 | rule | modify-existing |

> **★ 设计要点（F1–F4 + 批评⑨ + 事实核查，落地前必做）**：
> - **F1（阻断级）**：`.claude/hooks/` **缺 `rule_index_check.py`**（只有 rule_size_check.py）。自身层 pre-commit 会调到不存在的文件——**先把 rule_index_check.py 镜像进 `.claude/hooks/`**，否则自身层这道闸永久空跑、承诺未验证。
> - **F2（必写进 gap 描述）**：bridgeforge 自身**无 `.claude/rules/` 目录**、rule 全在 `templates/rules/`——本闸在自身**恒为 no-op**。dogfood 价值仅在验证脚本无异常挂载，真实拦截只发生在下游 clone 出的项目。**index_check 的路径自门控要能干净 no-op**（自身无 `.claude/rules/` 时直接 exit 0，不空跑不误报）。CHANGELOG 按 §1 第 4 问「对 bridgeforge 不适用但仍挂上验证产品承诺」注明。
> - **F3（读法分治，据事实核查）**：staged blob 读法在本机实测可行（`git show :path` / `git ls-files -s` 均 OK，无 blocker）。据此**分两条**：`rule_size_check`→**读 staged blob**（单文件自洽，真正近零误伤）；`rule_index_check`→**保留工作树 + 注释局限 + `[skip-rule-size]` 兜底**（跨目录集合比对，纯 staged 反而更易漏判/误判部分暂存场景）。二者不强求同一读法。
> - **F4（升硬闸前修）**：索引正则 `rules/([a-z_]+\.md)` 只认全小写下划线，遇 `gateway-v2.md` 恒判 unlisted 误伤。升硬闸前放宽到 `rules/([\w-]+\.md)`（两侧同规则），或对不匹配惯例的文件名降级放行。

---

### D7 · 协作模式（多 agent 编排）

**用户偏好**：Q17 大活才叫（大/复杂/要彻底才派多 agent，日常单干）= 现有 lvl0 默认 + 自动升级。宪法：起不起多 agent = 节奏/轻重判断 → 软；本维唯一该硬的点是「多 agent 产出的验收真实性」（对齐 N2④假验证）。

**落地机制**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | 起不起多 agent | **维持现状**：CLAUDE §8 升级阶梯（lvl0 单干默认，三类硬触发器才升级）+ collab/debate 轻量出口。零缺口，确认无需改动 | soft-signal | reuse-existing |
| M2 | 多 agent 产出验收真实性 | **不新建 hook**。collab Step6 已有独立 review 硬纪律（L96）。把「rules-based 验证（lint/类型/单测）> LLM-judge（只作补充不作唯一裁决）」一句共性红线从 collab Step6 上提进 `templates/CLAUDE.md §8` lvl1，让 debate 转 collab 后统一适用。真正铁证对账靠 D8 提交期镜像闸 + D6 规则闸，本维不重复造。诚实标注：「review 是否真跑」无文件痕迹→只能 rule 硬度 | rule | modify-existing |
| M3 | skill 自身健康度（死链/超长） | **登记需求，暂不可机检**。搭 D6 便车：待 D6 落地「体积扫描升 pre-commit 阻塞」+「**新建** SKILL.md 死链扫描」后，把 collab/debate SKILL.md 纳入扫描范围（扩 glob 到 skills/**）。junction 单一源在 D 盘，扫一处 | （依赖 D6 前置）hard-gate | reuse-existing |

> **★ 设计要点（constitution_ok=false → 修正标注）**：M3 支撑能力**当前不存在**——`rule_size_check.py` 是 PostToolUse advisory（exit 0）**且完全无死链检查**（死链在 rule_index_check.py，只扫 CLAUDE.md 索引、**不扫 SKILL.md**）。故 M3 须**显式声明依赖 D6 两项前置**：(1) 体积扫描升 pre-commit 阻塞，(2) **新建** SKILL.md 死链扫描（净新增工程，非「扩 glob」那么轻）。前置未落地前 M3 记为「登记、暂不成立」。

---

### D8 · 卫生 & 可移植（dogfood 漂移 / 换机崩）

**用户偏好**：Q18 dogfood 漂移/换机崩→机器可判硬拦（★ E-6：enforce 镜像——CLAUDE §2 承诺的镜像漂移检查做成 pre-commit 硬闸，缺的补装或 CHANGELOG 注明豁免）。宪法：dogfood 漂移属「产品健康 + 机器可判死」→ 硬闸侧无争议，**但仅限「缺文件」这类二值确定项；正文差异不当硬闸**（见下）。

**命中的外部方法**：确定性对账（花名册闸同款，零 LLM）、state/outcome-based grading（文件在不在）、rules-based verification（内容哈希比对做**提示**非做拦）、poka-yoke（换机自愈）。

**落地机制（本维承接 D1 想做而 pre-commit 不宜承载的「谎称已同步」硬闸——因为「文件缺没缺」才是真「机器判死」项；正文差异降级为软提示）**：

| # | 关注点 | 机制 | 硬软 | 新建/复用 |
|---|--------|------|------|-----------|
| M1 | dogfood 镜像漂移（实测已漂：`.claude/hooks/` 缺 memory_lint/rule_index_check/show_state/find_doc_reminder 4 个 + 若干正文不一致） | **新建** `mirror_drift_check.py` 比对脚本，由 `.githooks/pre-commit` 追加调用。**判据分级（据 fc:dogfood-diff）**：① **缺文件 → exit 2 硬拦**（templates/hooks/ 有某 .py 但 .claude/hooks/ 无对应——二值确定、近零误伤）；② **正文差异 → 只列 stderr 软提示，不 exit 2**（把 `.venv/Scripts/python.exe ↔ python/python3` 前缀归一化后逐字比对，不一致就 stderr 报「hook 正文疑似漂移，请核对」，**但放行**）。原因：dogfood 允许的合法差异不止 python 前缀（路径分隔、注释里 dev/下游措辞等），只要有一处合法差异未被归一化规则覆盖，「正文逐字一致」当 exit-2 就是硬停误伤（踩 framework 否 C1 的坑）；且文档「鸡生蛋」现象本身自证正文对账边界模糊到需人肉预清。比对手法复用 `skill_sync_check.py` 的 `dir_content_hash`（仅用于生成软提示）。**自门控**：无 `templates/hooks/` 目录（下游）即 no-op exit 0 | **hard-gate（仅缺文件）+ soft-signal（正文差异）** | **new-build** |
| M2 | 换机 core.hooksPath 丢失致闸静默失效 | **复用现成** `githooks_path_check.py`（SessionStart 已自愈 core.hooksPath）——mirror 闸挂进 pre-commit 后天然继承换机自愈。仅微调其提示文案从「重建 memory 索引的闸」泛化为「提交前闸（含 memory 索引 + dogfood 镜像）」 | hard-gate | reuse-existing |
| M3 | 开机知晓 + 非提交路径软兜底 | **不新建 hook**。在 `config_health_check.py`（SessionStart 只读体检）DELEGATED 表登记一行 `hooks-mirror-intact → mirror_drift_check.py (pre-commit)`，维持单一事实源。**不在 SessionStart 亲测**（避免与 pre-commit 双重刷屏）| soft-signal | modify-existing |
| M4 | 红线文本落地 | `templates/rules/portability.md §5` 加一条红线：templates/hooks/*.py 与 .claude/hooks/*.py 必须**文件齐全**（仅 python 前缀例外的正文差异属软提示），缺失由 mirror_drift_check 机检硬拦，硬拦豁免须 **CHANGELOG 顶部 `[dogfood-exempt: <hook> <因>]`** + 一行 Why 指针（memory feedback-dogfood-hook-gap）。CLAUDE §1.4 补一句指向硬闸 | rule | modify-existing |

> **★ 设计要点（硬伤 1/2 + 订正 1/2 + 批评④⑧⑪，落地前必做）**：
> - **硬伤 1（豁免语法在 pre-commit 阶段不可行）**：pre-commit 在 commit message 生成**之前**触发，`.git/COMMIT_EDITMSG` 尚未写入 → commit-message 豁免死在起跑线。**唯一路径 = 脚本读 `git show :CHANGELOG.md` 顶部当条是否含 `[dogfood-exempt: <hook> <因>]`**（CHANGELOG 提交时已 staged、可靠可得），与 CLAUDE §1.4「CHANGELOG 注明豁免」天然对齐。同理 D6 的 `[skip-rule-size]` 也走 CHANGELOG 顶部而非 commit message。
> - **硬伤 2（exit 2 被末行 exit 0 吞掉）**：现 pre-commit 以 `exit 0` 收尾。mirror「缺文件」段必须**置于 memory 段之前**，写成 `python mirror_drift_check.py; rc=$?; [ "$rc" = 2 ] && exit 2`（缺文件即刻 exit 2，正文差异段只回显 stderr 不改 rc，落下去继续跑）。脚本三态：无 templates/hooks/→exit 0；缺文件→exit 2；仅正文差异或全一致→exit 0（差异走 stderr）。
> - **订正 1**：下沉目录是 `templates/.githooks/`（点开头隐藏），**非** `templates/githooks/`；该 pre-commit 文件已存在且与自身逐字一致——改的是「往已存在文件追加 mirror 段」，非新建。
> - **订正 2**：本 repo **无 `.claude/rules/` 目录**，portability.md 改动只落 templates 一处，删掉「本 repo .claude/rules/ 同步」的空指针注记。
> - **鸡生蛋 + 提交前重验（批评⑪，见路线图 P1-7 紧前置守卫）**：落地本身要先修掉现存漂移（补齐 4 个缺失 hook + 对齐正文），否则新闸第一次提交自拦。**启 exit 2 前，紧贴一道「提交前 dry-run 重验零缺文件」守卫**——不依赖「P0 早已补齐、中间隔了若干次提交仍无新漂移」的假设。

---

### D9 · 人机沟通

**用户偏好**：Q19 沟通风格不硬化、保持软靠自觉、不加机关。沟通 prefs 归用户级全局 CLAUDE.md，不进产品 templates。

**落地机制（全软、零新增、无改动）**：

| # | 关注点 | 机制 | 硬软 | 层 | 新建/复用 |
|---|--------|------|------|----|-----------|
| M1 | 回复语言一致（禁漂日/英） | 不新建。沿用用户级全局 CLAUDE.md「简体中文、禁整轮漂移」软指令 | skill/advisory | user-global | reuse-existing |
| M2 | 信息投喂节奏（别一次倒一堆） | 不新建。沿用全局「一项一项来」软指令 | skill/advisory | user-global | reuse-existing |
| M3 | 白话解释 + 主动配类比 | 不新建。沿用全局「用白话、主动配类比」软指令 | skill/advisory | user-global | reuse-existing |

> **★ 设计要点（cosmetic 元数据）**：① 三条统一标 `skill/advisory`（原 M2 误标 soft-signal——soft-signal 在本 repo 特指 hook 主动注入的 `[...]` 信号，而这几条无任何 hook）；② layer 应标 **user-global**（用户级全局既非产品层也非 repo 自身 `.claude/`，属三层模型之外的「用户级共性」，portability.md:59 已列）。

---

## 2. 全局机制清单（硬闸/软信号归拢）

### 2.1 硬闸家族 —— 共骑一条 `.githooks/pre-commit`（少而精的核心体现）

commit 那一刻，`.githooks/pre-commit` 一次跑完所有确定性对账，各维一个自门控函数、分节隔离：

```
pre-commit 执行序（严格顺序，硬伤2 约束）：
  1. [D8] mirror_drift_check.py     → 缺文件即 exit 2（置最前，先于任何 exit 0）；
                                       正文差异只走 stderr 提示、不改退出码
  2. [D6] rule 闸（rule_size 读 staged blob + rule_index 读工作树，共用扫描分支）
                                     → 超标/死链/漏索引 exit 2，脚本异常一律 exit 0
  3. [既有] memory 索引重建         → 卫生段，永 exit 0 兜底
  收尾 exit 0
```

> **★ 已删除错列项（批评⑦）**：旧版本执行序把「version_check 覆盖的 bump 对账」列为 pre-commit 一步——**事实错误**。`version_check.py` 注册在 **PreToolUse**（templates/settings.json），`.githooks/pre-commit` 里**根本没有 version_check**，两者在两个不同触发层。已从执行序删除，消除与本节末「注意」段的自相矛盾。

**为什么能共骑一条**：谎报对账（dogfood 缺文件）/ 规则肿 / 死链，判据全是 `git diff --cached` / 文件存在性 / `git show :path` 内容 / 字节行数正则计数——同一物理来源（git 终态 + 磁盘），一次 staged 扫描即可分派给各维函数。**唯一 exit 非 0 的地方集中在 rule 闸 + mirror 缺文件闸**，且严格「只在确定性违规时 exit 2、脚本自身异常一律 exit 0」，防质量闸退化成误伤源。

**换机自愈**：`githooks_path_check.py`（SessionStart）自愈 `core.hooksPath` → 所有 pre-commit 闸 clone 即生效，不依赖人工记忆。

**注意（PreToolUse 层另有两道硬闸，不在 pre-commit 内）**：`settings.json` permissions.deny/ask（D1-M1）走 **PreToolUse** 层拦不可逆危险动作（拦动手前的 `rm`/`push`）；`version_check`（改产品层不 bump）也走 **PreToolUse**。**硬闸别下沉进 pre-commit 的教训（D1 P4）**：所有「机器判死」硬拦优先走 PreToolUse Bash hook（exit 2 只拦 Claude Code 发起的动作，不影响 IDE/CLI 手动提交，blast radius 可控）；pre-commit 只承载「提交快照本身的结构对账」这类无法在工具边界拦的项（dogfood 缺文件 / 规则结构）。

### 2.2 软信号家族 —— reminder hook 复用

| Hook | 触发点 | 信号 | 维 |
|------|--------|------|----|
| `clarify_reminder.py` | UserPromptSubmit | `[clarify]` | D2 |
| `focus_reminder.py` | UserPromptSubmit | `[focus]` | D2/D1 |
| `context_warning.py` | UserPromptSubmit | `[ctx-budget]`（软化后） | D5 |
| `stall_warning.py` ⭐新建 | UserPromptSubmit | `[stall]`（弱事后提醒） | D4 |
| `test_receipt.py` ⭐新建 | PostToolUse(Bash) | 写收据，声称时可查 | D1 |
| `fallback_smell_check.py` ⭐新建 | PostToolUse(Edit\|Write) | `[fallback-smell]`（仅裸吞异常） | D3 |
| `memory_rebuild_index.py --from-hook`（改，脚本在 `.claude/scripts/`） | PostToolUse(Edit\|Write) | 追加一行 ASCII `[memory-write]`（当轮可见） | D5 |
| `mirror_drift_check.py` ⭐新建（正文差异段） | pre-commit（stderr） | 正文疑似漂移提示（不拦） | D8 |

> `memory_rebuild_index.py --from-hook` 是 **PostToolUse hook**（写入后触发、当轮可见），**区别于同名的 pre-commit 脚本**（commit 时才跑、当轮不可见）——「当场报」只能挂前者。

### 2.3 汇总：新建 / 改 / 复用（各标层）

**新建（3 个 hook + 1 个脚本，全属 both 层，需 dogfood 镜像）**：
- `test_receipt.py`（D1，软，PostToolUse Bash）
- `fallback_smell_check.py`（D3，软，PostToolUse Edit\|Write，仅裸吞异常）
- `stall_warning.py`（D4，软，UserPromptSubmit，含多轮遍历+content-block 扫描+多特征合取判据）
- `mirror_drift_check.py`（D8，缺文件硬/正文差异软，pre-commit 调用）

**改（modify-existing）**：
- `templates/CLAUDE.md`：§9.5（D2 保守权重）、§9.6 增「方案替换」类 + N7「大偏离必先说」红线（D1-M5）、§9 顺手改必告知红线（D3-M2）、§10 软化（D5）、§2.5→明文收据红线含假验证澄清（D1-M3）、§8 lvl1 加「rules-based>LLM-judge」（D7-M2）、§1.4 补硬闸指针（D8-M4）
- `context_warning.py` instruction 字符串（D5，both）
- `rule_size_check.py`（抽 check_rule + pre-commit 读 staged blob + exit 2）/ `rule_index_check.py`（抽检测 + pre-commit 读工作树 + exit 2 + 正则放宽 F4）（D6，both）
- `memory_rebuild_index.py`：`--from-hook` 分支追加一行 ASCII `[memory-write]`（D5-M3，both）
- `.githooks/pre-commit` + `templates/.githooks/pre-commit`：追加 mirror 段（缺文件 exit2 / 正文差异 stderr）+ rule 闸段（D6/D8，both，逐字同步）
- `debugging.md`：§6 T1 阈值 ≥3（**T2 不动**）、§3 verbalized-uncertainty、§5 改动面自证 + 顺手改告知（D3/D4）
- `meta_rule_design.md` §5/§6.4/§8（D6-M4）
- `portability.md` §5 加镜像红线（D8-M4）
- `config_health_check.py` DELEGATED 表登记一行（D8-M3）
- `githooks_path_check.py` 提示文案泛化（D8-M2）

**复用/dogfood 补齐（零新代码）**：
- `settings.json` permissions.deny/ask 查漏 + CHANGELOG 明示（D1-M1）
- 镜像进 `.claude/hooks/`：**show_state.py、rule_index_check.py、memory_lint.py、find_doc_reminder.py**（清偿 dogfood 欠账，D5/D6）
- `escalate`/`collab`/`focus_reminder`/`clarify_reminder`（逻辑不动）

---

## 3. 与 antifabrication-framework 的对齐 / 翻案

framework 当年把 C1(L4 deny) / C2(超时哨兵) / Stop(甩锅自检) 三 hook 刻意留在 docs/examples、**不进产品层**，理由：C1「hint 恒空≈啰嗦 FileNotFoundError + 误伤是硬停」；C2「hint 恒空 + 硬卡死失明 + 与 C3 重叠」；Stop「每回合 LLM-judge 贵 + 文字判定难」。

**逐条结论**：

| framework 既有决策 | 本设计 | 判定 |
|--------------------|--------|------|
| **C3 = R1–R5 红线进产品层** | 全盘保留，D1-M3 复用 `anti_fabrication.md` R1–R5，只加「交付处结论必附工具返回证据 + 假验证澄清」明文收据红线 | **对齐保留** |
| **C1（L4 deny 不进产品层）** | 未激活、未翻案。D1 的 A 类纯文字幻觉明确不加 hook，完全遵从 framework §7「L3 只能事前约束、任何 hook 看不见」 | **对齐保留** |
| **C2（超时哨兵降 docs）** | 未翻案。D1-M2 `test_receipt.py` 挂 PostToolUse on Bash，**继承 C2 同一「硬卡死失明」缺陷**（命令真卡死不返回则 PostToolUse 不触发、收据不写、声称时查不到反被判编造）——已在 §5.7 残余风险显式补记，非「用途不同故无关」 | **不翻案（继承缺陷已辨明并记账）** |
| **Stop hook（LLM-judge 甩锅自检不进产品层）** | ★ **未翻案，关键澄清如下** | **不翻案** |
| **§7 残余风险 2「长会话衰减→节流信号 hook」预留** | ★ D4-M4 `stall_warning.py` **正是兑现此预留**（仿 focus「攒够轮数才注入」的节流信号），非凭空新增 | **兑现既有预留** |

**★ 「确定性对账硬闸」是否翻了「Stop hook 不进产品层」？—— 没有，且必须说清它 ≠ 被否的 LLM-judge 版**：

- 被否的 Stop hook 是**语义判定**——扫本轮文字输出、判「归因/资源名在会话记录里指不指得到原文」，这个判定**需要每回合 LLM-judge**（贵、文字判定难），framework 因此否掉。
- 本设计所有硬闸（D6 规则闸 / D8 缺文件闸 / D1 permissions deny）走的是**完全不同的物理路径**：查 `git diff --cached` 终态 / 文件存在性 / `git show :path` 字节行数 / 命令签名——**零 LLM、零 hint 依赖、判据二值确定**。用户 Q4「只认铁证」正是把「确定性对账」与「LLM-judge」切开：前者近零误伤可下沉，后者贵且难。
- 所以本设计**只在 framework「铁证类硬闸可下沉」的留白里加料**，无一处推翻旧账。framework 当年否三 hook 的核心顾虑（误伤全下游、hint 恒空、LLM-judge 贵）在本设计硬闸上**均不成立**：误伤被「只认铁证 + 自门控 no-op + `[skip-rule-size]`/`[dogfood-exempt]` 逃生舱 + 脚本异常一律放行 + 正文差异降软」压到近零。

**唯一被用户新偏好正当松动的**：`rule_size_check`/`rule_index_check` **自身原先的 exit-0 软策略**（D6 升为 pre-commit exit 2）——推翻理由充分（判据 100% 机器判死、三重误伤兜底、与 Q15 概率启发式不矛盾）。这不是翻 framework 三 hook，是升级两个**本就存在**的确定性 hook 的硬度。

---

## 4. 实施路线图（性价比 + 依赖 + **本机可验证性** 三轴排序，P0→P2）

> **排序轴（批评⑩）**：除「价值/机器判死近零误伤」与「依赖」外，v1 显式引入第三轴 **本机可验证性**——**在 bridgeforge 自身能立即触发自验的项优先，自身恒 no-op（无 rules 目录、无下游双份结构）、只能靠人眼审+下游实测的项标注「需下游实测」并适度靠后**。这修正了旧版「把本机不可自验的 D6/D8 硬闸排在本机可自验的软信号之前」的倒置。

### P0 · 先偿 dogfood 欠账 + 零风险文本改（无新代码，解锁后续）
> 必须最先做——D6/D8 硬闸依赖 `.claude/hooks/` 镜像齐全，否则自身层闸空跑；且这批全是复用/文本，风险最低、本机即可验（补齐后 SessionStart 就能看到 hook 挂载无异常）。

1. **镜像补齐 `.claude/hooks/`**：`show_state.py`、`rule_index_check.py`、`memory_lint.py`、`find_doc_reminder.py`（+ 对齐 clarify/context_warning/requirements_check 正文），并在 `.claude/settings.json` 补注册（系统 python 前缀）。[D5-M4, D6-F1]
2. **D9**：确认零改动（元数据标注订正随手做）。
3. **D2-M1 / D5-M1&M2 / D1-M3 / D1-M5 / D3-M2&M3 文本改**：`templates/CLAUDE.md` §9.5 保守权重、§9.6 增「方案替换」类 + N7 红线、§9 顺手改必告知、§10 软化、§2.5 收据红线（含假验证澄清）、§8 lvl1 红线（D7-M2）；`debugging.md` §3 verbalized-uncertainty、§5 顺手改告知。
4. **D4-M1 阈值统一**：`debugging.md §6 T1` ≥2→≥3（**T2 保持不动**）+ 权威 pointer；更新 `ghost-wall-threshold-conflict` memory 为已收口。
5. **D1-M1**：`settings.json` deny/ask 查漏补齐 + CHANGELOG 明示 deny 清单是产品层承诺。

### P1 · 硬闸升级（复用现成 hook，共骑 pre-commit）
> 高价值、机器判死、近零误伤；依赖 P0 的镜像齐全。**本机可验证性弱**：D6 在自身恒 no-op（无 `.claude/rules/`）、D8 缺文件闸补齐后也 no-op，F3/F4 正确性**无法自身 dogfood、须人眼审 + 下游实测**——因此本 Phase 每步落地都要显式跑「下游模拟」dry-run（临时造一个 rules 目录+索引验证 exit 2 真触发），不能只靠自身跑一遍绿灯。

6. **D6 规则闸升 pre-commit**（标注：**自身 no-op，需下游实测**）：抽 `check_rule` → `.githooks/pre-commit` 加 staged-rules 扫描分支——`rule_size` 读 staged blob、`rule_index` 读工作树，exit 2 + CHANGELOG 顶部 `[skip-rule-size]` 豁免 + try 兜底。**先修 F3（两条读法分治+局限注释）+ F4（正则放宽 `[\w-]`）**。改 `meta_rule_design.md` §5/§6.4/§8 文档同步。两处 pre-commit 逐字镜像。造临时 rules 目录 dry-run 确认真能 exit 2。[D6, D3-M2 scope-reminder 一并加]
7. **D8 镜像闸**（缺文件段自身可验、正文差异段自身可验）：新建 `mirror_drift_check.py`（缺文件 exit 2 / 正文差异归一化前缀后只 stderr / dir_content_hash 仅做提示 / 自门控）。`.githooks/pre-commit` **mirror 段置最前** + `rc=$?; [ "$rc" = 2 ] && exit 2`。**豁免走 CHANGELOG 顶部 `[dogfood-exempt]`（非 commit message）**。**★ 紧前置守卫（批评⑪）**：本步启 exit 2 之前，**紧贴一道 dry-run「提交前重验零缺文件」**——现场再跑一遍比对、确认此刻无缺文件漂移，**不依赖 P0-1 早已补齐、中间隔了 P1-6 若干次提交仍无新漂移的假设**；若 dry-run 报缺文件，先补齐再启闸。改 `portability.md §5` + CLAUDE §1.4 指针 + `config_health_check` DELEGATED 登记 + `githooks_path_check` 文案泛化。[D8]

### P2 · 新建软信号 hook（误伤近零、本机可立即自验，但含新逻辑/需先验 payload）
> 软信号、误伤成本近零；**本机可验证性强**（stall/fallback/memory-write 在自身 repo 就能立即触发观察），故虽含新逻辑仍安全，排在硬闸之后是因依赖 P0 文本与 P1 pre-commit 骨架就位。

8. **D5-M3**：`memory_rebuild_index.py --from-hook` 分支追加一行 ASCII `[memory-write]`（并入既有 PostToolUse hook，不新建，**当轮可见可自验**）。
9. **D3-M1**：新建 `fallback_smell_check.py`（**仅裸吞异常**，exit 0）+ dogfood 镜像（改一处 rule 文件即可自验触发）。
10. **D4-M4**：新建 `stall_warning.py`（多轮遍历 + content-block 扫描 + **多特征合取判据 a/b/c** + 降级弱提醒）+ CLAUDE §10 加 `[stall]` 响应节（**写明事后代理、非实时刹车、对合法长思考轮无区分力**）+ dogfood。
11. **D1-M2**：新建 `test_receipt.py`——**落地前先 dump 一次 PostToolUse payload 确认 Bash exit code 在 `tool_response` 里可取**（拿不到则从文本反解，脆，需评估）；收据带命令指纹 + 时间窗防钓鱼 + dogfood。

> 每批产品层改动 bump `templates/VERSION` + `[product]` CHANGELOG；对 bridgeforge no-op 的闸（D6/D8 在自身无 rules/无下游结构）按 §1 第 4 问注明「不适用但仍挂上验证产品承诺」。

---

## 5. 残余风险 + 诚实缺口

1. **纯文字 A 类幻觉（最高残余，防不住）**：编造假 API/文件名、谎称「跑了没跑的测试」——这些是 0 工具调用或事后才可揭穿，**任何工具边界 hook 都看不见**（framework §7 已诚实标注 L3 最薄弱）。只能靠 `anti_fabrication.md` R1–R5 + D1-M3 收据红线**概率遵守、压低概率**，长会话衰减，**非硬保证**。

2. **假验证「exit 0 但内容错」——D1-M2 收据的核心盲区（批评②，必须点破）**：`test_receipt.py` 只证「命令真跑了且退出码为 0」，**对「验证内容本身无效」完全失明**——测试断言写歪、漏断言、断错路径的「看着对跑起来错」，命令照样 exit 0、收据照样盖章通过。收据**不是防假验证的机制**，只是防「谎称跑了」。这类假验证无任何工具边界抓手，只能靠 D1-M3 红线「声称验证通过须说清验了什么断言/覆盖哪条路径」软约束，属残余。

3. **谎称「已改文件」在不 commit 的会话里无铁证**：D8 缺文件闸只在真去 commit 时现形；纯口头「改了 N 处」在不提交的轮次里零铁证 → 退回 D1-M3 收据红线（软）兜。硬闸对「谎称已改」的实际拦截力仅覆盖「提交快照缺不缺文件」这个窄子集，不宣传成「拦已改文件谎报」的硬闸。

4. **空转结构性滞后 + 高误报（去抖救不了，批评⑧）**：`stall_warning.py` 受 SUSPENDED 约束只能**事后提醒（非当轮止损）**；本 repo「连续多轮写 rule/doc 无 tool_use」是**最常见的合法长思考**，「≥N 轮去抖」对它**几乎不设防**、无区分力——已诚实放弃「去抖解决误报」的假设，改为**多特征合取（无 tool_use + 用户未插新指令 + 高 thinking 占比）+ 降级为只在明显场景弱提醒**。即便如此仍无法可靠分开真假空转，Opus 4.8 无硬开关、概率遵守、不保证根治（Q5 已知情）。

5. **根因质量无机检抓手**：D3-M3 诚实弃做「根因验证 hook」（LLM-judge 在 false-success 上 AUROC<0.65 = 假验证，违北极星）。根因优先只能靠 rule + verbalized-uncertainty 软约束。

6. **软信号「狼来了」脱敏**：`fallback_smell_check` 即便收窄到裸吞异常，仍可能刷屏致模型无视 → 已按修正砍掉高误报正则、只留近零合法用途一类；后续若仍脱敏，可再收窄或撤下。

7. **test_receipt 继承 C2「硬卡死失明」缺陷（批评④）**：`test_receipt.py` 与 framework 降级的 C2 同挂 PostToolUse on Bash，**继承 C2 同一失明**——命令若真卡死不返回，PostToolUse 不触发、收据不写，此时若模型声称「测试通过」反而查不到收据被判编造（误伤方向），或模型直接放弃声称（漏防方向）。这不是「用途不同故无关」，是明确继承的缺陷，记账在此。另 payload 可取性（Bash exit code 是否在 `tool_response`）P2 落地前必须先 dump 确认——拿不到则整条 M2 需改从文本反解（脆）或降级。

8. **D6/D8 硬闸在 bridgeforge 自身为 no-op**：自身无 `.claude/rules/`、无「双份 templates↔.claude rules」下游结构，本闸真实拦截只发生在下游 clone 项目。dogfood 价值仅在验证脚本挂载无异常——这是 §1「自门控 no-op 验证产品承诺」哲学的正当结果，非缺陷，但须在 gap 描述/CHANGELOG 明写以免误以为在拦自身提交；F3/F4 的正确性也因此**只能人眼审 + 下游实测**（路线图 P1 已按此排序并要求下游模拟 dry-run）。

9. **D8 正文差异降软后的漏防**：正文差异只 stderr 提示不硬拦（为避免合法差异误伤），意味着「python 前缀之外的真漂移」可能被放行且被忽视 → 靠 `config_health_check` SessionStart 软登记 + 人工核对兜底，非硬保证。这是「近零误伤」与「防漂移彻底性」权衡后的自觉取舍。

---

## 6. v0.1→v1 修订记录

> §1-§5 的设计主体已把下列修正**融进正文**（非批注）。本节仅逐条登记「改了啥、依据」，便于审阅对照。

**① D1-M5「悄悄跑偏·换方案」不再挂空 focus**：旧版让 focus_reminder 承接「同一任务内擅自换实现方案」，但 focus 锚是首条 prompt、四分类判话题漂移、换方案不改话题→锚不动→永不 fire（空指针）。改为 `templates/CLAUDE.md §9.6` **增第五类「方案替换」** + 落 **N7「大偏离必先说」明文红线**（换方案/扩缩范围前先一句话告知），focus 只继续管话题漂移。

**② 假验证「exit 0 但内容错」盲区显式点破**：旧版把 D1-M2 收据措辞偏向「防假验证」。改为在 M2 边界、M3 红线、§5.2 残余风险**三处明写**：收据只证「命令真跑了且 exit 0」，**不证验证内容有效**；断言写歪/漏断言的假验证收据照样盖章，属防不住的残余。不再把收据吹成防假验证。

**③ Q11「边角顺手改必须主动告知」红线补齐**：旧版 D3-M2 只有「>N 文件/M 行贴 diff」的量闸，漏了小范围顺手改（不触阈值却正是该告知的场景）。D3-M2 补一条**质**的红线（`debugging.md §5` + `templates/CLAUDE.md §9`）：任何非用户点名的顺手改动，哪怕只碰 1-2 文件，也必须响应里一句话「顺带改了 X，因为 Y」，绝不静默夹带。

**④ D8-M1 正文比对从硬闸降为软提示（据 fc:dogfood-diff）**：旧版把「正文归一化后逐字一致」当 exit-2 硬闸。因 dogfood 合法差异不止 python 前缀（路径分隔、dev/下游注释措辞等），逐字一致当硬闸只要一处未覆盖就硬停误伤（踩 framework 否 C1 坑）。改为**缺文件才 exit 2**（二值确定、近零误伤）、**正文差异只 stderr 提示不拦**（dir_content_hash 仅生成提示）。§2.1 执行序、portability.md 红线、路线图同步。

**⑤ D5-M3 memory「当场报」改接正确 hook（据 fc:memory-hook）**：旧版把提醒并入「pre-commit 的 memory_rebuild_index 脚本」——commit 时才跑、当轮不可见，跑不通。批评③曾建议改接 `allow_memory_write.py`，但核查证实那是 **PreToolUse 放行闸、只能吐 permissionDecision、回注不进 context**，同样不行。**v1 采信核查第三选项**：直接在**已挂 PostToolUse 的 `memory_rebuild_index.py --from-hook` 分支**（写入后触发、当轮可见、门控精确）追加一行**纯 ASCII** `[memory-write]` 提醒（防 utf8-garble）。§2.2 软信号表同步改标此条为 PostToolUse hook 并注明区别于同名 pre-commit 脚本。

**⑥ framework 对齐补两条线（批评④）**：① D4 stall 显式声明**兑现 `antifabrication-framework.md §7 残余风险 2` 的「长会话衰减→节流信号 hook」预留**（§3 对齐表加行）；② D1-M2 test_receipt 在 §5.7 残余风险**补记「继承 C2 硬卡死失明缺陷」**（命令卡死不返回→PostToolUse 不触发→收据缺失→误伤/漏防），不再用「用途不同故无关」轻描淡写。

**⑦ §2.1 执行序删掉错列的 version_check（批评⑤）**：旧执行序把「version_check 覆盖的 bump 对账」列为 pre-commit 一步，但 version_check 实注册在 **PreToolUse**、pre-commit 里根本没有它——事实错误且与本节末「注意」段自相矛盾。已从执行序删除。

**⑧ stall ≥2 轮去抖失灵，诚实改判据 + 降级（批评⑧）**：旧版把「≥2 轮去抖」当误报解法，但写文档任务本就是连续多轮无 tool_use，该阈值对主力误报场景几乎不设防、无区分力。改为**多特征合取**——(a) ≥2 轮高 output 且零 tool_use + (b) 期间用户未插新指令 + (c) 高 thinking 占比（可得时取）——并**降级为「只在明显场景弱提醒」**，达不到全部可得特征就不 fire。文案诚实标注「弱事后提醒、对合法长思考轮无区分力、不保证根治」。§5.4 同步。

**⑨ rule 闸读法分治（据 fc:staged-blob，批评⑨）**：旧版两条 rule hook 都读工作树、升硬闸带病。据核查**分治**：`rule_size_check`→**读 staged blob**（`git show :path`，单文件自洽、真正近零误伤）；`rule_index_check`→**保留工作树 + 注释显式声明局限 + `[skip-rule-size]` 兜底**（跨目录集合一致性比对，纯 staged 反而漏判/误判部分暂存）。二者不强求同一读法。D6-F3/F4 正文改写。

**⑩ 路线图引入「本机可验证性」第三排序轴（批评⑩）**：旧版把本机恒 no-op、不可自验的 D6/D8 硬闸排在本机可自验的软信号之前（倒置）。v1 显式加第三轴：自身能立即触发自验的项优先，自身 no-op 只能靠人眼+下游实测的项标注「需下游实测」并要求 P1 每步跑下游模拟 dry-run（临时造 rules 目录验证 exit 2 真触发）。

**⑪ P1-7 mirror 闸启 exit 2 前紧贴「提交前重验零缺文件」守卫（批评⑪）**：旧版把「补齐镜像」放 P0-1、「启 mirror 闸」放 P1-7，中间隔着 P1-6（也会改 pre-commit 并触发提交），留自拦窗口。v1 在 P1-7 启 exit 2 之前**紧贴一道现场 dry-run 重验**，确认此刻零缺文件漂移，**不依赖 P0 早已做完、中间无新漂移的假设**；报缺则先补再启。

**其余已在 v0.1 §6 记录并本轮融入正文的 verify 修正**（未改判、仅从批注转正文）：D1 pre-commit 不承载新硬闸/CHANGELOG 对账砍除；D2 §9.5 豁免 dogfood 理由订正；D3 fallback 正则收窄到仅裸吞异常；D4 T1/T2 轴分离、stall 复用量诚实标注、事后代理时机；D5 show_state 已存在降级为 dogfood 补齐；D6 F1 补 rule_index_check 镜像、F2 自身 no-op、F4 正则放宽；D7-M3 依赖 D6 两前置且 SKILL 死链是净新增；D8 硬伤1 豁免走 CHANGELOG 顶部/硬伤2 exit2 置前防吞/订正1 `.githooks` 点开头/订正2 无 `.claude/rules/`；D9 元数据标 skill/advisory + user-global。

---

相关文件锚点（全绝对路径）：
- 权威偏好：`d:/Quant/BridgeForge/.claude/memory/harness-preferences.md`（N7 换方案 L78、N6 假验证 L74-76、Q11 L105-106、Q14 L116-117）
- 既有框架：`d:/Quant/BridgeForge/docs/antifabrication-framework.md`（§7 残余风险 2 节流 hook 预留 L111；C2 失明缺陷 L72）
- pre-commit 底座：`d:/Quant/BridgeForge/.githooks/pre-commit`（现仅 memory rebuild、无 version_check）、`d:/Quant/BridgeForge/templates/.githooks/pre-commit`
- memory「当场报」正确落点：`memory_rebuild_index.py --from-hook`（PostToolUse，settings.json:189-197 / templates:178-186）；错误落点辨析：`allow_memory_write.py`（PreToolUse 放行闸）、pre-commit 的 `.claude/scripts/memory_rebuild_index.py`（commit 时跑、当轮不可见）
- rule 读法：`templates/hooks/rule_size_check.py`（改读 staged blob）、`templates/hooks/rule_index_check.py`（保留工作树 L36/L39；正则 `rules/([a-z_]+\.md)` L38 放宽为 `[\w-]`）
- version_check 实为 PreToolUse：`d:/Quant/BridgeForge/templates/settings.json`（L146/162）
- 待镜像补齐（自身层缺失）：`d:/Quant/BridgeForge/.claude/hooks/`（缺 show_state.py / rule_index_check.py / memory_lint.py / find_doc_reminder.py）
- 复用骨架：`templates/hooks/context_warning.py`（stall 借骨架）、`templates/hooks/requirements_check.py`（fallback_smell 借骨架）、`templates/hooks/skill_sync_check.py`（mirror_drift 借 dir_content_hash 做软提示）、`templates/hooks/version_check.py`（exit2+skip 逃生舱范式）、`templates/hooks/show_state.py`（snapshot 提示已实现）
