# 反哺工作流 Playbook

> **定位**：把下游项目（StratusAgent / causis_risk_suite / ClaudeBridgeAssist 等）攒到的通用 agent 协作经验，提炼脱敏后写回 bridgeforge 这个上游骨架库。
>
> **为什么不做成 skill / 自动化**：反哺的核心是"通用 vs 业务专属"判断，需要人脑逐段把关；bridgeforge 又是公开 GitHub 仓库，自动化容易把内部术语/账户号/API endpoint 等敏感物泄露到公网。先把流程跑顺 2-3 次，再判断要不要工具化。

---

## 1. 触发时机

> **2026-05-29（v0.16.0）起：捕捉与推送分离，落到两个命令。** 本 playbook 是 **`/harvest`（推送侧）** 的权威流程。
> - **捕捉**（日常）：`/summary` 顺手判通用性 → 通用的记一行进下游 `.claude/harvest-inbox.md`（反哺收件箱）。详见 `skills/summary/SKILL.md` 第 6 步。
> - **推送**（本流程）：`/harvest` 把收件箱（或立即单条）脱敏写回上游。

满足任一即可触发一次反哺（即跑 `/harvest`）：

- **收件箱攒到 ≥ 3 行**（从"凭感觉≥3条"升级为"可数"——数 `.claude/harvest-inbox.md` 未处理行）
- **一眼确定要立即反哺**：`/harvest <描述>` 走快车道，跳过收件箱（高信心也照样过 §3 脱敏）
- **用户主动喊**（"反哺一下 bridgeforge" / `/harvest`）
- **季度/月度盘点**（清一次收件箱，避免积压太多差异）

> **两个入口、一个仪式**：无论"收件箱批量"还是"立即单条"，都汇进下方 §2-§3 同一套判通用性 + 脱敏流程，不分叉。

---

## 2. 五步操作流程

### Step 1：列源项目 + 探查现状

```powershell
# 列所有候选源项目的 .claude/rules/
ls D:/Quant/StratusAgent/.claude/rules/
ls D:/Quant/causis_risk_suite/.claude/rules/
ls D:/Quant/<其他>/.claude/rules/

# 对比 bridgeforge 现有 templates：Claude 用 templates/claude，Codex 用 templates/codex
ls D:/Quant/BridgeForge/templates/claude/rules/
ls D:/Quant/BridgeForge/templates/codex/rules/
```

明确**这次反哺的范围**（哪几个源 → 哪几个目标文件）。范围不要贪大，一次 5-8 个文件对比为宜，超过就拆成几次。

### Step 2：逐文件 diff，标候选段

每个目标文件（如 `portability.md`），把所有源项目对应文件并排读，标出：

- 🟢 **通用增量**（bridgeforge 没有 + 真的跨项目通用）
- 🟡 **可抽象**（偏某语言/某平台特有，但脱敏后仍有参考价值）
- 🔴 **业务专属**（gateway / oms / 内部包名等，绝对不能反哺）

工具技巧：

- 用 `Read` 并行读多个文件
- 用 `Grep` 快速找特定段落是否已存在
- 标 🟢 的段落，逐字记下"来源文件 + 行号"，方便 review 时回查

### Step 3：脱敏（最关键 — 见 §3 checklist）

对每个 🟢 段落，按 **§3 脱敏 checklist** 逐项过。脱敏不彻底就不要进 bridgeforge。

### Step 4：写 bridgeforge

- 写入路径**允许**：
  - `templates/<agent>/rules/` — rule 文件
  - `templates/claude/CLAUDE.md` / `templates/codex/AGENTS.md` — 项目级常驻指令模板
  - `templates/memory/` — memory 模板
  - `templates/doc/` — doc 分层模板
  - `templates/<agent>/hooks/` — Python hook 脚本（2026-05-24 加入：session_snapshot.py / memory_lint.py / rule_index_check.py / context_warning.py 等，agent 检测项目有 `.venv` 时复制）
  - `templates/<agent>/scripts/` — Python 工具脚本（2026-05-24 加入：archive_scan.py 等给 skill 调用的脚本）
  - `docs/` — playbook / rationale 等 bridgeforge 自身文档
