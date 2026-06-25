# {{PROJECT_NAME}} 项目开发规范

> 项目专属指令，每次新对话自动加载。
> 详细规则按需加载自 `.claude/rules/`

---

## 1. 架构红线

<!-- 项目专属红线，随开发增量补充（3-5 条"必须/禁止"，填好后删此注释）。 -->

---

## 2. 规则文件索引

| 规则文件 | 内容 | 加载条件 |
|---------|------|---------|
| `rules/architecture.md` | 职责边界 + 数据流方向（核心红线） | 始终加载 |
| `rules/modules.md` | 模块组织范式 + 目录职责 + 新模块接入流程 | 始终加载 |
| `rules/debugging.md` | 调试检查项 + 鬼打墙红线 + 修 bug 前确认根因 | 编辑 `tests/**` 或核心代码目录 |
| `rules/workflow.md` | 范式同步文档 + 文档索引同步 + 经验总结 | 编辑 `doc/**`、`.claude/rules/**` |
| `rules/portability.md` | 换机可移植性 + 包安装陷阱 + hooks 路径约束 | 编辑 `.claude/**`、配置文件、依赖清单 |
| `rules/meta_rule_design.md` | 元规则：怎么写 rule（强制力梯度 + 加载策略 + 反模式速查） | 编辑 `.claude/rules/**` 或 `CLAUDE.md` |
| `rules/anti_drift_hooks.md` | 反漂移 hook（clarify / focus / ctx-budget）的分工论述 + 路径 / 调参 / 豁免 | 编辑 `.claude/hooks/**`、`.claude/settings.json` |

<!-- TODO: 按需追加项目特定 path-rule，例如：
| `rules/api.md` | API 设计约束 | 编辑 `src/api/**` |
| `rules/db.md` | 数据库 schema / 写入约束 | 编辑 `src/db/**`、迁移文件 |
-->

---

## 2.5 工具选择：检索用 Glob/Grep，执行才用 shell

**红线**：找文件 / 查内容 → 用 `Glob`（找文件）/ `Grep`（搜内容）/ `Read`，**禁止**反射性用 shell 的 `find` / `Get-ChildItem` / `Select-String`（受控只读工具零弹窗 + 跨平台 + 不夹带删改）。

- **边界**：找东西 / 看内容用检索工具，干事情（构建 / 测试 / git / 进程 / 系统配置）用 shell —— 各司其职，非淘汰。
- **Glob 三诀**：① `path` 给具体别全盘扫（会超时）；② 匹配文件不匹配目录，找文件夹 `foo` 写 `**/foo/**`；③ 默认跳过 `.` 开头隐藏目录，目标在里面就把 `path` 扎进去。
- **禁止自拼 shell 批处理大检索 / 大输出**：不准用 `for` 循环 + 管道 / 多命令 `;` 串做大范围检索或批量大输出，一律拆成受控 `Grep` / `Glob` 单命令。**Why**：自拼 shell 批处理大输出会触发"工具传结果线"概率性抽风（同段重影 / 命中 0 假空 / 幻影文件名），把脏数据喂进判断。
- **红线·脏数据上不拍板**：工具返回出现同段重影 / 命中 0 与预期矛盾 / 不认识的文件名 / `__unparsedToolInput` 时，**禁止**直接在该返回上下结论或改盘，先用 `wc -c`（真实字节）/ `git status`（真实改动）/ 受控 `Grep` 单命令二次验真。**口诀：dry-run 报的 N 处 ≠ 已改 N 处。**

---

## 3. 快速命令

<!-- 填入项目的构建/测试/启动命令（填好后删此注释）。 -->

---

## 4. Skills（可调用技能）

技能目录：`.claude/skills/<name>/SKILL.md`（项目内）和 `~/.claude/skills/<name>/SKILL.md`（用户级）。

<!-- TODO: 按本项目实际安装的 skill 调整。常见通用 skill：
| 技能 | 触发 | 用途 |
|------|------|------|
| `plan` | `/plan` 或"先规划" | 只读分析，列任务/风险/文件，等用户确认后再实施 |
| `summary` | `/summary` | 总结对话决策写入 memory |
| `note` | `/note` | 新问题归档到 doc/2_pending/，不打断主线 |
| `archive-scan` | `/archive-scan` | 扫描 doc/2_pending/ 可归档候选，批量 mv 到 4_archive/ |
| `find-doc` | agent 主动调用 | doc 综合检索（grep + read 一次性） |
| `escalate` | `/escalate` | 鬼打墙急停按钮（详见 §8） |
-->

