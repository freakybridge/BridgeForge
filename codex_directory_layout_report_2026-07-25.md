# Codex 目录职责与收敛建议

日期：2026-07-25  
范围：Codex 下游项目的共享 skill、项目 rule 与 memory 的存放和加载边界。

## 结论

应收敛为两层，而不是保留 `.agents` 这层中间目录：

```text
C:\Users\bridg\.codex\skills\     所有 Codex 下游项目共用的 skill
<项目>\.codex\skills\              仅该项目专用的 skill
<项目>\.codex\rules\               仅该项目的持久规则
<项目>\.codex\memory\              仅该项目的经验与索引
```

项目进入工作目录后，项目范围已经明确；因此项目内 `.agents/` 不应再承担任何职责。

## 目录关系

| 目录 | 应有职责 | 是否应作为项目 rule/memory 的加载源 |
|---|---|---|
| `C:\Users\bridg\.codex\` | Codex 用户主目录：全局配置、通用 skill、插件与运行时状态 | 否；仅保存跨项目通用能力与 Codex 自身状态 |
| `C:\Users\bridg\.codex\skills\` | 全部 Codex 下游项目共用的 skill | 是，作为用户级共享 skill 来源 |
| `C:\Users\bridg\.agents\` | 旧 BridgeForge 协作骨架的共享 skill 架 | 否；应迁移后退役 |
| `C:\Users\bridg\.bridgeforge\` | 可选的 BridgeForge 模板/发布源仓库 | 否；不得作为运行时加载源 |
| `<项目>\.codex\` | 项目专属 rule、memory、hook、skill 与项目配置 | 是；项目规则与 memory 的唯一事实源 |
| `<项目>\.agents\` | 无独立职责的旧项目级遗留目录 | 否；应删除 |
| `<项目>\.bridgeforge\` | 历史归档或迁移记录 | 否；若保留，仅限 archive，不参与加载 |

## 为什么应移除 `.agents`

`.agents` 不是 Codex 的必要目录。保留用户级与项目级两套 `.agents` 会造成：

- 同一 skill 可能在多个目录存在副本，出现同步漂移。
- Agent 无法从目录名判断应加载哪个版本。
- 项目级 `.agents` 与项目级 `.codex` 职责重叠，增加维护面。
- hook 为校验 `.agents` 而增加额外运行时依赖，使项目无法完全自包含。

## 推荐迁移路径

1. 将 `C:\Users\bridg\.agents\skills\` 中仍需跨项目复用的 skill 迁入 `C:\Users\bridg\.codex\skills\`。
2. 将每个项目真正私有的 skill、rule、memory 和 hook 留在各自 `<项目>\.codex\`。
3. 删除项目内空的 `.agents/`；不再创建新的项目级 `.agents/`。
4. 移除项目 hook、脚本、文档中对 `~/.agents` 的运行时依赖，包括 skill 同步检查。
5. 将 `<项目>\.bridgeforge\` 降级为历史归档；模板源若保留，应在用户主动执行安装/升级时使用，而不是每次会话加载。

## 边界

- 不能、也不应删除 `C:\Users\bridg\.codex\`：它是 Codex 的用户主目录。
- 项目可以做到“项目 rule/memory 只来自 `<项目>\.codex`”，但 Codex 自身的系统指令与用户级配置仍属于运行环境，不由单个项目仓库控制。
- 通用 skill 属于用户级能力，应统一放入 `C:\Users\bridg\.codex\skills\`；项目 rule 和 memory 不应提升到用户级。

## 对 StratusAgent 的直接含义

StratusAgent 已将项目 rules、memory、hooks 和项目 skill 放在 `D:\Quant\StratusAgent\.codex\`。下一步应移除其对 `~/.agents` 的同步/加载假设，并删除项目内空 `.agents/`。这样项目的持久行为只需审阅一个位置：`.codex/`。
