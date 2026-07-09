# 需求：非 ASCII shell 中转防护 hook
> 日期：2026-07-10
> 状态：trial
> 入口：用户要求根据 `doc/2_pending/2026-07-10_non_ascii_shell_pipe_hook_proposal.md` 开发 hook，让 Claude / Codex 两套骨架都能管理非英语文本传输风险，并检查两套骨架现存乱码。

## 背景与目标

下游 StratusAgent 反馈：非 ASCII 正文经 PowerShell here-string、管道、重定向或解释器 stdin 中转后，可能在 shell / 终端 / 解释器 / 文件默认编码边界被污染，写入源码或文档后只剩三连问号或 `U+FFFD`，原文不可恢复。

本轮目标是在 BridgeForge 产品层同时加入 Claude / Codex 防护：命令同时满足“含非 ASCII 文本”“经 shell 中转”“可能写文件或动态执行脚本”时，在 PreToolUse 阶段 fail-fast；并补充现存乱码扫描能力，明确两套骨架当前是否还有污染。

## 非目标

- 不泛禁 shell。
- 不阻断普通只读输出命令。
- 不自动修复已污染文本，因为原文不可可靠恢复。
- 不修改历史提交。
- 不改变非 shell 工具的写入路径；`apply_patch`、Edit、Write、MultiEdit 仍按既有编码检查链路处理。

## 用户可见行为

- Claude / Codex 下游项目安装或同步新骨架后，危险 shell 写入 / 动态执行命令会被 hook 阻断，并提示改用安全 UTF-8 路径。
- 只读的非 ASCII 输出命令应继续放行，避免日常查看中文日志、文档、终端输出被误伤。
- 编辑后 / 提交前的编码检查会报告受管文本文件中的可疑三连问号或 `U+FFFD`。

## 约束 / 风险边界

- 触发条件必须同时命中非 ASCII、shell 中转、写入或动态执行入口，降低误伤。
- hook 必须兼容 stdin JSON、`CODEX_TOOL_INPUT` 和 `CLAUDE_TOOL_INPUT` 读取方式。
- Codex 产品层 hook / settings 改动必须 dogfood 到自身 `.codex/`。
- Claude 产品层 hook / settings 改动必须 dogfood 到自身 `.claude/`。
- 产品层改动需要 bump `templates/claude/VERSION`、`templates/codex/VERSION`、根 `VERSION` / `SKILL.md` / 两套薄入口版本，并写 `[product]` CHANGELOG。

## 验收清单

- [x] Codex 模板新增并注册 PreToolUse shell 防护 hook。
- [x] Claude 模板新增并注册 PreToolUse shell 防护 hook。
- [x] BridgeForge 自身 `.codex` / `.claude` dogfood 副本同步新增 hook 与 settings 注册。
- [x] 中文 here-string 管道到 `python -` 被阻断。
- [x] emoji 或中文文本重定向写文件被阻断。
- [x] 中文 `Set-Content` / `Out-File` / `Add-Content` 写文件被阻断。
- [x] 中文只读 `Write-Output` 放行。
- [x] ASCII 管道到 `python -` 放行。
- [x] 编辑后 / pre-commit 编码扫描能报告受管文本文件中的可疑三连问号或 `U+FFFD`。
- [x] 扫描两套骨架当前乱码，给出命中文件与处理结果。
- [x] 相关 harness / 单测验证通过，或明确未验证项。
- [x] 交付前完成独立验证或明确说明未完成。

## 暂缓项

- 不实现跨仓库共享运行时脚本分发；本轮延续现有模板内 hook 文件模式，用测试和 dogfood 镜像降低漂移。
- 不尝试还原历史乱码原文。

## 实施计划

单线推进：

1. 增加非 ASCII shell 中转 PreToolUse hook，并同步 Claude / Codex 模板与 dogfood 副本。
2. 扩展编码扫描，对受管文本文件中的可疑三连问号 / `U+FFFD` 做软提示和 pre-commit 检查。
3. 补 harness 覆盖危险 / 放行命令、乱码扫描、settings 注册和版本 / CHANGELOG。

## 实施记录

- 2026-07-10：需求确认，开始实现。
- 2026-07-10：新增 `non_ascii_shell_guard.py` 到 Claude / Codex 模板与 `.claude` / `.codex` dogfood 副本，并接入 `PreToolUse(Bash)`。
- 2026-07-10：扩展 `encoding_check.py`，保留 BOM 硬拦，并新增可疑三连问号 / `U+FFFD` 扫描；修复两套模板与 dogfood settings 中既有问号乱码注释。
- 2026-07-10：补充 harness 覆盖危险命令阻断、安全命令放行、settings 注册和乱码扫描；版本升至根 `0.58.0`、Claude 模板 `0.22.0`、Codex 模板 `0.29.0`。
- 2026-07-10：独立审计发现三连问号漏检与需求包未收尾；已将检测阈值收紧到三连问号，并清除文档 / 测试源码中的字面三连问号，避免 pre-commit 自报。

## 验证记录

- `python tests\harness\run_downstream_fixture.py --case encoding-garble --case non-ascii-shell-guard --case non-ascii-shell-settings`：PASS，覆盖三连问号扫描、Claude/Codex hook 阻断与 settings 注册。
- `python .codex\hooks\encoding_check.py --scan-garble templates\codex templates\claude .codex\hooks .codex\settings.json .claude\hooks .claude\settings.json`：exit 0，两套模板骨架与 dogfood hooks/settings 未发现可疑三连问号或 `U+FFFD`。
- `rg` 扫描受检范围内的三连问号或 `U+FFFD`：exit 1，受检范围无命中。
- `python tests\harness\run_downstream_fixture.py`：全量 PASS，覆盖现有 harness 回归。
- `python .codex\hooks\mirror_drift_check.py` / `python .claude\hooks\mirror_drift_check.py`：exit 0；仅提示既有 `skill_sync_check.py` 正文漂移，未发现新增 hook 缺文件。
- 独立验证：第一次审计发现三连问号漏检与文档闭环未完成；修复后复核确认 P1/P2 已解决，交付前独立验证通过。残余提醒是提交时需精确纳入本需求的未跟踪 `non_ascii_shell_guard.py` 文件，避免混入 unrelated `cross_project_write_guard`。

## 用户试用反馈

- 待补。
