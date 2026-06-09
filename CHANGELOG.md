# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本按 `templates/rules/workflow.md §9` **简版**（小项目退化版）：

- **major (X)** — 破坏性变更 / 范式重写
- **minor (Y)** — 新功能（新 hook / 新 skill / 新 rule / 新模板）
- **patch (Z)** — bug 修复 / 文档调整 / refactor

**层标签**（每条 entry 前缀，让下游一眼看懂该不该 sync，语义见 `CLAUDE.md §3`）：

- `[product]` — 改了 `templates/` / `skills/`，会下沉到下游 → 下游 sync-from-upstream 时**应当**拉取
- `[repo]` — 只改了 setup_agent 自身配置 / 工具，不下沉 → 下游无关
- `[meta]` — 只改了 `docs/` / `README` / `SKILL.md` 等说明 → 一般无关
- 混合改动并列标，如 `[product][meta]`

> **追溯说明**：v0.1.0 - v0.7.0 基于 git log 历史回溯标记，**git tag 仅从 v0.8.0 开始打**。早期未启用版本号管理是 setup_agent 自打脸问题（要求下游用但自己没用），v0.8.0 修补。

---

## [0.26.0] - 2026-06-09

### Added
- `[product]` **`templates/hooks/memory_junction_check.py`（新 hook，SessionStart）+ settings 注册** — memory junction 自愈。把 memory 纳入项目 git（`.claude/memory/`），系统路径 `~/.claude/projects/<hash>/memory/` 透明转发；每次 session 开始静默检查，不是 junction 则恢复，让"clone 即恢复"无需人工。三情形：已链接 → noop（稳态）/ 系统缺失 + 项目内有 → 建 junction（新机 clone）/ 系统是实目录 → 首迁复制后 **rename-to-.bak（绝不硬删数据）**。project-hash 从 repo root 通用推导（**每个非字母数字字符 → `-`，大小写原样保留**，如 `d:\Quant\setup_agent` → `d--Quant-setup-agent`），项目无关。补 `portability.md §2.1` 自认欠账的"待迁 SessionStart hook"。
- `[product]` **`templates/hooks/requirements_check.py`（新 hook，PostToolUse Edit|Write）+ settings 注册** — `requirements*.txt` 可移植性红线机械化：① 绝对路径 URL（`@ file://`，换机/换盘符即 fail）② 非 ASCII 字符（Windows pip 默认 GBK 解码会 UnicodeDecodeError）。非阻塞提醒。自门控：非 `requirements*.txt` 静默 no-op。对应 `portability.md §4.1/§4.2`。
- `[product]` **下游 `.gitignore` 机制块（`SKILL.md` Step 3 + 更新模式 U2 类 E）** — setup_agent 的 hook 会自动生成临时产物（Python 字节码 `__pycache__`/`*.pyc`、session 快照 `.runtime/session_state/`、hook 日志 `.runtime/*.log`），下游若无 `.gitignore` 兜底会被 `git add .` 误提交。新增：init / 更新时**幂等 append** 一段"setup_agent 机制块"到下游 `.gitignore`（缺行才补，不删项目自有项，无则新建）。**不整份 ship `.gitignore`**（避免与项目主语言耦合），只挡 setup_agent 自身机制产生的物（Python hook 是所有项目硬依赖，故这几行语言无关）。

### Changed
- `[product]` **`templates/hooks/rule_size_check.py` 增强 — 新增触发器宽度检查** — 通用启发式：frontmatter `paths` 里单段目录通配（`a/**`）或裸 `**`/`*` 等同始终加载（伪常驻），flag 之；≥2 段前缀（`a/b/**`）才算够窄。不写死任何项目名。补 `meta_rule_design.md §4.2/§8` 此前只能靠人工 self-check 的盲点。
- `[product]` **`templates/rules/meta_rule_design.md` §6.4 + §8 校准** — §6.4 TODO 占位补实：登记 rule_index_check / rule_size_check 两道护栏实际查什么 + 点明 normative 比例需人工判断。§8 self-check 阈值与 hook 对齐（版本 > 5 / 日期 > 8 / 触发器单段通配），消除"文档说 >3、hook 实际 >8"的漂移；已被 hook 覆盖的项标注【hook 已自动查】。

### Fixed
- `[product]` **`memory_junction_check.py` project-hash 编码修正（关键，dogfood 挖出）** — 旧实现只替换 `: \ /` 且强制盘符小写，**漏了 `_`/`.`** → 在路径含下划线/点的项目（`setup_agent` 自己正中此坑）算出错误 hash，找不到系统 memory 目录 → hook **静默失效（永不自愈）**。改为 `re.sub(r"[^A-Za-z0-9]", "-", path)`（非字母数字 → `-`，大小写保留），与 Claude Code 实测目录编码一致。本仓库 junction 现能正确识别。
- `[product]` **`requirements_check.py` 输入读取改双兜底** — 原只读 legacy env-var `CLAUDE_TOOL_INPUT`，CC 仅走 stdin 时永不触发。改为 stdin JSON（`tool_input.file_path`）优先 + env-var fallback，与 `allow_memory_write.py` 一致。
- `[product]` **两个新 hook 小瑕疵** — 冗余 `except (AttributeError, Exception)` → `except Exception`；`memory_junction_check._is_link` 改用 `normcase(abspath)` 规范化比较，避免实目录被误判为链接。
- `[product]` **`templates/CLAUDE.md §5` 文档对齐** — 场景 A 由"删系统目录"改述为 hook 实际的 **rename-to-.bak（绝不硬删）**，并标明由 SessionStart hook 自动执行。
- `[product]` **`templates/rules/portability.md` 补 §2.1（实体化死引用）** — 原 hook docstring / settings 注释 / 本 entry 均引用 `portability.md §2.1`，但该小节**实际从未创建**（声称补了实际没补）。本次补上，记述 memory junction 自愈机制 + project-hash 编码规则。

