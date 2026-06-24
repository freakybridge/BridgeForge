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

<!-- TODO: 按需追加项目特定 path-rule，例如：
| `rules/api.md` | API 设计约束 | 编辑 `src/api/**` |
| `rules/db.md` | 数据库 schema / 写入约束 | 编辑 `src/db/**`、迁移文件 |
-->

---

## 2.5 工具选择：检索用 Glob/Grep，执行才用 shell

**找文件 / 查内容 → 优先 `Glob`（找文件）/ `Grep`（搜内容）/ `Read`，不要反射性用 shell 的 `find` / `Get-ChildItem` / `Select-String`。**

- **为什么**：检索类是受控只读工具，**零权限弹窗 + 跨平台 + 不可夹带删改** —— 同时满足"能用 / 清净 / 底线安全"。把只读检索从 shell 挪走，shell 就只剩"真要执行"的命令，该弹的权限弹窗才弹得有意义。
- **shell（PowerShell / bash）不是被淘汰，是各司其职**：构建、跑测试、git、进程管理、系统配置、算体积这些 Glob/Grep 干不了，shell 仍是主力。一句话边界 —— **找东西 / 看内容用检索工具，干事情用 shell**。
- **Glob 三诀**（否则常空手而归）：① `path` 给具体，别全盘递归扫（会超时）；② 它匹配文件不匹配目录，找文件夹 `foo` 要写 `**/foo/**`；③ 默认跳过 `.` 开头隐藏目录（如 `.claude`），目标在里面时把 `path` 直接扎进去。

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

**目的**：memory 纳入项目 git，不散落用户目录。

**每次对话开始静默检查**：`~/.claude/projects/<project-hash>/memory/` 是否为 junction → 不是则恢复链接指向项目内 `.claude/memory/`。

由 `SessionStart` hook `.claude/hooks/memory_junction_check.py` 自动执行（无需手动），三情形：

- **稳态**（系统路径已是 junction/symlink）→ noop（99% 的 session）
- **场景 A 首次迁移**（系统路径是普通实目录）：复制内容进 `.claude/memory/` → 系统目录**改名 `memory.premigrate.bak`（绝不硬删）** → 建 junction。事后人工确认无误再删 `.bak`
- **场景 B 新机 clone**（系统路径不存在 + 项目内已有 `.claude/memory/`）→ 直接建 junction
- **冲突**（系统与项目内同时有内容）→ 不敢自动合并，打印提示请人工处理

> 红线：**绝不硬删可能含数据的目录**。任何一步失败即中止并提示人工。

**手动建 junction 命令**（hook 失效时兜底）：
```powershell
# Windows
New-Item -ItemType Junction -Path '<系统memory路径>' -Target '<项目内.claude/memory绝对路径>'
```
```bash
# macOS/Linux
ln -s '<项目内绝对路径>' '<系统路径>'
```

后续 memory 读写用系统路径（junction 透明转发）。路径约束详见 `rules/portability.md` §2。

**Memory 检索原则（热区优先）**：需要召回某类知识时，按顺序：

1. **先查热区**：MEMORY.md 自动加载，直接检查是否有相关条目
2. **热区无匹配 → 搜冷区**：调用 `/find-memory <关键词>` 搜索 `.claude/memory/` 全量文件
3. **禁止**跳过热区直接遍历 memory/ 目录——热区覆盖则冷区搜索是浪费；直接 grep 目录则 token 消耗远高于 `/find-memory`

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

**触发**：用户报"从外部观察到的怪现象"或主观体验问题。常见场景：

- **UI / 桌面应用**："有点黏" / "偶尔不响应" / "位置不对" / "感觉慢"
- **CLI / 脚本**："有时候没输出" / "跑到一半卡住" / "时快时慢"
- **API / library**："偶尔返回空" / "QPS 上去就超时" / "某些参数下行为怪"
- **后端服务**："半夜偶尔重启" / "某接口偶发 500" / "内存慢慢涨"
- **数据 pipeline**："这一批结果跟上一批不一样" / "某天突然没数据"

核心特征：用户基于**外部观察**报告，缺乏数据 / 缺乏稳定复现路径。

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

**触发**：`UserPromptSubmit` hook（`.claude/hooks/clarify_reminder.py`）在每次用户提交 prompt 时做「便宜负向 gate」，候选轮（非 slash 命令 / 非纯续接词 / 非极短输入）输出 `[clarify]` system reminder。

**混合判定分工**（hook 粗筛 + 模型精判）：

| 谁 | 干什么 | 为什么归它 |
|----|--------|-----------|
| **hook** | 每轮粗筛掉 slash / `next`·`继续` 等续接词 / 极短输入，其余贴 `[clarify]` 便利贴 | 可靠、不随长会话衰减；但它没 LLM，判断不了"大不大"也不会提问 |
| **我（模型）** | 读到 `[clarify]` 后**语义精判**这轮够不够大，再决定问不问、问什么 | 只有 LLM 干得了 |

**我读到 `[clarify]` 后必须**：

- **是较大需求 / 设计问题 / 模糊目标**（信息不全、范围未定）→ **先用 `AskUserQuestion` 问 2-4 个背景问题**帮用户理清思路、对齐范围，**再动手**。禁止不做思考直接开干。
- **是琐碎改动 / 续接确认 / 用户已说全细节** → 忽略本提示，直接执行。

### 红线

