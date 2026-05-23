---
description: 读取 .runtime/session_state/ 下的 snapshot 文件，把工作状态带入当前 session。可指定 tag 接续特定 session（多并发时必用），或不带参数让 Claude 列出所有候选让用户选。
---

# /resume — 从 snapshot 接续上下文

**定位**：配合 `/snapshot`（手动）和 Hook D（自动）生成的 session state 档案使用。打开新 CC session 时想"接着之前的活"就 call。

## 用法

```
/resume                # 列出所有候选让用户选
/resume <tag>          # 直接读 .runtime/session_state/<tag>/ 下最新
/resume root           # 显式读根目录最新（不带 tag 的兜底快照）
```

## 执行步骤

### 模式 A：`/resume <tag>` 带参数

1. **校验 tag 合法**（`[a-zA-Z0-9_-]+`）
2. **检查 `.runtime/session_state/<tag>/` 存在**：
   - 不存在 → 调 `--list-tags` 看有哪些可选，报错 + 列出建议
3. **读最新一份 snapshot**：
   ```bash
   ls -1t .runtime/session_state/<tag>/*.md | head -1
   ```
4. **跳到 Step 3-呈现**

### 模式 A2：`/resume root` 显式根目录

读 `.runtime/session_state/*.md`（顶层）最新一份，跳到 Step 3。

### 模式 B：`/resume` 无参数

1. **列出所有候选**：
   ```bash
   .venv/Scripts/python.exe .claude/hooks/session_snapshot.py --list-tags
   ```
   外加根目录最新一份（看 `ls -1t .runtime/session_state/*.md | head -3`）

2. **呈现给用户**：
   ```
   ## 可接续的 session

   ### Tagged sessions（手动 /snapshot 的，主观+客观）
   | tag             | 最新存档     | 主题摘要                          |
   |-----------------|------------|----------------------------------|
   | bug-44          | 1 小时前    | 修 EVENT_ACCOUNT 订阅 bug         |
   | refactor-cache  | 40 分钟前   | 重构 Cache pending_orders          |

   ### 根目录最新（hook 自动兜底，仅客观）
   2026-04-25_122500.md（25 分钟前，post-compact）

   要接续哪个？
   - 输入 `/resume bug-44` 或 `/resume refactor-cache`
   - 输入 `/resume root` 接续根目录
   - 或 "都不要"
   ```

3. 等用户回应后跳 Step 3。

### Step 3：呈现 + 对齐

读取选定的 snapshot 文件完整内容，向用户呈现：

```
## 接续 snapshot：<文件名> [tag=<tag>]

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

## 何时主动建议

- 用户在新 session 开场说"继续" / "接着昨天" / "我刚才做到哪了"
- 用户迷失方向 / 不记得上次在哪
- 看到 SessionStart hook 输出的 `[snapshot]` 提示
- 看到 SessionStart hook 输出的 `[active tags]` 提示

## 禁止

- 不要盲信 snapshot 是当前状态——必须 `git status` 对齐
- 不要把 snapshot 内容写入 memory（snapshot 是短期可过时的）
- 不要一次读多份 snapshot（只读最新一份）
- `/resume <tag>` 找不到时不要静默 fallback 到 root（要报错让用户选）