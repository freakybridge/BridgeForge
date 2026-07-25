# BridgeForge

> 面向长期项目的 Claude Code / Codex 协作骨架工厂。

BridgeForge 将可复用的协作约束、文档生命周期、memory、hooks 和通用 skills
打包为两套下游模板：`templates/claude/` 与 `templates/codex/`。在项目根运行
`/bridgeforge` 后，agent 会识别初始化、首次接入、收编或更新场景，并只改动当前
宿主对应的骨架。

## 适用范围

适合：有持续演进需求、多人或多 agent 协作、需要保留需求/设计/验收证据的中大型项目。

不适合：一次性脚本、短期 demo，或不接受 `doc/` 分层、Python hooks 和项目级协作约束的项目。

## 快速开始

BridgeForge 当前只支持 Windows。首次安装使用仓库内的安装器，它会从 canonical
`main` 获取受管 shared skills，并分别安装到 Codex 与 Claude Code 的用户级 skill
目录：

```powershell
git clone https://github.com/freakybridge/BridgeForge.git D:\tools\BridgeForge
Set-Location D:\tools\BridgeForge
& powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-shared-skills.ps1
```

随后在目标项目根目录使用：

```text
/bridgeforge
```

切换当前宿主的项目语义时使用：

```text
/bridgeforge switch claude
/bridgeforge switch codex
```

`/bridgeforge` 会先同步受管 shared skills，再根据项目状态进入 init、adopt 或 update。
已有项目的 rules、入口、memory 或文档发生冲突时，先展示差异并等待用户决定；不会
静默覆盖。

## 下游项目会得到什么

- Claude 的 `CLAUDE.md + .claude/` 或 Codex 的 `AGENTS.md + .codex/` 入口骨架。
- 按路径触发的 rules、会话快照、上下文预算、文档/规则/memory 健康检查等 hooks。
- 以 `doc/README.md` 为唯一索引的五层文档体系：
  `0_architecture / 1_delivery / 2_bugs / 3_reference / 4_archive`。
- 按需创建的 memory：初始只有 `MEMORY.md`；长期知识可写入
  `architecture/`、`engineering/`、`domain/`、`operations/`，专题恢复摘要写入
  `topics/<topic>/`。`completed` 与 `superseded` topic 只会冷却，不会被物理归档。
- `confirm`、`develop`、`summary`、`find-doc`、`find-memory`、`harvest`、`git-sync`
  等受管通用 skills。

## 文档与 memory 的边界

| 内容 | 单一事实源 | 使用方式 |
|---|---|---|
| 系统架构、接口契约、长期决策 | `doc/0_architecture/` | 常驻设计资料 |
| 需求确认、论证、计划、验收 | `doc/1_delivery/<topic>/` | 保留完整交付过程 |
| 未关闭 Bug 的发现到验证 | `doc/2_bugs/` | 独立修复闭环 |
| 外部资料 | `doc/3_reference/` | 只作参考，不替代设计 |
| 当前热索引 | `<agent>/memory/MEMORY.md` | 每次会话先读 |
| 专题跨会话摘要 | `<agent>/memory/topics/<topic>/` | 唯一识别当前 topic 时再读 |

`doc/README.md` 是文档索引和 delivery 布局的单一事实源。任何 `doc/**` 文档的新增、
删除、移动或重命名，都必须同步该索引。

## 仓库结构

```text
BridgeForge/
├── skills/bridgeforge/        # /bridgeforge 入口与按场景加载的运行手册
├── skills/                    # 受管通用 skills
├── templates/
│   ├── claude/                # Claude Code 下游模板
│   └── codex/                 # Codex 下游模板
├── scripts/                   # 安装、分发、迁移与 switch 工具
├── doc/                       # BridgeForge 自身的架构、交付、Bug、参考与归档
├── shared-skill-manifest.json # 用户级 skill 分发清单与文件哈希
├── VERSION                    # BridgeForge 版本单一事实源
└── CHANGELOG.md               # 上游变更记录；[product] 表示下游应关注
```

## 维护本仓库

BridgeForge 是“协作骨架工厂”，不是普通业务项目。修改前先判断改动属于：

- `templates/` 或 `skills/`：产品层，随下游同步传播；通常需要更新版本和
  `CHANGELOG.md` 的 `[product]` 条目。
- `.codex/`、`.claude/`：本仓库 dogfood 配置；模板 hook 或 settings 变化时必须同步。
- `doc/`、本 README：元文档；描述产品但不会自动复制进下游。

详细设计入口：[文档索引](doc/README.md)、
[设计依据](doc/0_architecture/design/design-rationale.md)、
[上游同步手册](doc/0_architecture/design/sync-from-upstream-playbook.md)、
[反哺手册](doc/0_architecture/design/reverse-sync-playbook.md)。

## License

MIT
