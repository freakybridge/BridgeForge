# 需求：跨项目写入保护 hook
> 日期：2026-07-10
> 状态：trial
> 入口：根据下游 `2026-07-10_cross_project_write_guard_proposal.md`，开发 Claude/Codex 两套骨架的跨项目代码修改防护。

## 背景与目标

用户在 A 项目对话框中验收 B 项目功能时，agent 可能因历史上下文、绝对路径或跨目录命令直接修改 B 项目。即使修改内容正确，这也破坏了“当前对话框属于哪个项目”的边界感。

本需求目标是在 BridgeForge 的 Claude 与 Codex 两套骨架中默认启用跨项目写入保护：当前对话归属项目为 A 时，静默写入、删除、移动 A 项目根外的文件，或在外部项目执行危险 git 操作，必须被 hook 阻断并清楚说明当前项目、目标路径和操作类型。

## 非目标

- 不阻断外部只读访问，例如读取上游文档或查看外部项目 `git status`。
- 不做永久白名单或长期路径授权。
- 不在第一版静态推断所有构建、测试、格式化命令的隐式副作用。
- 不替代现有高风险操作确认规则；外部危险 git / 删除操作仍需叠加现有规则。

## 用户可见行为

- 当前项目内写入继续放行。
- 写入、删除、移动当前项目根外的路径时，hook 返回 exit 2 阻断。
- 在当前项目根外使用 `git -C <path>` 执行 `add/commit/restore/reset/push/checkout/merge/cherry-pick/clean/branch/tag/update-ref/stash` 等危险操作时阻断。
- 阻断信息必须包含当前项目根、目标路径、操作类型，并提示用户显式确认后再由 agent 重试。

## 约束 / 风险边界

- hook 必须同时落地 `templates/claude` 与 `templates/codex`，并 dogfood 镜像到 `.claude` 与 `.codex`。
- Claude/Codex 两侧脚本正文应保持一致，差异只允许来自 settings 路径前缀。
- 第一版宁可漏掉复杂隐式副作用，也不要大面积误伤只读命令。
- 不因 sandbox escalation、历史上下文或绝对路径自动豁免。

## 验收清单

- [x] 当前项目内 `Write/Edit/MultiEdit` 路径放行。
- [x] 当前项目外 `Write/Edit/MultiEdit` 路径阻断，并显示当前项目与目标路径。
- [x] shell/PowerShell 对当前项目外路径的显式写入、删除、移动阻断。
- [x] 外部项目 `git status` 放行。
- [x] 外部项目危险 git 操作阻断。
- [x] Claude 模板 settings 挂载到 Bash、PowerShell 与 Write/Edit/MultiEdit。
- [x] Codex 模板 settings 挂载到 Bash、PowerShell 与 Write/Edit/MultiEdit。
- [x] BridgeForge `.claude` / `.codex` dogfood settings 挂载到 Bash、PowerShell 与 Write/Edit/MultiEdit。
- [x] 模板版本号与 CHANGELOG 已更新。

## 暂缓项

- 任务级一次性放行 token。
- monorepo/workspace 多根声明。
- 构建/测试/格式化命令的副作用分类。
- 外部只读访问的弱提示日志。

## 实施计划

单线实现。先新增共享风格 hook 脚本并复制到 Claude/Codex 模板与 dogfood，再挂载 settings，最后用 stdin payload 构造脚本级用例验证。

## 实施记录

- 2026-07-10：需求确认，开始实现。
- 2026-07-10：新增 `cross_project_write_guard.py`，同步 Claude/Codex 模板与 BridgeForge dogfood，并挂载 Bash、PowerShell、Write/Edit/MultiEdit。

## 验证记录

- `python .codex\hooks\cross_project_write_guard.py` stdin payload：项目内 `Write` 返回 `exit=0`。
- `python .codex\hooks\cross_project_write_guard.py` stdin payload：项目外 `Write` 返回 `exit=2`，输出当前项目与目标路径。
- `python .codex\hooks\cross_project_write_guard.py` stdin payload：外部 `git -C ... status` 返回 `exit=0`。
- `python .codex\hooks\cross_project_write_guard.py` stdin payload：外部 `git -C ... commit` 返回 `exit=2`。
- `python .codex\hooks\cross_project_write_guard.py` stdin payload：外部 `Set-Content`、`Remove-Item`、shell redirection 返回 `exit=2`，外部 `Get-Content` 返回 `exit=0`。
- `python -m json.tool`：`.codex/settings.json`、`.claude/settings.json`、`templates/codex/settings.json`、`templates/claude/settings.json` 全部返回 `0`。
- `python -B -c "compile(...)"`：四份 `cross_project_write_guard.py` 全部语法检查通过。
- `python -m py_compile ...` 未采用为最终语法验证，因为当前仓库无 `.venv` 且 `.codex/hooks/__pycache__` 写入被系统拒绝；已改用不落盘 `compile()` 验证。

## 用户试用反馈

待用户试用后补充。