### Dogfood
- `[repo]` **v0.26.0 全部 hook + settings 改动镜像进自身 `.claude/`（§1 Q4 红线）** — `memory_junction_check` / `requirements_check`（新）+ `rule_size_check`（改）复制进 `.claude/hooks/` 并补 `.claude/settings.json` 注册（命令用系统 `python`）。
- `[repo]` **顺带修复 `session_snapshot.py` 历史断链** — settings 早注册了它（PostCompact + Stop）但 `.claude/hooks/` 一直缺该文件 → 每轮 Stop/PostCompact `exit 2` 报错、**memory 自动重建（艾宾浩斯评分）从未运行**。本次镜像补齐。dev `.gitignore` 同步补 `.runtime/session_state/` + `.runtime/*.log`，防 hook 产物误提交。

## [0.25.1] - 2026-06-09

### Changed
- `[product]` **`SKILL.md` Step 0.5 — 项目级重名 skill 副本改为逐个确认删除** — 此前 DUP-IDENTICAL（与上游字节一致的纯重复）是"直接删"不问，只有含项目专属数据才问用户。现统一为**每个重名副本删除前都单独问一次"删/留"**（含字节一致的纯重复），分类结果降级为给用户的"推荐动作"。理由：单一源去重是低频一次性动作，删的是项目 git 里的文件，让用户对每个重名 skill 有知情权 + 否决权，胜过省那几次确认；用户不答即保留。配套在「禁止」段补一条"❌ 批量/静默删项目级重名 skill 副本"。

## [0.25.0] - 2026-06-09

### Added
- `[product]` **用户级 skill 漂移自检 + 退役检测（支柱 B / 开机自检，设计见 [docs/skill-distribution-gaps.md](docs/skill-distribution-gaps.md)）**：
  - **`templates/hooks/skill_sync_check.py`（新 hook）+ dogfood `.claude/hooks/` + 两处 settings `SessionStart` 注册**：每次 session 开始比对 `~/.claude/skills/<skill>` 副本与上游源 `~/.claude/skills/setup_agent/skills/` 的内容哈希，**缺失/不一致/已退役**则打印一行 `[skill-sync]` 提示跑 `/setup_agent`。**只读不改**（补/更/删仍由 Step 0 在用户确认下做，绝不静默覆盖或删除）。自门控：本机没装 setup_agent → 静默 no-op（范式同 `target_cleanup.py`）。
  - **`RETIRED.md`（新增 repo 根墓碑名单）**：机器可读的"已退役 skill"清单（首条 `prune-memory` v0.24.0），让自检 + Step 0 认出"下架的 skill 还赖在架子上"——补「删除不传播」洞（正向同步只增不减）。
  - **`SKILL.md` Step 0 退役清理**：读 `RETIRED.md`，把仍在用户级架子上的退役 skill 列出来**问用户删**（Step 0.5 清"重复"副本的亲兄弟，本步清"退役"副本；绝不静默删）。
  - **范围 v1**：离线比对本机上游 clone（不 git fetch，SessionStart 必须快）；退役 **hook**（项目级，如 `memory_guard`）不在自动清理内，仍手动删。**有意未做**：带版本号的 manifest —— 内容哈希自检已覆盖"漂移/落后"，再叠 manifest 属冗余机械（反膨胀取舍）。

## [0.24.0] - 2026-06-09

### Added
- `[product]` **`SKILL.md` Step 0.5（新增）— 清理项目级通用 skill 重复副本（单一源红线）** — 通用 skill 单一源在 setup_agent（装用户级 `~/.claude/skills/`）；项目 `.claude/skills/` 里的同名副本会 shadow 单一源、各项目各自漂移。Step 0.5 对 `skills/` 清单逐个比对：DUP-IDENTICAL / 纯旧版镜像 → 删；含项目专属数据（find-doc/sync-docs 旧内联字典 → 先迁 `.map.md` 再删；其他用户定制 → 给 diff 问用户）→ **绝不静默删**。init / 更新 / 收编三模式都跑（幂等，fresh-init 空跑）。项目专属 skill（不在 `skills/` 清单里的）绝不碰。

### Changed
- `[product]` **`skills/find-doc/SKILL.md` + `skills/sync-docs/SKILL.md` — 项目专属字典/映射表外置** — find-doc 的 `topic→rule` 字典、sync-docs 的源码→文档映射，从 skill 本体内联 placeholder 改为**读项目本地** `.claude/find-doc.map.md` / `.claude/sync-docs.map.md`。skill 本体回归纯通用单一源（怎么查），项目只维护数据文件（查什么）；这是让 find-doc/sync-docs 也能安全去重（Step 0.5）的前提。Step 4/7 收尾提醒同步改为"建/补 `.map.md`"。
- `[product]` **`SKILL.md` Step 0 install loop — 改 `ls` 派生（修 find-memory 漏装）** — 安装清单从硬编码 13 名改为 `ls "$SKILLS_SRC"` 派生；历史硬编码漏了 `find-memory`（仓库 ship 但从不装用户级），`ls` 派生杜绝此类漂移，且日后增删 skill 只动目录、不改这段。
- `[product]` **`templates/rules/portability.md §2` — 记录 skills 单一源拆分** — 明确"项目专属 skill + 通用 skill 的项目数据（`.map.md`）进项目 git；通用 skill 本体**不进**项目 git，靠 `/setup_agent` 装用户级恢复"。DRY 对 clone-完整性的有意取舍。
- `[product]` **`templates/hooks/context_warning.py` + dogfood `.claude/hooks/`** — 移植下游 (StratusAgent) 已验证的「读真实 usage」机制回灌上游：弃用 char/4 文件大小估算（受 JSONL 结构开销 UUID/时间戳/JSON 信封污染、越聊越虚高），改为从 transcript 末尾倒查最近一条 assistant 消息的 `usage`（input + cache_creation + cache_read + output），与 Claude Code `/context` 一致、精确到个位 token；缺 usage 字段（旧 session/损坏）时 fallback char/4。模板侧此前一直是老的 char/4 版，本次补齐。
- `[product]` **`context_warning.py`** — `WINDOW` 默认值 200k → `1_000_000`（**反转 v0.23.2**）。动因：Claude Code 不向任何 hook 暴露 model-id 的 `[1m]` 窗口标记（transcript 剥后缀、project/user settings 无 model 字段、`~/.claude.json` 无激活 model、env 无 model 变量、切 model 不触发 hook、仅 SessionStart 带 model 但同样剥 `[1m]`），hook 无法自动判窗口；默认 1M 让 1M Opus 主力用户开局即准。**权衡（已知并接受）**：标准 200k 模型项目若忘记手动下调 WINDOW，会因分母过大永不预警（静默 compact 风险），实例化后须手动改回 `200_000`。