- **禁止**自动写：
  - `skills/<name>/SKILL.md` — 用户级 skill 描述，独立维护（**例外**：当下游已实测验证的 SKILL.md 改动需要回灌时，单条修改允许 — 不允许批量改写多个 SKILL.md）
  - `scripts/` — bridgeforge 自身工具（如 `setup-junction.ps1`），不是给下游模板的
  - `SKILL.md` — bridgeforge 自身 skill 描述
  - `README.md` 核心段 — 用户对外文档，措辞要审；**例外**：加新独立 section（如 "Python 依赖"）允许，覆写已有段不允许
- 写完用 `git diff --stat` 看改动规模，**逐文件 review**（不批量 confirm）
- **hook / script 反哺额外要求**：每个 `.py` 文件按 §3 脱敏 checklist 逐项过；hook 文件名 / 主名需与 SKILL.md 引用一致（如 `session_snapshot.py` 给 `/snapshot` 用，不要随便改名）

### Step 5：review + 手动 push

```powershell
cd D:/Quant/BridgeForge
git diff                    # 全量看一遍
git diff --check            # 检查空白/编码异常
git status                  # 确认没意外文件
git add <精确路径>          # 不要 git add .
git commit -m "..."
git push                    # 用户手动，不让 AI 自动
```

**push 前最后一道闸**：搜一遍 commit 内容里有没有这些敏感关键词：

```powershell
git diff --cached | Select-String -Pattern "(causis_api|StratusAgent|账户|API.?key|0x[0-9a-f]{8}|D:/|C:/Users)"
```

有命中 → 停下脱敏；全过 → 放行。

---

## 3. 脱敏 checklist（红线）

每个反哺段落必须过这 7 项。**只要漏 1 项，反哺就不安全。**

| # | 检查项 | 例子（要替换的） | 替换为 |
|---|--------|------------------|--------|
| 1 | **项目名** | `StratusAgent` / `causis_risk_suite` / `causis_api` | 通用占位 `<project>` / `<pkg>` |
| 2 | **内部包/模块名** | `vnpy_ctp` / `causis_api.const.login` / `risk_daily.config` | 通用占位或删掉 |
| 3 | **账户号 / API key / token** | 任何看起来像凭证的字符串 | **整段删，不替换** |
| 4 | **内部 URL / endpoint** | `causis.internal/...` / 内部 IP | 通用占位 `<internal-url>` 或删 |
| 5 | **commit hash / 事故 ID** | `761274f` / `vtable mismatch 78 函数偏移` | 删 |
| 6 | **绝对文件路径** | `D:/Quant/<project>/...` / `C:/Users/<name>/...` | 相对路径或占位 |
| 7 | **业务术语** | 交易所代号 / 期权 greeks / 风控阈值名 / 客户产品名 | 通用化（如"外部 SDK"/"业务字段"）或删 |

**特别注意**：

- 事故案例（"YYYY-MM-DD 那次踩了 X"）原则上**整段删**，rule 文件不留案例，案例归 memory（meta_rule_design.md §2 规定）
- 段落里如果出现版本号/日期超过 3 处 → 信号说明案例越界 → 重写成 normative 表述
- 公开技术名（IB / Schwab / Deribit / CTP / Python / Rust / Node 等开源或公开品牌）**不算敏感**，可保留

### 3.1 实战记录（2026-05-24 三次反哺批次）

本会话 3 次反哺到 bridgeforge（v0.6.0 / v0.7.0 / v0.8.0）实测脱敏的典型场景。新人做反哺时对照参考。

#### 批次 1（v0.6.0 / commit `9cfa7ae`）— hooks/scripts 首次反哺

源：StratusAgent → `templates/hooks/session_snapshot.py` + `templates/scripts/archive_scan.py`

实测应用的 checklist 项：

