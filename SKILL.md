---
description: 在新项目里铺设标准化的 CLAUDE.md / rules / memory junction / doc 分层骨架。复制深度模板（含鬼打墙红线、UI 主动问范式、可移植性约束、文档管理规则）后让用户填项目特定占位。同时自检并补齐用户级通用 skill（plan / escalate / snapshot / summary 等）。
version: 0.18.1
model: sonnet
---

# /setup_agent — 项目协作骨架初始化

**定位**：一次性给新项目装好"Claude Code 协作管理体系"——双层 CLAUDE.md、rules 分层加载、memory junction、doc 三层归档；**并自检 ~/.claude/skills/ 下的全部通用协作 skill（清单以本仓库 `skills/` 目录为准），缺哪个补哪个，再清掉项目里的重复副本（单一源）**。运行后用户只需填占位（架构红线 / 快速命令 / 项目结构）即可上线。

> 模板素材出自 StratusAgent 项目长期沉淀（鬼打墙红线、UI 主动问 4 件事、换机可移植性、文档分层归档、通用协作 skill 集）。已剥离项目特定内容，只留通用骨架。

---

## 执行流程

### 前置：拉上游最新 + 认场子（工厂自检 / 更新 / 收编 / init 四分类）

**Step 前-1 先拉上游**（无论 init 还是更新，都要先拿到最新模板，否则铺的是旧版本）：

```bash
git -C "$HOME/.claude/skills/setup_agent" pull --ff-only
```

- pull 失败（冲突 / 网络）→ 报告并停下，**不强拉**；让用户先手动处理 clone 再重跑。
- clone 不是 git 仓库（用户手动拷的）→ 跳过 pull，提示"建议改用 `git clone` 以便后续 `/setup_agent` 自动拉更新"。

**Step 前-2 工厂自检（最先判，硬闸）**：cwd 是不是 setup_agent 源头仓库**自己**？

```bash
# 同时满足才算源头：有产品层 templates/ + 根 SKILL.md 是 setup_agent 自己
test -f templates/CLAUDE.md && grep -q "项目协作骨架初始化" SKILL.md && echo FACTORY_SELF
```

- 命中 `FACTORY_SELF` → **立即硬拒并退出**，告诉用户："这是 setup_agent 源头仓库（模板工厂），不能在它自己身上 bootstrap / 更新——要改框架请直接编辑 `templates/` / `SKILL.md`，不要跑 `/setup_agent`。"
- 为什么这是第一闸：源头仓库**故意不带** `.claude/.setup_agent_version`（靠 `templates/` 存在性识别身份，比版本戳更本质，见 [docs/design-rationale.md](docs/design-rationale.md) §9.4）。没有这道闸，源头会落进下方"无戳 + 有 CLAUDE.md"分支被误当 init → 等于装修队拆自己样板间。

**Step 前-3 认场子（判定模式）**：

```bash
test -f .claude/.setup_agent_version && cat .claude/.setup_agent_version
```

按下表四分类：

| 场景 | 判据 | 走哪 |
|------|------|------|
| **更新** | 有 `.claude/.setup_agent_version` | 【更新模式】跳到下方 "## 更新模式" 段（Step 0 + Step 0.5 自检仍先跑一遍：幂等补 skill + 清项目重复副本） |
| **收编 (adopt)** | 无戳，但已有 CLAUDE.md/rules **像 setup_agent 铺过的**（指纹 ≥2 项命中） | 【收编模式】跳到下方 "## 收编模式 (adopt)" 段 |
| **全新 init** | 无戳，且 cwd 干净（无 CLAUDE.md / `.claude/rules/`） | 继续 Step 0 → Step 7 |
| **有内容但不像衍生** | 无戳，有 CLAUDE.md/rules 但**不命中**衍生指纹 | 问用户：(A) 当作全新 init（已存在文件按 Step 1 备份/跳过处理）+ 末尾补写版本戳；(B) 退出 |

**setup_agent 衍生指纹**（命中 **≥2 项**即判"像铺过的"，走收编；目的只是区分"我铺的 vs 别人的项目"，宁松勿严）：

