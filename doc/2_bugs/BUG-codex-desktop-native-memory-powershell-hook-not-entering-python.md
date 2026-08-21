# BUG：Windows Codex App 的 Native Memory PowerShell hook 未进入 Python

**状态**：resolved-and-runtime-verified  
**发现日期**：2026-08-21  
**影响版本**：BridgeForge `1.4.35` 及更早使用内联 PowerShell 用户 hook 的版本  
**影响范围**：Windows Codex App 中已授权的用户级 Native Memory 自动同步

## 结论

Codex App 能派发 `SessionStart`、`UserPromptSubmit` 和 `Stop` command hook，但
BridgeForge 原 Native Memory `commandWindows` 使用的内联 PowerShell 命令未进入
`codex_memory_sync.py`。结果是 Hooks 页面显示已安装且已信任，GitHub 自动同步仍不运行，
`last-synced.json` 长期不更新。

当前证据只把故障定位到“App 派发完成后、Python 入口之前”的 Windows 命令层；Codex App
内部具体解析缺陷未验证。产品修复不继续依赖该内联命令，改用独立 `cmd.exe` wrapper。

## 现场证据

在同一用户级 `hooks.json` 中临时追加不联网 canary，并在 Codex App 逐项信任：

```text
event=UserPromptSubmit time=2026-08-21 17:27:31
event=Stop             time=2026-08-21 17:27:57
event=SessionStart     time=2026-08-21 17:28:10
event=UserPromptSubmit time=2026-08-21 17:28:11
event=Stop             time=2026-08-21 17:28:14
event=UserPromptSubmit time=2026-08-21 17:28:19
```

同一批生命周期事件发生后，原同步收据仍为：

```json
{
  "commit": "110276887fcabd124040d33063d796698db9b83d",
  "revision": 11,
  "utc": "2026-08-18T15:12:17.062343+00:00"
}
```

`pending.json` 不存在。若原 `reconcile` 已进入，无论最终是 `noop`、`push` 还是 `restore`，
`last-synced.json` 都会更新；运行期失败则会写 pending。因此现场证明原 Python 入口未运行。

canary 卸载后，用户 `hooks.json` 精确恢复到安装前 SHA-256
`F27F9E7EE7B6FD32F5D51A87B2FB5CEE5232F4220099FF7DCAA850C760B869F1`；未运行手动
reconcile，未访问或修改 GitHub。

## 修复设计

1. 新增 `scripts/codex_memory_sync_hook.cmd`，在 wrapper 内解析当前 Git 根，调用当前项目
   `.venv\Scripts\python.exe`，禁止持久化项目 Python 绝对路径。
2. `commandWindows` 只调用该 wrapper，不再承载内联 PowerShell 程序。
3. wrapper 向 `hook-dispatch.log` 写入进入点与 Python exit code；Python 的 `hook-run` 为每个
   事件原子写入 started/succeeded/failed 收据；`last-synced.json` 继续作为 reconcile 结果收据。
4. `status` 分开输出 `hookInstalled`、`hookRuntimeVerified` 和最近运行收据。只有当前
   handler revision 成功运行过，才允许宣称 runtime 已验证。
5. `SessionStart` 与 `Stop` 同步执行 reconcile；`SessionEnd` 继续只 kick 后台 reconcile，
   保持原超时与非阻塞语义。
6. 升级只替换内容完全匹配的官方旧版 handler；第三方 handler 原样保留，任何人工改动仍按
   ownership drift 零写入拒绝。

## 验收标准

- Windows wrapper 在真实 Git 根中调用项目 `.venv`，禁用 memories 时不访问网络并写出三层收据。
- `SessionStart` 成功 reconcile 后，当前 revision 的运行收据为 `succeeded`，status 返回
  `hookRuntimeVerified=true`。
- reconcile 失败时运行收据为 `failed`、pending 存在，status 禁止报告 runtime 健康。
- 用户 hooks 合并保持幂等并保留第三方 handler；新命令不含内联 PowerShell。
- 真实 Codex App 安装修复版后，新建任务自动推进运行收据；修改 memory 后 GitHub commit
  自动推进；无修改任务返回 `noop` 但运行收据仍更新。

## 六类关闭证据

| 类别 | 当前状态 |
|---|---|
| 源码 | wrapper、`hook-run`、runtime status 与精确旧版迁移已实现；60 项定向测试通过 |
| 产品传播 | BridgeForge `1.4.37`、源码 commit `9012df5`、CHANGELOG、Skill 与 manifest 已发布 |
| dogfood | 正式用户 hook 已安装并重新信任；wrapper 与 Python exit 0 收据已生成 |
| fixture | Windows 真实 `cmd.exe` wrapper 已调用项目 `.venv` 并写出 Python 成功收据 |
| 真实下游 | Codex App 的 `SessionStart` / `Stop` 已自动进入正式 wrapper；未使用手动 reconcile |
| runtime | `hookRuntimeVerified=true`，pending 不存在，revision `11 -> 12`，本地与 GitHub `main` 均为 `5d568f3b5e93859b5b6040f5be38c77688781644` |

用户已执行 `$summary 同意验收`。六类证据齐全，本 Bug 关闭。

本地验证收据：

```text
.venv\Scripts\python.exe -B -m unittest scripts.tests.test_memory_native_sync scripts.tests.test_bridgeforge_codex_root_skill
Ran 60 tests in 15.837s — OK

.venv\Scripts\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py"
Ran 266 tests in 136.135s — OK

.venv\Scripts\python.exe -B scripts\tests\run_downstream_fixture.py
status=passed；3/3 checks passed

.venv\Scripts\python.exe -B scripts\rebuild_shared_skill_manifest.py --check
[manifest] unchanged

.venv\Scripts\python.exe -B templates\hooks\project_structure_check.py --pre-commit
exit 0（仅既有归档 advisory）

git diff --check
exit 0
```
