---
description: 在新项目里铺设标准化的 CLAUDE.md / rules / memory junction / doc 分层骨架。复制深度模板（含鬼打墙红线、UI 主动问范式、可移植性约束、文档管理规则）后让用户填项目特定占位。同时自检并补齐用户级通用 skill（plan / escalate / snapshot / summary 等）。
---

# /setup_agent — 项目协作骨架初始化

**定位**：一次性给新项目装好"Claude Code 协作管理体系"——双层 CLAUDE.md、rules 分层加载、memory junction、doc 三层归档；**并自检 ~/.claude/skills/ 下的 12 个通用协作 skill，缺哪个补哪个**。运行后用户只需填占位（架构红线 / 快速命令 / 项目结构）即可上线。

> 模板素材出自 StratusAgent 项目长期沉淀（鬼打墙红线、UI 主动问 4 件事、换机可移植性、文档分层归档、通用协作 skill 集）。已剥离项目特定内容，只留通用骨架。

---

## 执行流程

### Step 0：自检并补齐用户级通用 skill

本 skill 仓库内的 `skills/` 子目录包含 12 个通用协作 skill（脱敏自 StratusAgent 长期沉淀）。Claude Code 只扫描 `~/.claude/skills/<name>/SKILL.md` 顶层，**不递归**——所以 `~/.claude/skills/setup_agent/skills/<name>/SKILL.md` 这样嵌套的 skill 扫不到，必须复制到 `~/.claude/skills/<name>/` 平级。

**自检逻辑（幂等，不覆盖已有）**：

```bash
SKILL_DIR="$HOME/.claude/skills/setup_agent"   # 本 skill 的仓库 clone 位置
SKILLS_SRC="$SKILL_DIR/skills"
SKILLS_DST="$HOME/.claude/skills"

for s in plan collab debate escalate snapshot resume git-sync archive-scan todo find-doc summary sync-docs; do
  if [ ! -d "$SKILLS_DST/$s" ]; then
    cp -r "$SKILLS_SRC/$s" "$SKILLS_DST/$s"
    echo "✓ 安装通用 skill: $s"
  else
    echo "- 已存在，跳过: $s"
  fi
done
```

**12 个通用 skill 速查**：

| Skill | 触发 | 用途 |
|------|------|------|
| `plan` | `/plan` | 只读分析，列任务/风险/文件，等用户确认后再实施 |
| `collab` | `/collab` | 分治协作，拆分子任务并行执行 |
| `debate` | `/debate` | 双 Agent 辩论，多轮讨论达成共识 |
| `escalate` | `/escalate` | 鬼打墙急停按钮（详见 CLAUDE.md §8） |
| `snapshot` | `/snapshot` | 手动存档 session 工作状态 |
| `resume` | `/resume` | 读 snapshot 接续上下文（上下文不够时换会话用） |
| `git-sync` | `/git-sync` | 全自动 fetch / commit / push |
| `archive-scan` | `/archive-scan` | 扫描 doc/2_pending/ 可归档候选 |
| `todo` | `/todo <描述>` | 新问题归档到 TODO-INDEX 主表（短期）或 1_plan/ 远期文档 |
| `find-doc` | agent 主动 | doc 综合检索（grep + read 一次性） |
| `summary` | `/summary` | 总结对话决策写入 memory，并按需更新 rules/docs |
| `sync-docs` | `/sync-docs` | 根据代码变更同步设计文档 |

**告知用户**：若复制了任何 skill，提示"需要重启 Claude Code 才能看到新 skill 在 / 列表里"。

> 跳过条件：若用户明确说"我不要这些通用 skill"，可在 Step 0 完全跳过；但默认全装。

### Step 1：核对当前位置

```bash
pwd                                 # 必须是新项目根目录
ls -la                              # 看是否已有 CLAUDE.md / .claude/ / doc/
git rev-parse --is-inside-work-tree # 是否已 git init
```

**若 cwd 已有 CLAUDE.md 或 `.claude/rules/`** → 立即停下问用户："检测到已存在 CLAUDE.md/rules，要 (A) 跳过已存在的文件只补缺失部分；(B) 备份后覆盖；(C) 退出？"

**若 cwd 已有 `.claude/settings.json`** → **禁止直接覆盖**（会丢已有 hook/permission/env）。必须读现存 settings.json，把模板里的 `hooks.UserPromptSubmit` 条目 **merge** 进去（数组追加，不替换）；其他字段保持原样。merge 完后给用户 review 一次再保存。

**若 cwd 不是新项目根** → 问用户预期的目标项目根路径。

### Step 2：收集项目元信息

> **红线**：本 skill **强制铺设 doc/ 六层结构**，不接受跳过。doc/ 是项目级红线（见 `templates/CLAUDE.md` §11 + `rules/workflow.md` §5.5）。如果用户明确不需要文档分层 → **建议改用其他脚手架**，不要用 setup_agent。

一次性问全 4 个问题（不挤牙膏）：

1. **项目名**（用于 CLAUDE.md 标题）
2. **主语言/技术栈**（`python` / `rust` / `node` / `go` / `mixed` 等，用于快速命令模板**和 Step 3 自动裁剪 LANG-specific 段落**）
3. **目标操作系统**（`windows` / `macos` / `linux` / `cross-platform`，用于 Step 3 自动裁剪 PLATFORM-specific 段落）
4. **是否需要换机 checklist**（默认是；纯单机玩具项目可跳过）

**Q2/Q3 答案的特殊值**：
- 主语言答 `mixed` → 保留所有 LANG-specific 段落
- 操作系统答 `cross-platform` → 保留所有 PLATFORM-specific 段落

