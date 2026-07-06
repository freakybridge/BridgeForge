# Codex 中 `/bridgeforge` 斜杠命令不可见问题报告

## 1. 问题现象

在 Claude Code 中，用户曾经可以通过输入 `/bridgeforge` 调用对应命令；切换到 Codex 后，在斜杠菜单中输入 `/bridgeforge`，菜单里看不到对应命令，也无法按同样方式调用。

本问题不是用户输入错误，也不是 BridgeForge 业务逻辑失效，而是 Claude Code 与 Codex 的扩展注册机制不同。

## 2. 已验证事实

在 `D:\Quant\causis_risk_suite` 当前项目中检索后，未发现 Codex 可识别的 `bridgeforge` 命令定义。

已观察到：

```text
rg: .Codex: 系统找不到指定的文件。
rg: .codex: 系统找不到指定的文件。
```

仓库中仅在历史文档里出现过 `/bridgeforge` 说法，例如：

```text
doc\2_pending\debates_2026-06-30_幻觉文件名干预.md:317:
上游骨架库 bridgeforge（由 `/bridgeforge` skill 铺设）是这套通用壳的入库目标
```

这说明当前项目文档记录了“预期入口”或历史入口，但 Codex 当前环境里没有实际安装 / 注册名为 `bridgeforge` 的 slash command、skill 或 plugin。

## 3. 根因分析

### 3.1 Claude Code 与 Codex 不共享斜杠命令体系

Claude Code 的自定义斜杠命令通常来自 Claude 自己的配置目录，例如：

```text
~/.claude/commands/
项目内 .claude/commands/
```

Codex 不会自动扫描这些 Claude Code 命令目录，因此 Claude Code 里可用的 `/bridgeforge` 不会天然出现在 Codex 菜单里。

Codex 的可调用入口来自另一套体系：

```text
内置 slash commands
Codex skills
Codex plugins
~/.codex/prompts/*.md 旧版 custom prompts
```

因此，`/bridgeforge` 必须被迁移 / 注册到 Codex 的体系中，Codex 才能显示或调用它。

### 3.2 Codex 当前推荐用 skill/plugin，而不是旧式 custom prompt

Codex 官方机制中，skill 是可复用工作流的主要承载方式；plugin 是可分发安装单元。旧式 `~/.codex/prompts/*.md` 仍可用于兼容，但属于 deprecated custom prompts。

因此，长期推荐路径不是简单复制 Claude Code 的 slash command，而是将 BridgeForge 工作流改造成 Codex skill，必要时再打包为 plugin。

### 3.3 当前已有近似能力：`harvest`

当前 Codex 技能列表中存在 `harvest`：

```text
把下游项目攒下的通用经验脱敏后反哺回 bridgeforge 上游骨架库（reverse-sync）。
```

如果用户意图是“把当前项目经验反哺回 BridgeForge 上游骨架库”，那么当前应优先调用：

```text
$harvest
```

而不是 `/bridgeforge`。

## 4. 修复方案

## 方案 A：推荐修复，将 `/bridgeforge` 迁移为 Codex skill

适用场景：希望 BridgeForge 成为 Codex 中长期可维护、可隐式触发、可跨项目复用的能力。

建议创建：

```text
%USERPROFILE%\.agents\skills\bridgeforge\SKILL.md
```

或项目级：

```text
<repo>\.agents\skills\bridgeforge\SKILL.md
```

示例骨架：

```markdown
---
name: bridgeforge
description: 将当前项目中可复用的规则、经验、脚手架改动脱敏后同步回 BridgeForge 上游骨架库；当用户要求反哺 bridgeforge、更新骨架库、沉淀通用项目模板时使用。
---

# BridgeForge Sync

## 触发场景

- 用户要求把当前项目经验反哺到 BridgeForge
- 用户要求更新项目骨架 / 通用规则 / 通用 hooks / 通用 skill
- 用户提到 `/bridgeforge` 的历史入口

## 工作流

1. 明确要反哺的是规则、文档、hook、skill、模板还是脚手架代码。
2. 从当前项目提取通用经验，去除项目私有业务、路径、账号、密钥、交易细节。
3. 在 `D:\Quant\BridgeForge` 中定位对应上游文件。
4. 小步修改，保持可删除性和低系统复杂度。
5. 输出改动摘要和验证证据。
```

创建后，Codex 通常可以通过以下方式调用：

```text
$bridgeforge
```

如果 skill 已启用，也可能出现在 slash command 列表中。若未立即出现，重启 Codex。

## 方案 B：把 BridgeForge 能力做成 Codex plugin

适用场景：希望在多台机器、多项目间分发；或者除了 skill，还要一起分发 hooks、MCP、脚本、资源文件、菜单元数据。

建议结构：

```text
BridgeForge plugin
├─ .codex-plugin/plugin.json
├─ skills/bridgeforge/SKILL.md
├─ scripts/
├─ hooks/
└─ assets/
```

优点：

- 适合团队共享
- 适合统一版本管理
- 能把 skill、hook、脚本、MCP 配置打成一个安装单元

缺点：

- 初始结构比单个 skill 更重
- 需要维护 plugin manifest 和安装流程

长期看，如果 BridgeForge 是上游骨架库，plugin 是更适合的分发形态。

## 方案 C：临时兼容，创建 Codex custom prompt

适用场景：只想快速恢复“菜单里能搜到一个入口”，不追求长期机制正确。

创建文件：

```text
%USERPROFILE%\.codex\prompts\bridgeforge.md
```

示例：

```markdown
---
description: 将当前项目经验反哺回 BridgeForge 上游骨架库
argument-hint: [TOPIC=""]
---

请执行 BridgeForge 反哺流程：分析当前项目中与 $ARGUMENTS 相关的通用经验，脱敏后同步到 D:\Quant\BridgeForge。
优先保持低系统复杂度、低耦合、单一事实源和可删除性。
```

调用方式是：

```text
/prompts:bridgeforge
```

注意：这不是 `/bridgeforge`，而是 `/prompts:bridgeforge`。Codex 官方更推荐 skill，因此该方案只建议作为过渡。

## 5. 推荐决策

推荐采用方案 A：先把 BridgeForge 做成 Codex skill。

原因：

- 比 custom prompt 更符合 Codex 当前推荐机制
- 比 plugin 更轻，适合先恢复可用性
- 后续如需团队分发，可平滑升级为 plugin
- 可通过 `$bridgeforge` 明确调用，也可依赖 description 做隐式触发

如果目标是把 BridgeForge 作为全局上游骨架库长期维护，再进一步升级为方案 B 的 plugin。

## 6. 验收标准

修复后应满足：

1. Codex 可通过 `$bridgeforge` 调用 BridgeForge 工作流。
2. `/skills` 列表中可看到 `bridgeforge` skill。
3. 如果使用 custom prompt 兼容方案，则 `/prompts:bridgeforge` 能在 slash 菜单中出现。
4. 用户输入“把这个经验反哺到 bridgeforge”时，Codex 能自动选择或建议 BridgeForge 工作流。
5. 不再依赖 Claude Code 的 `.claude/commands` 目录。

## 7. 一句话结论

Claude Code 能调用 `/bridgeforge`，是因为它读到了 Claude Code 自己的命令注册；Codex 看不到，是因为该命令没有迁移到 Codex 的 skill / plugin / prompt 体系。长期修复应将 BridgeForge 做成 Codex skill，必要时再打包为 plugin。
