---
description: 读取 .runtime/session_state/ 下的 snapshot 文件，把工作状态带入当前 session。不带参数时让 Claude 列出候选让用户选，或带 `latest` 直接读最新一份。
---

# /resume — 从 snapshot 接续上下文

**定位**：配合 `/snapshot`（手动）和 Hook D（自动）生成的 session state 档案使用。打开新 CC session 时想"接着之前的活"就 call。

## 用法

```
/resume                # 列出所有候选让用户选
/resume latest         # 直接读最新一份（跳过列表）
```

## 执行步骤

### 模式 A：`/resume latest` 直接读最新

读 `.runtime/session_state/*.md` 最新一份，跳到 Step 3。

```bash
ls -1t .runtime/session_state/*.md | head -1
```

### 模式 B：`/resume` 无参数

1. **列出最近候选**：

   ```bash
   ls -1t .runtime/session_state/*.md | head -10
   ```

2. **呈现给用户**：

   ```
   ## 可接续的 session（按时间倒序）

   | # | 存档时间   | 主题摘要                          |
   |---|-----------|----------------------------------|
   | 1 | 1 小时前   | 修 EVENT_ACCOUNT 订阅 bug         |
   | 2 | 40 分钟前  | 重构 Cache pending_orders          |
   | 3 | 25 分钟前  | post-compact 自动存档（仅客观）    |

   要接续哪个？输入编号（1/2/3）或 "都不要"。
   ```

3. 等用户回应后跳 Step 3。

### Step 3：呈现 + 对齐

读取选定的 snapshot 文件完整内容，向用户呈现：

```
## 接续 snapshot：<文件名>

**上次状态**：
- Branch: <branch>
- 版本: v<x.y.z>
- Uncommitted: <N 个文件>
- 存档事件: <event>

**上次做了什么**（从 snapshot 主观 section 抽，若有）：
- ...

**下一步打算**（snapshot 记的）：
- ...

准备从这里继续吗？
```

### Step 4：git 状态对齐

跑 `git status` 对比当前实际状态 vs snapshot 里的 uncommitted。

- 一致 → 直接接续
- **不一致**（用户这期间改了别的）→ 提示："当前 git 状态和 snapshot 不一致，你期间可能动了别的事，要先 git stash 还是直接覆盖式接续？"

### Step 5：memory 对齐

从 snapshot 内容提取 2-4 个关键词（branch 名 + P0 TODO 关键词 + 任务主题词）。

**先查热区**：扫 MEMORY.md，判断热区是否已有与当前任务相关的条目。

- **有匹配** → 无需额外操作，热区已覆盖，继续 Step 6。
- **无匹配** → 调用 `/find-memory <关键词>`，读取命中的最相关 1-2 个文件。

> 这一步的目的是确保接续任务前，相关 memory 已被召回，不会因冷却而遗漏历史决策。

### Step 6：建议对话框重命名（必做）

用户在 Step 3 回 yes 接续后，**主动**提议把当前 Claude Code 对话框（session）从默认的 "resume" 改成描述性名称。

**为什么必做**：
- `/resume` 启动的 session 默认 title 就是 "resume"，无指导性
- 多 session 并发时 "resume" / "resume (2)" 无法区分内容
- 在 Claude Code 对话历史列表里翻找旧 session 时，描述性名称才能一眼定位

**抽取主题**（agent 自己想，不要问用户）：
- 优先从 snapshot 的"本轮做了什么" / "下一步打算" 段抽**动词 + 对象**，3-12 字
- snapshot 主观段为空时（如 root 自动存档只有客观状态）→ 从 uncommitted 改动模式 + branch 名推断（例：`branch=feature/oms-refactor` → 建议「OMS 重构」）
- 主题示例：「修 EVENT_ACCOUNT 订阅 bug」/「重构 Cache pending_orders」/「setup_agent 通用化整理」/「M2.A ladder 性能优化」

**呈现**（可与 Step 4 git 对齐结果合并到同一 message）：

```
💡 建议把当前对话框重命名为「<主题>」
   （/resume 默认 session 名是 "resume" 无指导性，描述性命名后续在 Claude Code 历史列表好找）
```

**命名机制提示**：agent 没有 API 直接改 Claude Code session title（截至 2026-05）。用户需在 Claude Code UI 手动改（点击 session 名 → 编辑）。如果未来 CC 暴露 rename API，本 Step 可升级为自动改。

**禁止**：
- ❌ 空泛名（"继续工作" / "新任务" / "X 项目"）— 必须含**动作语义**
- ❌ 强制重命名 — 用户回"不用"就闭嘴，不要追问
- ❌ 在 Step 3 之前提（用户还没确认接续就提命名是冗余的）

## 何时主动建议

- 用户在新 session 开场说"继续" / "接着昨天" / "我刚才做到哪了"
- 用户迷失方向 / 不记得上次在哪
- 看到 SessionStart hook 输出的 `[snapshot]` 提示

## 禁止

- 不要盲信 snapshot 是当前状态 — 必须 `git status` 对齐
- 不要把 snapshot 内容写入 memory（snapshot 是短期可过时的）
- 不要一次读多份 snapshot（只读用户选定的那一份）
