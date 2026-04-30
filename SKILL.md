---
description: 在新项目里铺设标准化的 CLAUDE.md / rules / memory junction / doc 分层骨架。复制深度模板（含鬼打墙红线、UI 主动问范式、可移植性约束、文档管理规则）后让用户填项目特定占位。
---

# /setup_agent — 项目协作骨架初始化

**定位**：一次性给新项目装好"Claude Code 协作管理体系"——双层 CLAUDE.md、rules 分层加载、memory junction、doc 三层归档。运行后用户只需填占位（架构红线 / 快速命令 / 项目结构）即可上线。

> 模板素材出自 StratusAgent 项目长期沉淀（鬼打墙红线、UI 主动问 4 件事、换机可移植性、文档分层归档）。已剥离项目特定内容，只留通用骨架。

---

## 执行流程

### Step 1：核对当前位置

```bash
pwd                                 # 必须是新项目根目录
ls -la                              # 看是否已有 CLAUDE.md / .claude/ / doc/
git rev-parse --is-inside-work-tree # 是否已 git init
```

**若 cwd 已有 CLAUDE.md 或 `.claude/rules/`** → 立即停下问用户："检测到已存在 CLAUDE.md/rules，要 (A) 跳过已存在的文件只补缺失部分；(B) 备份后覆盖；(C) 退出？"

**若 cwd 不是新项目根** → 问用户预期的目标项目根路径。

### Step 2：收集项目元信息

一次性问全 4 个问题（不挤牙膏）：

1. **项目名**（用于 CLAUDE.md 标题）
2. **主语言/技术栈**（Rust / Python / TypeScript / Go / Mixed-XX 等，用于快速命令模板）
3. **是否需要换机 checklist**（默认是；纯单机玩具项目可跳过）
4. **doc/ 是否要建**（默认是；纯单文件项目可跳过）

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
| `templates/doc/README.md` | `<project>/doc/README.md` |
| 创建空目录 | `<project>/doc/{1_plan,2_pending,4_archive,9_reference}/` |

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

---

## 模板包含的内容速查

| 文件 | 性质 | 说明 |
|------|------|------|
| `CLAUDE.md` | 部分模板 + 部分占位 | §1/§3/§7 占位，其余通用直接给 |
| `rules/architecture.md` | 骨架 | 职责边界 / 数据流 / 禁止反向横向（占位） |
| `rules/modules.md` | 骨架 | 新增模块流程 / 禁止事项表（占位） |
| `rules/debugging.md` | **通用** | 鬼打墙红线 + 修 bug 前确认根因 + 性能先量化 |
| `rules/workflow.md` | **通用** | 同步文档 / 主动写规则 / 经验总结 / 任务收尾自查 |
| `rules/portability.md` | **通用** | 换机可移植性 / pip 陷阱 / hooks 路径约束 |
| `memory/MEMORY.md` | 空索引 | 含 4 类 memory 命名约定注释 |
| `doc/README.md` | 索引模板 | 1_plan / 2_pending / 4_archive / 9_reference 分层说明 |
