# bridgeforge

> AI 项目协作骨架初始化器。支持 Claude / Codex 双骨架，一行 skill 命令铺好入口说明、rules、memory、hooks 与 doc 分层归档。

## 适合 / 不适合什么项目

模板素材出自 [StratusAgent](https://github.com/freakybridge/StratusAgent)（量化交易终端，中大型 Rust + Python 项目）+ [causis_risk_suite](https://github.com/freakybridge/causis_risk_suite)（金融风控 Python 项目）长期沉淀。所以默认体系**偏中大型项目 + 多模块 + 长周期 + Sprint 节奏**。

| ✅ 适合 | ⚠️ 不太适合（裁剪后可用） |
|--------|---------------------------|
| 中大型应用（≥ 5 个模块） | 单脚本 / 周末玩具 |
| 长周期项目（≥ 3 个月） | 一次性 demo |
| 有 Milestone / Sprint 节奏 | Jupyter Notebook 数据分析 |
| 多人协作 + AI 协作 | 静态文档站（如 Hugo / VitePress） |
| 后端服务 / 桌面应用 / 多 Gateway 集成 | 移动 app（无 doc/ 分层需求） |
| 需要长记忆 + ctx 预警 + 鬼打墙红线 | 一次性脚本（不需要 session 管理） |

**不太适合的项目也能用** — 跑 Claude Code `/bridgeforge` 或 Codex `/bridgeforge` 时按引导答 OS / 主语言会自动裁剪不相关段落（详见 SKILL.md Step 3 的 OPTIONAL 段落处理），但 doc/ 六层 + Milestone-bound SemVer + 通用 skill 体系这些**核心范式假设了"项目有持续演进"** — 周末玩具用了反而是负担。

> ⚠️ **使用 bridgeforge = 接受 `doc/` 六层文档结构强制**（红线，不可裁剪 / 不可改名 / 不可合并）。详见 `templates/claude/CLAUDE.md §11` / `templates/codex/AGENTS.md §11` + 对应 `rules/workflow.md §5.5`。如果不接受这个约束 → 改用其他更宽松的脚手架。

---

## Python 依赖（agent 安装前必读）

> **v0.12.0 起：Python 是硬依赖，所有项目都装 hook**（不再因主语言非 Python 而跳过）。

bridgeforge 分两类内容：

**核心模板（无 Python 依赖，所有项目无条件复制）**：
- `templates/claude/rules/` / `templates/codex/rules/` — rule 文件（按文件路径触发加载）
- `templates/claude/CLAUDE.md` / `templates/codex/AGENTS.md` — 项目级入口说明
- `templates/claude/doc/` / `templates/codex/doc/` — `doc/` 六层骨架（红线，强制）
- `skills/<name>/SKILL.md` — skill 描述（agent 加载的指令）
- `templates/claude/memory/` / `templates/codex/memory/` — memory 框架
- `templates/claude/settings.json` / `templates/codex/settings.json` 的权限块 — 少弹框配置（allowlist / deny 等，与语言无关）

**hook 自动化（用 Python 实现，所有项目安装）**：
- `templates/claude/hooks/*.py` / `templates/codex/hooks/*.py` — hook 自动化：**version_check（git commit 强制 bump 版本号）**、PostCompact 自动 snapshot、Stop 5min 节流自动保存、memory 格式校验、rules 索引同步检查、ctx 预警、find-doc 提醒
- `templates/claude/scripts/*.py` / `templates/codex/scripts/*.py` — 工具脚本（如 `archive_scan.py` 给 `/archive-scan` / `$archive-scan` skill 用）
- `templates/claude/settings.json` / `templates/codex/settings.json` 里的 `hooks` 段（注册上面 hook 到 PreToolUse / PostToolUse / PostCompact / Stop / SessionStart 等时机）

**Python 解释器选择**（agent 跑 bridgeforge skill 时按优先级确定）：
1. 项目根有 `.venv/Scripts/python.exe`（Windows）/ `.venv/bin/python`（Unix）→ 用它（首选，最可移植）
2. 否则系统 `python` 在 PATH 上 → 用系统 python（纯 Rust/Node 项目走这条）
3. 两者都没有 → **停下，要求用户先装 Python（≥ 3.8）再继续**

**为什么强制 Python（不再可选）**：
hook 体系是 bridgeforge 区别于"纯文档脚手架"的核心价值——尤其 `version_check` 把"每次 commit 必 bump 版本号"从软规则升级为**机制硬强制**（历史上软规则被反复忘记，CHANGELOG 多次自打脸为证）。这个价值与项目主语言无关，因此即便主语言不是 Python，也要求装 Python 让 hook 跑起来。

> 设计 rationale：hook 体系沿用 StratusAgent / causis_risk_suite 的 Python 栈，未做 multi-runtime（PowerShell / Bash / Node）抽象。多 runtime 拆分工作量大且收益不明确，先接受"统一要求 Python"的现实。不接受 Python 依赖 → 改用其他纯文档脚手架。

---

## 未反哺的上游 hook（为什么不在 templates 里）

bridgeforge 反哺工作流（详见 `docs/reverse-sync-playbook.md`）会定期从下游项目（StratusAgent / causis_risk_suite）拉新通用范式回 templates。但**不是所有上游 hook 都会反哺** — 以下类别**故意不反哺**：

| 未反哺 hook | 来源 | 为什么不反哺 |
|------------|------|--------------|
| **语言专属构建检查** （如 `cargo_check.py`） | StratusAgent | 写死 `cargo check --workspace --quiet` + 路径过滤 `stratus` — 只对 Rust 项目有意义，反哺后 95% 用户用不上。**正确做法**：抽象为通用"PostToolUse 跑构建检查"框架（参数化命令），但工作量大且收益不明确，**暂不做** |
| **业务术语过滤** （如 hook 里硬编码 `oms` / `gateway` / `causis_api` 路径） | 任何下游 | 反哺时按 reverse-sync-playbook §3 脱敏 checklist 第 1/2/7 项整段删，**不留替换占位** |
| **凭证 / 账户号 / 内部 URL** | 任何下游 | 按 §3 checklist 第 3/4/5/6 项**整段删** |

**判断标准**：

- ✅ **反哺**：跨项目语义通用（如 memory 索引检查 / rule 行数限制 / session snapshot 触发 / ctx 预警）
- ❌ **不反哺**：硬绑特定语言 / 业务术语 / 内部资源

**用户视角**：

- 装 bridgeforge 后只看到通用 hook（context_warning / session_snapshot / memory_lint / rule_index_check / rule_size_check / show_state / find_doc_reminder / version_check 等 8 个）
- 项目自己的语言/业务专属 hook 由用户在 `.claude/hooks/` 下自行添加，不依赖 bridgeforge
- 若发现某个上游 hook 抽象后**应该**反哺，欢迎在 [GitHub issue](https://github.com/freakybridge/BridgeForge/issues) 提议

---

## 这是什么

把一个长期沉淀过的 AI 协作管理体系打包成可复用 skill，进新项目跑一次 Claude Code `/bridgeforge` 或 Codex `/bridgeforge` 就能拿到：

- **项目入口说明**：Claude 骨架用 `CLAUDE.md` + `.claude/`，Codex 骨架用 `AGENTS.md` + `.codex/`
- **rules 分层加载**：agent 配置目录下的 `rules/<topic>.md` 按文件路径触发，入口说明文件维护索引表
- **Memory 框架**：memory 索引与脚本随骨架下发，纳入项目 git
- **doc/ 分层归档**：`0_architecture（含 acceptance + TODO-INDEX）/ 1_plan（含 sprints）/ 2_pending / 3_design / 4_archive / 9_reference` — 二分语义"正在做（acceptance + sprints）vs 暂时没空（TODO-INDEX 主表）vs 远期 backlog（TODO-INDEX §远期索引）"
- **工作流红线**：鬼打墙觉察 + 渐进升级（lvl 0→3）、修 bug 前确认根因、UI 偶现 bug 主动问 4 件事
- **可移植性约束**：pip 陷阱、hooks 路径、换机 checklist

模板素材出自 [StratusAgent](https://github.com/freakybridge/StratusAgent) 长期沉淀，已剥离项目特定内容。

## 安装

```bash
# 完整 BridgeForge 工厂统一放到中立目录
git clone https://github.com/<你的用户名>/bridgeforge.git ~/.bridgeforge

# Codex：slash 命令目录只放薄入口 wrapper
mkdir -p ~/.agents/skills/bridgeforge
cp ~/.bridgeforge/scripts/codex_bridgeforge_entry.SKILL.md ~/.agents/skills/bridgeforge/SKILL.md

# Claude Code：skill 命令目录也只放薄入口 wrapper
mkdir -p ~/.claude/skills/bridgeforge
cp ~/.bridgeforge/scripts/claude_bridgeforge_entry.SKILL.md ~/.claude/skills/bridgeforge/SKILL.md

# Windows（PowerShell）
git clone https://github.com/<你的用户名>/bridgeforge.git "$env:USERPROFILE\.bridgeforge"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.agents\skills\bridgeforge" | Out-Null
Copy-Item "$env:USERPROFILE\.bridgeforge\scripts\codex_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.agents\skills\bridgeforge\SKILL.md"
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills\bridgeforge" | Out-Null
Copy-Item "$env:USERPROFILE\.bridgeforge\scripts\claude_bridgeforge_entry.SKILL.md" "$env:USERPROFILE\.claude\skills\bridgeforge\SKILL.md"
```

详细安装说明见 [INSTALL.md](INSTALL.md)。

## 使用

用户只需要记两个入口：

```text
/bridgeforge
/bridgeforge switch <claude|codex>
```

`/bridgeforge` 维护当前正在运行的 agent 骨架：在 Codex 里默认维护 Codex 骨架，在 Claude Code 里默认维护 Claude 骨架。若项目里只有另一套 agent 骨架，它不会静默多铺一套，而是先提示"继续会 switch 到当前 agent"，用户确认后才启动 switch 流程。

每次调用 `/bridgeforge` 时，叶子入口会先对 `~/.bridgeforge` 执行 `git pull --ff-only`，刷新成功后才读取完整 `SKILL.md` 并进入后续判场；如果 pull 失败，会停下让用户先处理，不继续用旧模板执行。

### 新项目初始化 —— 对 agent 说这一句（任何机器都成立）

在新项目根目录开 Codex 或 Claude Code，把下面这句话发给 agent：

> 如果这台机器还没装 bridgeforge：把完整仓库 clone 到 `~/.bridgeforge`；Codex 把 `scripts/codex_bridgeforge_entry.SKILL.md` 复制到 `~/.agents/skills/bridgeforge/SKILL.md`；Claude Code 把 `scripts/claude_bridgeforge_entry.SKILL.md` 复制到 `~/.claude/skills/bridgeforge/SKILL.md`；若存在旧的 `~/.codex/skills/bridgeforge`，先移到 `~/.codex/backups/`；然后照它的 SKILL.md 给当前项目铺设骨架。

这一句**自带兜底**：装过的机器直接铺，没装过的先自举（建 `.bridgeforge` 工厂源头 + 两个 agent 的叶子入口）再铺。agent 会读 [SKILL.md](SKILL.md) 按 Step 0~7 执行——问你 4 个问题（项目名 / 主语言 / OS / 是否需要换机 checklist），铺骨架，最后列出要手填的 3 处占位。

> ⚠️ 自举安装那次跑完需**重启当前 agent**。Codex 和 Claude Code 都用 `/bridgeforge`。

**已装过的机器**可用更短写法，直接调用：

```
# Codex
/bridgeforge

# Claude Code
/bridgeforge
```

### 更新已有项目（重跑即更新）

不需要单独的同步命令——**在已铺过的项目里再跑一次 bridgeforge skill 即进入"更新模式"**：

1. 先 `git pull` 上游 clone 拿最新模板；
2. 读项目里的 agent 版本戳（Claude `.claude/.bridgeforge_version`；Codex `.codex/.bridgeforge_version`），对比上游 `CHANGELOG.md` 的 `[product]` 条目，给你一份"上游这些更新冲着下游来"的增量清单；
3. 按业务专属程度分类处理：hooks/scripts 一致就覆盖、settings.json merge、**rules/入口文件（CLAUDE.md 或 AGENTS.md）只 diff 让你逐段定**、memory/doc 碰都不碰。

判断半场（rules/入口文件吸收哪段）全程交你——skill 只做拉取/diff/分类/呈现的机械活。详见 [docs/sync-from-upstream-playbook.md](docs/sync-from-upstream-playbook.md)。

如果项目已有 `AGENTS.md` / `CLAUDE.md` 或 agent 配置目录，但没有 BridgeForge 版本戳，`/bridgeforge` 会先判定它像不像旧 BridgeForge 骨架：像旧骨架就走"收编"并登记纳管；不像旧骨架就按"既有项目首次接入"处理，保留现有内容并在入口文件、rules、settings、memory、doc 有冲突时先问用户。

### 切换目标 agent

BridgeForge 模板已拆为 `templates/claude/` 与 `templates/codex/` 两套骨架。切换入口固定为：

```bash
/bridgeforge switch claude
/bridgeforge switch codex
/bridgeforge switch codex --dry-run
/bridgeforge switch codex --interactive
```

核心逻辑由 `scripts/bridgeforge_switch.py` 执行：只支持 `claude` / `codex`，真实切换只改工作区文件，不自动提交。同 agent switch 等价普通 `/bridgeforge` 更新/收编；跨 agent switch 会把旧 agent 骨架归档进当前项目的 `.bridgeforge/archive/<agent>/<timestamp>/`，每个 agent 只保留最新一份归档，归档成功后删除旧 agent 原路径。目标 agent 优先从当前项目自己的归档恢复，没有归档才从上游模板安装；目标 live path 已存在时停止，不覆盖。memory 合并到目标 agent，完全重复自动去重，相似冲突逐条确认；settings 默认不迁移，逐项确认；hooks / skills / rules / 入口文件只归档并报告，不自动迁移。dry-run 会列完整清单。切换脚本拒绝在 BridgeForge 源头仓库自己身上执行。

日常 `/bridgeforge` 也可能引导进入 switch：例如项目当前只有 Codex 骨架，而你在 Claude Code 里运行 `/bridgeforge`，它会先提示即将执行 `/bridgeforge switch claude`，说明归档和恢复后果，得到确认后才切换。

## 目录结构

```
bridgeforge/
├── SKILL.md                    ← skill 入口（Claude 读它执行 init）
├── README.md                   ← 本文件
├── INSTALL.md                  ← 安装与卸载指引
├── templates/
│   ├── claude/                 ← Claude 骨架（CLAUDE.md + .claude 目标形态）
│   │   ├── CLAUDE.md
│   │   ├── rules/
│   │   ├── hooks/
│   │   ├── scripts/
│   │   ├── memory/
│   │   └── settings.json
│   └── codex/                  ← Codex 骨架（AGENTS.md + .codex 目标形态）
│       ├── AGENTS.md
│       ├── rules/
│       ├── hooks/
│       ├── scripts/
│       ├── memory/
│       └── settings.json
├── scripts/
│   ├── bridgeforge_switch.py   ← bridgeforge switch <agent> 核心切换逻辑
│   ├── setup-junction.ps1      ← Windows: New-Item -ItemType Junction
│   └── setup-junction.sh       ← macOS/Linux: ln -s
└── docs/
    └── design-rationale.md     ← 为什么这样分层（设计说明）
```

## 设计原则

完整论述见 [docs/design-rationale.md](docs/design-rationale.md)。核心：

1. **rules vs memory 分工**
   - rules：架构约束/红线/范式（"必须 / 禁止"），少且稳定
   - memory：踩坑经验/决策记录（"上次踩了 X"），多且增长
   - feedback memory 沉淀够多 → 升级为 path-rule

2. **rules 按需加载**
   - Claude `CLAUDE.md` / Codex `AGENTS.md` 索引表的"加载条件"列控制：始终加载 / 路径触发
   - 路径触发用 frontmatter `paths:` 列表，编辑对应文件时自动加载

3. **Memory junction 跨机复现**
   - Claude 系统路径（`~/.claude/projects/<hash>/memory/`）只是 junction 入口；Codex 由项目 hook 自愈
   - 真实存储在项目内 `.claude/memory/` 或 `.codex/memory/`，纳入 git
   - clone 即恢复，不依赖用户目录状态

## License

MIT
