# 建议报告：封堵 memory writer 的 Windows stdin 编码旁路

状态：待裁定  
日期：2026-08-04  
关联主题：`non-ascii-shell-guard`、`memory-lifecycle-governance`

## 结论

现有非 ASCII shell 防护不能作为 memory 写入的唯一保障。`project_memory_writer.py`
仍接受 `--content-file -`，使 Windows PowerShell 的 native stdin 编码成为未受 writer
约束的输入边界。应在 writer 模板直接禁用 stdin 正文输入，并在共享 skill 与 workflow
规则中指定“无 BOM UTF-8 内容文件”作为唯一传递方式。

## 真实复现

在一个 Windows 下游项目中，PowerShell 的 `$OutputEncoding` 实测为 `us-ascii`。将中文
here-string 通过管道交给 Python 时，Python 从 `stdin.buffer` 读到的字节为
`3f3f0d0a`，即两个 ASCII `?` 和换行，而不是中文的 UTF-8 字节。

当前 writer 随后会把这些已经污染的 `?` 作为合法文本写入 UTF-8 文件、计算 SHA-256 并
重建索引。因此写入收据、严格 UTF-8 解码和索引检查均可通过，却无法证明正文语义未被
上游管道破坏。原文不可由 `?` 恢复。

同一次命令静态上同时命中“非 ASCII + here-string/管道 + Python stdin”，但没有被外层
PreToolUse hook 阻断。当前未取得该会话的 hook trust / 实际投递收据，因此不能把原因
断言为 matcher 或 dispatcher 缺陷；但这已证明 writer 不能依赖外层 hook 提供完整保护。

## 现有边界

- `templates/{codex,claude}/hooks/non_ascii_shell_guard.py` 已尝试阻断非 ASCII 文本经
  shell 中转进入动态执行。
- `templates/{codex,claude}/scripts/project_memory_writer.py` 仍在
  `_read_content_file()` 中将 `-` 映射为 `sys.stdin.read()`。
- `skills/summary/SKILL.md` 要求使用 writer，但未规定 Windows 下不得以 PowerShell
  管道向 writer 传递正文。

## 建议变更

### P0：writer 模板 fail-closed

同时修改 Claude 与 Codex 的 `project_memory_writer.py`：

1. `--content-file -` 直接报错，提示“Windows / 跨 shell 写入必须提供 UTF-8 内容文件”。
2. 只接受显式内容文件；严格按 UTF-8 读取，并拒绝 UTF-8 BOM。
3. 保持现有原子写、回滚、SHA-256 与索引重建机制不变。

writer 无法可靠判断一个合法的 `?` 是否原本是中文，因此必须从输入通道消除该歧义，不能
新增“检测问号后猜测”的伪保护。

### P1：调用与规则双层约束

1. 在 `skills/summary/SKILL.md` 明确：向 project memory writer 传最终正文时，必须先由
   非 shell 中转的安全写入工具形成无 BOM UTF-8 内容文件，再传该文件路径；禁止 stdin、
   here-string、管道和命令行内嵌非 ASCII 正文。
2. 在 `templates/{codex,claude}/rules/workflow.md` 的 `doc/**` 与 memory 适用范围加入
   同一条窄红线，覆盖非 memory 的文档生成脚本。
3. 保留现有 `non_ascii_shell_guard` 作为前置补防，不以它替代 writer 的输入边界。

### P1：运行时投递验收

补一个真实 Codex Desktop / Windows PowerShell smoke：危险组合必须在执行前被拒绝，且
记录 hook 已信任、实际 matcher 名称、dispatcher 收到的 command 和拒绝结果。现有静态
harness 通过不能替代该运行时收据。

## 验收建议

- 两宿主 writer 对 `--content-file -` 均 fail-closed，且不创建 / 修改 memory 或索引。
- 含中文、emoji 与特殊标点的 UTF-8 内容文件，写入后目标文件字节与输入文件完全一致；
  索引摘要也保留相同文本。
- BOM 输入被拒绝；无效 UTF-8 输入被拒绝；失败后目标和索引保持原状。
- `$summary` 与 workflow 模板均不再给出或允许 PowerShell stdin 正文示例。
- Codex / Claude 模板、dogfood 副本和下游 fixture 语义一致。
- 实际 Windows hook smoke 能拦截“非 ASCII here-string | python -”和同等 writer 调用；
  `apply_patch` 与复制已存在 UTF-8 文件仍可放行。

## 非目标

- 不通过扫描或模型猜测还原既有乱码。
- 不泛禁 shell、Python 或普通 ASCII stdin。
- 不改变 writer 的 topic、索引、路径校验和回滚职责。

