# Switch 模式操作手册

仅当根 `SKILL.md` 判定为显式或经用户确认的隐式 `switch` 时读取本文件。目标是切换当前项目使用的 agent 骨架，不是修改 BridgeForge 源头仓库。

## 1. 命令与前置判定

支持：

```bash
/bridgeforge switch claude
/bridgeforge switch codex
/bridgeforge switch codex --dry-run
/bridgeforge switch codex --interactive
```

只支持 `claude` / `codex`，不接受 `gpt` / `openai` / `claude-code` 等别名。

先同时检查目标 agent 与旧 agent 的 live 路径。目标 agent “完整”至少要求入口文件、配置目录和 `settings.json` 同时存在：

- 目标完整、旧 agent live 路径不存在：不要调用切换脚本，回根入口按普通维护流程判定 init / update / adopt。
- 目标完整、旧 agent live 路径仍存在：调用脚本，执行 cleanup-only switch；目标来源是 `live`，不覆盖目标，只归档/删除旧 agent 并处理 memory/settings。
- 目标不完整或不存在：直接调用项目内切换脚本，不进入 init / update / adopt。
- 目标 live path 只存在一部分，或会覆盖目标且不属于 cleanup-only：停止，不覆盖、不继续归档。

## 2. 执行

```bash
python scripts/bridgeforge_switch.py <claude|codex> [--dry-run|--interactive] [--skip-settings-migration] [--migrate-setting KEY] [--memory-conflict REL=ACTION]
```

若项目内没有 `scripts/bridgeforge_switch.py`，执行：

```bash
python "$BRIDGEFORGE_HOME/templates/$TEMPLATE_AGENT/scripts/bridgeforge_switch.py" <claude|codex> --template-root "$BRIDGEFORGE_HOME" [其余参数]
```

cwd 若是 BridgeForge 源头仓库，脚本必须拒绝；源头改框架应直接编辑 `templates/`。

## 3. 不可改变的切换契约

- `--dry-run` 只报告完整计划，不改文件；清单必须覆盖归档、删除、目标来源、memory 合并、settings 候选、只归档不迁移项和目标冲突。
- 旧 agent 归档范围固定：Claude 为 `CLAUDE.md + .claude/`；Codex 为 `AGENTS.md + .codex/ + .agents/skills/`。
- 归档路径固定为 `.bridgeforge/archive/<agent>/<timestamp>/`。每个 agent 只保留最新一份；新归档成功后才删除该 agent 旧归档。
- 归档成功后删除旧 agent 原路径；`.agents/` 变空才删除，否则保留。
- 当前项目没有旧 agent 骨架也允许 switch，此时语义是启用目标 agent。
- 目标来源优先使用当前项目自己的最新归档；没有目标归档才从 `$BRIDGEFORGE_HOME/templates/<agent>/` 安装。禁止读取全局缓存或其他项目归档。
- memory 合并到目标 agent 活跃 memory：完全重复自动去重；相似但不相同、同路径不同内容必须逐条确认。非交互模式用 `--memory-conflict REL=keep-target|copy-old|append-old` 回放选择。
- settings 默认不迁移；先列候选 key，再逐项确认。非交互模式用 `--skip-settings-migration` 明确全部不迁移，或用 `--migrate-setting KEY` 指定迁移项。
- hooks / skills / rules / 入口文件只归档并报告，绝不自动迁移。
- 真实切换只改工作区文件，不运行 `git add` / `git commit` / `git push`。
- 缺少必须的 memory/settings 决策时，脚本应以 exit 2 停止，并保证尚未改文件。

## 4. 验证收据

执行后必须报告：

1. 目标入口文件、配置目录和 `settings.json` 是否存在。
2. 旧 agent live 路径是否全部消失。
3. 本次目标来源是 `live`、`archive` 还是 `template`。
4. 旧 agent 归档的实际路径。
5. memory 的去重、自动复制和逐项决策结果。
6. settings 的迁移/不迁移结果。
7. 脚本退出码；exit 0 才可称“Validation passed”。

白话：旧工具箱先封箱进当前项目自己的归档柜；新工具箱优先从同一项目的柜子里拿，拿不到才领上游新套装。笔记要合并，电线、专用工具和规章只存档，不硬接。
