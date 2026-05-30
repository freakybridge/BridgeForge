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

## [Unreleased]

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
