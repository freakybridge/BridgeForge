# Codex 空 `.agents/` 未自动清理调查报告（2026-07-06）

## 结论

`.agents/` 没有被删除，不是因为 CausisRiskSuite 漏装了上游清理脚本，也不是因为目录不满足清理条件。

本次查证显示：

- BridgeForge 上游 Codex 模板已注册 `SessionStart` hook：`.codex/hooks/legacy_agents_cleanup.py`
- CausisRiskSuite 当前 `.codex/settings.json` 也已注册同一 hook
- `.agents/` 当时是普通空目录，符合删除条件
- 手动执行同一个脚本后，`.agents/` 被成功删除

因此可以确认的直接事实是：`.agents/` 不是因为清理脚本失效而残留。更具体地说：

1. `legacy_agents_cleanup.py` 能删除普通空 `.agents/`；
2. 当前仓库内没有发现创建项目根 `.agents/` 的代码；
3. 普通 shell 命令不会自动重新创建 `.agents/`；
4. 因此创建源更可能在 Codex 外层运行时 / 启动兼容探测层，但还没有进程级日志能最终确认。

现有证据能排除“脚本自身删不掉”和“仓库脚本主动创建”两种解释；不能直接确认具体是哪一个外层进程创建了 `.agents/`。

## BridgeForge 复核补充（2026-07-06）

BridgeForge 后续最小复现实验进一步确认：项目根空 `.agents/` 的复发源是 Codex 文件编辑工具链，具体可由 `apply_patch` 触发。

复现实验：

```text
基线：Test-Path .agents => False
执行：apply_patch 新增 .runtime/agent_repro_apply_patch.tmp
结果：Test-Path .agents => True
目录时间：CreationTime = 2026/7/6 21:54:12
```

删除临时文件后，`.agents` 仍然存在；再执行现有清理脚本才消失：

```text
python .codex/hooks/legacy_agents_cleanup.py
agents_after_cleanup=False
```

因此，本报告原结论中的“缺少进程级证据、不能确认具体创建点”已经被后续复核推进为：普通 shell / 只读外援 agent 不会创建它，文件编辑工具链会在编辑后留下项目根空 `.agents`。修法应保留 `SessionStart` 清理，并额外在文件编辑后的 `PostToolUse` 复用 `legacy_agents_cleanup.py`。

## 证据

### 1. 上游确实已有自动清理

对 BridgeForge 上游模板检索结果：

```text
D:\Quant\BridgeForge\templates\codex\settings.json:278:    "SessionStart": [
D:\Quant\BridgeForge\templates\codex\settings.json:293:            "command": ".venv/Scripts/python.exe .codex/hooks/legacy_agents_cleanup.py",
D:\Quant\BridgeForge\templates\codex\settings.json:294:            "comment": "清理运行时兼容探测留下的项目根空 .agents/：仅删除普通空目录；非空、symlink、junction 或异常均静默 no-op。"
```

上游 `CHANGELOG.md` 也记录过该能力：

```text
D:\Quant\BridgeForge\CHANGELOG.md:23:- [product][repo] Codex 空 `.agents/` 工作区清洁 hook：新增 `templates/codex/hooks/legacy_agents_cleanup.py` 并同步 dogfood 到 `.codex/hooks/`，SessionStart 时只删除项目根普通空 `.agents/`；非空、symlink、junction 或异常均静默 no-op。
```

### 2. 本项目已复制并注册该 hook

本项目当前注册：

```text
.codex\settings.json:278:    "SessionStart": [
.codex\settings.json:293:            "command": ".venv/Scripts/python.exe .codex/hooks/legacy_agents_cleanup.py",
.codex\settings.json:294:            "comment": "清理运行时兼容探测留下的项目根空 .agents/：仅删除普通空目录；非空、symlink、junction 或异常均静默 no-op。"
```

脚本本体的删除条件：

