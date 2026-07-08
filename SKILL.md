---
name: bridgeforge
description: 在新项目里铺设或更新标准化的 Claude/Codex 协作骨架（CLAUDE.md 或 AGENTS.md、rules、memory、hooks、doc 分层），并自检补齐用户级通用 skill。用户提到 bridgeforge、项目骨架初始化、同步上游模板、switch claude/codex、Codex/Claude 入口 /bridgeforge 时使用。
version: 0.57.0
user_invocable: true
user-invocable: true
argument: 可选——switch claude|codex [--dry-run|--interactive] [--skip-settings-migration] [--migrate-setting KEY] [--memory-conflict REL=ACTION]，不带参数则维护当前 agent 骨架；若检测到另一套 agent 骨架，先确认再转 switch
model: sonnet
---

# bridgeforge — 项目协作骨架初始化 / 更新

**定位**：一次性给新项目装好 Claude Code 或 Codex 协作管理体系——入口说明、rules 分层加载、memory junction、hooks、doc 分层归档；**并自检用户级通用协作 skill（清单以本仓库 `skills/` 目录为准），缺哪个补哪个，再清掉项目里的重复副本（单一源）**。运行后用户只需填占位（架构红线 / 快速命令 / 项目结构）即可上线。

**用户只需记两个入口**：
- `$ENTRY_COMMAND`：维护当前正在运行的 agent 骨架。空项目走初始化，已托管项目走更新，旧骨架走收编，既有项目首次接入时先问冲突；若发现项目里只有另一套 agent 骨架，先提示"继续会 switch 到当前 agent"，用户确认后再启动 switch。
- `$ENTRY_COMMAND switch <claude|codex>`：显式切换当前项目使用的 agent 骨架。

> 模板素材出自 StratusAgent 项目长期沉淀（鬼打墙红线、UI 主动问 4 件事、换机可移植性、文档分层归档、通用协作 skill 集）。已剥离项目特定内容，只留通用骨架。

---

## 入口与路径（先判 agent）

| Agent | 显式调用 | 上游仓库 / 入口安装目录 | 项目骨架目录 |
|------|----------|-------------------|--------------|
| Claude Code | `/bridgeforge` | 完整仓库：`~/.bridgeforge`；薄入口 wrapper：`~/.claude/skills/bridgeforge/SKILL.md` | `.claude/` + `CLAUDE.md` |
| Codex | `/bridgeforge`（从 slash 命令清单选中） | 完整仓库：`~/.bridgeforge`；薄入口 wrapper：`~/.agents/skills/bridgeforge/SKILL.md` | `.codex/` + `AGENTS.md`；项目专属 skill 放 `.agents/skills/` |

执行前先确定当前 agent：完整 BridgeForge 工厂统一放在 `$HOME/.bridgeforge`。在 Codex 中运行时，`$HOME/.claude/skills` 读作 `$HOME/.agents/skills`，项目内 `.claude/` 主配置目录读作 `.codex/`，但项目专属 skill 目录读作 `.agents/skills/`，`CLAUDE.md` 读作 `AGENTS.md`。`~/.codex/` 只用于 Codex 自身配置和 memory 系统路径，不作为用户级 skill 安装目录。

```bash
# Claude Code
ENTRY_COMMAND="/bridgeforge"
USER_SKILLS_DIR="$HOME/.claude/skills"
BRIDGEFORGE_HOME="$HOME/.bridgeforge"
BRIDGEFORGE_COMMAND_DIR="$USER_SKILLS_DIR/bridgeforge"
PROJECT_AGENT_DIR=".claude"
PROJECT_ENTRY_FILE="CLAUDE.md"
PROJECT_SKILLS_DIR=".claude/skills"
TEMPLATE_AGENT="claude"

# Codex
ENTRY_COMMAND="/bridgeforge"
USER_SKILLS_DIR="$HOME/.agents/skills"
BRIDGEFORGE_HOME="$HOME/.bridgeforge"
BRIDGEFORGE_COMMAND_DIR="$USER_SKILLS_DIR/bridgeforge"
PROJECT_AGENT_DIR=".codex"
PROJECT_ENTRY_FILE="AGENTS.md"
PROJECT_SKILLS_DIR=".agents/skills"
TEMPLATE_AGENT="codex"
```

若 `$BRIDGEFORGE_HOME/SKILL.md` 不存在，但旧路径存在（Codex: `$HOME/.agents/bridgeforge-home/SKILL.md`；Claude: `$HOME/.claude/skills/bridgeforge/templates/`），说明本机仍是旧安装布局。此时不要静默删除旧目录：本轮可把旧路径作为临时 `BRIDGEFORGE_HOME` 继续执行，同时提示用户按 INSTALL.md 迁移到 `$HOME/.bridgeforge`，并把 agent 货架里的 `bridgeforge/SKILL.md` 替换成对应薄入口 wrapper。

## 执行流程

### Step -2：刷新用户级骨架库（所有分支前）

薄入口 wrapper 应该已经在读取本文件前执行过本步；这里仍保留兜底，防止用户直接打开根 `SKILL.md` 或使用旧 wrapper。

```bash
git -C "$BRIDGEFORGE_HOME" pull --ff-only
```

- pull 成功 → 继续后续判场。
- pull 失败（冲突 / 网络 / 权限）→ 报告并停下，**不继续用旧模板执行**；让用户先处理 `$BRIDGEFORGE_HOME` 后重跑 `$ENTRY_COMMAND`。
- `$BRIDGEFORGE_HOME` 不是 git 仓库（用户手动拷的）→ 跳过 pull，但提示"建议改用 `git clone` 到 `~/.bridgeforge`，后续 `$ENTRY_COMMAND` 才能自动拉更新"。

### Step -1：switch 子命令优先分流（刷新后）

如果用户调用的是：

```bash
/bridgeforge switch claude
/bridgeforge switch codex
/bridgeforge switch codex --dry-run
/bridgeforge switch codex --interactive
```

先判断当前项目是否已经是目标 agent：
- 已经是目标 agent（如已有 `AGENTS.md + .codex/` 又 `switch codex`）→ **不要调用切换脚本**，按普通 `/bridgeforge` 继续走初始化 / 更新 / 收编流程。
- 不是目标 agent → 不进入下面的初始化 / 更新 / 收编流程，直接调用项目内切换脚本：

```bash
python scripts/bridgeforge_switch.py <claude|codex> [--dry-run|--interactive] [--skip-settings-migration] [--migrate-setting KEY] [--memory-conflict REL=ACTION]
```

执行契约：
- 只支持 `claude` / `codex`，不接受 `gpt` / `openai` / `claude-code` 等别名。
- `--dry-run` 只报告完整计划，不改文件；清单必须覆盖归档、删除、目标来源、memory 合并、settings 候选、只归档不迁移项和目标冲突。
- 旧 agent 归档范围固定：Claude → `CLAUDE.md + .claude/`；Codex → `AGENTS.md + .codex/ + .agents/skills/`。归档路径为 `.bridgeforge/archive/<agent>/<timestamp>/`，每个 agent 只保留最新一份归档，新归档成功后删除该 agent 旧归档。
- 归档成功后删除旧 agent 原路径；`.agents/` 若因此变空可删除，若还有其他内容则保留。
- 若当前项目没有旧 agent 骨架，允许 switch；语义变成启用目标 agent。
- 目标 agent 优先从当前项目自己的归档恢复；没有目标归档才从上游 `templates/<agent>/` 安装全新骨架。**只认当前项目归档**，不读全局缓存或其他项目。
- 目标 agent live path 已存在且不是“同 agent switch”时，直接停止，不覆盖、不归档继续。
- memory 必须合并到目标 agent 的活跃 memory：完全重复自动去重；相似但不完全一样 / 同路径不同内容必须逐条确认。非交互时用 `--memory-conflict REL=keep-target|copy-old|append-old` 回放用户选择。
- settings 默认不迁移；列出候选 key 后逐项确认。非交互时用 `--skip-settings-migration` 表示全部不迁移，或用 `--migrate-setting KEY` 指定迁移项。
- hooks / skills / rules / 入口文件默认只归档并报告，不自动迁移；它们存在 agent 兼容性风险，不能机械搬入目标 agent。
- 真实切换只改工作区文件，不 `git add` / `git commit` / `git push`。
- 若项目内没有 `scripts/bridgeforge_switch.py`，用本 skill clone 里的 `templates/$TEMPLATE_AGENT/scripts/bridgeforge_switch.py` 兜底执行，并显式传 `--template-root "$BRIDGEFORGE_HOME"`。
- 若 cwd 是 bridgeforge 源头仓库自己，切换脚本会拒绝执行；源头改框架应直接编辑 `templates/`。

