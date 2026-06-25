---
name: project-v031-state
description: v0.31.0 effortLevel 治理反转：空转根因分析 + 机检 hook 替代散文 rule + 全局 SessionEnd 自动还原
metadata: 
  node_type: memory
  type: project
  originSessionId: 18992951-df51-47c9-910b-1f37d200374e
---

## v0.31.0（2026-06-26）

### 背景：多项目 token 空转根因

调研 4 个下游项目的空转现象（token 消耗但无回复）。

**根因**：Opus 4.8 在 high/xhigh effort 下"拿到信息不收口"——收到任何工具返回（哪怕 14 字符）就触发超长思考，命中 64k `max_tokens` 截断，输出 0 可见字符。证据：同 Opus 4.8、同 xhigh effort 的 subagent（无项目 CLAUDE.md）0 次空转，判别因子 = 主线程元上下文负载（rulebook + hooks）。

**触发分布（49 次跑偏轮）**：TOOL_RESULT 61%、SHORT_PROMPT 10%、BIG_RESULT 8%、PROMPT 8%、CHAIN_THINK 6%、其余 6%。

### 核心改动

#### 1. effortLevel 治理反转

| 旧红线（portability.md §1）| 新红线 |
|---|---|
| 项目级**应当**写 effortLevel 覆盖全局（可移植） | 项目级**一律不写** effortLevel，全局统一管 |

**为什么反转**：项目级优先级 > 全局（Project > User），旧红线把顺手的 slider/`/effort` 顶掉，用户"调了不生效、被锁在 high 难降"，high effort 是空转放大器。

#### 2. 机检 hook 替代散文 rule（"骨架特征"）

用户语录："如果下游项目流入了 effortLevel 整套机制就白费了。加入了强制删的 hook 后就没必要 rule 了，这是这个骨架的特征。"

- 新建 `templates/hooks/enforce_no_effortlevel.py`（产品层）：SessionStart 自动剔除项目 `.claude/settings.json` 里的 effortLevel（原子写 + .bak + ASCII 通知）
- `.claude/hooks/enforce_no_effortlevel.py`（dogfood 镜像，逐字一致）
- 删 portability.md §1 散文规则 → 替换成一行"反向例外 + 指向 hook"面包屑
- portability.md §3 表格同步更新 `~/.claude/settings.json` 行

#### 3. 全局 SessionEnd 自动还原（个人，非产品层）

- `~/.claude/reset_effort.py`：SessionEnd hook，还原 effortLevel→medium（原子写）
- 注册进 `~/.claude/settings.json` SessionEnd 钩子
- baseline = medium；临时提效 → `/effort high` 或 ultracode，关对话自动还原
- **刻意不进 templates/**（否则 N 个下游抢改同一全局文件打架）

### 版本

- `VERSION`：0.30.0 → 0.31.0
- `templates/VERSION`：0.3.0 → 0.4.0

### 遗留（不变）

- 4 个下游仓库需手动 sync + 删各自的项目级 effortLevel（下次开会话 hook 会自动剔除，也可提前手删）
- `.claude/settings.json.bak` 需加进下游 .gitignore（可选，如不加则产生一次性 diff）
- [[ghost-wall-threshold-conflict]] 阈值冲突仍未解决
- live session e1a00860 跑偏已交接至单独对话（`.runtime/spinoff/live-offtrack-investigation.md`）

关联 [[effort-config-layering]]（完整覆盖关系 + 决策推理）。
