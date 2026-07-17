---
name: bridgeforge
description: 在新项目里铺设或更新标准化的 Claude/Codex 协作骨架（CLAUDE.md 或 AGENTS.md、rules、memory、hooks、doc 分层），并自检补齐用户级通用 skill。用户提到 bridgeforge、项目骨架初始化、同步上游模板、switch claude/codex、Codex/Claude 入口 /bridgeforge 时使用。
version: 0.62.0
user_invocable: true
argument: 可选——switch claude|codex [--dry-run|--interactive] [--skip-settings-migration] [--migrate-setting KEY] [--memory-conflict REL=ACTION]，不带参数则维护当前 agent 骨架；若检测到另一套 agent 骨架，先确认再转 switch
model: sonnet
---

# bridgeforge — 项目协作骨架初始化 / 更新

## 定位与边界

给新项目安装或维护 Claude Code / Codex 协作骨架：入口文件、rules、memory、hooks、settings、doc 分层和用户级通用 skills。

`bridgeforge` 是用户级全局入口，必须由主对话完成刷新、判场、用户确认和模式编排；不按下游 18-skill manifest 分派 named custom agent。

用户只需记住：

- `/bridgeforge`：维护当前正在运行的 agent 骨架；自动判定 init、既有项目首次接入、adopt 或 update。
- `/bridgeforge switch <claude|codex>`：显式切换当前项目的 agent 骨架。

本文件只保留刷新、判场、分流、硬红线和验证入口。命中具体模式后，只读取对应 reference；禁止为方便一次性加载全部 references。

## 渐进读取路由

| 命中条件 | 必须读取 |
|---|---|
| 显式 `switch`，或用户确认隐式 switch | [references/switch.md](references/switch.md) |
| init / update / adopt 的公共用户级 skill 维护 | [references/user-skill-maintenance.md](references/user-skill-maintenance.md) |
| 全新项目或既有项目首次接入 | [references/init.md](references/init.md) |
| BridgeForge 衍生项目缺版本戳 | [references/adopt.md](references/adopt.md) |
| 已有 `.bridgeforge_version` | [references/update.md](references/update.md) |

`references/` 只允许这一层；所有操作手册都由本入口直接链接。不要沿引用链加载无关手册。

## Step 0：确定 agent 与路径

完整工厂统一放在 `$HOME/.bridgeforge`。用户级 `bridgeforge` 入口必须是只含 `SKILL.md` 的薄 wrapper。

| Agent | 用户级 skill 目录 | 项目配置 | 入口 | 项目专属 skill |
|---|---|---|---|---|
| Claude Code | `~/.claude/skills` | `.claude/` | `CLAUDE.md` | `.claude/skills/` |
| Codex | `~/.agents/skills` | `.codex/` | `AGENTS.md` | `.agents/skills/` |

设置以下逻辑变量：

```bash
ENTRY_COMMAND="/bridgeforge"
BRIDGEFORGE_HOME="$HOME/.bridgeforge"
```

Claude：

```bash
USER_SKILLS_DIR="$HOME/.claude/skills"
BRIDGEFORGE_COMMAND_DIR="$USER_SKILLS_DIR/bridgeforge"
PROJECT_AGENT_DIR=".claude"
PROJECT_ENTRY_FILE="CLAUDE.md"
PROJECT_SKILLS_DIR=".claude/skills"
TEMPLATE_AGENT="claude"
```

Codex：

```bash
USER_SKILLS_DIR="$HOME/.agents/skills"
BRIDGEFORGE_COMMAND_DIR="$USER_SKILLS_DIR/bridgeforge"
PROJECT_AGENT_DIR=".codex"
PROJECT_ENTRY_FILE="AGENTS.md"
PROJECT_SKILLS_DIR=".agents/skills"
TEMPLATE_AGENT="codex"
```

Codex 的 `~/.codex/` 只承载 Codex 配置/memory，不是用户级 skill 货架。

若新位置缺少 `SKILL.md`，但旧位置存在（Codex `~/.agents/bridgeforge-home/SKILL.md`；Claude `~/.claude/skills/bridgeforge/templates/`），本轮可临时把旧路径作为 `BRIDGEFORGE_HOME`，但必须提示按 `INSTALL.md` 迁移。禁止静默删除旧目录。

## Step 1：刷新用户级骨架库（所有分支前）

薄 wrapper 应已刷新；本入口仍必须兜底：

```bash
git -C "$BRIDGEFORGE_HOME" pull --ff-only
```

- 成功：只读取刷新后的文件继续。
- 冲突、网络或权限失败：报告并停止；禁止拿旧模板继续执行。
- 不是 Git 仓库：可继续，但提示改用 `git clone` 到 `~/.bridgeforge` 才能自动更新。

## Step 2：工厂自检（硬闸）

同时满足以下条件才是 BridgeForge 源头仓库自己：

```bash
test -f "templates/$TEMPLATE_AGENT/$PROJECT_ENTRY_FILE" && grep -q "项目协作骨架初始化" SKILL.md && echo FACTORY_SELF
```

命中 `FACTORY_SELF` 必须立即停止：源头不能 bootstrap、update、adopt 或 switch 自己；改框架应直接编辑根 `SKILL.md`、`references/`、`templates/` 或 `skills/`。

## Step 3：显式 switch 优先

若参数以 `switch` 开头，先读取 [switch 手册](references/switch.md)，再按其中的完整性判定和脚本契约执行。

目标 agent 已完整且旧 agent 不存在时，不调用脚本，回到 Step 4 按普通维护判场。其他 switch 分支不得继续走 init/update/adopt。

## Step 4：识别 live 骨架与模式