---

## 5. Memory 项目内托管（自动）

**目的**：memory 纳入项目 git（`.claude/memory/`），不散落用户目录；系统路径 `~/.claude/projects/<project-hash>/memory/` 用 junction 透明转发。

由 `SessionStart` hook `.claude/hooks/memory_junction_check.py` 每次对话开始自动维护（迁移 / 新机建链 / 冲突提示），无需手动。

> 红线：**绝不硬删可能含数据的目录**。任何一步失败即中止并提示人工（迁移时原目录改名 `.bak` 而非删除）。

**Memory 检索原则（热区优先）**：需要召回某类知识时按序：① 先查热区（MEMORY.md 自动加载，直接看有无相关条目）；② 热区无匹配 → `/find-memory <关键词>` 搜冷区全量文件；③ **禁止**跳过热区直接 grep 遍历 memory/ 目录（token 消耗远高于 `/find-memory`）。

> 换机 / 手动重建 junction 的双平台命令与三情形 SOP → `rules/portability.md` §2。

---

## 6. 换机首次启动 Checklist

用户提到"**换电脑 / 新机 clone / 重装**"时必走：

```bash
git clone <repo_url> {{PROJECT_NAME}} && cd {{PROJECT_NAME}}

<!-- TODO: 填写本项目的环境初始化步骤
示例（按主语言替换）：
- Python: python -m venv .venv && .venv/Scripts/pip.exe install -r requirements.txt
- Rust:   cargo build --workspace
- Node:   npm ci  或  pnpm install --frozen-lockfile
- Go:     go mod download
-->
```

**常见可移植性陷阱**（详见 `rules/portability.md` §4）：
1. 依赖清单**禁止**绝对路径 URL（用相对路径或 `--find-links`）
2. 配置文件注释**避免**非 ASCII（某些工具默认编码非 UTF-8 会爆）
3. 关键 binary / DLL / 模型文件由项目自带，不依赖 pip 包提供
4. （可选，中文 Windows）给本仓库 git 配 UTF-8，避免中文文件名/log 显示乱码：
   `git config --local core.quotepath false && git config --local i18n.logOutputEncoding utf-8 && git config --local i18n.commitEncoding utf-8`（`.git/config` 不随 clone 走，换机需重跑）

---

## 7. 项目结构速查

<!-- 列出顶层目录及职责，帮助 Claude 快速定位代码（填好后删此注释）。 -->

---

## 8. 鬼打墙觉察 + 渐进升级（红线）

**默认**：单 agent 处理任务（lvl 0）。

### 自动升级条件（我必须自觉触发，不等用户提）

| From → To | 触发 | 我必须做 |
|-----------|------|---------|
| **lvl 0 → lvl 1**（加 verification）| 等价性验收 / 重写 / 移植 | 完成后派**独立** verification agent，**禁止**自己写测试 |
| **lvl 0 → lvl 2**（加 research）| 任务跨 ≥ 2 模块且我不熟悉代码 | 先派 Research agent 并行调研，再动手 |
| **lvl 1/2 → lvl 3**（升 4 角色）| **同一 bug 前 3 次代码改动失败,无论我是否还有新思路,第 4 次禁止动手** | **必须停下**,列已试方案 + 当前未验证的新假说 → 提议 `/escalate` 或 `/debate`,新思路留给多角色讨论 |

### 红线

- **禁止**鬼打墙时闷头继续试（必须停下提议升级）
- **禁止用"我有新思路"豁免第 4 次硬停**。**计数**只看"同一症状下连续失败的代码改动次数",不看"思路是否机制不同"。每次我感觉"这次不一样"恰恰是规则最该绑住我的时候 — 高信心错误才是规则存在的理由,低信心错误自己会停。
- **禁止**等价性任务自己写测试（自证陷阱）
- **禁止**不熟悉的多模块任务直接动手不调研

### 计数规则（明确化,不留主观豁免）

- **同一 bug**：用户报告同一症状（同一面板/字段/行为），计数器加 1
- **失败**：改完用户回报"还不对" / "还是 X" / "依然 Y"
- **每次失败必须做的事**：在动第 N+1 次前（N ≤ 3），先取一项**量化数据**（console 日志 / 编译产物 mtime / 代码路径 grep 结果 / 用户截图反推数值），没有量化数据就直接跳到 `/escalate`,不准凭推断动手
- **重置条件**：用户明确说"修好了" / "OK 了" / 切到不同 bug

