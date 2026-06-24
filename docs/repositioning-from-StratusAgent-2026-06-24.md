# setup_agent 重新定位 — 待办 spec（来自 StratusAgent 2026-06-24 harness 审计）

> 来源：StratusAgent 一次全面 harness 审计 + 多轮辩论。本文件是**交接清单**，用户回头开发 setup_agent 时一起做。
> 状态：**全部待做（None implemented）**。每条带 what / why / where / 优先级。

---

## 0. 触发背景（一句话）

StratusAgent 用户报 agent 工作异常（读串/空转/跑题/低效），查 harness。过程中发现**用户级全局 settings.json 被攒进了 40+ 条别项目(CausisRiskSuite/Stratus.Py)的专属 allow**，引出"setup_agent 该如何定位用户级 vs 项目级"的重新思考。

---

## 1. 必须先认清的事实（否则会开错药）

**F1. 这次全局污染不是 setup_agent 造的。** setup_agent 往用户级只放**通用 skill**（plan/escalate/… 单一源），**从不往用户级 settings.json 写 allow**。那 40+ 条脏 allow 是**用户长期点 always-allow / 手动加**沉淀的。→ 所以"砍 setup_agent 用户级产物"**治不了**污染。

**F2. 现在的 Claude Code，always-allow 默认写【项目本地 `settings.local.json`】，不写用户级全局**（claude-code-guide 查证，依官方文档表格 + 社区，高度可信非铁证）。→ 污染**源头基本已被默认行为堵上**；那 40+ 条是**老版本/历史遗留 + 跨机带过来**的存货。

**F3. 没有"写时拦截 always-allow 写用户级"的 harness 开关。** 唯一能硬锁用户级权限的是 **Managed Settings**（`allowManagedPermissionRulesOnly:true`），但它会**连项目自己的 allow/deny 一起禁掉**，杀鸡用牛刀，**不采用**。→ "零污染"落地只能是**事后周期审计 + 下沉**这层准机制。

---

## 2. 确立的设计原则（北极星）

**P1. 用户级 = 只放共性条目**（所有项目通用：通用 skill 本体 + 共性红线 + 沟通/安全协议）。
**P2. 项目专属红线 → 项目自己的 CLAUDE.md，随开发增量补充**（不在 init 预设/逼填——init 时这些内容还不存在）。
**P3. 污染零容忍的价值对，但手段是【审计 + 下沉】，不是砍 setup_agent 产物。** 且"零容忍"必须**显式豁免** setup_agent 出品的通用 skill（那是 DRY 设计不是污染）。

### ⛔ 明确否决（防再次提出）

**不要"零用户级 / 全项目本地化"。** 推翻 2026-06-09 `portability.md §2`「通用 skill 用户级单一源」是**反向退化**：① N 项目各拷一份 → M 份漂移；② `/harvest` 反哺失去单一落点；③ 换机从"跑一次 /setup_agent 全装"退化成"处处装处处维护"。且它**堵不住 always-allow**（见 F1/F2）。skill 单一源是有意 DRY 让步，**保留**。

---

## 3. 待做改动清单

### C1 · CLAUDE.md 模板：删 3 个预设空格 → 增量留白 〔P1〕
- **What**：`templates/CLAUDE.md` 里"架构红线 / 快速命令 / 项目结构"3 处，**不要**预设成 `<!-- TODO 你自己填 -->` 的填空。改成**一句明确标注**"项目专属红线，随开发增量补充"。
- **Why**：项目 init 时这些内容**根本不存在**（数据流方向/铁律是开发跑一阵才长出的结论）；"事后填空"实践中退化成"永不填"。符合 `meta_rule_design.md §6`「从空开始增量演化」。
- **作废前案**：原想"setup 时当场引导问用户填"——也错，问得太早，那天答不出来。