> 白话：`/bridgeforge switch ...` 是换当前项目的 agent 工具箱。旧工具箱先封箱进项目自己的归档柜，目标工具箱优先从同项目归档柜拿，拿不到才领一套上游新工具箱；笔记本（memory）要合并，电线/专用工具/规章（hooks / skills / rules / 入口文件）只存档不硬接。

### 前置：认场子（工厂自检 / 当前 agent 维护 / 隐式 switch 确认）

**Step 前-1 刷新确认**：到这里时 `$BRIDGEFORGE_HOME` 应已由薄入口 wrapper 或 Step -2 刷新到最新；后续所有 init / 更新 / 收编 / switch 都以刷新后的模板和脚本为准。

**Step 前-2 工厂自检（最先判，硬闸）**：cwd 是不是 bridgeforge 源头仓库**自己**？

```bash
# 同时满足才算源头：有产品层 templates/ + 根 SKILL.md 是 bridgeforge 自己
test -f "templates/$TEMPLATE_AGENT/$PROJECT_ENTRY_FILE" && grep -q "项目协作骨架初始化" SKILL.md && echo FACTORY_SELF
```

- 命中 `FACTORY_SELF` → **立即硬拒并退出**，告诉用户："这是 bridgeforge 源头仓库（模板工厂），不能在它自己身上 bootstrap / 更新——要改框架请直接编辑 `templates/` / `SKILL.md`，不要跑 `$ENTRY_COMMAND`。"
- 为什么这是第一闸：源头仓库**故意不带** `$PROJECT_AGENT_DIR/.bridgeforge_version`（靠 `templates/` 存在性识别身份，比版本戳更本质，见 [docs/design-rationale.md](docs/design-rationale.md) §9.4）。没有这道闸，源头会落进下方"无戳 + 有 `$PROJECT_ENTRY_FILE`"分支被误当 init → 等于装修队拆自己样板间。

**Step 前-3 认场子（判定模式）**：

```bash
test -f "$PROJECT_AGENT_DIR/.bridgeforge_version" && cat "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

先按当前运行环境确定两套 live 骨架：

| 当前 agent | 当前 live 骨架 | 另一套 live 骨架 |
|------------|----------------|------------------|
| Claude Code | `CLAUDE.md` 或 `.claude/` | `AGENTS.md` 或 `.codex/` 或 `.agents/skills/` |
| Codex | `AGENTS.md` 或 `.codex/` 或 `.agents/skills/` | `CLAUDE.md` 或 `.claude/` |

普通 `$ENTRY_COMMAND` 的核心语义：**维护当前 agent；发现只有另一套 agent 时，先确认再转 `$ENTRY_COMMAND switch $TEMPLATE_AGENT`，绝不静默多铺一套。**

按下表判定：

| 场景 | 判据 | 走哪 |
|------|------|------|
| **双 live 骨架冲突** | 当前 live 骨架和另一套 live 骨架同时存在 | 停止，提示项目处于双骨架状态；让用户选择：(A) 只维护当前 agent 骨架并进入下方当前判场；(B) 退出，先手动归档/清理另一套后再切换；(C) 退出 |
| **更新** | 有 `$PROJECT_AGENT_DIR/.bridgeforge_version` | 【更新模式】跳到下方 "## 更新模式" 段（Step 0 + Step 0.5 自检仍先跑一遍：幂等补 skill + 清项目重复副本） |
| **收编 (adopt)** | 无戳，但当前 agent 的 `$PROJECT_ENTRY_FILE` / `$PROJECT_AGENT_DIR/rules` **像 bridgeforge 铺过的**（指纹 ≥2 项命中） | 【收编模式】跳到下方 "## 收编模式 (adopt)" 段 |
| **当前 agent 文件冲突** | 无戳，当前 agent 的 `$PROJECT_ENTRY_FILE` / `$PROJECT_AGENT_DIR/rules` 已存在但**不命中**衍生指纹 | 【既有项目首次接入】继续 Step 0 → Step 1；Step 1 必须问用户跳过补缺 / 备份覆盖 / 退出，禁止静默覆盖 |
| **隐式 switch 候选** | 当前 live 骨架不存在，但另一套 live 骨架存在 | 提示："检测到本项目是另一套 agent 骨架；继续将执行 `$ENTRY_COMMAND switch $TEMPLATE_AGENT`。" 用户确认后启动 switch；不确认则退出，不改文件 |
| **全新 init** | 两套 live 骨架都不存在，且 cwd 基本为空 / 无业务文件 | 继续 Step 0 → Step 7 |
| **既有项目首次接入** | 两套 live 骨架都不存在，但 cwd 已有业务文件 / git 历史 / 项目配置 | 说明会安装当前 agent 骨架且保留已有内容；继续 Step 0 → Step 1，遇到入口文件 / settings / rules / memory / doc 冲突必须问 |

**bridgeforge 衍生指纹**（命中 **≥2 项**即判"像铺过的"，走收编；目的只是区分"我铺的 vs 别人的项目"，宁松勿严）：

```bash
grep -q "鬼打墙"     "$PROJECT_ENTRY_FILE"                  2>/dev/null   # 鬼打墙红线
grep -q "ctx-budget" "$PROJECT_ENTRY_FILE"                  2>/dev/null   # ctx-budget 信号
grep -rq "OPTIONAL_BEGIN" "$PROJECT_AGENT_DIR/rules/"       2>/dev/null   # OPTIONAL 裁剪残留标记
test -f "$PROJECT_AGENT_DIR/rules/meta_rule_design.md"                     # 元规则文件名
test -f "$PROJECT_AGENT_DIR/rules/workflow.md"                             # 工作流 rule 文件名
```

> **判别树（文字版）**：
> ① 工厂自检命中 → 硬拒退出
> ② 双 live 骨架 → 停止让用户选方向
> ③ 当前 agent 有版本戳 → 更新模式
> ④ 当前 agent 无戳 + 像衍生（指纹 ≥2）→ 收编模式（写戳转更新，**绝不覆盖**）
> ⑤ 当前 agent 无戳 + 有入口/规则但不像衍生 → 既有项目首次接入，Step 1 处理冲突
> ⑥ 当前 agent 不存在 + 另一套 agent 存在 → 先确认，再转 `$ENTRY_COMMAND switch $TEMPLATE_AGENT`
> ⑦ 两套都不存在 + 空项目 → 全新 init（Step 0→7）
> ⑧ 两套都不存在 + 已有业务内容 → 既有项目首次接入，保守补骨架

### Step 0：自检并补齐用户级通用 skill

本 skill 仓库内的 `skills/` 子目录包含全部通用协作 skill（脱敏自 StratusAgent 长期沉淀；清单以目录实际内容为准，**不再硬编码个数**）。Claude Code / Codex 都只扫描用户级 skill 目录下的 `<name>/SKILL.md` 顶层，**不递归**——所以 `$BRIDGEFORGE_HOME/skills/<name>/SKILL.md` 这样嵌套的 skill 扫不到，必须复制到 `$USER_SKILLS_DIR/<name>/` 平级。

**入口注册红线**：`$USER_SKILLS_DIR/bridgeforge` 必须是**只含 `SKILL.md` 的叶子 skill**，且这个 `SKILL.md` 是极小 wrapper（Claude 源文件：`$BRIDGEFORGE_HOME/scripts/claude_bridgeforge_entry.SKILL.md`；Codex 源文件：`$BRIDGEFORGE_HOME/scripts/codex_bridgeforge_entry.SKILL.md`）。完整 BridgeForge 仓库放在 `$BRIDGEFORGE_HOME`，即 `~/.bridgeforge`。不要把整份 BridgeForge 仓库 clone / junction / symlink 到 `$USER_SKILLS_DIR/bridgeforge`；Codex 会加载仓库里的子 skill，但不会把仓库根 `SKILL.md` 显示成 `/bridgeforge` 命令，Claude 侧也会让“入口货架”和“完整工厂”语义混在一起。安装 / 升级时把 wrapper 复制到 `$USER_SKILLS_DIR/bridgeforge/SKILL.md`。历史残留的 `~/.codex/skills/bridgeforge` 也必须移出技能扫描目录；它不是 Codex 用户级 skill 货架，会造成“子 skill 可见、根 `/bridgeforge` 不可见”的假象。

**自检逻辑（幂等：缺失→装 / 旧版→提议更新 / 定制→问，绝不静默覆盖）**：

```bash
SKILL_DIR="$BRIDGEFORGE_HOME"                  # 本 skill 的仓库 clone 位置
SKILLS_SRC="$SKILL_DIR/skills"
SKILLS_DST="$USER_SKILLS_DIR"

