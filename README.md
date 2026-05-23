# setup_agent

> Claude Code 项目协作骨架初始化器。一行 skill 命令铺好 CLAUDE.md / rules / memory junction / doc 分层归档。

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

**不太适合的项目也能用** — 跑 `/setup_agent` 时按引导答 OS / 主语言会自动裁剪不相关段落（详见 SKILL.md Step 3 的 OPTIONAL 段落处理），但 doc/ 六层 + Milestone-bound SemVer + 12 个 skill 这些**核心范式假设了"项目有持续演进"** — 周末玩具用了反而是负担。

> ⚠️ **使用 setup_agent = 接受 `doc/` 六层文档结构强制**（红线，不可裁剪 / 不可改名 / 不可合并）。详见 `templates/CLAUDE.md §11` + `templates/rules/workflow.md §5.5`。如果不接受这个约束 → 改用其他更宽松的脚手架。

---

## Python 依赖（agent 安装前必读）

setup_agent 分两类内容。agent 在跑 `/setup_agent` 时，**先检测项目根目录是否存在 `.venv/Scripts/python.exe`（Windows）或 `.venv/bin/python`（Unix）**，再按下表决定装哪些：

**核心模板（无 Python 依赖，所有项目无条件复制）**：
- `templates/rules/` — rule 文件（按文件路径触发加载）
- `templates/CLAUDE.md` — 项目级 CLAUDE.md
- `templates/doc/` — `doc/` 六层骨架（红线，强制）
- `skills/<name>/SKILL.md` — skill 描述（agent 加载的指令）
- `templates/memory/` — memory junction 框架

**Python 依赖功能（需 `.venv` 存在才复制 + 注册）**：
- `templates/hooks/*.py` — hook 自动化（PostCompact 自动 snapshot、Stop 5min 节流自动保存、memory 格式校验、rules 索引同步检查、ctx 预警等）
- `templates/scripts/*.py` — 工具脚本（如 `archive_scan.py` 给 `/archive-scan` skill 用）
- `templates/.claude/settings.json` 里的 `hooks` 段（注册上面 hook 到 PreToolUse / PostToolUse / PostCompact / Stop / SessionStart 等时机）

**非 Python 项目（agent 检测到无 `.venv`）行为**：
- 跳过复制 `templates/hooks/` 和 `templates/scripts/`
- 注册 `settings.json` 时省略 `hooks` 段
- 向用户说明：本项目装了 setup_agent 核心模板，但**失去**以下自动化兜底 — PostCompact 自动 snapshot、Stop 5min 节流自动保存、memory 格式自动检查、rules 索引同步检查、ctx 预警
- **保留**：所有手动 skill（`/snapshot` / `/archive-scan` / `/find-doc` / `/summary` 等 agent 用 Bash + Write 直接做，不依赖 Python hook）

> 设计 rationale：hook 体系沿用 StratusAgent / causis_risk_suite 的 Python 栈，未做 multi-runtime（PowerShell / Bash / Node）抽象。多 runtime 拆分工作量大且收益不明确，先接受 Python 依赖现实。

---

## 未反哺的上游 hook（为什么不在 templates 里）

setup_agent 反哺工作流（详见 `docs/reverse-sync-playbook.md`）会定期从下游项目（StratusAgent / causis_risk_suite）拉新通用范式回 templates。但**不是所有上游 hook 都会反哺** — 以下类别**故意不反哺**：

| 未反哺 hook | 来源 | 为什么不反哺 |
|------------|------|--------------|
| **语言专属构建检查** （如 `cargo_check.py`） | StratusAgent | 写死 `cargo check --workspace --quiet` + 路径过滤 `stratus` — 只对 Rust 项目有意义，反哺后 95% 用户用不上。**正确做法**：抽象为通用"PostToolUse 跑构建检查"框架（参数化命令），但工作量大且收益不明确，**暂不做** |
| **业务术语过滤** （如 hook 里硬编码 `oms` / `gateway` / `causis_api` 路径） | 任何下游 | 反哺时按 reverse-sync-playbook §3 脱敏 checklist 第 1/2/7 项整段删，**不留替换占位** |
| **凭证 / 账户号 / 内部 URL** | 任何下游 | 按 §3 checklist 第 3/4/5/6 项**整段删** |

**判断标准**：