### Removed
- `[product]` **废弃手动 MEMORY.md 治理整代：`memory_guard.py` hook + `prune-memory` skill 退役** — 删 `templates/hooks/memory_guard.py`（185 行硬阻断）+ dogfood `.claude/hooks/` + 两处 settings 注册；`prune-memory` skill 正式废弃（手动引导式裁剪）。动因：`memory_rebuild`（Stop hook 自动评分，封顶活跃 40 条 + >45 天冷区化）已把 MEMORY.md 自动控制在 ~45 条、且改由机器每轮重排 —— 185 cap 从不触发，手动 prune 成冗余。`summary` skill / `docs/memory-scoring-design.md` 内 `/prune-memory` 引用一并清理。**下游**：已装项目若有 `memory_guard.py` / `prune-memory/`，需手动删（update 模式暂不自动删"上游已移除"的文件）。

## [0.25.0] - 2026-06-05

### Added
- `[product]` **`templates/hooks/target_cleanup.py` 加 L2 deps 变体裁剪** — 在原 L1（incremental/ 体积触发清）之上新增第二遍 pass：扫 `target/**/deps`，按 crate 分组、每组按 hash 的 max mtime 只留最新 `DEPS_KEEP_VARIANTS=2` 个变体、删更旧的。治本 deps/ 里同一 crate 旧 hash 变体无限堆积（本地 workspace crate 因频繁重编尤甚，长期占 target 绝大头）的问题。安全设计：留 2 给足余量（当前变体即便第二新也存活）、只动 ≥3 变体的 crate（稳定 deps 不碰）、无 hash 当前产物正则不匹配永不删、可回收 < `DEPS_MIN_FREE_GB=5` 跳过避免扰动；run_worker 重构成 L1+L2 两遍 pass 共用节流。下游实测删旧变体后 `cargo build` 仍为增量（仅本地 crate 因 incremental 缓存被清重编一次，deps 全复用）。来源 StratusAgent harvest

## [0.24.0] - 2026-06-05

### Added
- `[product]` **`templates/scripts/memory_bootstrap_cold.py`（新脚本）** — 冷启动一次性引导：把从未被 recall（`session_dates` 为空）的 memory 的 `created_at` 拨到数周前，使其立即沉入 Cold 区，让 Hot 区在首次铺设/重置后立刻收敛成"近期 recall 过的"，跳过约 1-2 周自愈期；只动空 `session_dates` 文件（`created_at` 对已 recall 文件是死字段，绝对安全）。来源 StratusAgent harvest
- `[meta]` **`docs/memory-scoring-design.md`** — 加「冷启动 / 首次激活」节：首次重建覆盖手工 MEMORY.md 的备份提醒 + Hot 区头 1-2 周随机的成因 + bootstrap 引导 + 安全不变量

## [0.23.2] - 2026-06-03

### Fixed
- `[product][repo]` **`context_warning.py`** — `WINDOW` 默认值从 1M 改为 200k（标准版 Opus 4.8 / Sonnet 4.6 / Haiku 4.5 默认 200k context，1M 专用版才需改为 1_000_000）；同步更新注释中的模型版本说明；dogfood 同步 `.claude/hooks/` 与 `templates/hooks/`

## [0.23.1] - 2026-06-03

### Fixed
- `[product]` **`templates/scripts/memory_search.py`** — `main()` 顶部加 stdout UTF-8 reconfigure（`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`），防止 Windows 中文环境下 memory 文件名/内容输出乱码或报 UnicodeEncodeError；来源 CausisRiskSuite harvest

## [0.23.0] - 2026-06-03

### Added
- `[meta]` **`docs/memory-scoring-design.md`（新文档）** — Memory 热度评分系统完整设计规范（艾宾浩斯衰减公式 + 五组件架构 + 决策记录），来源 2026-06-03 双轮 debate
- `[product]` **`templates/hooks/memory_access_tracker.py`（新 hook）** — PostToolUse/Read：检测 memory 文件访问，快速预过滤后写入 `_stats.json` 唯一日期，防突发读取污染
- `[product]` **`templates/hooks/session_snapshot.py`** — Stop 末尾追加调用 `memory_rebuild_index.py`（`_rebuild_memory_index()`），闭合触发链路
- `[product]` **`templates/scripts/memory_rebuild_index.py`（新脚本）** — 按艾宾浩斯衰减分重建 MEMORY.md 热区 + MEMORY_COLD.md 冷区；Stop hook 末尾调用
- `[product]` **`templates/scripts/memory_search.py`（新脚本）** — 关键词 grep 搜索 memory/ 所有文件，由 /find-memory skill 调用
- `[product]` **`templates/memory/_stats.json`（新模板）** — 访问记录初始模板，含 config（hot_n/pinned）+ files{}
- `[product]` **`skills/find-memory/SKILL.md`（新 skill）** — 按需 memory 搜索，Claude 找不到热区记录时调用
- `[product]` **`templates/settings.json`** — PostToolUse/Read 追加 `memory_access_tracker.py` 注册

### Known TODO
- 端到端测试：新项目 setup → 写 memory → Stop → 验证 MEMORY.md 重建正确

## [0.22.0] - 2026-06-03

### Added
- `[product]` **`templates/hooks/memory_guard.py`（新 hook）** — PreToolUse 硬阻断：Write/Edit 到 MEMORY.md 超 185 行时 exit 2，提示 `/prune-memory`。补全 `memory_lint.py`（PostToolUse 非阻塞警告）缺失的"阻止写入"环节
- `[product]` **`skills/prune-memory/`（新 skill）** — 引导 Claude 按删留标准逐章节分析 MEMORY.md 条目，展示 🔴/🟡/🟢 候选清单，用户确认后执行删除并移档至 `memory/archive/`
- `[product]` **`templates/settings.json`** — 在 PreToolUse `Write|Edit` hook 数组追加 `memory_guard.py` 注册

## [0.21.1] - 2026-05-31