- **#1 项目名**：StratusAgent 原版含"stratus session ..."类日志前缀 → 通用化为"session ..."
- **#2 内部包名**：原版从 stratus 内部 config 模块读版本号 → 改为读项目根 `VERSION` 文件 fallback（通用版本检测）
- **#6 绝对路径**：原版含 `D:/Quant/StratusAgent/...` 硬编码 → 改为 `Path(__file__).resolve().parents[2]` 推断项目根
- **删 session-tag 残留**（§5 日志原话）：v0.5.0 已删 session-tag skill，hook 里相关引用一并清掉
- **公开技术名豁免**：`subprocess` / `pathlib` / `json` 等标准库不脱敏

#### 批次 2（v0.7.0 / commit `4b976da`）— 5 hook + modules.md 反哺

源：StratusAgent 5 hook（`memory_lint` / `rule_index_check` / `rule_size_check` / `find_doc_reminder` / `show_state`）+ causis_risk_suite `modules.md §3.1/§3.2`

实测应用的 checklist 项：

- **#1 项目名**：hook 错误信息里的"stratus ..."前缀全部去掉
- **#2 内部包名**（modules.md §3.2 重灾区）：`risk_daily.config / causis_api.const.login / BusyTracker` 等具体类名 → 占位为 `<config 模块> / <const 子包> / <横切服务类>`，案例改写为 normative 模式描述
- **#7 业务术语**（§5 日志原话："脱敏 risk_daily / causis_api / BusyTracker 等业务专属"）：删 / 通用化
- **公开技术名豁免**：`PreToolUse` / `PostToolUse` 等 Claude Code 内置 hook 名称保留

#### 批次 3（v0.8.0 / commit `12c7c16`）— **非反哺批次**对照

本批次**全是 bridgeforge 自身改动**（VERSION / CHANGELOG.md / SKILL.md frontmatter / resume Step 5），**没有从上游脱敏反哺**。作为对照记录，说明：

- 不是每次 bump 版本号都涉及反哺 — 自身演进版本（如本批次）reverse-sync-playbook 不参与
- 版本号语义直接引用 `templates/rules/workflow.md §9`，**不重复**定义规则
- §5 反哺日志这种情况不记（日志只记真正从上游脱敏拉回的批次）

#### 批次（v0.19.0 / 2026-05-30）— target_cleanup.py hook 反哺

源：StratusAgent → `templates/hooks/target_cleanup.py` + `templates/settings.json`

实测应用的 checklist 项：

- **#1 项目名**：`find_workspace()` 原硬编码项目特定子目录（workspace 在子目录的布局）→ 通用化为"根 `Cargo.toml` 优先，再扫一层 `*/Cargo.toml`"。下游可保留特定子目录名，上游必须通用查找
- **#5 具体数值**：docstring 原含下游事故实测数（"`--time 3` 只清 302KiB / 288GB"）→ 删，hook 内改 normative 表述（"陈年产物长期看起来热而清不动"）；具体动机数值只留在 CHANGELOG 作背景，不进可复用代码
- **#6 绝对路径**：原版已用 `Path(__file__).resolve().parents[2]` 推断项目根，无硬编码 ✓
- **#7 业务术语豁免**：`cargo` / `incremental` / `Defender` 是公开技术名，不脱敏
- **设计层面**：条件加载用 hook 自门控（无 Cargo.toml → no-op）实现，而非 setup 时按主语言裁剪 settings.json —— 既免改受保护的主 `SKILL.md`，又比静态裁剪更稳（项目后增 Rust crate 自动激活）

#### 批次（v0.24.0 / 2026-06-05）— memory 冷启动引导脚本反哺

源：StratusAgent → `templates/scripts/memory_bootstrap_cold.py` + `docs/memory-scoring-design.md`

实测应用的 checklist 项：