```bash
grep -q "鬼打墙"     CLAUDE.md                  2>/dev/null   # §8 鬼打墙红线
grep -q "ctx-budget" CLAUDE.md                  2>/dev/null   # §10 ctx-budget 信号
grep -rq "OPTIONAL_BEGIN" .claude/rules/        2>/dev/null   # OPTIONAL 裁剪残留标记
test -f .claude/rules/meta_rule_design.md                     # 元规则文件名
test -f .claude/rules/workflow.md                             # 工作流 rule 文件名
```

> **判别树（文字版）**：
> ① 工厂自检命中 → 硬拒退出
> ② 有版本戳 → 更新模式
> ③ 无戳 + 像衍生（指纹 ≥2）→ 收编模式（写戳转更新，**绝不覆盖**）
> ④ 无戳 + 干净 → 全新 init（Step 0→7）
> ⑤ 无戳 + 有内容但不像衍生 → 问用户 (A) init / (B) 退出

### Step 0：自检并补齐用户级通用 skill

本 skill 仓库内的 `skills/` 子目录包含全部通用协作 skill（脱敏自 StratusAgent 长期沉淀；清单以目录实际内容为准，**不再硬编码个数**）。Claude Code 只扫描 `~/.claude/skills/<name>/SKILL.md` 顶层，**不递归**——所以 `~/.claude/skills/setup_agent/skills/<name>/SKILL.md` 这样嵌套的 skill 扫不到，必须复制到 `~/.claude/skills/<name>/` 平级。

**自检逻辑（幂等：缺失→装 / 旧版→提议更新 / 定制→问，绝不静默覆盖）**：

```bash
SKILL_DIR="$HOME/.claude/skills/setup_agent"   # 本 skill 的仓库 clone 位置
SKILLS_SRC="$SKILL_DIR/skills"
SKILLS_DST="$HOME/.claude/skills"

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

> **（可选）GitHub 新鲜度**：以上比对的是**本机上游 clone 的工作区**。要对 GitHub 最新版，先 `git -C "$SKILL_DIR" pull` 再跑本步——但若 `$SKILL_DIR` 是**开发机 junction**（指向你的开发仓库），`pull` 会动到未提交工作区，**此时跳过 pull**。

**通用 skill 速查（清单以 `skills/` 目录为准）**：

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
| `find-doc` | agent 主动 | doc 综合检索（grep + read 一次性）；项目 topic→rule 字典外置 `.claude/find-doc.map.md` |
| `find-memory` | `/find-memory` | 按关键词搜 memory 冷区（MEMORY.md 索引没覆盖时） |
| `summary` | `/summary` | 总结对话决策写入 memory，并按需更新 rules/docs；**顺手捕捉通用经验进反哺收件箱** |
| `sync-docs` | `/sync-docs` | 根据代码变更同步设计文档 |
| `harvest` | `/harvest` | 把下游攒的通用经验脱敏反哺回 setup_agent 上游（无参批量清收件箱 / 带描述立即单条） |

**全局 CLAUDE.md 自检（幂等，与 skill 自检同批）**：确保用户全局 CLAUDE.md 含"Glob 查文件"规则，防止新会话里 Claude 反射性用 shell 搜文件触发权限弹窗：

```bash
grep -q "禁止用 shell 查文件" "$HOME/.claude/CLAUDE.md" 2>/dev/null && echo "✓ 已有" || echo "缺失"
```

- **已有** → 跳过
- **缺失且 `~/.claude/CLAUDE.md` 存在** → 用 Edit 工具在 `**主动工具**` 条目后插入一行：
  ```
  - **查文件/查内容用 Glob/Grep/Read，禁止用 shell 查文件**：`find`、`Get-ChildItem`、`Select-String` 等 shell 命令访问工作目录外路径会触发权限弹窗。检索类操作一律走受控只读工具（Glob 找文件、Grep 搜内容、Read 读文件），shell 只留给构建/git/进程等"真要执行"的动作。Glob 三诀：① path 要具体不要全盘扫（会超时）；② 匹配文件不匹配目录，找文件夹写 `**/foo/**`；③ 默认跳过 `.` 开头隐藏目录，目标在 `.claude` 里时把 path 直接扎进去
  ```
- **`~/.claude/CLAUDE.md` 不存在**（新用户还没有全局配置）→ 跳过，只靠项目级 `CLAUDE.md §2.5` 兜底

**告知用户**：若复制了任何 skill，提示"需要重启 Claude Code 才能看到新 skill 在 / 列表里"。

> 跳过条件：若用户明确说"我不要这些通用 skill"，可在 Step 0 完全跳过；但默认全装。

### Step 0.5：清理项目级通用 skill 重复副本（单一源红线）

> **背景**：通用协作 skill 的**单一源是 setup_agent**，装到**用户级** `~/.claude/skills/`。若项目自己的 `.claude/skills/` 里也有同名副本 → **shadow 掉用户级单一源**：改进流不到项目、各项目副本各自漂移。本步把重复副本清掉，让通用 skill 一律从用户级解析。
>
> **只清通用 skill**：项目专属 skill（不在 `skills/` 清单里的，如某项目的 `restart-ui` / `acceptance` / `test-first`）**绝不碰**。
>
> 所有模式（init / 更新 / 收编）都跑：fresh-init 项目本来没有副本 → 空跑；存量项目才有清理对象（幂等）。

对每个 setup_agent 出品的通用 skill（清单 = `skills/` 目录），若 `<project>/.claude/skills/$s/` 存在就分类：

```bash
SKILLS_SRC="$HOME/.claude/skills/setup_agent/skills"
PROJ_SKILLS=".claude/skills"
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
| **DUP-DIVERGENT 且含项目专属数据** | **建议保留 / 迁移后删**（绝不轻易删）→ 给 `diff` 问"删（回落用户级单一源）/ 保留定制" | 两类典型：① `find-doc` / `sync-docs` 旧版**内联字典/映射表**（外置前的填充版）→ 先把字典迁到 `.claude/find-doc.map.md` / `.claude/sync-docs.map.md`（格式分别见 find-doc Step 4 / sync-docs Step 7），迁完且用户确认后再删副本；② 其他被用户改过的定制 → 给 `diff` 让用户判 |