### Added
- `[meta]` **`INSTALL.md` 新增「开发者模式：junction 指向开发仓库（单一真相源）」小节**，并给「升级」节补注记。澄清一个长期文档缺口：INSTALL 主安装流程教的是直接 `git clone` 到 `~/.claude/skills/setup_agent`（在 C 盘留**真实副本**），但维护者本人（既用又改 setup_agent、做下游 harvest）实际跑的是 **junction 模式**——开发仓库放工作区（如 `D:\Quant\setup_agent`），`~/.claude/skills/setup_agent` 只是 junction 透明入口，物理一份、改即生效
  - 此前该模式只在 `README.md` 自举提示里顺带提过一句，没有正式集中说明；文档系统大量讲的 junction 其实是 **memory junction**（另一回事）
  - 附「验真 & 防骗」：`Get-Item ... -Force` 看 `LinkType: Junction` / `Target`；**Glob 会穿透 junction** 把同一份列成两份一模一样的内容（连 `.git/objects` 哈希都对应），别误判成两个独立副本。经验已存本仓 memory `project_skill_junction_single_source`
  - **不触发 dogfood 镜像红线**（§1 第4问只管 hook / settings，这是元文档）；不下沉、下游无关

### Added
- `[product]` **`SKILL.md` Step 0 新增"全局 CLAUDE.md 自检"**：`/setup_agent` 执行时自动检查并补全用户 `~/.claude/CLAUDE.md` 里的"Glob 查文件"规则（幂等，已有则跳过）。补完后，该用户所有项目、所有新对话都不会因为 agent 反射性用 shell 搜文件而触发权限弹窗。`~/.claude/CLAUDE.md` 不存在的新用户跳过此项（只靠项目级 `CLAUDE.md §2.5` 兜底）

## [0.20.0] - 2026-05-31

### Added
- `[product]` **`templates/CLAUDE.md` 新增 §2.5「工具选择：检索用 Glob/Grep，执行才用 shell」**。源自本仓实测——Windows 下 agent 反射性用 PowerShell `Get-ChildItem` 查文件，一旦访问工作目录外路径（如 C 盘根）就频繁触发权限弹窗，噪音大且无谓
  - **结论**：找文件 / 查内容优先 `Glob` / `Grep` / `Read`（受控只读、零弹窗、跨平台、不可夹带删改），同时满足用户三诉求"能用 / 清净 / 底线安全"；shell（PowerShell / bash）保留给构建 / git / 进程 / 系统配置等"真要执行"的动作 —— 是各司其职，不是淘汰 shell
  - **为什么进 `CLAUDE.md` 而非 `workflow.md`**：查文件是**每个任务**都会发生的反射，必须 always-on。`workflow.md` 是 `doc/` / `rules/` path-gated，只在改文档时加载，会漏掉最需要它的编码场景（同 §1「跨任务通用规矩进 CLAUDE.md」的逻辑）
  - 附「Glob 三诀」防空手而归：`path` 给具体防超时 / 匹配文件非目录（找文件夹写 `**/foo/**`）/ 默认跳过 `.` 开头隐藏目录（目标在 `.claude` 内时把 path 扎进去）
  - **不触发 dogfood 镜像红线**（§1 第4问只管 hook / settings，这是 rule 内容）；setup_agent 自身经验已存本仓 memory `feedback_glob_search_gotchas`，自产自用已覆盖

## [0.19.0] - 2026-05-30

### Added
- `[product]` **新 hook `templates/hooks/target_cleanup.py`（SessionStart）：Rust 项目 target/incremental 缓存体积触发式清理**。源自下游实测——Rust workspace 的 `incremental/` 缓存会无界膨胀（实测可达数十万小文件 / 200GB+），拖垮磁盘 I/O 致整机发黏（CPU/内存却正常、重启才好）
  - **为什么不用 cargo-sweep**：`cargo sweep --time N` 看文件**访问时间(atime)**，但 Windows 上 Defender 实时扫描 / 每次 build / 目录遍历都刷新 atime，陈年产物长期"看起来热"而清不动（下游实测 `--time 3` 对 200GB+ 缓存只肯清几百 KiB）。atime 在开杀软的 Windows 上不是可靠冷热信号
  - **机制**：改用可信信号 incremental/ **体积**。超 `THRESHOLD_GB`(30) 时先把 `incremental` 瞬间改名为 `.trash`(cargo 立刻能建新的)，再后台慢删；量体积 + 删除全在 detached worker，不阻塞 session 启动。incremental 是纯缓存、100% 可再生，删整个目录绝对安全（cargo 下次 build 自动重建，deps 保留）
  - **自门控 = 条件加载**：`find_workspace()` 无 Cargo.toml 即静默 no-op，故 `templates/settings.json` 无条件挂 SessionStart 对非 Rust 项目零影响，且项目后来新增 Rust crate 会自动激活——比"setup 时按主语言裁剪"更稳，无需改主 SKILL.md
  - `templates/settings.json` SessionStart 注册该 hook（带 `comment` 说明 Rust-only + 自门控）
  - 自测入口 `--dry-run`（前台量体积 + 报告会删什么，不删/不改名/不写时间戳），便于 harvest 后在新项目验证
  - 扫描用 `target.glob("**/incremental")` 递归挖到底：既覆盖普通编译 `target/{debug,release}/incremental`，也覆盖交叉编译 `target/<triple>/debug/incremental`（多埋一层，`*/incremental` 单层 glob 会漏）
- `[product]` **新 hook `templates/hooks/allow_memory_write.py`（PreToolUse Write/Edit）：放行 memory `.md` 写入免弹窗**。根因——`.claude/` 是 Claude Code 受保护目录（连同 `.git`/`.vscode`/`.idea`/`.husky`/`.cargo`），写入无视 `acceptEdits` 和 `permissions.allow` 规则强制弹窗（求值序 deny→ask→allow，受保护优先于 allow）；本范式 memory 在 `.claude/memory/` 下被连带保护，导致每次保存记忆都弹窗
  - **试过的死路（实测全失败）**：① `permissions.allow` 加 `Write(...)`/`Edit(...)` 规则，三种路径格式（`C:\\` 反斜杠 / `//c/` POSIX / 项目相对）全被保护层压过；② `additionalDirectories` 列 memory 目录——只解除"能访问"不免确认；③ 把 memory 搬出 `.claude/`——能修但牺牲"记忆与配置内聚"，被否决
  - **治本**：PreToolUse hook 抢在权限弹窗之前返回 `permissionDecision:allow`（位置比那道问话更靠前，实测能压过受保护目录）。只放行 memory 的 `.md`，settings/hooks 本体不碰，安全边界不破
  - `templates/settings.json` PreToolUse 注册该 hook（matcher `Write|Edit|MultiEdit|NotebookEdit`）
  - **改完须开新会话生效**（hook 不热重载）。详见下游 memory `feedback_claude_dir_protected_memory_write_hook`