### Step 3：复制模板到目标项目

模板根在**本 skill 目录**的 `templates/`。skill 安装后通常在 `~/.claude/skills/setup_agent/templates/`。

**Windows**：
```bash
SKILL_DIR="$HOME/.claude/skills/setup_agent"
cp -r "$SKILL_DIR/templates/." .
```

**macOS/Linux** 同上。

实际复制清单：

| 模板 | 目标 |
|------|------|
| `templates/CLAUDE.md` | `<project>/CLAUDE.md` |
| `templates/rules/*.md` | `<project>/.claude/rules/` |
| `templates/memory/MEMORY.md` | `<project>/.claude/memory/MEMORY.md` |
| `templates/hooks/context_warning.py` | `<project>/.claude/hooks/context_warning.py` |
| `templates/settings.json` | `<project>/.claude/settings.json`（**已存在则 merge 不覆盖**，详见 Step 1）|
| `templates/doc/README.md` | `<project>/doc/README.md` |
| 创建空目录 | `<project>/doc/{0_architecture,1_plan,1_plan/sprints,2_pending,3_design,4_archive,9_reference}/` |

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

**ctx-budget hook 适配**（复制完后必做）：

1. 检查目标项目用的 Python 解释器路径是否匹配 `templates/settings.json` 里的 `.venv/Scripts/python.exe`
   - 项目用 conda → 改成 `python` 或 conda env 绝对路径
   - 项目无 venv → 改成系统 `python`
2. 检查目标项目使用的 Claude 模型窗口，调 `context_warning.py:27` 的 `WINDOW` 常量
   - Opus 4.7 / Sonnet 4.6 1M context → `1_000_000`（默认）
   - 200k context 模型 → `200_000`
3. 提示用户：CLAUDE.md §10 ctx-budget 红线生效，新会话开始即享受预警保护

### Step 4：替换占位符

用 Edit 工具把以下占位符替换成 Step 2 收集的值：

| 占位符 | 替换为 |
|--------|--------|
| `{{PROJECT_NAME}}` | Step 2 项目名 |
| `{{PRIMARY_LANGUAGE}}` | Step 2 主语言 |
| `{{TODAY}}` | 今天日期（YYYY-MM-DD） |

`{{...}}` 之外的占位区段（架构红线 / 快速命令 / 项目结构）保留 `<!-- TODO: ... -->` 注释，让用户后续手填——**不要替你瞎编**。

### Step 5：建 memory junction

跑对应平台的脚本（要求用户 review 并执行，不要静默 sudo）：

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

### Step 6：初始化 git（可选）

若项目还没 `git init`：
```bash
git init
git add .
git status        # 给用户 review
```

**不自动 commit** — 等用户填完占位再 commit。

### Step 7：输出 next-step 清单

呈现给用户：

```
✅ 骨架已铺设，下一步你需要手填这 3 处：

1. CLAUDE.md §1 架构红线 — 写明你项目的"职责边界 / 数据流方向 / 禁止反向"
2. CLAUDE.md §3 快速命令 — 填项目的构建/测试/启动命令
3. CLAUDE.md §7 项目结构 — 列出顶层目录及职责

可选：
- 在 .claude/rules/ 下按需新增 path-specific 规则
- doc/README.md 索引随项目展开补充
- 跑 git commit 收尾
```

---

## 禁止

- ❌ 静默覆盖已存在的 CLAUDE.md / rules — 必须先问用户
- ❌ 自己编填架构红线 / 项目结构 — 这是用户必须自己写的核心内容
- ❌ 自动 git commit — 留给用户
- ❌ 跳过 memory junction 这步——它是项目协作体系能跨机复现的关键
- ❌ 覆盖用户已有的同名 skill — Step 0 自检必须幂等，已存在的 skill 跳过不覆盖（用户可能有定制版）

---

## 模板包含的内容速查

| 文件 | 性质 | 说明 |
|------|------|------|
| `CLAUDE.md` | 部分模板 + 部分占位 | §1/§3/§7 占位，其余通用直接给（含 §8 鬼打墙红线 / §9 UI 主动问范式 / §10 ctx-budget 信号约定） |
| `rules/architecture.md` | 骨架 | 职责边界 / 数据流 / 禁止反向横向（占位） |
| `rules/modules.md` | 骨架 | 新增模块流程 / 禁止事项表（占位） |
| `rules/debugging.md` | **通用** | 鬼打墙红线 + 修 bug 前确认根因 + 性能先量化 |
| `rules/workflow.md` | **通用** | 同步文档 / 主动写规则 / 经验总结 / 任务收尾自查 |
| `rules/portability.md` | **通用** | 换机可移植性 / pip 陷阱 / hooks 路径约束 |
| `hooks/context_warning.py` | **通用** | UserPromptSubmit hook，跨 75/85/95% 阈值输出 [ctx-budget] 信号给 Claude |
| `settings.json` | **通用** | 注册 ctx-budget hook 到 UserPromptSubmit；已存在则 merge 不覆盖 |
| `memory/MEMORY.md` | 空索引 | 含 4 类 memory 命名约定注释 |
| `doc/README.md` | 索引模板 | 0_architecture (含 acceptance + TODO-INDEX) / 1_plan (含 sprints) / 2_pending / 3_design / 4_archive / 9_reference 分层说明 |
| `skills/<12 个>/SKILL.md` | **通用** | 协作 skill 集（plan / collab / debate / escalate / snapshot / resume / git-sync / archive-scan / todo / find-doc / summary / sync-docs）。Step 0 自检补齐到 `~/.claude/skills/` 平级。 |
