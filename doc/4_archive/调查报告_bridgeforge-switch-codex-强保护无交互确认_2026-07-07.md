# 调查报告：`/bridgeforge switch codex` 强保护拦截后缺少交互式覆盖确认

> 日期：2026-07-07
> 来源项目：`D:\Quant\CausisRiskSuite`
> 触发命令：`/bridgeforge switch codex`
> 状态：已定位为 BridgeForge switch 流程的体验/流程缺口；未在下游本地绕过强保护
> 建议优先级：P1。不会破坏业务代码，但会让用户误以为“没有按既定更新流程给出覆盖确认”，影响下游切换收尾。

---

## 0. TL;DR

本次并不是 Codex 模板不可用，也不是切换脚本找不到 BridgeForge 模板。实际发生的是：

1. `scripts/bridgeforge_switch.py codex` 已识别目标为 `codex`，并列出了将覆盖的 Codex 骨架文件；
2. Git 强保护发现这些目标文件在工作区已经是未提交/未跟踪/已修改状态；
3. switch 脚本按硬保护策略直接退出：

```text
ERROR: strong protection blocked this switch. Commit, stash, or clean the listed files first.
```

用户预期的是类似 `/bridgeforge` 更新模式的响应：列出哪些文件要覆盖、哪些存在风险，然后逐项交给用户确认。

实际脚本行为是：打印 `Will overwrite` / `Blocked by strong protection` 清单，但没有进入逐项确认，也没有把“下一步如何处理这个中间态”整理成用户可执行的选择。

**核心结论**：`switch` 子命令当前是“硬门禁”模型，不是“更新模式的人审覆盖”模型。这个差异没有在用户侧形成清晰反馈，导致用户认为“应该出现的覆盖确认列表没有出现”。

---

## 1. 现场收据

第一次运行时，Git 因 Windows sandbox 用户与仓库 owner 不一致，触发 `dubious ownership`：

```text
Git protection: unavailable (fatal: detected dubious ownership in repository at 'D:/Quant/CausisRiskSuite'
...
To add an exception for this directory, call:

	git config --global --add safe.directory D:/Quant/CausisRiskSuite); existing target files are treated as blocked.
```

随后用进程级临时 Git 配置重跑，不写全局配置：

```powershell
$env:GIT_CONFIG_COUNT='1'
$env:GIT_CONFIG_KEY_0='safe.directory'
$env:GIT_CONFIG_VALUE_0='D:/Quant/CausisRiskSuite'
python scripts/bridgeforge_switch.py codex
```

这次 Git 保护可用，但仍被强保护拦截：