### C2 · 批量铺时附解释 〔P2 锦上添花〕
- **What**：Step3 批量复制 hook/rule/memory junction 时，附一段"这批各干嘛"的简短说明（不逐文件确认）。
- **Why**：下游一次冒出 15 hook + 6 rule，黑箱认知负担重。对骨架作者本人价值低，主要利于"别人用/未来的你"。

### C3 · 用户级 allow 周期审计（核心治污染件）〔P1〕
- **What**：加审计能力——扫 `~/.claude/settings.json` 的 `permissions.allow`，揪出**项目专属/一次性**条目：
  - 带**项目绝对路径**（`[A-Za-z]:\\…`、`/[a-z]/Quant/…`、`d:\\Quant\\<proj>`）
  - 写死 **PID**（`Get-Process -Id \d{4,6}`）
  - 写死 **IP**（`\d+\.\d+\.\d+\.\d+`）
  - 一次性 **clone / 编译** 命令（`git clone …`、`cl.exe …`、`cargo build --manifest-path …`）
  - **只报不删**（删错麻烦，列给用户拍）。
- **Where**：脚本放 `templates/scripts/`（或 setup_agent 自带 `scripts/`）；`SKILL.md` 记成**必做步骤**——跑 `/setup_agent` 时顺手审一遍（触发时机用户选①「跑 setup_agent 时」，非②每会话）。
- **定位（诚实）**：belt-and-suspenders。鉴于 F2（always-allow 已默认写项目本地），它抓的是**换机带过来 / 老版本遗留**的漏网条目，不是"不装就持续被污染"的救火件。**用户因换机开发明确要此技能、记入必做项。**

### C4 · 跨项目授权下沉范式（文档化 norm）〔P1〕
- **What**：写进 `templates/rules/portability.md`（或骨架检查项）：「**项目专属 `additionalDirectories`/`allow` 禁放用户级**；被权限弹窗时优先落项目级 `settings.local.json`。用户级只放共性（=P1）。」
- **Why**：这是 P3 零污染的"法律"；配合 C3 审计的"执法"。

### C5 · 文档化豁免边界 〔P1〕
- **What**：白纸黑字写清：「setup_agent 出品的**通用 skill 本体**进用户级 = 合法 DRY；**项目专属授权**进用户级 = 污染。」
- **Why**：防 C3/C4 的"零容忍"被扩大解释，误杀 skill 单一源（见 §2 否决项）。

### C6 · skill 单一源治理：清"扁平 vs 目录式"shadow 〔P2〕
- **What**：用户级 `~/.claude/skills/` 里发现 `collab.md`/`debate.md`（扁平残留）与 `collab/SKILL.md`/`debate/SKILL.md`（目录式）**同名 shadow**，frontmatter 还漂移（`user-invocable` vs `user_invocable`）。setup_agent 更新模式（Step0.5 清重复副本）应**扩到自检并清扁平残留** + frontmatter 键标准化为 `user_invocable`。
- **Note**：上游 `D:/Quant/setup_agent/skills/` 下已全是目录式 `SKILL.md`，扁平是历史**部署**遗留，Step0.5 该在用户级清。

### C7 · hook UTF-8 输出兜底（骨架红线）〔P1〕
- **What**：所有**输出中文**的 python hook 必须在顶部 `try: sys.stdout.reconfigure(encoding="utf-8") except Exception: pass`。Windows 控制台默认 GBK，漏设 → 中文经 stdout 被当 UTF-8 解 → **mojibake 注入 SessionStart 上下文**（StratusAgent 的 `target_cleanup.py` 曾是唯一漏设者，导致 agent"读串"）。
- **Where**：核对 `templates/hooks/` 每个输出中文的 hook 都有此行；写进 hook 编写规范。
- **Note**：可顺带在 `templates/settings.json` 给 python hook 命令统一前缀 `-X utf8` / `PYTHONIOENCODING=utf-8` 做全局兜底。另：**禁止用 PowerShell 编辑含中文的模板文件**（GBK 会写坏，固化成 U+FFFD）——StratusAgent 的 rule 文件就是这么被写坏的。