- ✅ **反哺**：跨项目语义通用（如 memory 索引检查 / rule 行数限制 / session snapshot 触发 / ctx 预警）
- ❌ **不反哺**：硬绑特定语言 / 业务术语 / 内部资源

**用户视角**：

- 装 setup_agent 后只看到通用 hook（context_warning / session_snapshot / memory_lint / rule_index_check / rule_size_check / show_state / find_doc_reminder 等 7 个）
- 项目自己的语言/业务专属 hook 由用户在 `.claude/hooks/` 下自行添加，不依赖 setup_agent
- 若发现某个上游 hook 抽象后**应该**反哺，欢迎在 [GitHub issue](https://github.com/freakybridge/setup_agent/issues) 提议

---

## 这是什么

把一个长期沉淀过的"Claude Code 协作管理体系"打包成可复用 skill，进新项目跑一次 `/setup_agent` 就能拿到：

- **双层 CLAUDE.md**：全局 `~/.claude/CLAUDE.md` 管沟通/安全/执行协议；项目 `<repo>/CLAUDE.md` 管架构红线 + rules 索引 + skills 表
- **rules 分层加载**：`.claude/rules/<topic>.md` 按文件路径触发，CLAUDE.md 维护索引表
- **Memory junction**：系统 memory 路径链回 `.claude/memory/`，纳入项目 git
- **doc/ 分层归档**：`0_architecture（含 acceptance + TODO-INDEX）/ 1_plan（含 sprints）/ 2_pending / 3_design / 4_archive / 9_reference` — 二分语义"正在做（acceptance + sprints）vs 暂时没空（TODO-INDEX 主表）vs 远期 backlog（TODO-INDEX §远期索引）"
- **工作流红线**：鬼打墙觉察 + 渐进升级（lvl 0→3）、修 bug 前确认根因、UI 偶现 bug 主动问 4 件事
- **可移植性约束**：pip 陷阱、hooks 路径、换机 checklist

模板素材出自 [StratusAgent](https://github.com/freakybridge/StratusAgent) 长期沉淀，已剥离项目特定内容。

## 安装

```bash
# 1. clone 到 Claude Code 用户级 skill 目录
git clone https://github.com/<你的用户名>/setup_agent.git ~/.claude/skills/setup_agent

# Windows（PowerShell）
git clone https://github.com/<你的用户名>/setup_agent.git "$env:USERPROFILE\.claude\skills\setup_agent"
```

详细安装说明见 [INSTALL.md](INSTALL.md)。

## 使用

进任何新项目根目录（建议先 `git init`），调用：

```
/setup_agent
```

skill 会问你 4 个问题（项目名 / 主语言 / 是否需要换机 checklist / 是否建 doc/），然后铺骨架，最后告诉你哪 3 处占位需要手填。

## 目录结构

```
setup_agent/
├── SKILL.md                    ← skill 入口（Claude 读它执行 init）
├── README.md                   ← 本文件
├── INSTALL.md                  ← 安装与卸载指引
├── templates/
│   ├── CLAUDE.md               ← 项目级 CLAUDE.md 深度模板
│   ├── rules/
│   │   ├── architecture.md     ← 骨架（职责边界占位）
│   │   ├── modules.md          ← 骨架（模块组织 + .runtime/ + 根目录极简）
│   │   ├── debugging.md        ← 通用（鬼打墙红线 / 修 bug 前确认根因）
│   │   ├── workflow.md         ← 通用（同步文档 / 主动写规则 / Milestone-bound SemVer）
│   │   ├── portability.md      ← 通用（换机可移植性 / venv 重建 / CRLF / 入口脚本 ASCII）
│   │   └── meta_rule_design.md ← 元规则（强制力梯度 / 加载策略 / 反模式速查）
│   ├── memory/MEMORY.md        ← 空索引模板
│   └── doc/README.md           ← 文档分层索引模板
├── scripts/
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
   - CLAUDE.md 索引表的"加载条件"列控制：始终加载 / 路径触发
   - 路径触发用 frontmatter `paths:` 列表，编辑对应文件时自动加载

3. **Memory junction 跨机复现**
   - 系统路径（`~/.claude/projects/<hash>/memory/`）只是 junction 入口
   - 真实存储在项目内 `.claude/memory/`，纳入 git
   - clone 即恢复，不依赖用户目录状态

## License

MIT
