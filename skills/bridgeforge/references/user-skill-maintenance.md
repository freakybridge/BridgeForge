# 用户级 skill 分发收据与当前项目遗留布局

根入口完成平台检查、无参数共享更新和模式判定后，init / update / adopt 模式读取本文件。本文件不再自行复制用户级 skill；用户级分发的唯一写入口是 command bundle 内的 `scripts/bridgeforge_shared_update.ps1`。

## 1. 用户级分发边界

- Codex 受管 skill 位于 `~/.codex/skills/`，托管账本是 `~/.codex/bridgeforge-managed.json`。
- Claude 受管 skill 位于 `~/.claude/skills/`，托管账本是 `~/.claude/bridgeforge-managed.json`。
- `BRIDGEFORGE_HOME` 是当前 agent 已安装的 `bridgeforge` command bundle：Codex 为 `~/.codex/skills/bridgeforge/`，Claude 为 `~/.claude/skills/bridgeforge/`。
- 共享更新只允许修改 manifest 管理且已登记的 BridgeForge skill。未登记的同名目录必须阻断；其他来源的 skill 必须保持不变。
- 受管 skill 的本地改动不保留、不备份、不跳过。通用改动必须进入 GitHub `main`。
- 禁止从 `~/.agents`、`~/.bridgeforge`、本地 clone、当前工作副本或项目目录读取共享 skill 内容。
- 同一用户同一时刻只允许一个 updater 实例；并发调用必须在创建事务日志或写入受管目录前失败。
- 同一 commit 且实际目录与 manifest hash 完全一致时跳过该 skill 的换包；账本一致但目录缺失、增删或 hash 不符时必须重装。
- 每个 skill 必须先在 stage 验证完整目录 hash，再原子换包，并在写账本前重新验证 Codex / Claude 的全部实际目标。
- 中断恢复只能使用与事务开始时目录 hash 一致的 backup；backup 缺失或损坏时必须保留当前目标并停止，禁止用空目录或未验证内容回滚。

## 2. 无参数更新收据

无参数 `/bridgeforge` 已在根入口 Step 1 显式运行 updater。继续维护当前项目前，必须保留并报告：

- updater 退出码、成功输出中的目标完整 commit SHA；
- Codex 与 Claude 托管账本中各 skill 的 `source_commit`、`content_hash` 与 `installed_at`；
- 两个平台托管账本是否全部收敛到同一 commit；
- Codex 与 Claude 实际受管目录是否均与 manifest 的完整文件集合和 hash 一致；
- 未登记同名冲突、恢复日志或可写性错误；
- 非 BridgeForge skill 未被修改。

updater 非 `0` 时立即停止。不得拿旧 command bundle 继续维护项目，也不得回退到任何本地内容源。

## 3. 当前项目 `.agents/` 检查

只检查当前工作目录根部的 `.agents/`。不得枚举父目录、兄弟目录、用户主目录或其他项目。

不存在 `.agents/` 时继续当前唯一模式。存在时必须先运行：

```powershell
python "$BRIDGEFORGE_HOME\scripts\bridgeforge_migrate_layout.py" --project-root "$PWD" --dry-run
```

dry-run 必须把内容分为：

| 分类 | 处理 |
|---|---|
| 空目录 | 可删除候选 |
| 已知公共 skill 副本 | 可删除候选 |
| Codex 项目私有内容 | 迁入当前项目 `.codex/` 的候选 |
| Claude 项目私有内容 | 迁入当前项目 `.claude/` 或 `CLAUDE.md` 的候选 |
| 未知文件、链接、路径逃逸或无法归类内容 | 阻断 |

dry-run 只能展示计划，禁止写入、移动或删除。若脚本非 `0` 或出现阻断项，报告后停止。

## 4. 用户确认后的迁移

把完整 dry-run 清单展示给用户，并明确说明迁移只影响当前项目。只有用户明确确认该清单后才运行：

```powershell
python "$BRIDGEFORGE_HOME\scripts\bridgeforge_migrate_layout.py" --project-root "$PWD" --apply
```

禁止把用户对 `/bridgeforge` 的调用本身视为删除授权。禁止调用 `bridgeforge_switch.py` 代替本迁移。apply 失败时保留脚本诊断并停止；不得手工补删或跨项目重试。

成功后重新检查当前项目：

- `.agents/` 不再存在；
- 项目私有 Codex 资产只在 `.codex/`；
- 项目私有 Claude 资产只在 `.claude/` 与 `CLAUDE.md`；
- 当前项目之外没有文件变化。

## 5. 项目私有 skill 与全局配置

- 项目私有 skill 不属于共享 updater 的管理范围，不得提升到用户级目录。
- 不再执行旧版“项目同名 skill 去重”“扁平 shadow 清理”或 `RETIRED.md` 逐项删除流程；托管范围只以 manifest 与账本为准。
- 用户级 allow、Claude 全局规则和 Python UTF-8 配置不属于共享更新，不得借本步修改。

## 6. 收据与停止条件

结束时报告：

- 用户级 updater 收据；
- 当前项目是否发现 `.agents/`；
- dry-run 分类、阻断项与用户决定；
- 若执行 apply，其退出码、迁移结果和当前项目外零修改断言；
- 是否需要重启 agent 才能重新扫描更新后的 skill。

任何未登记同名冲突、更新失败、未知迁移内容或未取得确认都必须停止；禁止把“单一源”解释成项目级静默覆盖或删除授权。