```text
.codex\hooks\legacy_agents_cleanup.py:27:def _is_plain_empty_dir(path: Path) -> bool:
.codex\hooks\legacy_agents_cleanup.py:28:    if path.is_symlink() or _is_reparse_point(path):
.codex\hooks\legacy_agents_cleanup.py:29:        return False
.codex\hooks\legacy_agents_cleanup.py:30:    if not path.is_dir():
.codex\hooks\legacy_agents_cleanup.py:31:        return False
.codex\hooks\legacy_agents_cleanup.py:32:    try:
.codex\hooks\legacy_agents_cleanup.py:33:        next(path.iterdir())
.codex\hooks\legacy_agents_cleanup.py:34:    except StopIteration:
.codex\hooks\legacy_agents_cleanup.py:35:        return True
```

实际删除动作：

```text
.codex\hooks\legacy_agents_cleanup.py:41:def main() -> int:
.codex\hooks\legacy_agents_cleanup.py:42:    try:
.codex\hooks\legacy_agents_cleanup.py:43:        if _is_plain_empty_dir(LEGACY_AGENTS_DIR):
.codex\hooks\legacy_agents_cleanup.py:44:            LEGACY_AGENTS_DIR.rmdir()
```

### 3. `.agents/` 当时符合删除条件

检查结果：

```text
exists=True
mode=d-----
linkType=
attributes=Directory
fullName=D:\Quant\CausisRiskSuite\.agents
entry_count=0
```

这说明它是普通空目录，不是 symlink / junction，也没有内容。

### 4. 手动执行同一脚本可以删除

手动运行：

```text
cleanup_exit=0
agents_exists_after=False
```

这条是关键证据：清理脚本本身有效，路径推导也正确。

复查过程中一度再次看到 `.agents/` 出现：

```text
agents_exists=True
```

随后第二次手动运行同一脚本：

```text
cleanup2_exit=0
agents_exists_after_cleanup2=False
```

这说明即使脚本能删，仍有外部路径可能再次产生空 `.agents/`。但后续更小复现实验显示：清理后新开一个普通 shell 检查并不会重新创建它：

```text
new_shell_start=False
```

本轮新一轮对话开始时也没有看到 `.agents/`：

```text
agents_exists_at_turn_start=False
```

所以不能把原因简化成“每次 shell / 每次工具都会创建”；更准确的表述是：创建源不在仓库内，疑似 Codex 外层运行时某个特定启动 / 兼容探测路径，但目前缺少进程级证据。

## 原因判断

BridgeForge 的设计是假设 `SessionStart` 能覆盖“启动期产生的空 `.agents/`”。如果 `.agents/` 的来源位于 Codex 外层运行时兼容探测，那么只把清理挂在 `SessionStart`，会存在一个时序假设：

> 清理脚本必须在 `.agents/` 被创建之后运行。

这次现象提示该假设可能不稳定，但还不能直接证明具体创建点。白话类比：门口有人会先扫地，但我们只知道门口曾经又出现过空纸箱；还没装摄像头，所以不能断定是哪位快递员、哪个时间点放的。

## 影响

- `.agents/` 是空目录，不影响程序运行。
- 但它会污染工作区观感，容易让人误以为项目仍在使用旧 agent 目录。
- 如果后续 `git status --untracked-files=all` 暴露它，会增加提交前判断噪声。

## 建议

上游可以把清理从“只在 `SessionStart` 跑一次”改成更稳的两层或三层，但建议先加日志确认具体创建时序：

1. 保留当前 `SessionStart` 清理。
2. 给 `legacy_agents_cleanup.py` 增加一条极轻量诊断日志，写入 `.runtime/legacy_agents_cleanup.log`：记录时间、`.agents` 是否存在、是否删除。
3. 如果日志证明 `.agents/` 在 `SessionStart` 之后复现，再额外挂到 `Stop`，在每轮结束前再清一次。

本轮已多次手动执行清理脚本，均能删除 `.agents/`；但“谁创建它”目前只能定位到仓库外，不能确认到具体进程。