```text
BridgeForge switch target: codex
Project root: D:\Quant\CausisRiskSuite
Template root: D:\Quant\BridgeForge
Git protection: enabled
Python hook command: .venv/Scripts/python.exe
Will delete: none
Will overwrite:
  - AGENTS.md
  - .codex/rules/anti_drift_hooks.md
  - .codex/rules/anti_fabrication.md
  - .codex/rules/architecture.md
  - .codex/rules/debugging.md
  - .codex/rules/meta_rule_design.md
  - .codex/rules/modules.md
  - .codex/rules/portability.md
  - .codex/rules/workflow.md
  - .codex/hooks/allow_memory_write.py
  - .codex/hooks/clarify_reminder.py
  - .codex/hooks/config_health_check.py
  - .codex/hooks/context_warning.py
  - .codex/hooks/enforce_no_effortlevel.py
  - .codex/hooks/fallback_smell_check.py
  - .codex/hooks/find_doc_reminder.py
  - .codex/hooks/focus_reminder.py
  - .codex/hooks/githooks_path_check.py
  - .codex/hooks/memory_junction_check.py
  - .codex/hooks/memory_lint.py
  - .codex/hooks/mirror_drift_check.py
  - .codex/hooks/requirements_check.py
  - .codex/hooks/rule_index_check.py
  - .codex/hooks/rule_size_check.py
  - .codex/hooks/session_snapshot.py
  - .codex/hooks/show_state.py
  - .codex/hooks/skill_sync_check.py
  - .codex/hooks/stall_warning.py
  - .codex/hooks/target_cleanup.py
  - .codex/hooks/test_receipt.py
  - .codex/hooks/version_check.py
  - .codex/scripts/archive_scan.py
  - .codex/scripts/audit_user_allow.py
  - .codex/scripts/bridgeforge_switch.py
  - .codex/scripts/memory_rebuild_index.py
  - .codex/scripts/memory_search.py
  - .codex/memory/_stats.json
  - .codex/memory/MEMORY.md
  - .codex/settings.json
  - scripts/bridgeforge_switch.py
  - .githooks/pre-commit
Will create: none
Unknown old-agent files: none
Blocked by strong protection:
  - .codex/hooks/allow_memory_write.py
  - .codex/hooks/clarify_reminder.py
  - .codex/hooks/config_health_check.py
  - .codex/hooks/context_warning.py
  - .codex/hooks/enforce_no_effortlevel.py
  - .codex/hooks/fallback_smell_check.py
  - .codex/hooks/find_doc_reminder.py
  - .codex/hooks/focus_reminder.py
  - .codex/hooks/githooks_path_check.py
  - .codex/hooks/memory_junction_check.py
  - .codex/hooks/memory_lint.py
  - .codex/hooks/mirror_drift_check.py
  - .codex/hooks/requirements_check.py
  - .codex/hooks/rule_index_check.py
  - .codex/hooks/rule_size_check.py
  - .codex/hooks/session_snapshot.py
  - .codex/hooks/show_state.py
  - .codex/hooks/skill_sync_check.py
  - .codex/hooks/stall_warning.py
  - .codex/hooks/target_cleanup.py
  - .codex/hooks/test_receipt.py
  - .codex/hooks/version_check.py
  - .codex/memory/_stats.json
  - .codex/memory/MEMORY.md
  - .codex/rules/anti_drift_hooks.md
  - .codex/rules/anti_fabrication.md
  - .codex/rules/architecture.md
  - .codex/rules/debugging.md
  - .codex/rules/meta_rule_design.md
  - .codex/rules/modules.md
  - .codex/rules/portability.md
  - .codex/rules/workflow.md
  - .codex/scripts/archive_scan.py
  - .codex/scripts/audit_user_allow.py
  - .codex/scripts/bridgeforge_switch.py
  - .codex/scripts/memory_rebuild_index.py
  - .codex/scripts/memory_search.py
  - .codex/settings.json
  - .githooks/pre-commit
  - AGENTS.md
  - scripts/bridgeforge_switch.py
ERROR: strong protection blocked this switch. Commit, stash, or clean the listed files first.
```

工作区状态显示当时不是干净切换起点，而是已经存在一批未收尾的 Codex 骨架产物：

```text
 D .claude/.bridgeforge_version
 D .claude/hooks/...
 D .claude/rules/...
 D .claude/settings.json
 D CLAUDE.md
 M .githooks/pre-commit
 M doc/README.md
?? .codex/.bridgeforge_version
?? .codex/hooks/...
?? .codex/rules/...
?? .codex/settings.json
?? AGENTS.md
?? scripts/bridgeforge_switch.py
```

版本戳也显示下游 Codex 骨架与上游不是同一版本：

```text
.codex/.bridgeforge_version = 0.45.0
D:\Quant\BridgeForge\VERSION = 0.47.0
```

---

## 2. 用户预期 vs 实际行为

### 用户预期

用户记得 BridgeForge 在类似覆盖场景中会：

1. 列出受影响文件；
2. 告诉用户哪些需要覆盖；
3. 让用户确认后再改。

这个预期符合 `/bridgeforge` 更新模式的设计：更新模式会把类 A/B/C/D/E 差异分类，尤其 rules/入口文件等类 C 项只 diff、不自动改，由用户逐段决定。

### 实际行为

`/bridgeforge switch codex` 直接分流到：

```text
python scripts/bridgeforge_switch.py codex
```

根据当前 `SKILL.md` 的 Step -1，switch 子命令“不进入初始化 / 更新 / 收编流程”。

因此本次没有进入更新模式的类 A/B/C 人审流程。switch 脚本只做：

1. 生成切换计划；
2. 用 `git status --porcelain=v1 -z --untracked-files=all` 判断将删除/覆盖的文件是否 dirty；
3. 如有 dirty 或未知旧 agent 文件，直接阻塞。

这解释了为什么用户没看到熟悉的“逐项覆盖确认”。

---

## 3. 根因

根因不是单点 bug，而是两个设计事实叠加：

1. **switch 脚本是硬保护脚本，不是交互式合并器。**
   - 代码中 `apply_plan()` 一旦发现 `plan.blocked_paths`，只调用 `describe_plan(plan)`，然后 `SystemExit`；
   - 没有 `--force`、`--adopt-existing`、`--interactive` 或逐项确认分支。