> 逐个确认看似比"IDENTICAL 直接删"啰嗦，但单一源去重是低频一次性动作（每个项目一生跑几次），且删的是项目 git 里的文件 —— 让用户对每个重名 skill 有知情权 + 否决权，比省那几次确认更重要。批量删的"效率"在这里不值得拿"误删用户没意识到自己改过的副本"的风险换。

**判定"含项目专属数据"**：副本里出现项目实际路径 / rule 文件名 / 内联填充的非-placeholder 字典。拿不准 → 当"定制"处理问用户，**宁可多问不可误删**。

> **可移植性**：通用 skill 移出项目 git 后，`git clone` 单独不再恢复它们 → 靠在该机跑 `/setup_agent`（Step 0 装用户级）恢复。这是 DRY（N 项目不各存一份）对 clone-完整性的**有意取舍**；`templates/rules/portability.md §2` 已记录该拆分。项目专属**数据**（`.claude/find-doc.map.md` 等）仍在项目 git，可移植性不受影响。

### Step 1：核对当前位置

```bash
pwd                                 # 必须是新项目根目录
ls -la                              # 看是否已有 CLAUDE.md / .claude/ / doc/
git rev-parse --is-inside-work-tree # 是否已 git init
```

**若 cwd 已有 CLAUDE.md 或 `.claude/rules/`** → 立即停下问用户："检测到已存在 CLAUDE.md/rules，要 (A) 跳过已存在的文件只补缺失部分；(B) 备份后覆盖；(C) 退出？"

> 注：若该 dir 有 `.claude/.setup_agent_version`，前置步骤已路由到**更新模式**，不会到这里。本分支只针对"有 CLAUDE.md 但无版本戳"的非托管项目。