- **#5 具体数值**：下游实测分区数（"15/40/237"）+ "256 条 memory" 等具体数 → 删，脚本/文档只留 normative 表述（"top-N 随机 / 拨数周前 / 1-2 周自愈"）
- **#6 绝对路径**：脚本用 `Path(__file__).resolve().parent.parent / "memory"` 推断项目根，无硬编码 ✓
- **#7 业务术语豁免**：无业务术语（纯 memory 系统机制）
- **定性校正（最关键）**：下游 `memory_rebuild.py` 有"假 Cold:0 + 静默截断" bug；上游 `memory_rebuild_index.py` 的 Cold = 排名溢出本就诚实、且 never-recalled 走 S=7 快衰减 → 反哺时**改定性**为"可选的冷启动加速引导"而非"bug 修复"，文档诚实标注上游自愈窗口。教训：**反哺前必须核对上游脚本逻辑，不能照搬下游 bug 叙事**

#### 批次（v0.25.0 / 2026-06-05）— target_cleanup.py 加 L2 deps 变体裁剪（增量反哺已有 hook）

源：StratusAgent → `templates/hooks/target_cleanup.py`（v0.19.0 已反哺 L1，本次叠加 L2）

实测应用的 checklist 项：

- **#5 具体数值**（本批主战场）：下游 docstring/对话里满是项目实测数 —— "deps 85GB"、"本地 stratus_* 各堆 280+ 变体"、"128GB 降到 ~9GB"、"删 15086 文件 / 82.6GB"。全部删，改 normative 表述（"旧 hash 变体无限堆积"、"本地 workspace crate 因频繁重编尤甚，长期可占 target 绝大头"）。具体数值只留 CHANGELOG 作背景，不进可复用代码
- **#1 项目名**：下游 docstring 用 `stratus_*` 举例大户 → 上游改 "本地 workspace crate"，不点名
- **不是脱敏、是"反向取上游更优实现"**：下游 L1 用 `*/incremental` + 硬编码 `stratus/` 子目录；上游 v0.19.0 早已通用化为 `**/incremental`（覆盖交叉编译）+ 通用 `find_workspace`。本次以**上游为基线**叠加 L2，并把 L2 的 `deps_dirs` 也写成 `**/deps` 与上游 L1 风格对齐 —— 反哺增量时基线选上游而非下游，避免把下游的项目特定退化带回上游
- **公开技术名豁免**：`cargo` / `deps` / `rlib` / `rmeta` / `hash` / `mtime` / `Defender` 均不脱敏
- **增量反哺的版本语义**：已反哺 hook 加新 pass = 新功能 = minor bump（0.24→0.25），不是 patch

### 3.2 实战记录的元规则

- 每次反哺后**当场**写实战记录到 §3.1（不要攒），否则 7 天后细节就忘了
- 实战记录的价值在"checklist 7 项的实例化"，不在"做了什么"（做了什么记 §5 日志即可）
- 攒 5+ 个批次后回头看 §3.1 是否有**重复出现的脱敏陷阱** → 提炼成 checklist 第 8 项（机制升级，不是案例堆积）
- **禁止虚构踩坑故事** — 实战记录只写真实发生 + 可从 git log / §5 日志核实的内容，宁可简略不可编造

---

## 4. 冲突仲裁规则

多个源项目同一段表述不一致时，按以下顺序仲裁：

1. **并集合并 + 用户拍板**（默认）— 列出每个源的版本差异，让用户选
2. **以更新更近的为主**（看 git log mtime）— 用户没空时退而求其次
3. **以源项目实战次数多的为主**（如 StratusAgent 跑了 1 年 vs 新项目跑了 1 周）
4. **不确定就不反哺** — 宁可漏，不可错

---

## 5. 反哺日志

每次反哺在下表追加一行。攒 5+ 行后再回头看是否值得做工具化。