2. **`/bridgeforge switch ...` 的用户反馈没有补齐“被拦后如何处理”。**
   - 脚本打印了机器清单，但没有转译成用户决策菜单；
   - agent 首轮反馈也只概括“强保护 blocked”，没有把 `Will overwrite` / `Blocked` 整理成“需要你确认的覆盖/收编清单”。

白话说：更新模式像“师傅拿着清单问你每个柜子换不换”；switch 脚本像“门禁发现仓库里有未登记物品就锁门”。两者都合理，但用户以为自己会遇到前者，实际遇到的是后者。

---

## 4. 影响范围

会受影响的场景：

- 下游项目已经部分生成 Codex 骨架，但未提交；
- 从旧版本 Codex 骨架继续切换到 Codex，新模板会覆盖已有 `.codex/**`；
- Windows / sandbox 场景下 Git 还可能先遇到 `dubious ownership`，进一步放大“为什么没继续”的困惑；
- 用户把 switch 与 update 的交互语义视为同一类操作。

不会受影响的场景：

- 干净工作区首次从 Claude 切到 Codex；
- 目标文件未 dirty，脚本可直接完成切换；
- 用户先提交/暂存/清理中间态后再运行 switch。

---

## 5. 修复建议

建议分两层处理。

### 5.1 低风险修复：改善 blocked 输出

在 `scripts/bridgeforge_switch.py` 的强保护失败分支中，把退出文案从：

```text
ERROR: strong protection blocked this switch. Commit, stash, or clean the listed files first.
```

扩展为更可执行的说明：

```text
ERROR: strong protection blocked this switch.

These files already contain uncommitted or untracked content, so BridgeForge will not overwrite them automatically.

Choose one:
1. Review and commit/stash the current switch output, then rerun this command.
2. Remove the listed untracked target files yourself if they are disposable, then rerun.
3. If this is an intentional partial switch, run the update/adopt flow instead of switch.

No files were changed by this failed run.
```

同时在 agent 层响应中要求把 `Will overwrite` 和 `Blocked by strong protection` 汇总成“待用户处理清单”，不要只说“blocked”。

优点：不改变安全模型，不引入误覆盖风险。

### 5.2 中风险增强：增加显式交互/收编模式

给 switch 脚本增加一个显式子模式，例如：

```text
python scripts/bridgeforge_switch.py codex --adopt-existing
```

语义：

- 只在目标 agent 已存在且 old agent 已删除/待删除的“中间态”使用；
- 不自动覆盖 dirty 文件；
- 可以把当前 `.codex/.bridgeforge_version` 与上游版本差异报告出来；
- 引导用户转入 update 模式，而不是把 switch 当作升级器。

或者增加：

```text
python scripts/bridgeforge_switch.py codex --interactive
```

但这个方案风险更高，因为逐项覆盖一旦做进脚本，就容易把“强保护”弱化成“误按确认后覆盖”。若实现，应限制为只覆盖“与旧模板字节一致、确认没有项目定制”的文件。

---

## 6. 建议落点

如果只修提示：

- 产品层：
  - `templates/claude/scripts/bridgeforge_switch.py`
  - `templates/codex/scripts/bridgeforge_switch.py`
- dogfood：
  - `.codex/scripts/bridgeforge_switch.py`
  - 根 `scripts/bridgeforge_switch.py`
- 元文档：
  - `SKILL.md` Step -1 增加 blocked 后 agent 响应要求；
  - `CHANGELOG.md` 增加 `[product]` 条目；
  - bump `VERSION`。

如果增加交互/收编模式，需要同步更新：

- `doc/3_design/sync-from-upstream-playbook.md` 或新增 switch 故障处理小节；
- `templates/*/AGENTS.md` 中 `/bridgeforge switch` 的用户预期说明；
- 对下游迁移过程补一条“中间态处理”说明。

---

## 7. 本次下游状态备注

CausisRiskSuite 当前处在切换中间态：

- `.claude/**` 和 `CLAUDE.md` 已显示为删除；
- `.codex/**`、`AGENTS.md`、`scripts/bridgeforge_switch.py` 显示为未跟踪；
- `.githooks/pre-commit` 和 `doc/README.md` 有修改；
- `.codex/.bridgeforge_version` 是 `0.45.0`，上游 `VERSION` 是 `0.47.0`。

下游本次未继续强行覆盖，也未 commit/push。后续应先由用户 review 当前切换产物，决定是提交中间态、清理后重跑，还是转入 BridgeForge 侧修复后的流程。

