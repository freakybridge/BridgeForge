# BUG：finalizer 在受保护宿主目录创建临时文件时近似无限重试

## 状态

- 发现日期：2026-08-15
- 状态：source-fixed-protected-host-smoke-pending
- 影响版本：至少 `0.86.4`
- 影响宿主：已在 Codex / Windows 复现；Claude 是否同样受影响尚未验证
- 发现项目：`D:\Quant\CodexWorktree\1d62\StratusAgent`

## 结论

`bridgeforge_project_finalize.py` 的两道硬检查均已完成，超时发生在写
`.bridgeforge_version` 的 `_atomic_write()` 阶段。该函数把临时文件直接创建在
受保护的 `.codex/` 内；Windows 上 `tempfile.mkstemp()` 遇到权限拒绝、但
`os.access(directory, os.W_OK)` 仍返回 `True` 时，会继续尝试新的随机文件名。
Python 3.12 的 `TMP_MAX` 为 `2147483647`，实际表现为进程长期不返回。

这是高置信根因。历史超时瞬间没有保留 Python 调用栈或文件系统拒绝事件，因此不声称
已取得 100% 的事后栈证明。

## 用户可见现象

StratusAgent 从 BridgeForge `0.86.2` 更新至 `0.86.4` 时：

1. finalizer 输出完整的 memory lint `[ok]` 结果；
2. 之后长期没有输出 `FINALIZED`，也不主动报错；
3. 外层分别等待 120 秒和 300 秒后超时终止；
4. `.codex/.bridgeforge_version` 保持 `0.86.2`；
5. 后续再次执行 `/bridgeforge` 仍判断项目需要更新，形成重复更新循环。

用户级 shared skills、Codex native memories 和项目 `.gitignore` 更新不受版本戳回滚；
被阻断的是“最终验收并写入新骨架版本”的步骤。

## 2026-08-15 系统重构复核

- Codex 项目更新不再调用独立 finalizer；统一事务的临时文件固定在项目根 staging，再原子替换目标。
- 任一捕获失败恢复已写资产，版本戳最后写；fixture 覆盖 apply、validate、stamp 前后故障注入。
- 真实受保护 StratusAgent worktree 的 ACL 现场仍需本轮样本收据；Claude 兼容 finalizer 不在本次重构范围。

## 排除项

使用 finalizer 自身的 `_run_check()` 控制流分别计时：

| 阶段 | 结果 | 耗时 |
|---|---|---:|
| canonical memory schema audit | exit 0 | 0.127 秒 |
| project config health check | exit 0 | 0.187 秒 |

Memory stdout 约 24,714 bytes。由于 `_run_check()` 使用 `capture_output=True`，只有子进程
结束并返回后才会打印捕获内容；因此看到完整 `[ok]` 输出，本身就证明第一道检查已经
退出。两道检查合计约 0.314 秒，不是 120–300 秒超时的来源。

## 根因链路

### 1. finalizer 的内部超时没有覆盖写戳

`scripts/bridgeforge_project_finalize.py::_run_check()` 的 `timeout=60` 只包围两个
`subprocess.run()`。随后调用的 `_atomic_write()` 没有任何超时保护。

### 2. 临时文件选错目录

当前实现：

```python
fd, raw = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
```

版本戳路径是 `<project>/.codex/.bridgeforge_version`，因此 staging 目录也是
`<project>/.codex/`。Codex 沙箱允许读取该目录，但会阻止创建任意随机临时文件。

### 3. Windows `tempfile` 权限判断与实际沙箱权限不一致

Python 3.12 `tempfile._mkstemp_inner()` 遇到 `PermissionError` 时，如果目录存在且
`os.access(directory, os.W_OK)` 为 `True`，会 `continue` 尝试下一个随机名称。
当前环境中 `os.access(.codex, os.W_OK)` 返回 `True`，但实际创建仍被宿主保护策略拒绝，
于是循环上限变成 `TMP_MAX=2147483647`。

### 4. 已有同型修复没有复用

