# bridgeforge-codex

> 面向长期 Codex 项目的协作骨架工厂。

bridgeforge-codex 将原生 AGENTS 指令、memory、hooks、文档生命周期和通用 skills 打包为
一套 Codex-only 下游模板。当前稳定产品边界为 `1.4.13`，最低支持 Python 3.11 和
Windows。

## 快速开始

```powershell
git clone https://github.com/freakybridge/BridgeForgeCodex.git D:\tools\BridgeForgeCodex
Set-Location D:\tools\BridgeForgeCodex
& powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-shared-skills.ps1
```

随后在目标项目根目录运行：

```text
$bridgeforge-codex
```

该入口会先把完整、可信的产品仓库安装到 `~/.bridgeforge-codex`，并只在
`~/.codex/skills/bridgeforge-codex` 保留 Codex 可发现的薄入口；随后维护用户级受管
skills，再根据项目状态选择 init、adopt 或 update。已有项目
的 AGENTS、hooks、memory、skills、文档与项目定制按 schema v2 ownership 事务更新，未知或
人工修改内容不会被静默覆盖。

旧 `$bridgeforge`、旧用户级 ledger、旧 `.bridgeforge` home 和 Claude 用户级资产不再受
支持，也不会由当前产品读取、接管或删除。旧用户必须按当前安装流程重新安装
`$bridgeforge-codex`。Claude 骨架、switch 和双骨架 parity 已退役；项目内偶遇 Claude
文件时只提示，不读取或修改。

## 下游项目内容

- 根 `AGENTS.md`：BridgeForge 公共区只读更新，项目级专区逐字保留；嵌套 `AGENTS.md` 全部属于项目。
- `.codex/hooks/` 与 pre-commit：可机器判定的硬闸；会话快照及文档、AGENTS、memory 健康检查。
- skills：按用户调用执行的流程；长 SOP、原理和案例进入 `doc/`。
- 以 `doc/README.md` 为索引的五层文档体系。
- `confirm`、`develop`、`summary`、`find-doc`、`find-memory`、`git-sync` 等通用 skills。

## 仓库结构

```text
BridgeForgeCodex/
├── skills/bridgeforge-codex/ # $bridgeforge-codex 产品入口
├── skills/                   # 通用 skills
├── templates/               # 唯一活跃下游模板根
├── scripts/                 # 安装、项目同步与 tests
├── doc/                     # 架构、交付、Bug、参考与归档
├── bridgeforge-codex-manifest.json # updater 的 Codex-only 正式分发清单
├── VERSION
└── CHANGELOG.md
```

`templates/`、`skills/` 属于产品层；`.codex/` 是本仓库 dogfood；`doc/` 和 README 是
元文档。产品层变化需要同步版本、CHANGELOG、schema/manifest 与 dogfood。

详细入口：[文档索引](doc/README.md)、
[设计依据](doc/0_architecture/design/design-rationale.md)、
[原生指令架构](doc/0_architecture/design/codex-native-instruction-architecture.md)、
[Codex 项目同步设计](doc/0_architecture/design/codex-project-sync.md)。

## License

MIT
