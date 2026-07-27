# 提案：将 memory junction 维护收敛为用户级双宿主 hook

## 结论

将 memory junction 的运行 hook 从下游项目模板中移除，收敛为 BridgeForge 安装并维护的用户级 hook：

- Codex：`~/.codex/hooks.json` + 用户级通用脚本；
- Claude Code：`~/.claude/settings.json` + 用户级通用脚本。

下游项目继续把 `.codex/memory/` 和 `.claude/memory/` 作为 Git 内唯一事实源，但不再携带同类 SessionStart hook 或其脚本副本。

## 背景与问题

当前双骨架都在项目内携带 `memory_junction_check.py`。Claude 的定义位于 `.claude/settings.json`，可被 Claude Code 发现；Codex 的定义位于 `.codex/settings.json`，而 Codex 仅发现 `<repo>/.codex/hooks.json` 或 `<repo>/.codex/config.toml` 的 hooks 配置，因此该定义不会执行。

继续修复为项目级 Codex hook 虽可解决当前缺陷，但会让同一通用逻辑随每个下游项目复制、更新和审计。该逻辑只依赖当前会话的工作目录与项目内 memory 目录，适合收敛为用户级公共能力。

## 目标设计

```text
BridgeForge 用户级安装物
  ├─ ~/.codex/hooks.json
  │    └─ SessionStart → bridgeforge_memory_junction.py --host codex
  └─ ~/.claude/settings.json
       └─ SessionStart → bridgeforge_memory_junction.py --host claude

任一宿主启动
  └─ 从会话 cwd 定位 Git 根目录
       └─ 确认是 BridgeForge 管理项目
            └─ 建立或核验系统 memory → <repo>/.codex|.claude/memory junction
```

脚本按 `--host` 区分系统目录：Codex 使用 `~/.codex/projects/<hash>/memory`，Claude Code 使用 `~/.claude/projects/<hash>/memory`。业务逻辑、迁移保护与 hash 规则共享一份实现。

## 强制安全约束

1. 非 BridgeForge 项目必须 no-op：不得创建目录、junction、备份或修改任何文件。
2. 仅在项目内目标 memory 目录存在且系统侧项目目录已存在时执行；不猜测或批量扫描用户项目目录。
3. 首次迁移保留现有 `memory.premigrate.bak` 策略，禁止硬删除。
4. 系统与项目两侧同时有内容时停止自动合并并输出明确诊断。
5. 切换前必须移除下游同类 hook；Codex 会叠加运行用户级与项目级匹配 hook，双跑会造成重复检查与不可预测的迁移顺序。

## 上游改动范围

1. 将当前双份项目脚本收敛为用户级共享脚本，并让 BridgeForge 用户级 updater 管理其安装和更新。
2. 添加 `~/.codex/hooks.json` 的受管定义；不得再将 Codex hook 写入 `.codex/settings.json`。
3. 保留 Claude 的用户级 `SessionStart` 定义，但改为调用共享脚本的 Claude 分支。
4. 从 `templates/codex/` 与 `templates/claude/` 移除 `memory_junction_check.py` 及对应项目级 SessionStart 定义；下游仍保留 memory 目录、规则和索引工具。
5. 更新 BridgeForge 的安装、更新、迁移与换机文档；添加版本迁移说明和 CHANGELOG `[product]` 条目。

## 验收

1. 新安装 BridgeForge 后，Codex 与 Claude Code 的用户级 hook 均可被各自宿主发现并通过信任流程。
2. 在一个 BridgeForge 下游项目启动会话，两个宿主各自建立正确的 junction；重复启动为 no-op。
3. 在一个普通非 BridgeForge Git 仓库启动会话，脚本不创建或修改任何路径。
4. 系统 memory 与项目 memory 同时有内容时，不自动合并且不丢失数据。
5. 已有下游项目升级时，先展示删除项目级 hook 的迁移计划；用户确认后应用；迁移后不再出现双跑。

## 代价与决策

该设计使下游项目不再具备“仅 clone 即自行恢复 junction”的完全独立性：新机器需先安装 BridgeForge 用户级组件。这个依赖是可接受的，因为 junction 是宿主本地状态，而 BridgeForge 本身已是该项目协作骨架的前置工具；作为交换，获得单一实现、统一升级、跨下游一致性与更低的维护成本。

