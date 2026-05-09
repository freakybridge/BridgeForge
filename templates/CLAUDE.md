# {{PROJECT_NAME}} 项目开发规范

> 项目专属指令，每次新对话自动加载。
> 详细规则按需加载自 `.claude/rules/`

---

## 1. 架构红线

<!-- TODO: 填写本项目的核心架构红线 — 通常 3-5 条最关键的"必须 / 禁止"
示例（请替换为本项目的实际内容）：

- **职责边界**：模块 A 只做 X，模块 B 只做 Y
- **数据流方向**：单向 `Source → Pipeline → Sink`，禁止反向
- **禁止**：模块 A 不得直接 import 模块 B 的内部实现
- 详见 `rules/architecture.md`

判断标准：架构红线是"违反就是 P0 缺陷"的硬约束，不是 nice-to-have。
-->

---

## 2. 规则文件索引

| 规则文件 | 内容 | 加载条件 |
|---------|------|---------|
| `rules/architecture.md` | 职责边界 + 数据流方向（核心红线） | 始终加载 |
| `rules/modules.md` | 模块组织范式 + 目录职责 + 新模块接入流程 | 始终加载 |
| `rules/debugging.md` | 调试检查项 + 鬼打墙红线 + 修 bug 前确认根因 | 编辑 `tests/**` 或核心代码目录 |
| `rules/workflow.md` | 范式同步文档 + 文档索引同步 + 经验总结 | 编辑 `doc/**`、`.claude/rules/**` |
| `rules/portability.md` | 换机可移植性 + 包安装陷阱 + hooks 路径约束 | 编辑 `.claude/**`、配置文件、依赖清单 |

<!-- TODO: 按需追加项目特定 path-rule，例如：
| `rules/api.md` | API 设计约束 | 编辑 `src/api/**` |
| `rules/db.md` | 数据库 schema / 写入约束 | 编辑 `src/db/**`、迁移文件 |
-->

---

## 3. 快速命令

<!-- TODO: 填写本项目的常用命令 — 只列高频用到的，不是穷尽所有
示例（{{PRIMARY_LANGUAGE}} 项目，请按实际替换）：

```bash
# 构建
<build-command>

# 运行测试
<test-command>

# 启动应用
<run-command>

# 包安装（必须用项目隔离环境，禁止全局安装 — 详见 rules/portability.md）
<install-command>
```
-->

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

- **场景 A 首次迁移**（系统路径是普通目录）：创建 `.claude/memory/` → 复制内容 → 删系统目录 → 建 junction
- **场景 B 新机 clone**（项目内已有 `.claude/memory/`）：删系统空目录（若存在）→ 直接建 junction

**建 junction 命令**：
```powershell
# Windows
New-Item -ItemType Junction -Path '<系统memory路径>' -Target '<项目内.claude/memory绝对路径>'
```
```bash
# macOS/Linux
ln -s '<项目内绝对路径>' '<系统路径>'
```

后续 memory 读写用系统路径（junction 透明转发）。路径约束详见 `rules/portability.md` §2。

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

<!-- TODO: 列出顶层目录及职责，帮助 Claude 快速定位代码
示例：

- `src/` — 主代码
- `tests/` — 测试
- `doc/` — 文档（详见 doc/README.md）
- `config/` — 配置文件
- `.claude/rules/` — 架构约束与开发规则（唯一权威）

判断标准：列出"刚进项目的人能借此 5 分钟内找到任何文件"的最小集，不要 ls -R。
-->

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

## 9. UI / 偶现 bug 主动问范式（红线）

**触发**：用户报 UI bug 或主观体验问题（"有点黏" / "偶尔不响应" / "位置不对" / "感觉慢"）。

### 我必须主动问全这 4 件事（一次性问完，不要挤牙膏）

1. **能截图吗？** — UI 视觉/位置问题首选
2. **能描述前 N 步操作吗？** — 触发序列
3. **大概多久发生一次？** — 偶发率（1/10 vs 1/100 决定打法）
4. **能存档当前状态吗？** — 锁现场（如果项目有 `/snapshot` skill）

### 接到信息后必须

- **量化**：写 timer / counter / log 插到相关代码（不只是猜测）
- **教用户复现协议**：怎么触发、按啥、攒几次
- **接受概率方法**：偶发率从 1/10 降到 1/100 也是修，允许"改一版后用 1 周观察"作为收尾

### 禁止

- ❌ 单凭描述就猜测修（必须有数据 / 截图 / 复现）
- ❌ 一次只问 1 个问题挤牙膏（一次问全 4 个）
- ❌ 假装"我懂你的感受"绕开量化

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