| 日期 | 源项目 | 目标文件 | 反哺内容（一句话） | 操作人 |
|------|--------|----------|--------------------|--------|
| 2026-07-08 | StratusAgent | templates/claude/hooks/git_add_all_guard.py + settings.json | 新 hook：bulk git add 安全护栏；脱敏项目文案后阻断凭证类文件和 `.runtime/` 临时产物被全量 add | bridgexue |
| 2026-07-08 | StratusAgent | templates/claude/hooks/memory_dup_check.py + settings.json | 新 hook：新建 memory 前按文件名主题词提示同主题碎片化；脱敏本地 debate/memory 来源记录 | bridgexue |
| 2026-07-08 | StratusAgent | templates/claude/hooks/cargo_default_run_check.py + settings.json | 新 hook：多 `[[bin]]` Cargo.toml 缺少 default-run 时软提醒；脱敏本地启动脚本与 memory 来源 | bridgexue |
| 2026-05-24 | causis_risk_suite | modules.md | +§4 `.runtime/` 运行时数据目录 + §5 根目录极简 | bridgexue |
| 2026-05-24 | causis_risk_suite | portability.md | +§4.3 venv 不可移植 + §4.4 CRLF + §4.4.1 入口脚本 ASCII + §4.5 editable 安装 | bridgexue |
| 2026-05-24 | StratusAgent | workflow.md | §9 版本号简版 → Milestone-bound SemVer 详细版 | bridgexue |
| 2026-05-24 | StratusAgent | meta_rule_design.md（新建） | 整体脱敏搬入元规则（强制力梯度 / 加载策略 / 反模式速查） | bridgexue |
| 2026-05-24 | ClaudeBridgeAssist | playbook.md §4 | 白名单加入 `templates/hooks/` + `templates/scripts/`；明确 SKILL.md / README 的反哺例外条件 | bridgexue |
| 2026-05-24 | ClaudeBridgeAssist | README.md | 加 "Python 依赖" 段，明确核心模板跨语言 vs hook 功能需 `.venv` | bridgexue |
| 2026-05-24 | ClaudeBridgeAssist | SKILL.md Step 3 | 加 Python hook 体系条件复制 + 无 .venv fallback + 非 Python 项目跳过说明 | bridgexue |
| 2026-05-24 | StratusAgent | templates/hooks/ (5 个 hook) | 反哺 memory_lint / rule_index_check / rule_size_check / show_state / find_doc_reminder（脱敏 stratus 路径 + 删 session-tag 残留 + 通用版本检测） | bridgexue |
| 2026-05-24 | StratusAgent | templates/settings.json | 加 PreToolUse / PostToolUse / SessionStart hook 注册段（对应新反哺的 5 个 hook） | bridgexue |
| 2026-05-24 | causis_risk_suite | templates/rules/modules.md | 加 §3.1 协调中枢内部分层（纯常量 / 幂等引导 / 横切服务）+ §3.2 提炼共享常量三件套范式（脱敏 `risk_daily` / `causis_api` / `BusyTracker` 等业务专属） | bridgexue |
| 2026-05-30 | StratusAgent | templates/hooks/target_cleanup.py + settings.json | 新 hook：Rust target/incremental 缓存体积触发式清理（脱敏：项目特定子目录硬编码 → 通用 Cargo.toml 查找 + 删事故实测数值；自门控故无条件挂 SessionStart，不改主 SKILL.md） | bridgexue |
| 2026-06-03 | StratusAgent | templates/hooks/memory_guard.py + skills/prune-memory/ + settings.json | 新 hook：MEMORY.md 写入行数硬阻断（PreToolUse，>185 行 exit 2）；新 skill：prune-memory 引导式清理流程（删留标准 + 用户确认 + archive 移档）；settings 注册同步 | bridgexue |
| 2026-06-03 | StratusAgent | docs/memory-scoring-design.md + hooks/memory_access_tracker.py + scripts/memory_rebuild_index.py + scripts/memory_search.py + memory/_stats.json + skills/find-memory/ + settings.json + session_snapshot.py | Memory 热度评分系统（艾宾浩斯衰减）完整闭环：tracker→_stats.json→Stop时rebuild→MEMORY.md热区+MEMORY_COLD.md冷区；本次核实系统完整性并发版 v0.23.0 | bridgexue |
| 2026-06-03 | CausisRiskSuite | templates/scripts/memory_search.py | main() 顶部加 stdout UTF-8 reconfigure，防 Windows 中文环境输出乱码 | bridgexue |
| 2026-06-05 | StratusAgent | templates/scripts/memory_bootstrap_cold.py + docs/memory-scoring-design.md | 新脚本：memory 冷启动一次性引导（拨 never-recalled 文件 created_at 入 Cold，跳过约 1-2 周自愈期；只动空 session_dates 文件，安全）+ 设计文档加「冷启动/首次激活」节（含手工 MEMORY.md 备份提醒；回收收件箱 line 24）| bridgexue |
| 2026-06-05 | StratusAgent | templates/hooks/target_cleanup.py | 给已反哺的 hook 叠加 L2 deps 多版本变体裁剪（按 crate 分组、mtime 留最新 N=2、删旧变体）；脱敏下游实测数值（"deps 85GB / stratus_* 280+ 变体 / 降到 9GB"）为 normative 表述，复用上游已通用化的 find_workspace + `**` 递归 glob；快车道单条，无收件箱条目可回收 | bridgexue |
| 2026-06-09 | StratusAgent | templates/hooks/{memory_junction_check,requirements_check}.py + rule_size_check.py + rules/meta_rule_design.md + settings.json | 把 3 条「机械可判定」的 rule 约束 hook 化（v0.26.0）：①新 SessionStart hook memory_junction_check 自愈 junction（通用 project-hash 推导 + rename-to-.bak 不硬删）②新 requirements_check 查绝对URL+非ASCII ③rule_size_check 加触发器宽度检查（单段通配=伪常驻）；meta_rule §6.4/§8 校准阈值消漂移。脱敏：§10「本项目实测案例库」含 stratus/**/gateway_ctp_sopt.md 等项目专属名，整段不反哺 | bridgexue |
| 2026-06-25 | StratusAgent | templates/hooks/focus_reminder.py（+ 自用副本）| `[focus]` 措辞中性化（v0.28.2）：审问+催办语气（"还在推进它吗?…别闷头做…→/spinoff"）诱导模型把正当新任务误判为漂移 → 答非所问；改为"用户转入新任务是正常的,默认忽略"的中性提示,只在真不知不觉偏离时才纠偏。无业务术语,纯通用机制改进,7 项 checklist 全过；快车道单条无收件箱条目可回收 | bridgexue |