### C8 · hook 成本治理（最佳实践注释）〔P2〕
- **What**：在 hook 模板注释/规范里沉淀：「**重型 hook**（如全量编译检查）应 `async` 或 debounce；**轻量检查**按 `file_path` 早短路。」
- **Note**：StratusAgent 的 `cargo_check.py`（每次 .rs 编辑跑全量 `cargo check --workspace`，卡十几秒）是反例；它是项目自加、不在上游模板，故本条主要是**规范注释**。

### C9 · 用户级编码兜底 env（防未来 hook 乱码）〔P1〕
- **What**：setup_agent 应确保 `~/.claude/settings.json` 有 `"env": {"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8"}`——让所有 python 子进程（含 hook）默认 UTF-8 输出，从根上杜绝 Windows GBK 控制台 mojibake。C7 是**逐 hook** 补 reconfigure，本条是**全局网**，互补。
- **设计取舍**：setup_agent 当前**不写**用户级 settings.json（只写 skills + 条件补 CLAUDE.md 2 规则）。本条要么 ① 给 setup_agent 加"补用户级 env"的窄能力（在 Step0 补 CLAUDE.md 规则那块顺带），要么 ② 列为换机手动步骤写进 `INSTALL.md`。**用户拍。**
- **Note**：StratusAgent 本机已加（U-8，2026-06-24）；`PYTHONUTF8=1` 跨平台无害（非 Windows 也 OK）。

### C10 · 用户级 CLAUDE.md：补"写 rule 红线"共性条目 〔P1〕
- **What**：setup_agent 写用户级 `~/.claude/CLAUDE.md` 时，补一条共性红线——「写 `.claude/rules/*.md` 或任何约束文件只写'必须/禁止'、不讲故事；完整事故复盘 / >20 行 code / 方案对比搬 memory / doc，rule 内最多留**一行** `**Why**: …（memory xxx）` 指针」。
- **关键约束（补充非覆盖）**：末句**必须**声明「**本条是共性底座，不覆盖项目自有的 rule 撰写规范**；项目带 meta_rule（量化红线 / 案例库 / 加载策略）时以项目版为准」。量化红线（50KB/500 行）/ 案例库 / 加载策略是**项目专属**，**禁止**抄进用户级（违 §2.4.3 单一事实源）。
- **Why**：rule 退化成"百科全书 + 踩坑集"是跨项目通病；把"只写红线"提到用户级当底座，新项目还没长出 meta_rule 时也有约束兜着。但细则归项目、原则归用户级，分层避免漂移。
- **追加（2026-06-24）**：该共性条目再加一句——「rule 触发条件**必须机器可解析**：项目按 frontmatter `paths` 触发加载 rule 时，每个 rule 顶部**必须**有 YAML `paths:`，**禁止**只写散文"加载条件"」。这是 setup_agent 出品项目的 house style（setup_agent 铺的项目都靠 frontmatter `paths` 触发加载 rule；StratusAgent CLAUDE.md §0 明文"触发条件以各文件 frontmatter `paths` 为准"）。StratusAgent 本机用户级 CLAUDE.md 已加。
- **Where**：用户级 CLAUDE.md 新增一节（与现有"沟通风格 / 防空转 / Git / 主动工具"并列）。StratusAgent 本机已加（2026-06-24）。

---

## 4. 优先级速览

| P1（该做） | P2（锦上添花） |
|---|---|
| C1 删空格→增量留白 · C3 allow 审计 · C4 下沉 norm · C5 豁免边界 · C7 hook UTF-8 兜底 · C9 用户级 env 编码网 · C10 用户级写-rule 红线 | C2 批量铺附解释 · C6 skill shadow 清理 · C8 hook 成本注释 |

> 反哺渠道：本 spec 经 `.claude/harvest-inbox.md` 一行指针挂载。