**若 cwd 已有 `.claude/settings.json`** → **禁止直接覆盖**（会丢已有 hook/permission/env）。必须读现存 settings.json，把模板里的下列条目 **merge** 进去（数组追加，不替换），其他字段保持原样：
- `hooks.*`（各 hook 数组追加）
- `permissions.allow` / `permissions.ask` / `permissions.deny`（三个数组各自追加去重；**deny 优先级最高，绝不删用户已有 deny**；ask 同样只增不删）
- `permissions.defaultMode`：**仅当用户原配置没设过**才写 `acceptEdits`；用户已设（哪怕设成 `default`）则保留其值，不覆盖

merge 完后给用户 review 一次再保存。

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

| 模板 | 目标 | 条件 |
|------|------|------|
| `templates/CLAUDE.md` | `<project>/CLAUDE.md` | 总是 |
| `templates/rules/*.md` | `<project>/.claude/rules/` | 总是 |
| `templates/memory/MEMORY.md` | `<project>/.claude/memory/MEMORY.md` | 总是 |
| `templates/hooks/*.py` | `<project>/.claude/hooks/` | **总是**（Python 是硬依赖，见下方"Python hook 体系") |
| `templates/scripts/*.py` | `<project>/.claude/scripts/` | **总是** |
| `templates/settings.json` | `<project>/.claude/settings.json`（**已存在则 merge 不覆盖**，详见 Step 1）| 总是（含 `permissions` + 整个 `hooks` 块） |
| `templates/doc/README.md` | `<project>/doc/README.md` | 总是 |
| `templates/VERSION` | `<project>/VERSION` | **条件复制**（见下方"版本号 SoT 条件复制"） |
| `templates/CHANGELOG.md` | `<project>/CHANGELOG.md` | 总是（即使有原生版本源，CHANGELOG 仍统一在此） |
| 写版本戳 | `<project>/.claude/.setup_agent_version`（内容 = 本 skill clone 的 `VERSION`，如 `0.14.0`）| 总是（init 末尾写。既是"上次同步到哪版"记录，又是前置步骤判定 init/更新的信号） |
| 创建空目录 | `<project>/doc/{0_architecture,1_plan,1_plan/sprints,2_pending,3_design,4_archive,9_reference}/` | 总是 |
| `.gitignore` setup_agent 机制块 | `<project>/.gitignore`（**已存在则 merge-append 不覆盖**，详见下方）| 总是 |

**`.gitignore` 兜底（堵 hook 生成物被误提交）**：setup_agent 装的 hook 会自动生成一批临时产物——Python 字节码、session 快照、hook 日志。若下游 `.gitignore` 不挡，用户 `git add .` 会把它们一并提交（污染历史）。这是机制化义务，不能只靠口头约定。**确保**下游 `.gitignore` 含以下"setup_agent 机制块"（**幂等**：缺哪行补哪行；已存在则 grep 守卫后 append；项目自己其他忽略项**绝不删**；下游无 `.gitignore` 则新建）：

```gitignore
# === setup_agent 协作骨架机制自动生成（勿提交，由 /setup_agent 维护）===
__pycache__/
*.pyc
.claude/settings.local.json
.runtime/session_state/
.runtime/*.log
```

> 为何不整份 ship `templates/.gitignore`：完整 `.gitignore` 与项目主语言强耦合（Rust 忽略 `target/`、Node 忽略 `node_modules/`），setup_agent 不该越俎代庖。这里只挡**setup_agent 自身机制**产生的物（Python hook 是所有项目的硬依赖，故这几行语言无关）。`.runtime/` 下持久资产（嵌入工具/缓存）仍可 track，只忽略快照/日志，与 `rules/modules.md` 的「`.runtime/output` gitignored」选择性策略一致。

**Python hook 体系（所有项目无条件安装 — Python 是硬依赖）**：