- `[repo]` **dogfood：上面两个产品层 hook 当场镜像进自身 `.claude/`**。`allow_memory_write.py` + `target_cleanup.py` 复制进 `.claude/hooks/`，`.claude/settings.json` 注册（命令前缀按 dev 仓库无 `.venv` 改用系统 `python`）。`allow_memory_write` 对 setup_agent 自己的 `.claude/memory/` 实有收益；`target_cleanup` 非 Rust 永远自门控 no-op，挂着 = 持续验证「无 Cargo.toml 静默跳过」这条产品承诺。已实测：JSON 合法、target dry-run 正确跳过、memory `.md` 放行 / 非 memory 不干预
- `[repo][meta]` **「传播三问」升级为「传播四问」**：新增第 4 问——产品层 hook/settings 改动必须当场镜像进自身 `.claude/` 吃狗粮（红线）。本次正是漏了这一环才补立。同步更新 `CLAUDE.md §1`/§2/§4、`docs/design-rationale.md §9.1`/§9.3 的措辞

## [0.18.1] - 2026-05-29

### Added
- `[repo]` **dogfood：setup_agent 自己也装上 ctx 预警 hook**。此前自身 `.claude/hooks/` 只有 `version_check`，缺它发给下游的 `context_warning`（"工厂不吃自己的狗粮"）
  - 复制 `templates/hooks/context_warning.py` → `.claude/hooks/`，并在 `.claude/settings.json` 注册 `UserPromptSubmit`（系统 `python`，dev 仓库无 .venv）。WINDOW=1_000_000 适配 Opus 1M
- 注：仍缺 session_snapshot / show_state 等其余 hook 的 dogfood（memory_lint / rule_index/size_check 因 setup_agent 自身无 .claude/rules、memory 结构，不适用）

## [0.18.0] - 2026-05-29

### Changed
- `[product]` **`templates/settings.json` 权限机制重做为三档：放宽 allow（压噪音）+ 新增 ask（要紧项必弹）+ 加厚跨平台 deny（拦灾难）**。设计目标：**弹窗的每一个都尽量是"需慎重的决策"，而非被训练成无脑确认**
  - **allow 放宽**（3 → 67 条）：日常安全命令静默放行——git 读/常规写（status/diff/log/add/commit/fetch/pull/stash…）+ shell 读（ls/cat/head/grep/find…）+ 构建测试（npm/cargo/pytest/python/node/go/make/maturin…）+ PowerShell 读 cmdlet。**allow 越全，弹窗噪音越少**（与"弹窗即信号"目标一致；deny 优先级更高，publish/branch -D 等危险子命令仍被 deny 碾过）
  - **ask 新增**（7 条）：**强制弹窗**的"慎重决策"类——`git push / rebase / reset / checkout / restore / merge / cherry-pick`（远程/历史/可丢改动）。ask 优先级高于 allow，即使将来被"别再问"误加进 allow 也照样弹
  - **deny 加厚**（11 → 60 条）：安全地板（优先级最高、`bypassPermissions` 下仍生效）。凭证读+写 / git 历史销毁 / POSIX 破坏性 / **Windows·PowerShell 破坏性（补上之前 POSIX-only 的洞）** / 对外发布 / 系统级；含 PowerShell 的 `Remove-Item`（别名自动覆盖 `rm`/`del`/`rmdir`）+ force-push/reset --hard/clean 镜像

### Note
- **三档 = 静默 / 弹窗 / 拦死**，对应"日常 / 慎重 / 灾难"。模式仍 `acceptEdits`：未在任何清单的陌生命令默认**弹窗**（安全），靠"别再问" + `/fewer-permission-prompts` 把 allow 养肥、噪音随时间递减。**不追求 dontAsk 的"100% 弹窗皆要紧"**，因其代价是陌生命令静默罢工（决策见本会话讨论）
- **此前 deny 是 POSIX-only（只拦 Bash `rm`），但用户在 Windows** —— `Remove-Item -Recurse -Force` 完全没拦，是真实漏洞，本版用 PowerShell matcher（语法经 claude-code-guide 核实）+ 别名 canonicalization 补齐
- `git push --force:*` 的空格词边界**不会**误伤 `--force-with-lease`（带安全检查的强推照常放行）
- **deny 是减速带不是保险柜**：靠命令字样匹配，子进程（`python -c "open('.env')"`）可绕过。它防 agent **手滑误删/误推**，真正恢复底牌仍是 git 历史 + 备份。故意**未** blanket-deny `python`/`node`（会废掉跑脚本/测试）
- **PowerShell 覆盖侧重**：Claude 主要走 Bash 工具，故 allow/ask 以 Bash 为主；PowerShell 侧覆盖读 cmdlet（allow）+ 破坏性命令（deny）。PS 跑构建若未 allow 会弹窗（B 模式安全默认），点"别再问"自增长
- `[repo]` dogfood：setup_agent 自己的 `.claude/settings.json` permissions 块已镜像本版三档（allow/ask/deny），与 `templates/settings.json` 一致 —— 总部自己也受同款 Windows 删除防护，不再"卖防盗门自家门敞着"。hooks 段保持 repo 特异性（系统 `python` + 最小 hook 集，dev 仓库无 `.venv`），不在镜像范围

## [0.17.0] - 2026-05-29

### Fixed
- `[meta]` **Step 0 自检堵住"改进流不到已装下游"的传播缺口**：原"逢重名 skill 一律跳过"虽保护用户定制，但副作用是**升级已有 skill 永远到不了老项目**（本会话给 `summary` 加捕捉反射就会卡在这）
  - `SKILL.md` Step 0 循环改为三分支：缺失→装 / 与上游**一致**→静默更新（无定制可保护）/ **不一致**→给 diff 问用户（覆盖 or 保留定制），**绝不静默覆盖**
  - 判断逻辑与「更新模式」§U2 类 A 对齐（一个事实源两处复用）；同步修正「禁止」段"已存在 skill 跳过不覆盖"为"先比对，不静默盖定制"