- **禁止**对大需求"零思考直接实现"——这正是本 hook 要纠正的行为（用户配置它就是因为每次都得手动提醒"还有什么要问我的"）
- **禁止**对琐碎任务 / 续接轮强行问背景（过度提问 = 噪声，会让用户开始无视提示 → 机制自废）。`[clarify]` 是**提醒不是命令**，最终问不问由你语义判断
- 背景问题用 `AskUserQuestion` 出**结构化选择题**（2-4 个、每个给候选项 + 推荐项），不要一长串散问

### 配置

- Hook 入口：`.claude/hooks/clarify_reminder.py`（项目内）
- 注册位置：`.claude/settings.json` → `hooks.UserPromptSubmit`
- 调参：hook 文件开头改 `MIN_CHARS`（极短阈值）和 `CONTINUATION_TOKENS`（续接/确认词集合，按团队语言习惯增删）

---

## 9.6 任务防漂移 — `[focus]` 信号 + 漂移分类响应

**触发**：`UserPromptSubmit` hook（`.claude/hooks/focus_reminder.py`）自动把本会话第一条实质 prompt 记为「任务锚 anchor」，攒够几轮后**周期性**注入 `[focus]` system reminder，把原始任务重新贴到我眼前。锚存 `.runtime/focus/anchor.json`，可用 `/focus` 查看 / 改 / 清。

### 主动 + 被动两条入口

| 入口 | 谁发起 | 机制 |
|------|--------|------|
| **主动** | hook 自动 | 周期贴 `[focus]`，我读到后自检是否跑偏 |
| **被动** | 用户 `/focus` | 当场让我对照锚核一次；`/focus <文本>` 纠正锚 |
| **被动** | 用户 `/spinoff` | 确认是前置阻塞后，一键交接派生到新对话 |

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

### 配置

- Hook 入口：`.claude/hooks/focus_reminder.py`（项目内）
- 锚文件：`.runtime/focus/anchor.json`（per-session，换 session 自动重置；并发多 session 会 last-write-wins 互相覆盖锚 — 用 `/focus <本会话任务>` 手动重设回来）
- 调参：hook 开头改 `FOCUS_MIN_TURN`（攒几轮才开始提醒）/ `FOCUS_EVERY`（每几轮提醒一次）
- 配套 skill：`/spinoff`（前置派生交接）、`/focus`（锚控制 + 手动自检）

---

## 10. 上下文预算红线 — `[ctx-budget]` 信号响应

**触发**：`UserPromptSubmit` hook（`.claude/hooks/context_warning.py`）在每次用户提交 prompt 时估算上下文用量，超阈值时输出 `[ctx-budget]` system reminder。我**必须**按下表响应：

| 信号级别 | 用量 | 我的行为 |
|---------|-----|---------|
| 无信号 | < 75% | 正常执行任务 |
| **MEDIUM** | 75-84% | 执行任务，**完成后**主动建议 "/snapshot 锁状态准备换会话" |
| **HIGH** | 85-94% | **响应开头**告知用户当前用量 + 建议 /snapshot + 询问是否继续。**只接受小任务**（单文件读 / 1-2 行改 / 询问），**拒绝复杂多文件改动** |
| **CRITICAL** | ≥ 95% | **立即拒绝**任务，告知"上下文几乎满，继续做事会被自动 compact 吞状态。请先 /snapshot 然后开新会话 /resume 接续。" 不开始任何新工作 |

### 红线

- **CRITICAL 信号下禁止开始任何新任务** — 即使用户说"快做"，也要拒绝。允许的只有 `/snapshot` 这种保命操作（slash command 已被 hook 自动豁免）
- **HIGH 信号下禁止启动复杂多文件改动** — 即使可能勉强做完，后续 compact 会丢上下文，不值得
- 信号判定基于 char/4 启发式，精度 ±10%。CRITICAL/HIGH 边界附近以信号为准，不要二次判断"我感觉还行"
- **不要悄悄忽略信号继续做事** — 用户配置这个 hook 就是因为容易忘，我必须主动响应

### slash command 豁免

`/snapshot` / `/resume` / `/git-sync` 等以 `/` 开头的 prompt 不触发预警 — 否则用户连保命操作都被拦，死锁。所以**响应 CRITICAL 时建议用户做的就是 `/snapshot`**，不会自相矛盾。

### 配置

- Hook 入口：`.claude/hooks/context_warning.py`（项目内）
- 注册位置：`.claude/settings.json` → `hooks.UserPromptSubmit`
- 调参：在 hook 文件开头改 `WINDOW`（窗口大小，按模型选 1M / 200k）和 `THR_MEDIUM/HIGH/CRITICAL`（三个阶梯阈值，默认 75/85/95）

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
- **强制** `doc/README.md` 作为唯一索引，任何 `doc/*.md` 文件的新增 / 删除 / 重命名都要同步本文件（详见 `rules/workflow.md` §5）

### 为什么是红线

文档分层是 setup_agent 的**核心范式**之一，与 rules / memory 等机制深度耦合：

- 13 个协作 skill 中 4 个（`/archive-scan` `/todo` `/find-doc` `/sync-docs`）依赖 doc/ 六层结构 — 缺层会让 skill 静默装死
- `rules/workflow.md` §6-§7 + `rules/meta_rule_design.md` 的"案例下沉" 范式都假设 `doc/3_design/` 和 `doc/2_pending/` 存在
- 长期可维护性：散落各处的文档随项目演进必然失控；强制集中是经验教训

**如果不接受 doc/ 强制 → 不应该使用 setup_agent** — 改用其他更宽松的脚手架。

详细规则见 `rules/workflow.md` §5-§7。
