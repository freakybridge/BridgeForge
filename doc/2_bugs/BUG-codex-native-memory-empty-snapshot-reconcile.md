# BUG：Codex 原生 memories 合法空快照无法完成 reconcile

**状态**：source-and-fixture-fixed-installed-hook-smoke-pending
**发现日期**：2026-08-15  
**影响版本**：BridgeForge `0.86.2`  
**影响范围**：启用 Codex 原生 memories GitHub 同步，且处于空快照或 Git 换行转换环境的用户

## 结论

远端存在合法的空快照时，`codex_memory_sync.py reconcile` 会把正常的“零文件”状态
误判为同步失败，持续保留 `pending=true`。现场未发生数据丢失，项目级
`.codex/memory/` 不受影响；缺陷仅影响用户级 `~/.codex/memories/` 同步状态收敛。

## 2026-08-15 系统重构复核

- 合法空 manifest、autocrlf 与 reconcile 的源码/fixture 修复保持有效。
- 用户级 native memories 仍是独立外部授权事务，不并入项目骨架 sync。
- 安装后的 Stop/SessionStart hook 现场 smoke 尚未复验，禁止把 fixture 通过写成 hook runtime 已验收。

## 现场证据

项目执行无参数 `/bridgeforge` 后，setup 成功：

```text
[memory-sync] configured; hook_installed=true; remote_configured=true;
remote_action=reused
```

随后运行：

```powershell
.venv\Scripts\python.exe -B `
  C:\Users\<user>\.codex\skills\bridgeforge\scripts\codex_memory_sync.py `
  reconcile --trigger bridgeforge
```

输出：

```text
[memory-sync] WARNING: git --work-tree=<temp>\remote-snapshot checkout -f
refs/remotes/origin/main -- memories snapshot-manifest.json failed:
error: pathspec 'memories' did not match any file(s) known to git
```

命令按当前容错设计返回 exit `0`，但后续 `status` 为：

```json
{
  "enabled": true,
  "hookInstalled": true,
  "pending": true,
  "remoteConfigured": true
}
```

远端 `main` 只包含 `snapshot-manifest.json`。该 manifest 是合法空快照：

```json
{
  "content_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
  "files": [],
  "revision": 2,
  "schema_version": 1,
  "updated_at_utc": "1970-01-01T00:00:00+00:00"
}
```

本地 `~/.codex/memories/` 同样没有文件。因此预期结果应为 `noop`，并清除 pending。

## 根因

### 1. 读取远端快照时无条件 checkout `memories/`

`scripts/codex_memory_sync.py::_read_remote_snapshot()` 解析 manifest 后，无论
`manifest["files"]` 是否为空，都会执行：

```python
_git([
    f"--work-tree={extracted}",
    "checkout",
    "-f",
    "refs/remotes/origin/main",
    "--",
    "memories",
    "snapshot-manifest.json",
], bare)
```

Git 不保存空目录。合法空快照只有 manifest，没有 `memories/` tree entry，因此该命令
必然报 `pathspec 'memories' did not match`。

### 2. 恢复逻辑同样假设 `memories/` 必然存在

即使读取阶段跳过上述 checkout，`_reconcile_in_work()` 在本地 memories 不存在时仍会
进入 `_restore_snapshot()`；后者直接读取 `extracted / "memories"`。合法空快照应当是
`noop`，不应创建空的用户级 memories 目录，也不应进入 restore。

### 3. 回归测试没有覆盖真实空远端

现有
`test_reconcile_does_not_create_native_memories_without_local_or_remote_content()` 将
`_read_remote_snapshot()` mock 为 `(None, None, None)`，只覆盖“远端分支或 manifest
完全不存在”，没有构造“远端 main 存在，manifest 合法且 `files=[]`”的真实 Git 快照。

## 实现结果

1. `_read_remote_snapshot()` 先验证 manifest 结构；当 `files=[]` 时只 checkout
   `snapshot-manifest.json`，在临时快照内创建空 `memories/` 供 digest 校验，不再要求远端
   存在 Git 无法记录的空目录。
2. `_reconcile_in_work()` 遇到“本地 memories 不存在 + 远端合法空快照”时：
   - 返回 `noop`；
   - 清除未变化的 pending；
   - 更新必要的 `last-synced.json` 收据；
   - 不创建 `~/.codex/memories/` 空目录。
3. 临时读取和发布仓库均通过 Git info attributes 与 `core.autocrlf=false` 禁止换行转换，
   保证 LF/CRLF 混合 memory 按 opaque bytes 入库和读回。
4. 非空 manifest 仍完整 checkout、校验 schema、文件 hash 与总 digest；空 manifest
   声明与实际 `memories/` tree 冲突时仍按损坏快照 fail closed。

## 验收标准

- 真实 bare Git remote 仅含合法空 `snapshot-manifest.json`，本地 memories 不存在：
  reconcile 返回 `noop`、pending 清除、本地目录不创建。
- 本地 memories 是空目录、远端为空快照：返回 `noop`、pending 清除。
- 本地有文件、远端为空快照：按现有冲突裁决选择 `push`，不得静默丢弃本地文件。
- `files=[]` 但 digest/schema 非法：保持损坏快照处理，不得认作合法空快照。
- `--trigger bridgeforge` 不输出 WARNING；Stop/SessionStart 的 hook stdout 契约不回归。
- 新测试必须使用真实 Git remote 覆盖空 tree，不得只 mock `_read_remote_snapshot()`。

## 验收收据

- `.venv\Scripts\python.exe -m unittest tests.harness.test_memory_native_sync tests.harness.test_shared_skill_distribution`：50 项通过、0 失败。
- 真实 GitHub remote 读回验证：本地与远端均为 6 个文件，文件 digest、总 digest、收据 commit 全部一致，`pending=false`。
- `rebuild_shared_skill_manifest.py --check` 报告 manifest current；`git diff --check` 退出 0。
- 用户已明确执行 `$summary 同意验收`；源码交付验收通过。用户级 Hook 仍为 `0.86.2`，安装 `0.86.3` 后的 Stop/SessionStart 运行时 smoke 不属于本次源码验收收据。

## 建议测试位置

`tests/harness/test_memory_native_sync.py`
