# setup_agent

> Claude Code 项目协作骨架初始化器。一行 skill 命令铺好 CLAUDE.md / rules / memory junction / doc 分层归档。

## 这是什么

把一个长期沉淀过的"Claude Code 协作管理体系"打包成可复用 skill，进新项目跑一次 `/setup_agent` 就能拿到：

- **双层 CLAUDE.md**：全局 `~/.claude/CLAUDE.md` 管沟通/安全/执行协议；项目 `<repo>/CLAUDE.md` 管架构红线 + rules 索引 + skills 表
- **rules 分层加载**：`.claude/rules/<topic>.md` 按文件路径触发，CLAUDE.md 维护索引表
- **Memory junction**：系统 memory 路径链回 `.claude/memory/`，纳入项目 git
- **doc/ 分层归档**：`0_architecture（含 acceptance + TODO-INDEX）/ 1_plan（含 sprints）/ 2_pending / 3_design / 4_archive / 9_reference` — 二分语义"正在做（acceptance + sprints）vs 暂时没空（TODO-INDEX 主表）vs 远期 backlog（TODO-INDEX §远期索引）"
- **工作流红线**：鬼打墙觉察 + 渐进升级（lvl 0→3）、修 bug 前确认根因、UI 偶现 bug 主动问 4 件事
- **可移植性约束**：pip 陷阱、hooks 路径、换机 checklist

模板素材出自 [StratusAgent](https://github.com/freakybridge/StratusAgent) 长期沉淀，已剥离项目特定内容。

## 安装

```bash
# 1. clone 到 Claude Code 用户级 skill 目录
git clone https://github.com/<你的用户名>/setup_agent.git ~/.claude/skills/setup_agent

# Windows（PowerShell）
git clone https://github.com/<你的用户名>/setup_agent.git "$env:USERPROFILE\.claude\skills\setup_agent"
```

详细安装说明见 [INSTALL.md](INSTALL.md)。

## 使用

进任何新项目根目录（建议先 `git init`），调用：

```
/setup_agent
```

skill 会问你 4 个问题（项目名 / 主语言 / 是否需要换机 checklist / 是否建 doc/），然后铺骨架，最后告诉你哪 3 处占位需要手填。

## 目录结构

```
setup_agent/
├── SKILL.md                    ← skill 入口（Claude 读它执行 init）
├── README.md                   ← 本文件
├── INSTALL.md                  ← 安装与卸载指引
├── templates/
│   ├── CLAUDE.md               ← 项目级 CLAUDE.md 深度模板
│   ├── rules/
│   │   ├── architecture.md     ← 骨架（职责边界占位）
│   │   ├── modules.md          ← 骨架（模块组织范式占位）
│   │   ├── debugging.md        ← 通用（鬼打墙红线 / 修 bug 前确认根因）
│   │   ├── workflow.md         ← 通用（同步文档 / 主动写规则 / 经验总结）
│   │   └── portability.md      ← 通用（换机可移植性 / pip 陷阱 / hooks 约束）
│   ├── memory/MEMORY.md        ← 空索引模板
│   └── doc/README.md           ← 文档分层索引模板
├── scripts/
│   ├── setup-junction.ps1      ← Windows: New-Item -ItemType Junction
│   └── setup-junction.sh       ← macOS/Linux: ln -s
└── docs/
    └── design-rationale.md     ← 为什么这样分层（设计说明）
```

## 设计原则

完整论述见 [docs/design-rationale.md](docs/design-rationale.md)。核心：

1. **rules vs memory 分工**
   - rules：架构约束/红线/范式（"必须 / 禁止"），少且稳定
   - memory：踩坑经验/决策记录（"上次踩了 X"），多且增长
   - feedback memory 沉淀够多 → 升级为 path-rule

2. **rules 按需加载**
   - CLAUDE.md 索引表的"加载条件"列控制：始终加载 / 路径触发
   - 路径触发用 frontmatter `paths:` 列表，编辑对应文件时自动加载

3. **Memory junction 跨机复现**
   - 系统路径（`~/.claude/projects/<hash>/memory/`）只是 junction 入口
   - 真实存储在项目内 `.claude/memory/`，纳入 git
   - clone 即恢复，不依赖用户目录状态

## License

MIT