```
所有项目（不分主语言，含 rust / node / go）：
  ✓ 复制 templates/hooks/ + templates/scripts/ 全部
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
  ✗ 跳过 templates/VERSION 复制（避免双 SoT 冲突，详见 templates/rules/workflow.md §9.1）
  ✓ 仍复制 templates/CHANGELOG.md（不冲突，所有项目都需要）
  → 向用户说明："检测到 <package.json/Cargo.toml/...>，已跳过 VERSION 文件复制。后续 bump 版本号请改原生源；CHANGELOG.md 仍统一在根目录维护。"
else (无原生版本源):
  ✓ 复制 templates/VERSION（初始内容 `0.1.0`）
  ✓ 复制 templates/CHANGELOG.md
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
4. **跑通验证**：在目标项目根执行 `python .claude/hooks/session_snapshot.py manual`，期望输出 `[session snapshot manual] -> .runtime/session_state/<ts>.md`。失败 → 检查 Python 解释器路径 / .runtime/ 目录权限。
5. **提示用户**：
   - CLAUDE.md §10 ctx-budget 红线生效，新会话开始即享受预警保护
   - PostCompact / Stop hook 自动启用 → 防 compact 吞状态 + Word-style 自动保存
   - `skill_sync_check` SessionStart hook 自动启用 → 用户级通用 skill 与上游漂移时，session 开始会打印 `[skill-sync]` 提示跑 `/setup_agent` 同步（只读检测，不自动改）
   - `find-doc` / `sync-docs` 两个 SKILL.md 里有 placeholder 表（topic→rule 字典 / 源码→文档映射），**现在不必填**，项目演进出稳定目录结构后再补；agent 在任务收尾时会主动提醒
   - 详见 README.md `## Python 依赖（agent 安装前必读）` 段

**目标机无 Python 时的处理**（前置硬检查未通过时必做）：

不要继续铺 hook（硬依赖缺失）。向用户明确说明并给出修复路径：
> setup_agent 的 hook 自动化体系（含 `version_check` 版本号 commit 硬检查、ctx 预警、自动 snapshot、memory/rules lint 等）**全部用 Python 实现，是硬依赖**。检测到本机没有可用 Python（既无项目 `.venv`，PATH 上也没有 `python`）。
>
> **请先装 Python（≥ 3.8）再重跑 `/setup_agent`**：
> - Windows：装 python.org 发行版 或 `winget install Python.Python.3`
> - macOS：`brew install python` 或系统自带
> - Linux：`apt install python3` / 发行版包管理器
> - 建议在项目根建 `.venv`（`python -m venv .venv`）让 hook 用项目隔离解释器，更可移植
>
> 已铺好的核心模板（rules / CLAUDE.md / doc 分层 / skill / **permissions 少弹框配置**）不受影响，装好 Python 后重跑即补齐 hook 段。
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

### Step 7：写版本戳 + 输出 next-step 清单

**先写版本戳**（让本项目纳入更新管理）：把本 skill clone 的 `VERSION` 内容写进 `<project>/.claude/.setup_agent_version`：

```bash
cp "$HOME/.claude/skills/setup_agent/VERSION" .claude/.setup_agent_version
```

之后用户在本项目重跑 `/setup_agent` 即自动进入**更新模式**（拉上游增量），不会再全新铺设。

**再呈现给用户**：

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

## 收编模式 (adopt)（已有 setup_agent 衍生内容但无版本戳）

> 触发：前置 Step 前-3 判定 cwd 无 `.claude/.setup_agent_version`，但已有 CLAUDE.md/rules 命中 setup_agent 衍生指纹（≥2 项）。常见于 **pre-stamp 老安装**（版本戳机制 v0.14.0 才引入）或手动拷过模板的项目。
>
> **核心红线：收编 = 登记纳管，绝不覆盖任何已有文件。** 用户已有内容大概率比上游脱敏模板更全（业务演进过），覆盖 = 倒退。

### A1：确认 + 写戳（默认动作）
1. 列出命中的指纹项，向用户说明："检测到本项目像是 setup_agent 铺过但缺版本戳，建议**收编**（仅登记纳管，不动你任何文件）。"
2. 用户确认后写戳：
   ```bash
   cp "$HOME/.claude/skills/setup_agent/VERSION" .claude/.setup_agent_version
   ```
   > 戳值 = 上游**当前** VERSION，等于声明"以此为同步基线"。首次收编**不补历史增量**（视现状为最新），从下次 `/setup_agent` 起才按 `(此版, 新版]` 拉 `[product]` 增量。