### 用户兜底

`/escalate` 是用户急停按钮：万一我没自觉成功，用户主动按 → 强制总结 + 派外援研判 + 推荐路径。

---

## 9. 主观体验报告主动问范式（红线）

**触发**：用户基于**外部观察**报主观体验 / 怪现象，缺数据缺稳定复现（UI "有点黏" / CLI "有时没输出" / API "偶尔返回空" / 后端 "偶发 500" / pipeline "某天没数据"）。

### 我必须主动问全这 4 件事（一次性问完，不要挤牙膏）

1. **能给一个可观察的证据吗？** — UI 用截图、CLI 用完整 input + output、API 用 request/response、后端用日志片段
2. **能描述前 N 步操作 / 触发条件吗？** — 触发序列
3. **大概多久发生一次？** — 偶发率（1/10 vs 1/100 决定打法）
4. **能存档当前状态吗？** — 锁现场（如果项目有 `/snapshot` skill）

### 接到信息后必须

- **量化**：写 timer / counter / log 插到相关代码（不只是猜测）
- **教用户复现协议**：怎么触发、按啥、攒几次
- **接受概率方法**：偶发率从 1/10 降到 1/100 也是修，允许"改一版后用 1 周观察"作为收尾

### 禁止

- ❌ 单凭描述就猜测修（必须有数据 / 截图 / 复现 / 日志）
- ❌ 一次只问 1 个问题挤牙膏（一次问全 4 个）
- ❌ 假装"我懂你的感受"绕开量化

---

## 9.5 较大需求主动澄清 — `[clarify]` 信号响应

**触发**：`UserPromptSubmit` hook（`clarify_reminder.py`）在候选轮（非 slash / 非续接词 / 非极短）输出 `[clarify]` system reminder。读到后**语义精判**这轮够不够大，再决定问不问。

### 红线（读到 `[clarify]` 后必须，二分支）

- **用户已表达执行意图、但范围 / 方案模糊**的较大需求 / 设计问题（要动手、但没说清怎么做）→ **先用 `AskUserQuestion` 出 2-4 个结构化选择题**（每个给候选项 + 推荐项）对齐范围，**再动手**。**禁止**对大需求零思考直接实现。
- **评估 / 咨询 / 可行性类问**（"能不能 X" / "有没有 Y 问题" / "该不该 Z" / "评估一下"这类**只要结论**的诊断问）→ 给出结论 + 风险即**收口**。**禁止**主动把"建议"包装成 `AskUserQuestion` 执行菜单递给用户——要不要执行由用户**下一条 prompt** 决定，不替用户开单。`[clarify]` 的"先问背景"只适用于已含执行意图的模糊需求，不适用于纯评估问。
- **琐碎改动 / 续接确认 / 已说全细节** → 忽略提示直接执行。**禁止**对琐碎 / 续接轮强行问背景（过度提问 = 噪声 → 机制自废）。`[clarify]` 是提醒不是命令。
- **`AskUserQuestion` 文案约束**：选项 / 入参必须短、纯文本、避免大段中文（长中文 → `\u` 长串是 `__unparsedToolInput` 转义炸的直接诱因）。

> 混合判定分工 / hook 路径 / 注册 / 调参 → `rules/anti_drift_hooks.md` §1。

---

## 9.6 任务防漂移 — `[focus]` 信号 + 漂移分类响应

**触发**：`UserPromptSubmit` hook（`focus_reminder.py`）把本会话首条实质 prompt 记为「任务锚」，周期性注入 `[focus]` system reminder。可用 `/focus` 查看 / 改 / 清。

### 我读到 `[focus]`（或 `/focus`）后必须：判断这轮还属不属于原任务，**若偏离，按类型分发，禁止闷头做**

| 漂移类型 | 判据 | 响应 |
|---------|------|------|
| **前置阻塞** | B 必须先解才能回到原任务 | **大**（值得独立对话）→ `/spinoff` 打包交接 + 提示用户开新对话；**小**（几行）→ 内联做完即回 |
| **附加扩张** | "顺带也做 X"，不阻塞原任务 | `/todo` 归档，先把原任务做完 |
| **无关支线** | 跟原任务无关的新话题 | `/todo` 或建议开新对话，**绝不内联** |
| **正当深入** | 仍是原任务的合理子步骤（非偏离） | 忽略 `[focus]`，继续做 |

