# 非 ASCII 文本经 shell 中转的乱码风险与 hook 防护提案

状态：pending  
日期：2026-07-10  
来源：ClaudeBridgeAssist / StratusAgent 手动账户验收过程中的真实踩坑

## 结论

BridgeForge 应在 Claude 与 Codex 两套骨架中默认加入 hook 防护：当命令同时满足“包含非 ASCII 文本”和“通过 shell 管道、重定向、here-string、解释器 stdin 等方式中转并可能写文件或执行脚本”时，PreToolUse 阶段应阻断或强提醒，要求改用更安全的 UTF-8 文件写入路径。

这个问题不只影响中文。CJK、重音拉丁字符、俄文、阿拉伯文、日文、韩文、emoji、特殊标点等所有非 ASCII 文本，都可能在 shell 编码、终端编码、解释器 stdin 编码、文件写入编码不一致时被破坏。

## 背景

在下游项目 StratusAgent 的手动账户 UI 验收中，曾通过 PowerShell here-string / 管道把包含中文的脚本或文本传给 Python，再由 Python 写入源码或文档。结果部分中文被写成 `连续问号`，后续需要用 Unicode escape 和手工修复恢复。

这类错误危险在于：

- 破坏发生在工具传输链路中，不一定是业务代码的问题。
- 一旦写入文件，diff 看起来像普通文本变更，容易被误认为是开发者主动修改。
- 对非英语用户高频出现，因为需求、注释、文档、UI 文案天然包含非 ASCII 字符。
- 事后扫描可以发现一部分 `连续问号` 或 `U+FFFD replacement character`，但不能还原原文，最佳策略是写入前阻断。

## 风险模式

高风险组合：

- 命令文本中出现非 ASCII 字符。
- 同时出现 shell 中转符号或结构：`|`、`>`、`>>`、`@' ... '@`、`@" ... "@`、heredoc、命令替换。
- 同时出现可能写文件或执行动态脚本的入口：`python -`、`python -c`、`node -`、`node -e`、`Set-Content`、`Out-File`、`Add-Content`、`tee`、重定向到文件。

典型危险例子：

```powershell
@'
print("中文")
'@ | python -
```

```powershell
"中文说明" | Set-Content README.md
```

```powershell
node -e "fs.writeFileSync('x.md', '中文')"
```

这些写法在某些环境中可以正常工作，但 BridgeForge 骨架的目标是跨机器、跨 shell、跨 agent 稳定，因此不应依赖“当前机器刚好没坏”。

## 目标

1. Claude 骨架默认启用防护。
2. Codex 骨架默认启用防护。
3. hook 在写入前 fail-fast，避免污染源码、文档、规则、memory。
4. 不泛禁 shell，只拦截“非 ASCII + shell 中转 + 写入/动态执行”的危险组合。
5. 提示给 agent 的替代路径必须具体，避免只说“编码有风险”。

## 建议实现

### 1. PreToolUse 阶段阻断

新增一个面向 shell/bash/powershell 工具的 hook，检测命令字符串：

- 若不含非 ASCII：放行。
- 若含非 ASCII，但只是普通只读命令或 UI 输出：放行或弱提示。
- 若含非 ASCII，并命中 shell 中转符号，再命中写入/动态执行入口：阻断。

阻断提示建议包含：

- “检测到非 ASCII 文本经 shell 中转写入/执行，可能造成乱码。”
- “请改用 apply_patch、已存在 UTF-8 文件复制、或脚本内使用 Unicode escape 后以 UTF-8 写入。”
- “如确需执行，需显式说明编码边界和豁免原因。”

### 2. PostToolUse / 交付前扫描补防

PreToolUse 是主防线，但仍建议加轻量补防：

- 扫描本轮新增或修改的文本文件中是否出现可疑 `连续问号`、`U+FFFD replacement character`。
- 对 `.md`、`.py`、`.ts`、`.tsx`、`.js`、`.json`、`.toml`、`.yaml`、`.yml`、`.rs` 等文本文件生效。
- 命中后不自动修复，只提示 agent 停下确认。

补防不能替代 PreToolUse，因为它只能发现一部分乱码，不能恢复原文。

### 3. 两套骨架同步落地

需要同时覆盖：

- `templates/claude/...` 中的 Claude hook 配置与 hook 脚本。
- `templates/codex/...` 中的 Codex hook 配置与 hook 脚本。
- 用户级或项目级 `CLAUDE.md` / `AGENTS.md` 规则文案。
- BridgeForge 自测，确保 switch / install 后两套骨架都带上同一类保护。

建议把检测逻辑做成共享脚本，再由 Claude/Codex 两侧用各自 hook 协议薄封装调用，避免两份规则长期漂移。

## 豁免建议

允许以下情况不阻断：

- `apply_patch` 直接写文件。
- 复制一个已经存在的 UTF-8 文件，不在 shell 命令里内嵌非 ASCII 内容。
- 命令只读输出，不写文件、不执行动态脚本。
- 测试 fixture 明确需要乱码样本，且文件路径或注释中有显式说明。
- 使用 Unicode escape / base64 / 外部 UTF-8 文件作为输入，并明确最终以 UTF-8 写入。

## 测试建议

至少覆盖：

- ASCII 管道到 Python：放行。
- 中文 here-string 到 `python -`：阻断。
- emoji 文本重定向到文件：阻断。
- 中文 `Set-Content` 写文件：阻断。
- 中文只读 `Write-Output`：放行或弱提示。
- `apply_patch` 写中文文档：放行。
- 复制已存在 UTF-8 文件到目标路径：放行。
- Claude 模板安装后 hook 生效。
- Codex 模板安装后 hook 生效。

## 严重性

建议按 P1 处理。

理由：它不会每次必现，但一旦出现会直接污染源码、文档、规则或 memory；并且对非英语用户属于高频工作流风险。BridgeForge 是骨架上游，应在模板层面消除这类系统性踩坑，而不是让每个下游项目重复发现。

## 额外补充

这不是“PowerShell 是否可用”的问题，而是“不要把非 ASCII 正文塞进 shell 命令字符串再让多层工具转手”的问题。PowerShell、cmd、bash、Python stdin、Node `-e`、终端 code page、文件默认编码中任何一环不一致，都可能造成损坏。

推荐默认安全路径：

- 小型源码/文档改动：使用 `apply_patch`。
- 大段非 ASCII 内容：先形成 UTF-8 文件，再复制文件本身。
- 必须由脚本生成：脚本源码只包含 ASCII，非 ASCII 内容用 Unicode escape 或读取 UTF-8 输入文件，最后显式 `encoding="utf-8"` 写入。