---

## 6. 什么时候考虑工具化

下面 3 个条件**同时满足**再考虑做 `/upstream-sync` skill：

- [ ] Playbook 已用 ≥ 3 次，流程没大改
- [ ] 脱敏 checklist 7 项里没有"凭直觉判断"的项（都能机械化）
- [ ] 有明确的"多源并发反哺"需求，手动协调成本变高

否则**别工具化** — 反哺的判断密集度太高，工具化只会把判断错误自动化。

---

## 7. 反哺的反方向：从 bridgeforge 拉新东西回下游

完整流程详见 **[sync-from-upstream-playbook.md](sync-from-upstream-playbook.md)**（2026-05-24 新建）。

核心要点：
- 同步分三类策略，按下游消费者**业务专属程度**决定：
  - **零业务专属**（hooks / scripts / 用户级 skill）→ 直接覆盖
  - **低业务专属**（settings.json）→ merge 不覆盖（保留下游 permissions / 自定义 hook）
  - **中-高业务专属**（rules / CLAUDE.md）→ 手动 diff 选择性吸收
  - **极高业务专属**（memory / doc）→ 绝对不动
- **没有 skill 自动做** — 跟反哺一样，靠人脑判断（与本 playbook 共用 §6 工具化标准）

reverse-sync 和 sync-from-upstream 互为镜像：通常**先 sync-from-upstream 拉新 → 再 reverse-sync 推增量**。

---

## 参考

- [docs/design-rationale.md](design-rationale.md) — bridgeforge 整体设计思路
- [templates/claude/rules/meta_rule_design.md](../templates/claude/rules/meta_rule_design.md) / [templates/codex/rules/meta_rule_design.md](../templates/codex/rules/meta_rule_design.md) — 怎么写 rule 才不退化（反哺时判断"通用 vs 业务"的关键依据）