## [0.16.0] - 2026-05-29

### Added
- `[product]` **反哺机制落地为两个命令：`/summary`（捕捉）+ `/harvest`（推送）**，捕捉/推送分离
  - `skills/harvest/SKILL.md` **新建**（第 13 个通用 skill）：推送侧。无参=读下游 `.claude/harvest-inbox.md` 批量清；带描述=立即单条快车道。两入口汇进同一套脱敏 harvest 仪式（判通用性 → §3 七项脱敏 → 写 `templates/` → bump+CHANGELOG → 记日志 → 回收收件箱 → 给 diff 不自动 push）
  - `skills/summary/SKILL.md` 新增**第 6 步「反哺候选捕捉」**：summary 顺手判"本轮经验是否通用"，通用的追加一行进 `.claude/harvest-inbox.md`（收件箱）。捕捉是 summary 副产品，零新纪律
  - `SKILL.md` Step 0 自检循环加入 `harvest`（12→13 个 skill），各处计数 + 速查表 + 模板速查表同步
- `[meta]` `docs/reverse-sync-playbook.md` §1 触发时机重写：标注 v0.16.0 起捕捉/推送分离；触发从"凭感觉≥3条"升级为"收件箱≥3行（可数）"+ `/harvest <描述>` 快车道；强调"两个入口一个仪式"不分叉
- `[meta]` `docs/design-rationale.md` §7「不做什么」新增"**不监督下游合规**（不做 doctor / fleet）"——记录单项目体检 + 多项目合规盘探讨后**否决**的决定与理由（出版方非监管方 / 合理例外噪音 / 要可信须 PULL 而非 PUSH 自报 / junction 隐患已被开机自检覆盖），防止将来重提。与 §9.3"镜像漂移检查 hook"（工厂自查）区分

### Note
- **设计要点**：反哺真正的痛点不是"推送"（推送必须人工脱敏，公开 repo 不能自动化），而是"等盘点时已忘了学过啥"。故拆分——**捕捉做到当场零成本（搭车 `/summary`），推送保持人工批量**。复用 sync-from-upstream 的"机械半场/判断半场"拆分哲学
- **收件箱文件** `.claude/harvest-inbox.md` 用 ASCII 名（可移植）；是 per-下游项目文件，纳入下游 git
- 下游获得本能力需 sync：Step 0 自检会补 `harvest` skill（但**已存在的 skill 不覆盖**——存量下游的 `summary` 升级需手动覆盖或重装该 skill）

## [0.15.0] - 2026-05-29

### Added
- `[meta]` **`/setup_agent` 进门「认场子」四分类 + 工厂自检硬闸**：前置步骤从"有戳=更新 / 无戳=init（含一个 A/B 例外）"重做成判别树
  - `SKILL.md` 前置新增 **Step 前-2 工厂自检**：cwd 同时有 `templates/CLAUDE.md` + 自己的 `SKILL.md` → 硬拒（堵死"在 setup_agent 源头自己身上跑 bootstrap / 更新"的自伤，2026-05-29 实测可复现）
  - `SKILL.md` 前置 **Step 前-3** 改为四分类表 + setup_agent 衍生指纹判据（鬼打墙 / ctx-budget / `OPTIONAL_BEGIN` 残留 / `meta_rule_design.md` 等，命中 ≥2 即判"像铺过的"）
  - `SKILL.md` 新增 **「## 收编模式 (adopt)」** 主段：无戳但像衍生的项目走"登记纳管，绝不覆盖"——写戳=当前 VERSION 作同步基线，可选补差。固化此前靠 agent 临场判断的安全路径
  - `SKILL.md` 更新模式 U1 新增 **`[product]` 短路**：`(上次, 现在]` 区间无 `[product]` 条目 → 不跑全量 diff，直接刷戳退出（CHANGELOG 标签分布实测近半 bump 与下游无关，省空跑）
  - `SKILL.md` 禁止段补"不在源头仓库自己身上跑"
- `[meta]` `docs/design-rationale.md` §9.4「工厂自身不带版本戳——靠 `templates/` 存在性识别」：把"源头无戳"从 v0.14.0 潜在自伤正式定性为设计意图，附推论"识别项目类型优先用结构性事实而非约定标记"

### Note
- 本批次**全是 setup_agent 自身行为（SKILL.md）+ 元文档（design-rationale）改动**，产品层 `templates/` / `skills/` 未动 → 下游无新增量（无 `[product]` 条目）。下游下次跑 `/setup_agent`（pull 到本版后）自动获得新的认场子行为，无需 per-project sync
- frontmatter `version:` 字段顺手从滞后的 `0.9.1` 对齐到 `0.15.0`（自 v0.9.1 起漏更新的历史遗留）

## [0.14.0] - 2026-05-29

### Added
- `[product]` **`/setup_agent` 更新模式**：不新增 skill，把"拉上游增量到现有项目"并入 `/setup_agent` 自身（一个命令两用：全新项目 init / 已铺过项目更新）。下游在已铺过的项目里重跑 `/setup_agent` 即自动进更新模式
  - `SKILL.md` 新增「前置」步骤：先 `git -C ~/.claude/skills/setup_agent pull --ff-only` 拉上游最新（init/更新都先拿最新，堵住"铺旧版本"坑）+ 按 `.claude/.setup_agent_version` 判定 init/更新模式
  - `SKILL.md` 新增「更新模式」主段（U1 算增量→抓 `[product]` changelog / U2 按 sync-from-upstream §2 表格分类 diff / U3 路径适配 / U4 验证+收尾），机械半场自动、判断半场（类C rules/CLAUDE.md）全程人脑
  - `SKILL.md` Step 7 + 复制清单 + 速查表：init 末尾写 `.claude/.setup_agent_version`（= 安装时版本，既作"上次同步到哪版"记录，又作 init/更新判定信号）
- `[meta]` `README.md` 使用段重构：开头新增「新项目初始化——对 agent 说这一句」自带兜底引导（没装过先 clone+junction 自举、装过直接铺），并保留「更新已有项目（重跑即更新）」说明