### 红线

- **禁止**发现"得先做别的"就地闷头展开——先判类型（前置 / 附加 / 无关 / 正当深入）再响应
- **禁止**对小前置 / 不阻塞的附加滥用 `/spinoff`（小前置内联即回，附加走 `/todo`）；`/spinoff` 只给"够大的阻塞性前置"
- **禁止**反漂移机制自己变成漂移源——`[focus]` 是周期提醒不是每轮命令，命中"正当深入"就忽略，别打断合法的深度推进
- `[focus]` 是**提醒不是强制**：真漂没漂、哪类、怎么办，最终由我语义判断

> 主动+被动入口表 / 锚文件 / hook 路径 / 调参 / 配套 skill → `rules/anti_drift_hooks.md` §2。

---

## 10. 上下文预算红线 — `[ctx-budget]` 信号响应

**触发**：`UserPromptSubmit` hook（`context_warning.py`）每轮估算上下文用量，超阈值输出 `[ctx-budget]` system reminder（char/4 启发式，精度 ±10%）。我**必须**按下表响应：

| 信号级别 | 用量 | 我的行为 |
|---------|-----|---------|
| 无信号 | < 75% | 正常执行任务 |
| **MEDIUM** | 75-84% | 执行任务，**完成后**主动建议 "/snapshot 锁状态准备换会话" |
| **HIGH** | 85-94% | **响应开头**告知用户当前用量 + 建议 /snapshot + 询问是否继续。**只接受小任务**（单文件读 / 1-2 行改 / 询问），**拒绝复杂多文件改动** |
| **CRITICAL** | ≥ 95% | **立即拒绝**任务，告知"上下文几乎满，继续做事会被自动 compact 吞状态。请先 /snapshot 然后开新会话 /resume 接续。" 不开始任何新工作 |

### 红线

- **CRITICAL 信号下禁止开始任何新任务** — 即使用户说"快做"，也要拒绝。允许的只有 `/snapshot` 这种保命操作（slash command 已被 hook 自动豁免）
- **HIGH 信号下禁止启动复杂多文件改动** — 即使可能勉强做完，后续 compact 会丢上下文，不值得
- CRITICAL/HIGH 边界附近以信号为准，不要二次判断"我感觉还行"
- **不要悄悄忽略信号继续做事** — 用户配置这个 hook 就是因为容易忘，我必须主动响应
- `/snapshot` / `/resume` / `/git-sync` 等 slash 已被 hook 自动豁免（否则保命操作被拦会死锁），所以 CRITICAL 时建议 `/snapshot` 不自相矛盾

> hook 路径 / 注册 / 调参（`WINDOW` / `THR_*`）/ 豁免机制论述 → `rules/anti_drift_hooks.md` §3。

---

## 11. 文档管理（红线）

**本项目必须用 `doc/` 分层管理所有文档。结构按 `rules/workflow.md §6` 六层定义**：

```
doc/
├── 0_architecture/  ← 架构红线 + acceptance + TODO-INDEX
├── 1_plan/          ← 活跃推进 + sprints
├── 2_pending/       ← 未决问题展开备忘
├── 3_design/        ← 模块实现设计
├── 4_archive/       ← 已完成归档
└── 9_reference/     ← 外部参考资料
```

### 红线

- **禁止** 文档散落项目根目录或随便挂在其他位置（设计文档放 `doc/3_design/` 而不是 `src/<module>/README.md`）
- **禁止** 跳过六层中的任何一层（即使当前为空，目录也必须存在 — 占位 `.gitkeep` 即可）
- **禁止** 给六层改名 / 合并（`doc/design/` ≠ `doc/3_design/`，序号前缀是排序约定）
- **禁止** 新增同级目录（如 `doc/notes/` `doc/wip/`）— 新增需求按 §6 边界归到现有六层之一
- **强制** `doc/README.md` 作为唯一索引，任何 `doc/*.md` 文件的新增 / 删除 / 重命名都要同步本文件

**不接受 doc/ 强制 → 不应使用 bridgeforge**（改用更宽松的脚手架）。

> **Why（为什么是红线）+ 每层职责边界 + README 同步细则** → `rules/workflow.md §5.5-§8`（编辑 `doc/**`、`.claude/rules/**` 时自动加载）。