# 修复旧安装残留。旧版曾把完整仓库 junction/clone 到 ~/.codex/skills/bridgeforge，
# 这会让 Codex 扫到 BridgeForge 子 skill，却不显示根 /bridgeforge。
if [ "$TEMPLATE_AGENT" = "codex" ]; then
  LEGACY_CODEX_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/bridgeforge"
  if [ -e "$LEGACY_CODEX_SKILL" ]; then
    echo "⚠ 旧 Codex bridgeforge 入口残留: $LEGACY_CODEX_SKILL"
    echo "  建议先移到 ${CODEX_HOME:-$HOME/.codex}/backups/，确认后再继续；不要直接删除真实仓库。"
  fi
fi

if [ -e "$HOME/.agents/bridgeforge-home" ] || [ -d "$HOME/.claude/skills/bridgeforge/templates" ]; then
  echo "⚠ 检测到旧 BridgeForge 完整仓库位置。新布局要求完整仓库放在 $BRIDGEFORGE_HOME。"
  echo "  不要静默删除旧目录；按 INSTALL.md 迁移或确认后再继续。"
fi

mkdir -p "$BRIDGEFORGE_COMMAND_DIR"
if [ "$TEMPLATE_AGENT" = "codex" ]; then
  cp "$BRIDGEFORGE_HOME/scripts/codex_bridgeforge_entry.SKILL.md" "$BRIDGEFORGE_COMMAND_DIR/SKILL.md"
else
  cp "$BRIDGEFORGE_HOME/scripts/claude_bridgeforge_entry.SKILL.md" "$BRIDGEFORGE_COMMAND_DIR/SKILL.md"
fi

# 通用 skill 清单 = skills/ 目录下全部子目录（单一源：增删 skill 只动目录，不改这段；
# 历史上手维护清单漏掉过 find-memory，ls-派生杜绝此类漂移）
for s in $(ls "$SKILLS_SRC"); do
  [ -d "$SKILLS_SRC/$s" ] || continue
  if [ ! -d "$SKILLS_DST/$s" ]; then
    cp -r "$SKILLS_SRC/$s" "$SKILLS_DST/$s"
    echo "✓ 安装缺失 skill: $s"
  elif diff -rq "$SKILLS_SRC/$s" "$SKILLS_DST/$s" >/dev/null 2>&1; then
    echo "- 已是最新，跳过: $s"
  else
    echo "⚠ 已存在但与上游不一致: $s（旧版 or 你的定制）→ 见下方处理"
  fi
done
```

**对 ⚠ 不一致的 skill 怎么处理**（复用「更新模式」类 A 判断，**堵传播缺口**）：

之前这里是"逢重名一律跳过"——好心保护用户定制，但副作用是**"改进已有 skill"永远到不了已装下游**（如本次给 `summary` 加的捕捉反射，老项目会拿不到）。现在改为先**比对内容**：

- **一致（只是旧版镜像）**→ 上面已"静默跳过"标记为最新；若上游确有更新会落到下面分支，逐个 `cp` 覆盖即可，无需问（没有定制要保护）。
- **不一致（你改进过的定制版 / 或老版本被上游改进了）**→ **绝不静默覆盖**：逐个给用户看 `diff`，问"覆盖成上游版 (y) / 保留你的定制 (n)"。

> 这样既保住了原来"不偷偷盖掉定制"的好心，又补上了"改进流不到老项目"的缺口。判断逻辑与「更新模式」§U2 类 A 完全一致——一个事实源，两处复用。

**退役清理（正向同步只增不减的补丁，「删除不传播」洞）**：上面那个 loop 只**增/改**，上游**下架**的 skill 不会被它清掉——已装下游会抱着"僵尸 skill"。这里补一步：读上游退役墓碑 `RETIRED.md`，把名单里**仍赖在用户级架子上**的列出来问用户删。

```bash
RETIRED="$SKILL_DIR/RETIRED.md"   # repo 根墓碑名单（$SKILL_DIR 见上方变量）
if [ -f "$RETIRED" ]; then
  # 每行 `- <name> | ...`，只取第一列 skill 名
  grep '^- ' "$RETIRED" | sed -E 's/^- *([^ |]+).*/\1/' | while read -r s; do
    [ -d "$SKILLS_DST/$s" ] && echo "⚠ 已退役但仍在架上: $s（上游已下架，见 RETIRED.md）→ 建议删 $SKILLS_DST/$s"
  done
fi
```

- **绝不静默删**（同 Step 0.5 范式）：把 `RETIRED.md` 里该行的"原因"念给用户，问"删（回收下架 skill）/ 留"。用户改过它当定制 → 尊重保留。
- 退役的 **hook**（项目级，如 `memory_guard.py` 活在 `<project>/.claude/hooks/` + 项目 settings 注册里）**不在本步范围**——本步只清用户级 skill。退役 hook 仍按 CHANGELOG 提示手动删（见 `docs/skill-distribution-gaps.md` 支柱 B 待办）。

> **新鲜度前置**：到这里时 `$BRIDGEFORGE_HOME` 已由薄入口 wrapper 或 Step -2 执行过 `git pull --ff-only`。Codex / Claude 的 slash wrapper 不存模板；模板与通用 skills 只从刷新后的 `$BRIDGEFORGE_HOME` 读取。

**通用 skill 速查（清单以 `skills/` 目录为准）**：

| Skill | 触发 | 用途 |
|------|------|------|
| `feature-dev` | Claude `/feature-dev`；Codex `$feature-dev` | 大需求交付流水线：澄清需求、落盘文档、自动开发、独立验证、用户试用反馈闭环 |
| `plan` | Claude `/plan`；Codex `$plan` | 只读分析，列任务/风险/文件，等用户确认后再实施 |
| `collab` | Claude `/collab`；Codex `$collab` | 分治协作，拆分子任务并行执行 |
| `debate` | Claude `/debate`；Codex `$debate` | 双 Agent 辩论，多轮讨论达成共识 |
| `escalate` | Claude `/escalate`；Codex `$escalate` | 鬼打墙急停按钮（详见 `$PROJECT_ENTRY_FILE` 鬼打墙规则） |
| `snapshot` | Claude `/snapshot`；Codex `$snapshot` | 手动存档 session 工作状态 |
| `resume` | Claude `/resume`；Codex `$resume` | 读 snapshot 接续上下文（上下文不够时换会话用） |
| `git-sync` | Claude `/git-sync`；Codex `$git-sync` | 全自动 fetch / commit / push |
| `archive-scan` | Claude `/archive-scan`；Codex `$archive-scan` | 扫描 doc/2_pending/ 可归档候选 |
| `todo` | Claude `/todo <描述>`；Codex `$todo <描述>` | 新问题归档到 TODO-INDEX 主表（短期）或 1_plan/ 远期文档 |
| `find-doc` | agent 主动 | doc 综合检索（grep + read 一次性）；项目 topic→rule 字典外置 `$PROJECT_AGENT_DIR/find-doc.map.md` |
| `find-memory` | Claude `/find-memory`；Codex `$find-memory` | 按关键词搜 memory 冷区（MEMORY.md 索引没覆盖时） |
| `summary` | Claude `/summary`；Codex `$summary` | 总结对话决策写入 memory，并按需更新 rules/docs；**顺手捕捉通用经验进反哺收件箱** |
| `sync-docs` | Claude `/sync-docs`；Codex `$sync-docs` | 根据代码变更同步设计文档 |
| `harvest` | Claude `/harvest`；Codex `$harvest` | 把下游攒的通用经验脱敏反哺回 bridgeforge 上游（无参批量清收件箱 / 带描述立即单条） |
| `spinoff` | Claude `/spinoff`；Codex `$spinoff` | 前置阻塞问题派生交接 — 存档主任务 + 生成解前置的种子提示词 + 双向回链，去新对话解前置（配 focus_reminder.py 防漂移）|
| `focus` | Claude `/focus`；Codex `$focus` | 任务锚控制 + 手动漂移自检（查/改/清本会话原始任务锚，配 focus_reminder.py hook）|

**用户级 allow 审计（C3，换机/初次必做）**：Claude Code 扫 `~/.claude/settings.json`，Codex 扫 `~/.codex/settings.json` 的 `permissions.allow`，揪出疑似项目专属/一次性条目（绝对路径/PID/IP/一次性编译命令），**只报不删**，列给用户拍板后手动下沉到项目 `settings.local.json`：

```bash
python "$BRIDGEFORGE_HOME/templates/$TEMPLATE_AGENT/scripts/audit_user_allow.py"
```

- **无命中** → 继续；**有命中** → 列给用户看，建议下沉到对应项目的 `settings.local.json`（详见 `rules/portability.md §3.1`）。
- **触发时机**：init / 换机首次 setup 时必跑；后续按需（已知用户级干净可跳过）。

**全局用户规则自检（Claude Code only；幂等，与 skill 自检同批）**：仅当当前 agent 是 Claude Code 时执行，确保用户全局 `~/.claude/CLAUDE.md` 含以下通用规则，缺哪条补哪条。当前 agent 是 Codex 时**跳过本段**；Codex 用户级偏好由 Codex 自身的 AGENTS/配置机制承载，bridgeforge 只铺项目级 `AGENTS.md` + `.codex/`。

```bash
grep -q "禁止用 shell 查文件" "$HOME/.claude/CLAUDE.md" 2>/dev/null && echo "✓ Glob 规则已有" || echo "Glob 规则缺失"
grep -q "回复一律用简体中文" "$HOME/.claude/CLAUDE.md" 2>/dev/null && echo "✓ 中文输出规则已有" || echo "中文输出规则缺失"
grep -q "写 rule / 约束文件的红线" "$HOME/.claude/CLAUDE.md" 2>/dev/null && echo "✓ 写 rule 红线已有" || echo "写 rule 红线缺失"
```

- **已有** → 跳过
- **Glob 规则缺失且 `~/.claude/CLAUDE.md` 存在** → 用 Edit 工具在 `**主动工具**` 条目后插入一行：
  ```
  - **查文件/查内容用 Glob/Grep/Read，禁止用 shell 查文件**：`find`、`Get-ChildItem`、`Select-String` 等 shell 命令访问工作目录外路径会触发权限弹窗。检索类操作一律走受控只读工具（Glob 找文件、Grep 搜内容、Read 读文件），shell 只留给构建/git/进程等"真要执行"的动作。Glob 三诀：① path 要具体不要全盘扫（会超时）；② 匹配文件不匹配目录，找文件夹写 `**/foo/**`；③ 默认跳过 `.` 开头隐藏目录，目标在 `.claude` 里时把 path 直接扎进去
  ```
- **中文输出规则缺失且 `~/.claude/CLAUDE.md` 存在** → 用 Edit 工具在 `## 沟通风格` 段首条插入一行（无该段则在文件顶部新建 `## 沟通风格` 段落再插入该条）：
  ```
  - **回复一律用简体中文**。禁止整轮输出漂移到其他语言（实测发生过无故切日语）。技术术语/代码/文件名/引用原文不在此限；即使 skill 模板或工具输出含其他语言，回复正文也必须是简体中文。
  ```