### Changed
- `[meta]` `docs/sync-from-upstream-playbook.md` §6：标注机械半场已并入 `/setup_agent` 更新模式（判断半场仍人脑，不违反"别把判断错误自动化"红线）；§5 日志追加 v0.14.0 行

### Note
- **存量项目**（已装过但无版本戳，如早期下游）首次重跑 `/setup_agent` 时落到「前置」例外分支：当作 init 处理已存在文件 + 补写版本戳纳入管理
- 「③ 镜像漂移检查 hook」仍未做（延续 v0.13.0 节奏）

## [0.13.0] - 2026-05-29

### Added
- `[repo]` **工厂自觉前门闸**：新建 setup_agent 自己的 `CLAUDE.md`（之前缺失，自产自用只落实了 version_check 一小块）。核心是 §1「传播三问」always-on 红线——每个改动落地前必须回答 (1) 属于哪一层（产品 `templates`/`skills` vs 自身配置 `.claude` vs 元文档 `docs`/README/SKILL）(2) 通用的话镜像进 `templates/` 了吗 (3) 要不要 bump + 记 CHANGELOG。附 §2 分层地图 + §3 CHANGELOG 层标签约定 + §4 传播机制指引
- `[meta]` `docs/design-rationale.md` §9「setup_agent 的双重身份：工厂 + 自产自用」：固化 framing（工厂 vs 样板间两个身份）+ §9.1 前门闸 + §9.2 CHANGELOG 层标签为何能让下游有抓手 + §9.3 演进节奏（软规则先跑顺再升级为「镜像漂移检查 hook」机制）

### Changed
- `[meta]` `CHANGELOG.md` 顶部图例新增「层标签」说明（`[product]`/`[repo]`/`[meta]`），本版起所有 entry 打标签，下游 `grep "\[product\]"` 即得 sync 增量清单

### Note
- 本批次**全是 setup_agent 自身改动**（前门闸机制 + 元文档），**没有改产品层**——下游无新增量（故无 `[product]` 条目）。属 reverse-sync-playbook §3.1 批次 3 同类「非反哺批次」
- 「③ 镜像漂移检查 hook」本版**未做**——按演进节奏，等三问软规则跑顺 2-3 次、误报场景摸清后再机制化（见 design-rationale §9.3）

## [0.12.0] - 2026-05-29

### Changed
- **策略变更：Python 从「可选」改为「硬依赖」**。所有下游项目（含纯 rust / node / go）安装 setup_agent 时都安装整个 Python hook 体系，不再因主语言非 Python 而跳过 hook。主因：`version_check` 等红线 hook 价值与语言无关，不该因语言失去
  - `SKILL.md` Step 3：「Python hook 体系条件复制」→「所有项目无条件安装」+ 新增「前置硬检查」（无 Python 则停下要求先装）；「Python 解释器路径适配」适用范围改为所有项目；「非 Python 项目跳过说明」→「目标机无 Python 时的处理」（给装 Python 修复路径）
  - `SKILL.md` 复制清单表：hooks/scripts 复制条件 `仅 Python 项目` → `总是`
  - `README.md` 「Python 依赖」段重写：硬依赖声明 + 解释器优先级（.venv → 系统 python → 要求安装）+ 为什么强制 Python

### Added
- **setup_agent 自产自用**：dev 仓库自己装上 `version_check` hook（之前只把它作为模板分发给下游，自己 commit 不受约束 → 历史上自己反复忘 bump）
  - `.claude/hooks/version_check.py`（从 templates 复制）
  - `.claude/settings.json` 注册 PreToolUse(Bash) → version_check，用系统 `python`（dev 仓库无 .venv）

## [0.11.0] - 2026-05-29

### Added
- `templates/hooks/version_check.py` 新 hook：PreToolUse(Bash) 拦截 `git commit`，staged 改动未含版本号 SoT 文件（`VERSION`/`package.json`/`Cargo.toml`/`pyproject.toml`）则 `exit 2` 阻断 → 把 workflow.md §9「每次 commit 必 bump」从软规则升级为**机制硬强制**。`[skip-version]` / `--amend` / 正在 merge / 无版本号文件 可豁免。**未来所有 Python 项目装 setup_agent 时自动注册**（随 templates/hooks + settings.json 下沉）
- `templates/settings.json` PreToolUse 新增 Bash matcher 注册 version_check.py
- `templates/rules/workflow.md` §9.8「自动强制」：说明 hook 兜底机制 + 历史教训（§9 软规则被忘过多次）

### Changed
- `SKILL.md` Step 3 hook 条件复制：修正非 Python 项目应删**整个 hooks 块**（原文漏列 PreToolUse / PostToolUse，会残留死 hook）；明确 `permissions` 块必须保留
- `SKILL.md` 非 Python 跳过说明 + 模板速查表：补 version_check.py / find-doc / permissions 等丢失/保留项

## [0.10.0] - 2026-05-29

### Added
- `templates/settings.json` 新增 `permissions` 块，下沉「少弹框」黄金组合到所有下游项目：
  - `defaultMode: acceptEdits` — 文件编辑（Write/Edit）默认放行，不再逐个弹框
  - `allow` allowlist — 只读工具（Read/Grep/Glob）+ git 看状态类（status/diff/log/show/branch/fetch）+ ls/cat/pwd
  - `deny` 安全闸口 — 挡不可逆操作（`rm -rf` / `git push --force` / `git reset --hard` / `git clean -f`）+ 敏感文件读取（`.env` / `secrets/**` / `*.key` / `*.pem`），deny 优先级最高，bypass 模式下仍生效
- `SKILL.md` Step 1：settings.json merge 逻辑扩展——除 hooks 外，新增 `permissions.allow/deny` 数组追加去重 + `defaultMode` 仅在用户未设时才写（不覆盖用户已有偏好）
- `SKILL.md` 模板速查表：`settings.json` 行补充 permissions 块说明

### Note
- 下游已有项目不自动获得（permissions 只随**新** `/setup_agent` 安装下沉）；存量项目需手动 merge 或重跑 skill 的 settings 合并步骤
- 白名单设计为「精选起步 + 留白」——常用但因人而异的命令交给权限弹框的「别再问」选项自增长，或 `/fewer-permission-prompts` skill 批量补齐