当前/另一套 live 路径：

| 当前 agent | 当前 live | 另一套 live |
|---|---|---|
| Claude | `CLAUDE.md` 或 `.claude/` | `AGENTS.md` 或 `.codex/` 或 `.agents/skills/` |
| Codex | `AGENTS.md` 或 `.codex/` 或 `.agents/skills/` | `CLAUDE.md` 或 `.claude/` |

先检查当前版本戳：

```bash
test -f "$PROJECT_AGENT_DIR/.bridgeforge_version" && cat "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

无版本戳时检查 BridgeForge 衍生指纹；至少命中 2 项才算衍生：

```bash
grep -q "鬼打墙" "$PROJECT_ENTRY_FILE" 2>/dev/null
grep -q "ctx-budget" "$PROJECT_ENTRY_FILE" 2>/dev/null
grep -rq "OPTIONAL_BEGIN" "$PROJECT_AGENT_DIR/rules/" 2>/dev/null
test -f "$PROJECT_AGENT_DIR/rules/meta_rule_design.md"
test -f "$PROJECT_AGENT_DIR/rules/workflow.md"
```

按顺序判定，首个命中即停止继续判场：

| 场景 | 判据 | 路由 |
|---|---|---|
| 双 live 冲突 | 当前和另一套同时存在 | 停止，让用户选：只维护当前 / 先清理另一套 / 退出 |
| update | 当前有 `.bridgeforge_version` | 公共 skill 维护后读 `update.md` |
| adopt | 无戳，当前指纹 ≥2 | 公共 skill 维护后读 `adopt.md` |
| 当前文件冲突 | 无戳，当前入口/rules 存在但指纹不足 | 公共 skill 维护后读 `init.md`，必须先问保留补缺/备份覆盖/退出 |
| 隐式 switch | 当前不存在，另一套存在 | 告知将 switch 到当前 agent；用户确认后读 `switch.md`，不确认则退出 |
| 全新 init | 两套都不存在，cwd 基本为空 | 公共 skill 维护后读 `init.md` |
| 既有项目首次接入 | 两套都不存在，但有业务文件/Git/配置 | 说明保留已有内容；公共 skill 维护后读 `init.md`，冲突逐项问 |

普通 `/bridgeforge` 只维护当前 agent。发现另一套时，禁止静默多铺一套。

判场完成后锁定本轮唯一状态：

```text
REFRESHED
  ├─ FACTORY_SELF -> STOP
  ├─ SWITCH -> switch 手册 -> DONE 或回到普通判场
  ├─ UPDATE -> 公共维护 -> update 手册
  ├─ ADOPT -> 公共维护 -> adopt 手册
  └─ INIT / EXISTING-ONBOARD -> 公共维护 -> init 手册
```

禁止在同一轮把 init、adopt、update 混着执行。模式执行中若新证据改变判定，先停止并重新报告判场依据；不得凭惯性继续原分支。

## Step 5：公共维护后执行唯一模式

init、update、adopt 都先完整执行 [用户级 skill 与重复副本维护](references/user-skill-maintenance.md)，再只读取本轮模式手册：

- init / 既有项目首次接入：`references/init.md`
- adopt：`references/adopt.md`
- update：`references/update.md`

显式/隐式 switch 不执行这三条路线；完成 switch 后，若脚本报告“already target”，才回 Step 4 重新判定普通维护模式。

## 传播与数据边界红线

BridgeForge 下沉时按业务专属性分层：

| 内容 | 允许动作 |
|---|---|
| 上游 hooks/scripts、未定制的用户级 skill | 比对后覆盖；存在差异先展示并确认 |
| settings | merge，不覆盖；保留项目 permissions/env/additionalDirectories/自定义 hooks |
| rules、入口文件 | 只 diff，用户逐段决定 |
| memory、`doc/` | 绝对不动 |
| 项目专属 skill | 不属于通用去重范围，绝对不动 |

通用改进的源必须是 `$BRIDGEFORGE_HOME/templates/` 或 `skills/`；下游副本只是消费者。一次只维护当前 cwd，禁止 AI 自动跨多个项目同步。

## 通用危险红线

- 禁止静默覆盖已有入口文件、rules、settings 或同名定制 skill。
- 禁止批量/静默删除项目级重复 skill、用户级扁平 shadow 或退役 skill；每项单独确认。
- 禁止代编架构红线、快速命令和项目结构。
- 禁止跳过 doc 分层、Python 硬依赖或 memory junction。
- 禁止在 BridgeForge 源头仓库自身运行 bootstrap/update/adopt/switch。
- 禁止自动 `git commit` / `git push`；真实 switch 同样只改工作区。
- 禁止在未解决冲突、未完成验证时写新版本戳。
- 禁止把 Claude 与 Codex 的用户级目录、memory 机制或 settings 混用。

## 验证与输出

只有列出真实命令、断言和覆盖场景，才能说“验证通过”。按模式至少提供：

| 模式 | 最低收据 |
|---|---|
| switch | 脚本退出码；目标三件套存在；旧 live 消失；归档/memory/settings 结果 |
| init | 复制/merge 清单；OPTIONAL 残留检查；snapshot smoke test；memory junction；版本戳 |
| adopt | 命中指纹、用户确认、写入基线；确认未改既有内容 |
| update | 版本区间与 `[product]`；A-E 分类；hook smoke test；新版本戳；git diff |
| 公共 skill 维护 | 新装/一致/定制/退役/重复/shadow 的逐项结果；是否需重启 agent |

最终输出遵循“已做什么 / 验证了什么 / 还剩什么风险”。任何停止条件命中时，说明缺少的证据或用户决定，不得伪称完成。