- **写 rule 红线缺失且 `~/.claude/CLAUDE.md` 存在** → 用 Edit 工具新增一节（与现有"沟通风格 / 防空转"并列）：
  ```
  ## 写 rule / 约束文件的红线（所有项目通用）

  写 `.claude/rules/*.md` 或任何"约束文件"时：**只写"必须 X / 禁止 Y"的红线，不讲故事**。
  - 完整事故复盘、>20 行 code 示例、方案对比 → 搬 memory / doc；rule 里最多留**一行** `**Why**: <压缩动因>（memory xxx）` 当指针。
  - 判定：写完一段问自己"这是'必须 / 禁止'吗?" 是→留；是"某年某月那次踩了 X"→搬 memory。
  - **触发条件必须机器可解析**：项目若按 frontmatter `paths` 触发加载 rule，每个 rule 顶部**必须**有 YAML `paths:` 声明，**禁止**只写散文"加载条件"（机器扫不到 = 该加载时可能不加载）。
  - **本条是共性底座，不覆盖项目自有的 rule 撰写规范**：项目带 meta_rule（量化红线/案例库/加载策略）时以项目版为准。
  ```
- **`~/.claude/CLAUDE.md` 不存在**（新用户还没有全局配置）→ 跳过，只靠项目级 `CLAUDE.md` 兜底

**全局 settings.json 自检（Claude Code only；幂等，补 Python 编码环境变量）**：仅当当前 agent 是 Claude Code 时执行，确保 `~/.claude/settings.json` 有 `"env"` 块含 Python UTF-8 兜底，缺则补。当前 agent 是 Codex 时**跳过本段**，不要把 Claude Code 的全局配置写进 Codex 流程。

```bash
python -c "
import json, pathlib, sys
p = pathlib.Path.home() / '.claude' / 'settings.json'
d = json.loads(p.read_text('utf-8')) if p.exists() else {}
env = d.get('env', {})
missing = [k for k in ('PYTHONUTF8', 'PYTHONIOENCODING') if k not in env]
print('缺失:', missing if missing else '无（已有）')
"
```

- **已有 `PYTHONUTF8` 和 `PYTHONIOENCODING`** → 跳过
- **缺失** → 用 Edit / Write 工具把 `"env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}` merge 进 `~/.claude/settings.json`（已有 `env` 键则追加两个 key，不覆盖其他 key；无 `env` 键则新增整块）。
  > **Why**：Windows 终端默认 GBK，Python 子进程（含 hook）stdout 输出中文走 GBK 编码，被 Claude Code 当 UTF-8 解析 → mojibake 注入 context。`PYTHONUTF8=1` 让所有 Python 子进程默认 UTF-8，跨平台无害。hook 逐文件 `sys.stdout.reconfigure()`（C7）是 belt；本条是 suspenders，互补。
- **`~/.claude/settings.json` 不存在** → 新建：`{"env": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}}`

**告知用户**：若复制了任何 skill，提示"需要重启当前 agent（Claude Code 或 Codex）才能看到新 skill"。

> 跳过条件：若用户明确说"我不要这些通用 skill"，可在 Step 0 完全跳过；但默认全装。

### Step 0.5：清理项目级通用 skill 重复副本（单一源红线）

> **背景**：通用协作 skill 的**单一源是 bridgeforge**，装到**用户级** `$USER_SKILLS_DIR`。若项目自己的 `$PROJECT_SKILLS_DIR/` 里也有同名副本 → **shadow 掉用户级单一源**：改进流不到项目、各项目副本各自漂移。本步把重复副本清掉，让通用 skill 一律从用户级解析。
>
> **只清通用 skill**：项目专属 skill（不在 `skills/` 清单里的，如某项目的 `restart-ui` / `acceptance` / `test-first`）**绝不碰**。
>
> 所有模式（init / 更新 / 收编）都跑：fresh-init 项目本来没有副本 → 空跑；存量项目才有清理对象（幂等）。

对每个 bridgeforge 出品的通用 skill（清单 = `skills/` 目录），若 `<project>/$PROJECT_SKILLS_DIR/$s/` 存在就分类：

```bash
SKILLS_SRC="$BRIDGEFORGE_HOME/skills"
PROJ_SKILLS="$PROJECT_SKILLS_DIR"
for s in $(ls "$SKILLS_SRC"); do
  [ -d "$SKILLS_SRC/$s" ] || continue
  [ -d "$PROJ_SKILLS/$s" ] || continue            # 项目没这个副本 → 无需清
  if diff -rq "$SKILLS_SRC/$s" "$PROJ_SKILLS/$s" >/dev/null 2>&1; then
    echo "DUP-IDENTICAL : $s（与上游字节一致的纯重复 → 安全删）"
  else
    echo "DUP-DIVERGENT : $s（与上游不同 → 需判断，见下表）"
  fi
done
```

**处理（逐个确认，绝不批量/静默删 —— 复用 Step 0「不一致 → 问」的好心）**：

> **红线：每个重名副本删除前都要单独问用户一次**（含字节一致的纯重复）。分类结果只用来给用户一个**推荐动作**，不替用户做删除决定——这是「逐个确认是否删除重名 skill」的核心。先给一份总览清单（哪些是 IDENTICAL / 旧版镜像 / 含专属数据），再**逐个**呈现、逐个等用户拍板，确认一个删一个。用户不答 / 答"留" → 保留该副本，跳到下一个。

| 分类 | 推荐动作（呈现给用户的默认建议） | 删除前必做 |
|------|------|------|
| **DUP-IDENTICAL**（与上游字节一致）| **建议删**（纯重复，删了改从用户级单一源解析，无数据损失）→ 问"删 (y) / 留 (n)" | 无 |
| **DUP-DIVERGENT 但只是旧版镜像**（无项目专属内容，纯过时）| **建议删**（过时副本，用户级是更新版）→ 问"删 (y) / 留 (n)" | 无 |
| **DUP-DIVERGENT 且含项目专属数据** | **建议保留 / 迁移后删**（绝不轻易删）→ 给 `diff` 问"删（回落用户级单一源）/ 保留定制" | 两类典型：① `find-doc` / `sync-docs` 旧版**内联字典/映射表**（外置前的填充版）→ 先把字典迁到 `$PROJECT_AGENT_DIR/find-doc.map.md` / `$PROJECT_AGENT_DIR/sync-docs.map.md`（格式分别见 find-doc Step 4 / sync-docs Step 7），迁完且用户确认后再删副本；② 其他被用户改过的定制 → 给 `diff` 让用户判 |

> 逐个确认看似比"IDENTICAL 直接删"啰嗦，但单一源去重是低频一次性动作（每个项目一生跑几次），且删的是项目 git 里的文件 —— 让用户对每个重名 skill 有知情权 + 否决权，比省那几次确认更重要。批量删的"效率"在这里不值得拿"误删用户没意识到自己改过的副本"的风险换。

**判定"含项目专属数据"**：副本里出现项目实际路径 / rule 文件名 / 内联填充的非-placeholder 字典。拿不准 → 当"定制"处理问用户，**宁可多问不可误删**。

> **可移植性**：通用 skill 移出项目 git 后，`git clone` 单独不再恢复它们 → 靠在该机跑 `$ENTRY_COMMAND`（Step 0 装用户级）恢复。这是 DRY（N 项目不各存一份）对 clone-完整性的**有意取舍**；`templates/$TEMPLATE_AGENT/rules/portability.md §2` 已记录该拆分。项目专属**数据**（`$PROJECT_AGENT_DIR/find-doc.map.md` 等）仍在项目 git，可移植性不受影响。

**用户级扁平残留清理（C6 — 补充）**：用户级 `$USER_SKILLS_DIR/` 可能遗留历史**扁平文件**（如 `collab.md` / `debate.md`）与目录式（`collab/SKILL.md`）**同名 shadow**——agent 只扫 `<name>/SKILL.md`，扁平文件不被识别，反而遮蔽目录式 skill（路径解析可能优先命中扁平文件名）。本步同时清这类扁平残留：

```bash
SKILLS_DST="$USER_SKILLS_DIR"
SKILLS_SRC="$BRIDGEFORGE_HOME/skills"

for s in $(ls "$SKILLS_SRC"); do
  [ -d "$SKILLS_SRC/$s" ] || continue
  flat="$SKILLS_DST/$s.md"         # 扁平文件形式
  dir_skill="$SKILLS_DST/$s/SKILL.md"   # 目录式（正确）
  if [ -f "$flat" ] && [ -f "$dir_skill" ]; then
    echo "FLAT-SHADOW: $flat（与目录式 $s/SKILL.md 同名，建议删扁平文件）"
  fi
done
```

- **FLAT-SHADOW 命中** → 逐个问用户"删扁平 `$s.md`（留目录式单一源）/ 保留"。用户不答 → 保留。
- **扁平文件含 frontmatter `user_invocable` / `user-invocable`**：目录式正确拼写是 `user_invocable`（下划线）；`user-invocable`（连字符）是历史漂移。删扁平后目录式 frontmatter 若用连字符，提醒改为下划线。
- **只清 bridgeforge 出品的 skill 名**：非 bridgeforge 出品的扁平文件（项目定制的 `<proj>.md`）不碰。

### Step 1：核对当前位置

```bash
pwd                                 # 必须是新项目根目录
ls -la                              # 看是否已有 $PROJECT_ENTRY_FILE / $PROJECT_AGENT_DIR / doc/
git rev-parse --is-inside-work-tree # 是否已 git init
```

**若 cwd 已有 `$PROJECT_ENTRY_FILE` 或 `$PROJECT_AGENT_DIR/rules/`** → 立即停下问用户："检测到当前 agent 的入口文件/rules 已存在，但本项目还没有 BridgeForge 版本戳。要 (A) 保留现有内容，只补缺失骨架并 merge 配置；(B) 备份后覆盖入口文件/rules；(C) 退出？"

> 注：若该 dir 有 `$PROJECT_AGENT_DIR/.bridgeforge_version`，前置步骤已路由到**更新模式**，不会到这里。本分支只针对"有入口文件但无版本戳"的非托管项目。

**若 cwd 已有 `$PROJECT_AGENT_DIR/settings.json`** → **禁止直接覆盖**（会丢已有 hook/permission/env）。必须读现存 settings.json，把模板里的下列条目 **merge** 进去（数组追加，不替换），其他字段保持原样：
- `hooks.*`（各 hook 数组追加）
- `permissions.allow` / `permissions.ask` / `permissions.deny`（三个数组各自追加去重；**deny 优先级最高，绝不删用户已有 deny**；ask 同样只增不删）
- `permissions.defaultMode`：**仅当用户原配置没设过**才写 `acceptEdits`；用户已设（哪怕设成 `default`）则保留其值，不覆盖

merge 完后给用户 review 一次再保存。

**若 cwd 不是新项目根** → 问用户预期的目标项目根路径。

### Step 2：收集项目元信息

> **红线**：本 skill **强制铺设 doc/ 六层结构**，不接受跳过。doc/ 是项目级红线（见 `templates/$TEMPLATE_AGENT/$PROJECT_ENTRY_FILE` + `rules/workflow.md`）。如果用户明确不需要文档分层 → **建议改用其他脚手架**，不要用 bridgeforge。

一次性问全 4 个问题（不挤牙膏）：

1. **项目名**（用于 `$PROJECT_ENTRY_FILE` 标题）
2. **主语言/技术栈**（`python` / `rust` / `node` / `go` / `mixed` 等，用于快速命令模板**和 Step 3 自动裁剪 LANG-specific 段落**）
3. **目标操作系统**（`windows` / `macos` / `linux` / `cross-platform`，用于 Step 3 自动裁剪 PLATFORM-specific 段落）
4. **是否需要换机 checklist**（默认是；纯单机玩具项目可跳过）

**Q2/Q3 答案的特殊值**：
- 主语言答 `mixed` → 保留所有 LANG-specific 段落
- 操作系统答 `cross-platform` → 保留所有 PLATFORM-specific 段落

### Step 3：复制模板到目标项目

模板根在**本 skill 目录**的 `templates/`。skill 安装后通常在 `$BRIDGEFORGE_HOME/templates/`。

**Windows**：
```bash
SKILL_DIR="$BRIDGEFORGE_HOME"
# 不要整包复制 templates/，它现在同时包含 claude/codex 两套骨架。
# 按下方"实际复制清单"把 templates/$TEMPLATE_AGENT/ 映射到项目根与 $PROJECT_AGENT_DIR/。
```

**macOS/Linux** 同上。

**这批文件各干嘛（一眼速查）**：

| 批次 | 内容 | 用途 |
|------|------|------|
| `$PROJECT_ENTRY_FILE` | 骨架框架：鬼打墙红线 / ctx-budget / UI 主动问 / 文档管理 | 项目行为规范，§1/§3/§7 三处留空由用户渐进填充 |
| `rules/*.md` | 路径触发式规则：architecture / modules / debugging / workflow / portability / meta_rule_design | 按 `paths` frontmatter 按需加载，只在相关文件编辑时进入 context |
| `hooks/*.py` | 自动化钩子：ctx 预警 / 版本号检查 / snapshot / memory lint / skill 漂移检测等 | SessionStart / UserPromptSubmit / PreToolUse / PostToolUse 全自动触发 |
| `scripts/*.py` | 辅助脚本：memory 重建索引 / 搜索 / audit_user_allow（用户级 allow 审计）等 | 按需手动调用，非 hook 触发 |
| `settings.json` | 权限三档（allow/ask/deny）+ hook 注册 | 少弹窗噪音 + 危险操作强制确认 |
| `memory/MEMORY.md` | 空 memory 索引 + 4 类 memory 注释 | memory junction 目标文件 |
| `doc/README.md` | 文档分层结构模板 | 六层 doc/ 唯一索引 |

> **hook 成本提示（C8）**：hook 跑在用户输入和工具调用的关键路径上，每次触发都有 Python 冷启动开销。
> - **重型 hook**（如编译检查、全量 lint）应 `async` 后台执行或 debounce（加节流时间戳）
> - **轻量 hook** 应在读 stdin JSON 后**立即按 `file_path` / prompt 前缀短路退出**（匹配不上直接 `sys.exit(0)`），避免不必要的处理
> - StratusAgent 的 `cargo_check.py`（每次 .rs 编辑跑全量 `cargo check --workspace`）是反例——放后台/debounce 是正解

**实际复制清单**：

| 模板 | 目标 | 条件 |
|------|------|------|
| `templates/$TEMPLATE_AGENT/$PROJECT_ENTRY_FILE` | `<project>/$PROJECT_ENTRY_FILE` | 总是 |
| `templates/$TEMPLATE_AGENT/rules/*.md` | `<project>/$PROJECT_AGENT_DIR/rules/` | 总是 |
| `templates/$TEMPLATE_AGENT/memory/MEMORY.md` | `<project>/$PROJECT_AGENT_DIR/memory/MEMORY.md` | 总是 |
| `templates/$TEMPLATE_AGENT/hooks/*.py` | `<project>/$PROJECT_AGENT_DIR/hooks/` | **总是**（Python 是硬依赖，见下方"Python hook 体系") |
| `templates/$TEMPLATE_AGENT/scripts/*.py` | `<project>/$PROJECT_AGENT_DIR/scripts/` | **总是** |
| `templates/$TEMPLATE_AGENT/settings.json` | `<project>/$PROJECT_AGENT_DIR/settings.json`（**已存在则 merge 不覆盖**，详见 Step 1）| 总是（含 `permissions` + 整个 `hooks` 块） |
| `templates/$TEMPLATE_AGENT/doc/README.md` | `<project>/doc/README.md` | 总是 |
| `templates/$TEMPLATE_AGENT/VERSION` | `<project>/VERSION` | **条件复制**（见下方"版本号 SoT 条件复制"） |
| `templates/$TEMPLATE_AGENT/CHANGELOG.md` | `<project>/CHANGELOG.md` | 总是（即使有原生版本源，CHANGELOG 仍统一在此） |
| 写版本戳 | `<project>/$PROJECT_AGENT_DIR/.bridgeforge_version`（内容 = 本 skill clone 的 `VERSION`，如 `0.46.0`）| 总是（init 末尾写。既是"上次同步到哪版"记录，又是前置步骤判定 init/更新的信号） |
| 创建空目录 | `<project>/doc/{0_architecture,1_plan,1_plan/sprints,2_pending,3_design,4_archive,9_reference}/` | 总是 |
| `.gitignore` bridgeforge 机制块 | `<project>/.gitignore`（**已存在则 merge-append 不覆盖**，详见下方）| 总是 |

**`.gitignore` 兜底（堵 hook 生成物被误提交）**：bridgeforge 装的 hook 会自动生成一批临时产物——Python 字节码、session 快照、hook 日志。若下游 `.gitignore` 不挡，用户 `git add .` 会把它们一并提交（污染历史）。这是机制化义务，不能只靠口头约定。**确保**下游 `.gitignore` 含以下"bridgeforge 机制块"（**幂等**：缺哪行补哪行；已存在则 grep 守卫后 append；项目自己其他忽略项**绝不删**；下游无 `.gitignore` 则新建）：

```gitignore
# === bridgeforge 协作骨架机制自动生成（勿提交，由 bridgeforge skill 维护）===
__pycache__/
*.pyc
.claude/settings.local.json
.codex/settings.local.json
.runtime/session_state/
.runtime/focus/
.runtime/*.log
```

> 为何不整份 ship `templates/.gitignore`：完整 `.gitignore` 与项目主语言强耦合（Rust 忽略 `target/`、Node 忽略 `node_modules/`），bridgeforge 不该越俎代庖。这里只挡**bridgeforge 自身机制**产生的物（Python hook 是所有项目的硬依赖，故这几行语言无关）。`.runtime/` 下持久资产（嵌入工具/缓存）仍可 track，只忽略快照/日志，与 `rules/modules.md` 的「`.runtime/output` gitignored」选择性策略一致。

**Python hook 体系（所有项目无条件安装 — Python 是硬依赖）**：

```
所有项目（不分主语言，含 rust / node / go）：
  ✓ 复制 templates/$TEMPLATE_AGENT/hooks/ + templates/$TEMPLATE_AGENT/scripts/ 全部
  ✓ 保留 settings.json 整个 hooks 块（PreToolUse / PostToolUse / PostCompact / Stop / UserPromptSubmit）
  → 进入下方 "Python 解释器路径适配" 段

前置硬检查（Step 2 后、复制 hooks 前必做）：确认目标机有可用 Python（≥ 3.8）
  - 项目根有 .venv → 用 .venv 的 python（首选）
  - 否则系统 `python` 在 PATH 上 → 用系统 python
  - 两者都没有 → **停下，要求用户先装 Python 再继续**。hook 全是 .py，没 Python 跑不起来；
    不允许"先跳过 hook 以后再说"——version_check 等红线 hook 不能缺。
```

> **v0.12.0 起策略变更**：Python 从"可选（非 Python 项目跳过 hook）"改为"**硬依赖**（所有项目装 hook）"。
> 主因：`version_check` 把"每次 commit 必 bump 版本号"从软规则升级为机制强制，价值与项目主语言无关，
> 不该因主语言非 Python 而失去。即便是纯 Rust / Node 项目，也要求装 Python 让 hook 体系跑起来。
> 不接受 Python 依赖 → 改用其他纯文档脚手架（见 README "适合 / 不适合"）。

**版本号 SoT 条件复制**（基于项目原生版本源检测）：

```
检测项目根是否已有原生版本源：
  - package.json （Node）
  - Cargo.toml （Rust）
  - pyproject.toml / setup.py （Python，且文件里有 version 字段）

if 任一原生版本源存在:
  ✗ 跳过 templates/$TEMPLATE_AGENT/VERSION 复制（避免双 SoT 冲突，详见 templates/$TEMPLATE_AGENT/rules/workflow.md §9.1）
  ✓ 仍复制 templates/$TEMPLATE_AGENT/CHANGELOG.md（不冲突，所有项目都需要）
  → 向用户说明："检测到 <package.json/Cargo.toml/...>，已跳过 VERSION 文件复制。后续 bump 版本号请改原生源；CHANGELOG.md 仍统一在根目录维护。"
else (无原生版本源):
  ✓ 复制 templates/$TEMPLATE_AGENT/VERSION（初始内容 `0.1.0`）
  ✓ 复制 templates/$TEMPLATE_AGENT/CHANGELOG.md
  → 提示用户：CHANGELOG.md 的 `## [0.1.0] - {{TODAY}}` section 已带初始 entry，后续 bump 时按 workflow.md §9 规则追加新 section
```

**OPTIONAL 段落自动裁剪**（复制完后、替换占位符前必做）：

模板里的可选段落用 HTML 注释标记包住，按 Step 2 答案自动剔除不相关段落，让用户拿到的模板只含相关内容（避免 context 污染）。

标记格式：
```
<!-- OPTIONAL_BEGIN <TYPE>: <VALUE> -->
... 段落内容 ...
<!-- OPTIONAL_END -->
```

支持的 `<TYPE>: <VALUE>`：
- `PLATFORM: windows` / `PLATFORM: macos` / `PLATFORM: linux` — 平台特定段落
- `LANG: python` / `LANG: rust` / `LANG: node` / `LANG: go` — 语言特定段落
- `SCENARIO: rewrite` / `SCENARIO: native-binary` / `SCENARIO: build-product-mismatch` — 场景特定段落

裁剪逻辑（伪代码）：

```
user_platform = Step 2 Q3 答案
user_lang = Step 2 Q2 答案

for each .md file in 已复制的模板:
  for each OPTIONAL_BEGIN ... OPTIONAL_END 块:
    type, value = 解析标记
    if type == "PLATFORM":
      if user_platform == "cross-platform" or user_platform == value:
        保留段落（去掉 BEGIN/END 标记本身）
      else:
        删除整段（含 BEGIN/END 标记）
    elif type == "LANG":
      if user_lang == "mixed" or user_lang == value:
        保留段落（去掉 BEGIN/END 标记本身）
      else:
        删除整段
    elif type == "SCENARIO":
      # SCENARIO 类默认不启用，留 BEGIN/END 标记原样不动
      # 让用户后续手动判断要不要启用
      保留段落 + 保留标记
```

**关键点**：
- `PLATFORM` / `LANG` 类按用户答案物理删除整段（含标记），保证非目标平台/语言的项目**根本看不到**这些段落
- `SCENARIO` 类默认保留标记，方便用户后续判断（如项目从纯应用变为含 native 绑定时，搜 `SCENARIO: native-binary` 解开）
- 裁剪后用 `grep -c "OPTIONAL_BEGIN PLATFORM\|OPTIONAL_BEGIN LANG" <file>` 验证应为 0（确认所有 PLATFORM/LANG 段落都被处理）

**Python 解释器路径适配**（所有项目，复制完 hooks/scripts 后必做）：

1. **检测 .venv** 是否存在于目标项目根：
   - Windows：`.venv/Scripts/python.exe`
   - Unix：`.venv/bin/python`
2. **改写 settings.json 里所有 hook 命令的 Python 解释器路径**：
   - `.venv` 存在 → 用默认 `.venv/Scripts/python.exe`（Windows）/ `.venv/bin/python`（Unix）
   - `.venv` 不存在但系统 `python` 可用（如纯 Rust/Node 项目）→ 改成裸 `python`，每个 hook 的 `comment` 字段尾部加："建好 .venv 后可改回 .venv/Scripts/python.exe"
   - 项目用 conda → 改成 conda env 绝对路径
   - **系统也没有 python** → 不要继续铺 hook；回到上方"前置硬检查"，要求用户先装 Python
3. **调 `context_warning.py` 的 `WINDOW` 常量**（约 line 34）适配模型窗口（与 hook 头部注释保持一致）：
   - 1M 专用版（model-id 含 `[1m]` 后缀）→ `1_000_000`（**默认值**）
   - 标准 200k 模型（Opus 4.8 / Sonnet 4.6 / Haiku 4.5 等无 `[1m]`）→ **必须手动改回** `200_000`，否则分母过大永不预警（静默 compact 风险）
4. **跑通验证**：在目标项目根执行 `python "$PROJECT_AGENT_DIR/hooks/session_snapshot.py" manual`，期望输出 `[session snapshot manual] -> .runtime/session_state/<ts>.md`。失败 → 检查 Python 解释器路径 / .runtime/ 目录权限。
5. **提示用户**：
   - `$PROJECT_ENTRY_FILE` 的 ctx-budget 红线生效，新会话开始即享受预警保护
   - PostCompact / Stop hook 自动启用 → 防 compact 吞状态 + Word-style 自动保存
   - `skill_sync_check` SessionStart hook 自动启用 → 用户级通用 skill 与上游漂移时，session 开始会打印 `[skill-sync]` 提示跑 `$ENTRY_COMMAND` 同步（只读检测，不自动改）
   - `find-doc` / `sync-docs` 两个 SKILL.md 里有 placeholder 表（topic→rule 字典 / 源码→文档映射），**现在不必填**，项目演进出稳定目录结构后再补；agent 在任务收尾时会主动提醒
   - 详见 README.md `## Python 依赖（agent 安装前必读）` 段

**目标机无 Python 时的处理**（前置硬检查未通过时必做）：

不要继续铺 hook（硬依赖缺失）。向用户明确说明并给出修复路径：
> bridgeforge 的 hook 自动化体系（含 `version_check` 版本号 commit 硬检查、ctx 预警、自动 snapshot、memory/rules lint 等）**全部用 Python 实现，是硬依赖**。检测到本机没有可用 Python（既无项目 `.venv`，PATH 上也没有 `python`）。
>
> **请先装 Python（≥ 3.8）再重跑 `$ENTRY_COMMAND`**：
> - Windows：装 python.org 发行版 或 `winget install Python.Python.3`
> - macOS：`brew install python` 或系统自带
> - Linux：`apt install python3` / 发行版包管理器
> - 建议在项目根建 `.venv`（`python -m venv .venv`）让 hook 用项目隔离解释器，更可移植
>
> 已铺好的核心模板（rules / 入口文件 / doc 分层 / skill / **permissions 少弹框配置**）不受影响，装好 Python 后重跑即补齐 hook 段。
> 详见 README.md `## Python 依赖（agent 安装前必读）` 段。

### Step 4：替换占位符

用 Edit 工具把以下占位符替换成 Step 2 收集的值：

| 占位符 | 替换为 |
|--------|--------|
| `{{PROJECT_NAME}}` | Step 2 项目名 |
| `{{PRIMARY_LANGUAGE}}` | Step 2 主语言 |
| `{{TODAY}}` | 今天日期（YYYY-MM-DD） |

`{{...}}` 之外的占位区段（架构红线 / 快速命令 / 项目结构）保留 `<!-- TODO: ... -->` 注释，让用户后续手填——**不要替你瞎编**。

### Step 5：建 memory junction

按当前 agent 分流：

**Claude Code**：跑对应平台的脚本（要求用户 review 并执行，不要静默 sudo）：

**Windows**（管理员 PowerShell 或开发者模式）：
```powershell
& <SKILL_DIR>\scripts\setup-junction.ps1 -ProjectPath <project-abs-path>
```

**macOS/Linux**：
```bash
bash <SKILL_DIR>/scripts/setup-junction.sh <project-abs-path>
```

脚本逻辑：
1. 计算 project-hash（项目路径 hash，与 Claude Code 内部一致）
2. 系统 memory 路径 = `~/.claude/projects/<hash>/memory/`
3. 若该路径已是 junction/symlink → 跳过
4. 若是普通目录且非空 → 提示用户 backup 后再跑
5. 否则 → 创建 junction（Win）或 symlink（Unix）指向 `<project>/.claude/memory/`

**Codex**：不要跑上面的 Claude 专用 `setup-junction.*`。Codex 由项目内 hook 自愈：

```bash
python .codex/hooks/memory_junction_check.py
```

Codex hook 逻辑：
1. 系统 memory 路径 = `~/.codex/projects/<project-hash>/memory/`
2. 项目 memory 路径 = `<project>/.codex/memory/`
3. 若系统路径已是 junction/symlink → 跳过
4. 若系统路径不存在且项目 memory 存在 → 建 junction/symlink
5. 若系统路径是有内容实目录 → 复制进项目 memory，系统目录改名 `.bak` 后再建链接，**不硬删**

### Step 6：初始化 git（可选）

若项目还没 `git init`：
```bash
git init
git add .
git status        # 给用户 review
```

**不自动 commit** — 等用户填完占位再 commit。

### Step 7：写版本戳 + 输出 next-step 清单

**先写版本戳**（让本项目纳入更新管理）：把本 skill clone 的 `VERSION` 内容写进 `<project>/$PROJECT_AGENT_DIR/.bridgeforge_version`：

```bash
cp "$BRIDGEFORGE_HOME/VERSION" "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

之后用户在本项目重跑 `$ENTRY_COMMAND` 即自动进入**更新模式**（拉上游增量），不会再全新铺设。

**再呈现给用户**：

```
✅ 骨架已铺设，下一步你需要手填这 3 处：

1. 入口文件 §1 架构红线 — 写明你项目的"职责边界 / 数据流方向 / 禁止反向"
2. 入口文件 §3 快速命令 — 填项目的构建/测试/启动命令
3. 入口文件 §7 项目结构 — 列出顶层目录及职责

可选：
- 在 agent rules 目录下按需新增 path-specific 规则
- doc/README.md 索引随项目展开补充
- 跑 git commit 收尾
```

---

## 收编模式 (adopt)（已有 bridgeforge 衍生内容但无版本戳）

> 触发：前置 Step 前-3 判定 cwd 无 `$PROJECT_AGENT_DIR/.bridgeforge_version`，但已有入口文件/rules 命中 bridgeforge 衍生指纹（≥2 项）。常见于 **pre-stamp 老安装**（版本戳机制 v0.14.0 才引入）或手动拷过模板的项目。
>
> **核心红线：收编 = 登记纳管，绝不覆盖任何已有文件。** 用户已有内容大概率比上游脱敏模板更全（业务演进过），覆盖 = 倒退。

### A1：确认 + 写戳（默认动作）
1. 列出命中的指纹项，向用户说明："检测到本项目像是 bridgeforge 铺过但缺版本戳，建议**收编**（仅登记纳管，不动你任何文件）。"
2. 用户确认后写戳：
   ```bash
   cp "$BRIDGEFORGE_HOME/VERSION" "$PROJECT_AGENT_DIR/.bridgeforge_version"
   ```
   > 戳值 = 上游**当前** VERSION，等于声明"以此为同步基线"。首次收编**不补历史增量**（视现状为最新），从下次 `$ENTRY_COMMAND` 起才按 `(此版, 新版]` 拉 `[product]` 增量。

### A2：可选——顺便补上游差量
- 用户若想"把上游比我新的通用增量也过一遍"，在写戳**前**先把戳临时写成一个更早的基线（用户记得的安装版本；记不得就保守取 `0.1.0`），再走 [更新模式](#更新模式cwd-已被-bridgeforge-铺过时) U2 的类 C diff，让用户逐段吸收。
- 拿不准基线就**不补** —— 收编默认语义是"以现状为基线"，宁可漏增量也不冒覆盖业务内容的风险。

### 收编模式禁止
- ❌ 覆盖（哪怕"备份后覆盖"）任何已有入口文件 / rules / settings —— 那是 fresh-init 分支的事，收编不做
- ❌ 动 memory / doc
- ❌ 不经用户确认直接写戳

---

## 更新模式（cwd 已被 bridgeforge 铺过时）

> 触发：前置步骤检测到 `$PROJECT_AGENT_DIR/.bridgeforge_version`。这是 `$ENTRY_COMMAND` 的"拉上游增量到现有项目"流程——**机械半场**（拉 / diff / 分类 / 呈现）由 skill 做，**判断半场**（rules/入口文件选择性吸收）全程交用户。完整判据见 `$BRIDGEFORGE_HOME/docs/sync-from-upstream-playbook.md`（下称 playbook）。

### U1：算增量
- 读 cwd 的 `$PROJECT_AGENT_DIR/.bridgeforge_version`（下游上次同步的版本）vs clone 的 `VERSION`（上游当前版本，前置步骤已 pull 到最新）。
- 相等 + 文件无差异 → 报告"已是最新（vX.Y.Z）"后退出。
- 不等 → 从 clone 的 `CHANGELOG.md` 抓 `(上次, 现在]` 区间所有 **`[product]`** 条目，给用户一份"上游这些更新冲着下游来"的清单（`[repo]` / `[meta]` 条目不影响下游，过滤掉）。
- **`[product]` 短路**：若 `(上次, 现在]` 区间**没有任何 `[product]` 条目**（这次上游更新全是 `[repo]` / `[meta]`，与下游无关）→ **不跑 U2 全量 diff**，直接报"本次上游更新无 `[product]` 变更，下游无需同步"，把版本戳刷到当前 `VERSION`（U4）后退出。

### U2：按 playbook §2 表格分类 diff
逐类对比 clone 的 `templates/$TEMPLATE_AGENT/` 与 cwd 的 `$PROJECT_AGENT_DIR/`，**先给总览清单，再逐项过**：

| 类 | 文件 | 策略 |
|----|------|------|
| A | `$PROJECT_AGENT_DIR/hooks/*.py` `$PROJECT_AGENT_DIR/scripts/*.py` + 用户级 `$USER_SKILLS_DIR/` | 下游副本与模板**一致** → 提议覆盖（确认）；**被改过** → 标红给 diff 问用户（**不无脑覆盖**） |
| B | `$PROJECT_AGENT_DIR/settings.json` | **merge 不覆盖**：上游通用 hook 段更新/加入；保留下游 `permissions` / `additionalDirectories` / 自定义 hook 注册。给 merge 预览，确认后写 |
| C | `$PROJECT_AGENT_DIR/rules/*.md` `$PROJECT_ENTRY_FILE` | **只 diff，绝不自动改**。每个差异段贴 playbook §2 类C 判据：🟢 上游通用增量(吸收) / 🟡 下游业务补充(保留) / 🔴 上游脱敏后减弱(保留下游)，用户逐段定 |
| D | `$PROJECT_AGENT_DIR/memory/` `doc/` | **碰都不碰** |
| E | `<project>/.gitignore` | 按 Step 3「`.gitignore` 机制块」**幂等 append** bridgeforge 机制忽略项（缺行才补，项目自有忽略项不删）。存量项目早期没这块，更新时补上才不漏（否则 hook 生成物一直裸奔） |

### U3：路径适配
更新进来的 hook 命令若引用 `.venv` 但 cwd 无 `.venv` → 同 init 的"Python 解释器路径适配"，改裸 `python`。

### U4：验证 + 收尾
- 跑更新过的 hook 看 exit 0：`python "$PROJECT_AGENT_DIR/hooks/<hook>.py"`。
- 把 `$PROJECT_AGENT_DIR/.bridgeforge_version` 写成 clone 的当前 `VERSION`。
- **不自动 commit**：`git status` + `git diff` 给用户 review，提示自行 commit（参考 playbook §5）。

### 更新模式禁止
- ❌ 自动覆盖 rules / 入口文件（类C 必须用户逐段定）
- ❌ 动 memory / doc（类D 业务私有）
- ❌ 跨多个项目批量同步（一次只对当前 cwd）
- ❌ 自动 commit

---

## 禁止

- ❌ 静默覆盖已存在的入口文件 / rules — 必须先问用户
- ❌ 自己编填架构红线 / 项目结构 — 这是用户必须自己写的核心内容
- ❌ 自动 git commit — 留给用户
- ❌ 跳过 memory junction 这步——它是项目协作体系能跨机复现的关键
- ❌ **静默**覆盖用户已有的同名 skill — Step 0 对已存在 skill 先比对：一致则静默更新，不一致（可能是定制）必须给 diff 问用户，绝不静默盖掉
- ❌ **批量 / 静默删**项目级重名 skill 副本 — Step 0.5 清重复副本必须**逐个确认**：哪怕字节一致的纯重复也要单独问"删/留"，用户不答即保留，绝不一次性扫删
- ❌ 在 bridgeforge 源头仓库**自己身上**跑 bootstrap / 更新 — 前置 Step 前-2 工厂自检应已硬拒（源头改框架直接编辑 `templates/` / `SKILL.md`）

---

## 模板包含的内容速查

| 文件 | 性质 | 说明 |
|------|------|------|
| `$PROJECT_ENTRY_FILE` | 部分模板 + 部分占位 | §1/§3/§7 占位，其余通用直接给（含鬼打墙红线 / UI 主动问范式 / ctx-budget 信号约定） |
| `rules/architecture.md` | 骨架 | 职责边界 / 数据流 / 禁止反向横向（占位） |
| `rules/modules.md` | 骨架 | 新增模块流程 / 禁止事项表（占位） |
| `rules/debugging.md` | **通用** | 鬼打墙红线 + 修 bug 前确认根因 + 性能先量化 |
| `rules/workflow.md` | **通用** | 同步文档 / 主动写规则 / 经验总结 / 任务收尾自查 |
| `rules/portability.md` | **通用** | 换机可移植性 / pip 陷阱 / hooks 路径约束 |
| `hooks/context_warning.py` | **通用** | UserPromptSubmit hook，跨 75/85/95% 阈值输出 [ctx-budget] 信号给当前 agent |
| `hooks/version_check.py` | **通用** | PreToolUse(Bash) hook，拦 `git commit`：staged 未含版本号文件（VERSION/package.json/Cargo.toml/pyproject.toml）则 exit 2 阻断，强制落实 workflow.md §9「每次 commit 必 bump」。`[skip-version]` / `--amend` / merge 可豁免 |
| `hooks/allow_memory_write.py` | **通用** | PreToolUse(Write/Edit) hook，放行 memory `.md` 写入免弹窗。agent 配置目录是受保护目录，写入无视 acceptEdits/allow 规则强制弹窗；memory 在其下被连带保护。本 hook 在弹窗前返回 `permissionDecision:allow`，只放行 memory 的 `.md`，settings/hooks 本体不碰。**改完须开新会话生效**（hook 不热重载） |
| `settings.json` | **通用** | ① `permissions` **三档**（`defaultMode: acceptEdits`）：**allow 放宽**（日常 git 读写/shell 读/构建测试静默跑，压弹窗噪音）+ **ask 必弹**（push/rebase/reset/checkout 等慎重项强制确认）+ **deny 拦死**（跨平台：Bash `rm -rf`/git 历史销毁/发布 + **PowerShell `Remove-Item` 等 Windows 删除** + 读写 `.env`/密钥/`~/.ssh`）。优先级 deny>ask>allow；deny 在 bypass 下仍生效。设计目标=弹窗皆信号。注：deny 是减速带（子进程可绕过），防手滑非保险柜；② 注册 ctx-budget 等 hook。已存在则 merge 不覆盖（详见 Step 1） |
| `memory/MEMORY.md` | 空索引 | 含 4 类 memory 命名约定注释 |
| `doc/README.md` | 索引模板 | 0_architecture (含 acceptance + TODO-INDEX) / 1_plan (含 sprints) / 2_pending / 3_design / 4_archive / 9_reference 分层说明 |
| `VERSION` | 单一事实源 | 初始 `0.1.0`；若项目有原生版本源（`package.json` / `Cargo.toml` / `pyproject.toml`）则**跳过复制**避免双 SoT |
| `CHANGELOG.md` | 通用骨架 | Keep a Changelog 格式 + 引用 `rules/workflow.md §9` 语义；含 `[0.1.0] - {{TODAY}}` 初始 entry，所有项目都复制 |
| `$PROJECT_AGENT_DIR/.bridgeforge_version` | 生成（非模板文件）| init 末尾写 = 安装时 bridgeforge 版本；重跑 `$ENTRY_COMMAND` 据此进**更新模式**（拉上游 `[product]` 增量）而非全新铺设 |
| `skills/*/SKILL.md` | **通用** | 协作 skill 集（feature-dev / plan / collab / debate / escalate / snapshot / resume / git-sync / archive-scan / todo / find-doc / find-memory / summary / sync-docs / harvest / spinoff / focus）。Step 0 自检补齐到 `$USER_SKILLS_DIR/` 平级；Step 0.5 清掉项目里的重复副本（单一源）。find-doc / sync-docs 的项目专属字典外置 `$PROJECT_AGENT_DIR/*.map.md`（不进 skill 本体）。 |
