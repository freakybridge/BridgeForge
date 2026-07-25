# switch codex 后残留 .claude live 目录问题报告

日期：2026-07-09
来源项目：D:\Quant\StratusAgent
目标项目：D:\Quant\BridgeForge

## 结论

`bridgeforge switch codex` 执行后，项目根目录仍残留 `.claude/`，这不符合 switch 的语义。

显式 switch 到 Codex 后，Claude 侧骨架不应该继续以 live 目录存在。旧 Claude 内容只能进入归档区，不能继续留在项目根目录参与后续判断。

## 现象

StratusAgent 已切换到 Codex 骨架，当前 live 骨架应为：

```text
AGENTS.md
.codex/
.agents/skills/
```

但项目根目录仍存在 Claude 侧目录：

```text
.claude/
```

这会造成“双骨架 live 状态”：Codex 已启用，但 Claude 目录仍像有效项目骨架一样存在。

## 期望行为

执行：

```text
bridgeforge switch codex
```

完成后应满足：

```text
必须存在 AGENTS.md
必须存在 .codex/
允许存在 .agents/skills/
不得存在 CLAUDE.md
不得存在 .claude/
```

旧 Claude 内容应被归档到：

```text
.bridgeforge/archive/claude/<timestamp>/
```

归档范围固定为：

```text
CLAUDE.md
.claude/
```

归档成功后必须删除原 live 路径。

## memory 处理要求

`.claude/memory/` 不能简单丢弃。switch codex 时应合并到：

```text
.codex/memory/
```

建议规则：

- 完全重复：自动去重
- 同路径不同内容：要求确认，或使用显式参数回放策略
- 相似但不完全相同：要求确认，或使用显式参数回放策略

非交互模式可使用类似参数：

```text
--memory-conflict keep-target|copy-old|append-old
```

## hooks / rules / skills / entry 文件处理要求

Claude 侧以下内容默认只归档，不自动迁移进 Codex：

```text
CLAUDE.md
.claude/hooks/
.claude/rules/
.claude/skills/
.claude/settings.json
```

原因：这些内容存在 agent 兼容性风险，不能机械搬入 `.codex/`。

正确动作是：

```text
归档 + 报告
```

不是静默迁移，也不是继续保留 live 路径。

## 疑似根因

当前 `switch codex` 流程可能存在一个分支漏洞：

当项目已经存在 `AGENTS.md + .codex/` 时，流程判断“已经是目标 agent”，于是跳过 switch 脚本，转入普通 update / maintain 流程。

但该判断没有继续检查“另一个 agent 的 live 骨架是否仍存在”。结果是：

```text
Codex live 骨架存在 -> 被判定为已是 Codex -> 不执行 switch cleanup
Claude live 骨架残留 -> 没有被归档删除
```

这导致 `switch codex` 的完成状态是假的。

## 修复建议

### 1. switch 子命令必须优先处理双 live 冲突

`switch codex` 不应只判断目标骨架是否存在，还必须检查旧 agent live 骨架。

伪逻辑：

```text
if target == codex:
    target_live = AGENTS.md or .codex/ or .agents/skills/
    old_live = CLAUDE.md or .claude/

    if old_live exists:
        run switch cleanup/archive flow
    else if target_live exists:
        already codex; enter normal maintain/update
    else:
        install/restore codex skeleton
```

重点：只要旧 agent live 路径存在，显式 switch 就不能短路为普通 update。

### 2. switch 完成后增加硬验收

`switch codex` 最后必须检查：

```text
AGENTS.md exists
.codex exists
CLAUDE.md not exists
.claude not exists
```

若 `.claude/` 或 `CLAUDE.md` 仍存在，应直接报错，不能输出成功。

### 3. dry-run 必须列出归档和删除计划

`switch codex --dry-run` 应明确列出：

```text
archive: CLAUDE.md -> .bridgeforge/archive/claude/<timestamp>/CLAUDE.md
archive: .claude/ -> .bridgeforge/archive/claude/<timestamp>/.claude/
delete: CLAUDE.md
delete: .claude/
merge memory: .claude/memory/ -> .codex/memory/
```

这样用户能在执行前确认不会误删 memory。

## 验收条件

在任意项目中执行 `bridgeforge switch codex` 后：

```text
[pass] AGENTS.md exists
[pass] .codex/ exists
[pass] CLAUDE.md does not exist
[pass] .claude/ does not exist
[pass] .bridgeforge/archive/claude/<timestamp>/ contains old Claude skeleton
[pass] old memory is merged or explicitly handled
[pass] git status shows only expected archive/delete/create changes
```

## 优先级

P1。

理由：这是骨架切换语义错误。它不会立刻破坏业务代码，但会污染后续 agent 判断、memory 归属、规则加载和迁移状态。长期看会让项目处于“表面 Codex、实际双骨架”的模糊状态。