## [0.9.1] - 2026-05-29

### Changed
- 4 个写文档/轻量类 skill 的 `SKILL.md` frontmatter 加 `model:` 字段（利用官方机制 skill 激活期间临时切模型，结束自动恢复）：
  - `sync-docs` / `summary` → `sonnet`（写文档为主，能力够用速度更快）
  - `todo` / `archive-scan` → `haiku`（轻量追加 / 批量 git mv，无需推理）

### Fixed
- 版本号自打脸 v3：v0.9.0 commit (`4aa57c2`) 写了 CHANGELOG 但漏打 git tag → 本次补打 `v0.9.0` tag；`50edbac` 改 skill 配置时也漏走版本号流程 → 本版补齐

## [0.9.0] - 2026-05-24

### Added
- `templates/VERSION`（初始 `0.1.0`，下游项目无原生版本源时用）
- `templates/CHANGELOG.md`（通用骨架，引用 `rules/workflow.md §9` SemVer 语义，所有下游项目无条件复制）
- `SKILL.md` Step 3：新增"版本号 SoT 条件复制"段（检测 `package.json` / `Cargo.toml` / `pyproject.toml` → 跳过 VERSION 避免双 SoT；CHANGELOG.md 仍统一复制）
- `SKILL.md` Step 3 复制清单 + 模板速查表：新增 VERSION / CHANGELOG.md 两行
- `README.md` 新增"未反哺的上游 hook（为什么不在 templates 里）"段，明列 `cargo_check.py` 等语言/业务专属 hook 不反哺的判断标准
- `docs/reverse-sync-playbook.md` 新增 §3.1 实战记录（v0.6.0 / v0.7.0 / v0.8.0 三次反哺的 checklist 实例化）+ §3.2 元规则（含"禁止虚构踩坑故事"红线）

### Fixed
- 自打脸 v2：v0.8.0 给 setup_agent 自己装了版本号但**没下沉到 templates**，下游项目装完 `/setup_agent` 仍然没有版本号机制 → 本版闭环

## [0.8.0] - 2026-05-24

### Added
- `VERSION` 文件（单一事实源，符合 workflow.md §9.1）
- `CHANGELOG.md` 本文件
- `SKILL.md` frontmatter `version: 0.8.0` 字段
- `skills/resume/SKILL.md` **Step 5**：用户确认接续后主动建议对话框重命名（避免 `/resume` 默认 session 名 "resume" 无指导性，多 session 并发时无法区分内容）

### Fixed
- 自打脸：setup_agent 之前要求下游用版本号但自己没用 → 本版补齐版本号机制

## [0.7.0] - 2026-05-24（追溯，commit 4b976da）

### Added
- 反哺 5 个通用 hook：`memory_lint.py` / `rule_index_check.py` / `rule_size_check.py` / `find_doc_reminder.py` / `show_state.py`（脱敏简化版）
- `templates/settings.json` 扩展到 6 类 hook 注册段（PreToolUse / PostToolUse / PostCompact / Stop / UserPromptSubmit / SessionStart）
- `templates/rules/modules.md §3.1 §3.2` 从 causis_risk_suite 反哺（协调中枢三块分层 + 提炼共享常量三件套）
- `docs/sync-from-upstream-playbook.md`（与 reverse-sync-playbook 互为镜像，按业务专属程度分 4 层决定覆盖策略）

### Changed
- `SKILL.md` Step 3 改造：加 Python hook 体系条件复制（基于 Q2 主语言）+ 无 `.venv` fallback + 非 Python 项目跳过说明
- `docs/reverse-sync-playbook.md §7` 改为引用新 sync-from-upstream playbook 的精简版

## [0.6.0] - 2026-05-24（追溯，commit 9cfa7ae）

### Added
- `templates/hooks/session_snapshot.py`（脱敏简化版 ~150 行，去 tag 逻辑 + 通用版本检测）
- `templates/scripts/archive_scan.py`（通用版直接 cp）
- `templates/settings.json` 加 PostCompact + Stop hook 注册
- `README.md` "Python 依赖（agent 安装前必读）"段
- `docs/reverse-sync-playbook.md §4` 白名单扩展（加 `templates/hooks/` + `templates/scripts/`）
- `skills/find-doc` + `skills/sync-docs` SKILL.md 末尾加 placeholder 检测与提醒段

## [0.5.0] - 2026-05-24（追溯，commit d73ea5a）

### Added
- 反哺 StratusAgent + causis_risk_suite 经验：
  - `templates/rules/portability.md §4.3-§4.5` 多项可移植性约束
  - `templates/rules/workflow.md §9` 拆细为 §9.1-§9.7（Milestone-bound SemVer 详细版）
  - `templates/rules/meta_rule_design.md`（新建，元规则）
- `README.md` "适合/不适合"诚实段
- OPTIONAL 段落物理裁剪机制（`<!-- OPTIONAL_BEGIN PLATFORM/LANG/SCENARIO -->`）
- `templates/CLAUDE.md §11` doc/ 红线化

### Removed
- `session-tag` skill（过度设计，整目录删 + snapshot/resume 里的 tag 引用清理）

## [0.4.0] - 2026-05-23（追溯，commit fa8c75f）

### Added
- 13 个通用协作 skill：`archive-scan` / `collab` / `debate` / `escalate` / `find-doc` / `git-sync` / `plan` / `resume` / `session-tag` / `snapshot` / `summary` / `sync-docs` / `todo`（**`session-tag` 后于 v0.5.0 删除**）
- setup_agent SKILL.md 加 skill 自检流程

## [0.3.0] - 2026-05-09（追溯，commit 88db438）

### Added
- `templates/hooks/context_warning.py`（ctx-budget 红线 hook — 跨 75/85/95% 阈值预警）
- `templates/CLAUDE.md §10` ctx-budget 信号响应红线

## [0.2.0] - 2026-05-08（追溯，commit 2ed5df2）

### Added
- doc/ 分层引入 acceptance + TODO-INDEX 二分语义（短期 vs 远期 backlog）

## [0.1.0] - 2026-05-01（追溯，commit 7f30c9a）

### Added
- setup_agent skill 骨架初始化（CLAUDE.md / rules / memory junction / doc 基础模板）