`templates/codex/scripts/hooks_merge.py::_atomic_write()` 已说明并处理同一限制：当目标位于
`.codex/` 时，把临时文件放在项目根目录，再用 `os.replace()` 原子替换目标。finalizer
新增为唯一写版本戳入口时，没有复用这一 staging 规则。

## 现有测试为何漏过

`tests/harness/test_bridgeforge_project_finalize.py` 使用
`tempfile.TemporaryDirectory()` 创建普通可写的 `.codex/` / `.claude/` fixture。
测试覆盖了：

- 两道 gate 通过后写戳；
- memory gate 失败保留旧戳；
- config health 失败保留旧戳；
- 缺少 `--confirmed` 时保留旧戳。

但它没有覆盖“目录在 OS ACL 看似可写、实际创建被宿主策略拒绝”的情况，因此普通
Windows 测试和 CI 都不会触发该循环。

## 实施修复

finalizer 的 staging 目录已固定为项目根目录，而不是宿主配置目录：

```python
_atomic_write(stamp, version + "\n", staging_dir=project_root)
```

`project_root` 已经完成目录校验，且临时文件与目标仍在同一文件系统，`os.replace()` 的
原子替换保证不变。显式传入 staging 目录也避免依赖 `path.parent.parent` 推断路径层级。

不要只在 `mkstemp()` 外增加 `except PermissionError`：当前问题发生在标准库内部的重试
循环，调用不会及时返回，外层异常处理捕获不到。

未抽取跨分发层公共 helper：finalizer 与模板 merge 脚本位于不同 bundle 层，共享模块会
增加导入和打包依赖。两处保持相同的“宿主目录外、项目根 staging”约束。

## 回归验收

1. [x] 为 Codex 和 Claude 各建一个版本戳路径，mock `tempfile.mkstemp()` 并断言
   `dir == project_root`，禁止等于 `.codex` 或 `.claude`。
2. [x] 让 mock 在收到受保护目录时抛出 `PermissionError`，确认修复后的代码不会访问该路径。
3. [x] 保留现有四类 gate / 旧版本戳测试，确认写戳仍是 finalizer 的唯一职责。
4. [ ] 在真实 Codex 沙箱内运行一次完整 finalizer，要求 5 秒内返回 exit 0、打印
   `FINALIZED`，并把版本戳更新到目标版本。
5. [x] 运行双宿主 harness，确认项目根临时文件在成功和失败路径都被清理。

## 实施收据

- `.venv\Scripts\python.exe -m unittest tests.harness.test_bridgeforge_project_finalize -v`
  → 6 项通过；覆盖 Codex / Claude 项目根 staging、受保护目录拒绝、替换失败清理和原有
  gate / 旧版本戳路径。
- `.venv\Scripts\python.exe -m unittest tests.harness.test_bridgeforge_root_skill -v`
  → 6 项通过；确认 finalizer 仍是 update 唯一写戳入口。
- `test_repository_manifest_matches_complete_product_inventory` → 1 项通过；
  `rebuild_shared_skill_manifest.py --check` 返回 `already current`。
- 两个改动 Python 文件只读编译通过，`git diff --check` 退出 0。
- 真实 StratusAgent 受保护宿主目录的完整 `/bridgeforge` 更新尚未执行，运行时验收保持未验证。

## 相关文件

- `scripts/bridgeforge_project_finalize.py`
- `templates/codex/scripts/hooks_merge.py`
- `tests/harness/test_bridgeforge_project_finalize.py`
- `doc/2_bugs/BUG-update-stamped-before-memory-migration.md`

## 证据缺口与次要假设

- 缺少历史超时瞬间的 Python 调用栈和文件系统拒绝事件。
- stdout 管道反压理论上也能造成挂起，但相同 captured-output 控制流已在约 0.314 秒内
  完成两道检查，证据明显更弱。
- 历史文件锁或安全软件过滤 `os.replace()` 的概率更低；普通共享冲突通常立即抛错，
  不会稳定等待 120–300 秒。