### A2：可选——顺便补上游差量
- 用户若想"把上游比我新的通用增量也过一遍"，在写戳**前**先把戳临时写成一个更早的基线（用户记得的安装版本；记不得就保守取 `0.1.0`），再走 [更新模式](#更新模式cwd-已被-setup_agent-铺过时) U2 的类 C diff，让用户逐段吸收。
- 拿不准基线就**不补** —— 收编默认语义是"以现状为基线"，宁可漏增量也不冒覆盖业务内容的风险。

### 收编模式禁止
- ❌ 覆盖（哪怕"备份后覆盖"）任何已有 CLAUDE.md / rules / settings —— 那是 fresh-init 分支的事，收编不做
- ❌ 动 memory / doc
- ❌ 不经用户确认直接写戳

---

## 更新模式（cwd 已被 setup_agent 铺过时）

> 触发：前置步骤检测到 `.claude/.setup_agent_version`。这是 `/setup_agent` 的"拉上游增量到现有项目"流程——**机械半场**（拉 / diff / 分类 / 呈现）由 skill 做，**判断半场**（rules/CLAUDE.md 选择性吸收）全程交用户。完整判据见 `~/.claude/skills/setup_agent/docs/sync-from-upstream-playbook.md`（下称 playbook）。

### U1：算增量
- 读 cwd 的 `.claude/.setup_agent_version`（下游上次同步的版本）vs clone 的 `VERSION`（上游当前版本，前置步骤已 pull 到最新）。
- 相等 + 文件无差异 → 报告"已是最新（vX.Y.Z）"后退出。
- 不等 → 从 clone 的 `CHANGELOG.md` 抓 `(上次, 现在]` 区间所有 **`[product]`** 条目，给用户一份"上游这些更新冲着下游来"的清单（`[repo]` / `[meta]` 条目不影响下游，过滤掉）。
- **`[product]` 短路**：若 `(上次, 现在]` 区间**没有任何 `[product]` 条目**（这次上游更新全是 `[repo]` / `[meta]`，与下游无关）→ **不跑 U2 全量 diff**，直接报"本次上游更新无 `[product]` 变更，下游无需同步"，把版本戳刷到当前 `VERSION`（U4）后退出。

### U2：按 playbook §2 表格分类 diff
逐类对比 clone 的 `templates/` 与 cwd 的 `.claude/`，**先给总览清单，再逐项过**：

| 类 | 文件 | 策略 |
|----|------|------|
| A | `.claude/hooks/*.py` `.claude/scripts/*.py` + 用户级 `~/.claude/skills/` | 下游副本与模板**一致** → 提议覆盖（确认）；**被改过** → 标红给 diff 问用户（**不无脑覆盖**） |
| B | `.claude/settings.json` | **merge 不覆盖**：上游通用 hook 段更新/加入；保留下游 `permissions` / `additionalDirectories` / 自定义 hook 注册。给 merge 预览，确认后写 |
| C | `.claude/rules/*.md` `CLAUDE.md` | **只 diff，绝不自动改**。每个差异段贴 playbook §2 类C 判据：🟢 上游通用增量(吸收) / 🟡 下游业务补充(保留) / 🔴 上游脱敏后减弱(保留下游)，用户逐段定 |
| D | `.claude/memory/` `doc/` | **碰都不碰** |
| E | `<project>/.gitignore` | 按 Step 3「`.gitignore` 机制块」**幂等 append** setup_agent 机制忽略项（缺行才补，项目自有忽略项不删）。存量项目早期没这块，更新时补上才不漏（否则 hook 生成物一直裸奔） |

### U3：路径适配
更新进来的 hook 命令若引用 `.venv` 但 cwd 无 `.venv` → 同 init 的"Python 解释器路径适配"，改裸 `python`。

### U4：验证 + 收尾
- 跑更新过的 hook 看 exit 0：`python .claude/hooks/<hook>.py`。
- 把 `.claude/.setup_agent_version` 写成 clone 的当前 `VERSION`。
- **不自动 commit**：`git status` + `git diff` 给用户 review，提示自行 commit（参考 playbook §5）。

### 更新模式禁止
- ❌ 自动覆盖 rules / CLAUDE.md（类C 必须用户逐段定）
- ❌ 动 memory / doc（类D 业务私有）
- ❌ 跨多个项目批量同步（一次只对当前 cwd）
- ❌ 自动 commit

---

## 禁止

- ❌ 静默覆盖已存在的 CLAUDE.md / rules — 必须先问用户
- ❌ 自己编填架构红线 / 项目结构 — 这是用户必须自己写的核心内容
- ❌ 自动 git commit — 留给用户
- ❌ 跳过 memory junction 这步——它是项目协作体系能跨机复现的关键
- ❌ **静默**覆盖用户已有的同名 skill — Step 0 对已存在 skill 先比对：一致则静默更新，不一致（可能是定制）必须给 diff 问用户，绝不静默盖掉
- ❌ **批量 / 静默删**项目级重名 skill 副本 — Step 0.5 清重复副本必须**逐个确认**：哪怕字节一致的纯重复也要单独问"删/留"，用户不答即保留，绝不一次性扫删
- ❌ 在 setup_agent 源头仓库**自己身上**跑 bootstrap / 更新 — 前置 Step 前-2 工厂自检应已硬拒（源头改框架直接编辑 `templates/` / `SKILL.md`）

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
| `hooks/version_check.py` | **通用** | PreToolUse(Bash) hook，拦 `git commit`：staged 未含版本号文件（VERSION/package.json/Cargo.toml/pyproject.toml）则 exit 2 阻断，强制落实 workflow.md §9「每次 commit 必 bump」。`[skip-version]` / `--amend` / merge 可豁免 |
| `hooks/allow_memory_write.py` | **通用** | PreToolUse(Write/Edit) hook，放行 memory `.md` 写入免弹窗。`.claude/` 是受保护目录，写入无视 acceptEdits/allow 规则强制弹窗；memory 在其下被连带保护。本 hook 在弹窗前返回 `permissionDecision:allow`，只放行 memory 的 `.md`，settings/hooks 本体不碰。**改完须开新会话生效**（hook 不热重载） |
| `settings.json` | **通用** | ① `permissions` **三档**（`defaultMode: acceptEdits`）：**allow 放宽**（日常 git 读写/shell 读/构建测试静默跑，压弹窗噪音）+ **ask 必弹**（push/rebase/reset/checkout 等慎重项强制确认）+ **deny 拦死**（跨平台：Bash `rm -rf`/git 历史销毁/发布 + **PowerShell `Remove-Item` 等 Windows 删除** + 读写 `.env`/密钥/`~/.ssh`）。优先级 deny>ask>allow；deny 在 bypass 下仍生效。设计目标=弹窗皆信号。注：deny 是减速带（子进程可绕过），防手滑非保险柜；② 注册 ctx-budget 等 hook。已存在则 merge 不覆盖（详见 Step 1） |
| `memory/MEMORY.md` | 空索引 | 含 4 类 memory 命名约定注释 |
| `doc/README.md` | 索引模板 | 0_architecture (含 acceptance + TODO-INDEX) / 1_plan (含 sprints) / 2_pending / 3_design / 4_archive / 9_reference 分层说明 |
| `VERSION` | 单一事实源 | 初始 `0.1.0`；若项目有原生版本源（`package.json` / `Cargo.toml` / `pyproject.toml`）则**跳过复制**避免双 SoT |
| `CHANGELOG.md` | 通用骨架 | Keep a Changelog 格式 + 引用 `rules/workflow.md §9` 语义；含 `[0.1.0] - {{TODAY}}` 初始 entry，所有项目都复制 |
| `.claude/.setup_agent_version` | 生成（非模板文件）| init 末尾写 = 安装时 setup_agent 版本；重跑 `/setup_agent` 据此进**更新模式**（拉上游 `[product]` 增量）而非全新铺设 |
| `skills/*/SKILL.md` | **通用** | 协作 skill 集（plan / collab / debate / escalate / snapshot / resume / git-sync / archive-scan / todo / find-doc / find-memory / summary / sync-docs / harvest）。Step 0 自检补齐到 `~/.claude/skills/` 平级；Step 0.5 清掉项目里的重复副本（单一源）。find-doc / sync-docs 的项目专属字典外置 `.claude/*.map.md`（不进 skill 本体）。 |
