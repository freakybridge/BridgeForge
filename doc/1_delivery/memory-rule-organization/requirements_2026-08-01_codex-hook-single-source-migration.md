---
status: confirmed
topic: memory-rule-organization
date: 2026-08-01
source: "$confirm：下游 hook 投影单一源建议 + 当前 Codex hook 承载核查"
handoff: pending
recommended_handoff: develop
---

# Codex hook 单一注册源与全量承载迁移

## 原始需求摘要

下游报告提出 `memory_dup_check.py`、`memory_lint.py` 与
`rule_size_check.py` 应以上游模板为唯一源码，由下游项目保留运行投影。
核查发现根因不只涉及三个文件：`templates/codex/settings.json` 目前登记了
33 个 handler，而 Codex 不从该文件加载 lifecycle hook。因此本需求扩大为
全部 handler 的系统性审计、迁移、依赖编排和下游传播。

## 目标

将 BridgeForge 的 Codex 项目级 lifecycle hook 从无效的
`.codex/settings.json` 完整迁移到 `.codex/hooks.json`，建立唯一注册源、明确
依赖顺序，并让新建及存量下游项目都获得有效 hook。

## 不做

- 不把项目行为 hook 注册到用户级 `~/.codex/hooks.json`。
- 不改变 Claude Code 使用 `.claude/settings.json` 的注册方式。
- 不静默覆盖下游定制 hook。
- 不依赖 JSON 排列顺序表达执行依赖。
- 不顺带修改模型、reasoning effort、sandbox、MCP 或其他非 hook 配置。
- 不自动 commit 或 push。

## 已核实事实

- Codex 从 `.codex/hooks.json` 或 `.codex/config.toml` 的 `[hooks]` 加载项目级
  lifecycle hook；`.codex/settings.json` 不是有效承载面。
- BridgeForge 当前模板和 dogfood 的 `.codex/hooks.json` 只注册了
  `memory_junction_check.py`。
- `templates/codex/settings.json` 当前登记了 33 个 handler。
- 三个目标 hook 的 Python 实现已经存在于 `templates/codex/hooks/`。
- `memory_dup_check.py` 和 `memory_lint.py` 的模板与 Codex dogfood 实现一致。
- Codex、Claude 两侧 dogfood 的 `rule_size_check.py` 均保留旧
  `doc/3_design/` 文案，模板已改为 `doc/0_architecture/` 或所属 delivery topic。
- Codex 会并发启动同一事件下的多个 command hook；JSON 排列顺序不构成
  执行顺序。
- 现有 `portability.md §5` 已禁止在 `.codex/settings.json` 注册 hook，但尚未
  禁止 `.codex/config.toml [hooks]`，模板自身也仍保留旧 hooks 块。
- 新增或内容变化的 Codex hook 必须经过 `/hooks` review/trust；未信任时会被
  Codex 跳过。

## 已确认业务规则

1. 一次性审计 `.codex/settings.json` 中现有全部 33 个 handler。
2. 禁止机械复制；必须逐条核对当前 Codex 的事件、matcher、输入、输出和用途。
3. 保留 handler 的业务意图；无效、重复或已退役项允许在提供证据后删除或替换。
4. BridgeForge 项目级 hook 注册的唯一事实源是 `.codex/hooks.json`。
5. 禁止在 `.codex/settings.json` 或 `.codex/config.toml [hooks]` 重复注册。
6. 迁移验证完成后，从模板和 dogfood 的 `.codex/settings.json` 删除整个
   `hooks` 块，保留 permissions 等非 hook 配置。
7. 所有受管 hook 保持项目级运行，禁止注册到用户级
   `~/.codex/hooks.json`。
8. Claude Code 继续使用 `.claude/settings.json`；本需求不改变 Claude 注册方式，
   只核对双宿主实现 parity。
9. 同一事件的 handler 必须审查依赖关系：有依赖的显式串行，确认无依赖的才允许
   并发。
10. memory 写入链固定为：memory 写入 → `memory_rebuild_index` →
    `memory_lint`。
11. `memory_rebuild_index` 失败时必须跳过 `memory_lint` 并明确报错，禁止基于旧
    索引继续检查。
12. 存量下游修改过受管 hook 时，`/bridgeforge` 必须展示 diff 并取得覆盖确认。
13. 用户拒绝覆盖或冲突未解决时，保留下游文件，并禁止提前更新
    `.bridgeforge_version`。
14. “唯一 hook 注册源”红线写入现有 `portability.md §5`，同步产品模板与
    dogfood，禁止新增重复 rule 文件。
15. 该红线必须具备机器硬检查：发现 `.codex/settings.json` 存在 `hooks` 块，或
    `.codex/config.toml` 存在 `[hooks]`，验证失败并禁止发布或更新版本戳。
16. 仅 JSON/TOML 解析、脚本直跑和 harness 通过，只能标记为静态验证通过。
17. 完成 `/hooks` review/trust，并在新会话验证关键链路真实触发后，才能标记为
    运行时验收通过。
18. BridgeForge 与全部下游 hook 的最低解释器版本统一为 Python 3.11。任何项目写入
    前必须完成一次性 preflight；项目 `.venv` 存在时是唯一候选，低版本、损坏或缺
    解释器时禁止 PATH 回退，且不得复制、删除、merge 或写版本戳。

## 数据与配置映射

| 当前载体 | 目标载体 | 处理 |
|---|---|---|
| `templates/codex/settings.json: hooks` | `templates/codex/hooks.json` | 逐项审计后迁移，原 hooks 块删除 |
| `.codex/settings.json: hooks` | `.codex/hooks.json` | dogfood 镜像，原 hooks 块删除 |
| 存量下游 `.codex/settings.json: hooks` | 下游 `.codex/hooks.json` | `/bridgeforge` merge，保留第三方 hook |
| `.codex/config.toml [hooks]` | 不允许作为 BridgeForge 注册源 | 机器硬检查阻断 |
| `templates/codex/hooks/*.py` | 下游 `.codex/hooks/*.py` | 上游规范实现、下游运行投影 |
| `.claude/settings.json` | 保持原位 | 不迁移，仅 parity 核对 |

## 拟修改范围

### 产品层

- `templates/codex/hooks.json`
- `templates/codex/settings.json`
- 必要的 `templates/codex/hooks/` 与 `templates/codex/scripts/`
- `templates/codex/rules/portability.md`
- `skills/bridgeforge/references/init.md`
- `skills/bridgeforge/references/update.md`
- 必要的 adopt、配置检查和迁移逻辑

### 自身 dogfood

- `.codex/hooks.json`
- `.codex/settings.json`
- 必要的 `.codex/hooks/` 与 `.codex/scripts/`
- `.codex/rules/portability.md`

### 测试与元文档

- downstream harness、依赖顺序与失败路径测试
- Codex/Claude parity 检查
- 根与 Codex 模板版本、`[product]` CHANGELOG
- 本需求卡及 `doc/README.md`

## 验收标准

1. 33 个原 handler 均有审计结果：保留、适配、替换或删除，并附事实依据。
2. 模板、dogfood 和 fixture 下游的 `.codex/settings.json` 均不存在 `hooks` 块。
3. `.codex/config.toml` 不含 BridgeForge `[hooks]`。
4. 所有有效 handler 均由 `.codex/hooks.json` 注册。
5. hooks merge 保留下游第三方事件、handler 和其他配置。
6. `memory_rebuild_index → memory_lint` 顺序测试通过。
7. 重建失败时 lint 未运行，错误可见。
8. 其他同事件 handler 的依赖或并发资格均有记录和测试。
9. 三个目标 hook 在新建及存量 fixture 中有效。
10. `rule_size_check.py` 的模板及双宿主 dogfood 漂移收口。
11. 非法双源配置触发机器硬失败。
12. 下游冲突未解决时文件和旧版本戳保持不变。
13. 静态 harness、JSON/TOML 解析、脚本 smoke 和 pre-commit 路径通过。
14. `/hooks` review/trust 后的新会话真实触发关键链路。
15. 未写入用户级 hook，Claude 注册方式未改变。
16. 产品层版本、CHANGELOG 和传播收据完整。
17. merge、dispatcher、config health、root/Codex/Claude pre-commit 均硬拦
    Python `<3.11`；正向 hook 注册固定使用已通过 preflight 的同一解释器。

## 合理假设与风险

- 实施时必须重新核对当前 Codex 官方 hook schema，禁止按旧 matcher 或 payload
  机械迁移。
- 33 个 handler 中可能存在已经失效或不再需要的逻辑，最终数量不承诺仍为 33。
- 多 handler 并发可能暴露除 memory 链之外的新竞态，必须逐组审计。
- hook 内容变化会使既有 trust 失效，真实新会话验收需要用户参与。
- 存量下游定制可能阻止本轮完整升级，禁止用新版本戳掩盖。

## 自动化边界

- 可以自动完成确定性的 schema 检查、分类审计、merge 计划、fixture 和静态测试。
- 覆盖下游人工修改前必须取得确认。
- Codex `/hooks` trust 不能由迁移脚本代替。
- 真实新会话 smoke 未完成时必须明确标记“运行时未验证”。

## 后续交接目标

- 推荐使用 `$develop`：本需求涉及产品模板、dogfood、BridgeForge 更新流程、全量
  handler 审计和跨层验收，属于跨模块完整交付。
- 实际交接目标等待用户在需求卡落盘后选择；选择前禁止开始实现。

## 实施与验证记录

- 实施计划：以 `.codex/hooks.json` 为唯一注册面；每个事件注册单 dispatcher；再补
  下游确认式 merge、双源硬闸、fixture 和传播版本。
- 已实施：模板与 dogfood settings 均移除 hooks；两侧 hooks.json 已注册 6 事件 / 7 个
  dispatcher command；dispatcher、merge 工具、健康检查、pre-commit、portability §5、
  init/update/adopt 手册、版本、分发 manifest 与测试均已落盘。
- 独立审计修复：删除自制逐行 TOML parser，merge 与 health 改为共用 Python 3.11+
  标准库 `tomllib` 完整解析 `config.toml`；解析后只要存在顶层 `hooks` key 即硬拦，
  覆盖 table、quoted/unicode key、dotted assignment、inline table 与 array-table；无
  `hooks` 的合法多行嵌套数组正常放行，非法 TOML 及 Python 3.10 缺少 `tomllib` 均
  fail closed 且不更新版本戳；受管身份改为精确项目 `.codex/hooks|scripts`
  路径；apply_patch `Move to` 同时检查源/目标；普通 stdout 统一合并为单个
  `hookSpecificOutput.additionalContext` JSON；SessionStart best-effort 完成后返回首个
  非零码；33 项收据绑定 dispatcher 实际消费的 `RUNTIME_ROUTES`，删除任一路由会使
  audit 失败，不再以整份源码字符串搜索或文档行数自证。
- Python baseline 收口：`/bridgeforge` 在任何项目写入前只执行一次 preflight 并锁定
  `$HOOK_PYTHON`；init/update/adopt/switch 全程复用该值。已有 `.venv` 不得回退
  PATH。merge、dispatcher、health 与 root/Codex/Claude pre-commit 对 `<3.11`
  fail closed；Codex dogfood `hooks.json` 与模板统一使用项目 `.venv`；退役
  `model_policy_check.py` 的 Python 3.10 TOML fallback 死代码已删除。本变更作为
  0.75.0 / Codex 0.44.0 当前版本内 breaking baseline 收口，不额外 bump。
- 静态验证：
  - `.venv\\Scripts\\python.exe -m unittest tests.harness.test_codex_hook_single_source tests.harness.test_bridgeforge_root_skill tests.harness.test_shared_skill_distribution tests.harness.test_skill_metadata_budget tests.harness.test_downstream_version_sot -v`
    → exit 0，49 tests；覆盖 33 项真实路由绑定、新建/存量 merge、
    table/quoted/unicode/dotted/inline/array-table TOML 双源、合法多行 matrix 放行、
    非法 TOML 与 Python 3.10 merge/dispatcher/Codex+Claude health fail closed、三套 pre-commit
    低版本 `.venv` 禁止 PATH 回退且文件/版本戳不变、preflight 顺序、第三方同名碰撞、
    Move 目标保护、Pre/Post 单 JSON schema、PreTool 串行决策、memory 顺序/失败、
    SessionStart 首错、版本冲突、bundle manifest 与 dogfood。
  - `.venv\\Scripts\\python.exe tests\\harness\\run_downstream_fixture.py --case python-baseline --case settings-matchers --case non-ascii-shell-settings --case user-config-write-guard --case root-precommit --case precommit-shebang --case mirror-missing --case mirror-noop`
    → exit 0，8 cases。
  - Git for Windows `sh -n` 分别检查 root、Codex template、Claude template
    pre-commit → 全部 exit 0。
  - downstream fixture 中实际运行 `.githooks/pre-commit` → exit 0；严格健康闸、rule/skill/memory 段可执行。
  - `harness_parity_check.py --check`、`rebuild_shared_skill_manifest.py --check`、`git diff --check` → exit 0。
  - 模板/dogfood settings/hooks 与 manifest JSON 解析通过；config.toml 扫描确认无 `[hooks]`。
- `/hooks` review/trust：未执行。
- 新会话运行时 smoke：未执行。

### 33 handler 分类收据

分类口径是业务意图：`保留` 表示逻辑原样进入 dispatcher；`适配/替换` 表示 matcher、
payload 或依赖表达发生变化；`删除` 仅限确认重复项。总计保留 18、适配/替换 13、删除 2。

| # | 原事件 / handler | 结论 | 依据 / 新承载 |
|---:|---|---|---|
| 1 | PreTool Grep/Glob/Read `find_doc_reminder` | 适配/替换 | 当前工具面无可靠路径型 matcher；降级为已存在的 skill-routing / AGENTS 裸信号契约，不注册伪 hook |
| 2 | PreTool Bash `git_add_all_guard` | 保留 | Bash matcher 直接；dispatcher 串行 |
| 3 | PreTool Bash `non_ascii_shell_guard` | 保留 | 读取 `tool_input.command` |
| 4 | PreTool Bash `cross_project_write_guard` | 保留 | shell 写边界保持 |
| 5 | PreTool Bash `user_config_write_guard` | 保留 | 用户 config 红线保持 |
| 6 | PreTool PowerShell `cross_project_write_guard` | 删除 | 与 Bash/shell matcher 重复 |
| 7 | PreTool PowerShell `user_config_write_guard` | 删除 | 与 Bash/shell matcher重复 |
| 8 | PreTool Edit/Write `cross_project_write_guard` | 适配/替换 | matcher alias 为 Edit/Write，真实 apply_patch 从 `tool_input.command` 展开文件 |
| 9 | PreTool Edit/Write `user_config_write_guard` | 适配/替换 | 同上；逐文件标准化 payload |
| 10 | PreTool Edit/Write `allow_memory_write` | 适配/替换 | deny/dup 后串行；仅单一 memory Markdown patch 输出 allow JSON |
| 11 | PreTool Edit/Write `memory_dup_check` | 适配/替换 | Add File 标准化为 Write，且先于 allow |
| 12 | PostTool Edit/Write `memory_rebuild_index` | 适配/替换 | memory 链中位于 encoding 后；失败短路 lint |
| 13 | PostTool Edit/Write `memory_lint` | 适配/替换 | 仅 rebuild 成功后运行 |
| 14 | PostTool Edit/Write `rule_index_check` | 适配/替换 | apply_patch 逐文件 payload |
| 15 | PostTool Edit/Write `rule_size_check` | 适配/替换 | apply_patch 逐文件 payload |
| 16 | PostTool Edit/Write `requirements_check` | 适配/替换 | apply_patch 逐文件 payload |
| 17 | PostTool Edit/Write `cargo_default_run_check` | 保留 | 自门控逻辑保持 |
| 18 | PostTool Edit/Write `fallback_smell_check` | 保留 | 自门控逻辑保持 |
| 19 | PostTool Edit/Write `encoding_check` | 适配/替换 | 提升为 memory 依赖链首项 |
| 20 | PostTool Bash `test_receipt` | 保留 | Bash matcher 与普通 stdout 语义保持 |
| 21 | PostCompact `session_snapshot post-compact` | 保留 | 生命周期意图不变 |
| 22 | Stop `session_snapshot stop` | 保留 | 生命周期意图不变 |
| 23 | UserPrompt `show_state prompt-state` | 保留 | 普通 stdout 注入保持 |
| 24 | UserPrompt `context_warning` | 保留 | 裸信号保持 |
| 25 | UserPrompt `clarify_reminder` | 保留 | 裸信号保持 |
| 26 | UserPrompt `focus_reminder` | 保留 | 裸信号保持 |
| 27 | SessionStart `config_health_check` | 保留 | 增补单一源检查，不改变只读启动语义 |
| 28 | SessionStart `show_state session-start` | 适配/替换 | 明确排在 rebuild 之后 |
| 29 | SessionStart `target_cleanup` | 保留 | Rust 自门控保持 |
| 30 | SessionStart `skill_sync_check` | 保留 | 只读漂移检查保持 |
| 31 | SessionStart `enforce_no_effortlevel` | 保留 | 既有自愈保持 |
| 32 | SessionStart `githooks_path_check` | 保留 | 既有自愈保持 |
| 33 | SessionStart `memory_rebuild_index` | 适配/替换 | dispatcher 显式先于 show_state |

额外既有 `.codex/hooks.json` 的 `memory_junction_check` 不属于上述 33 项；迁移后继续由
SessionStart dispatcher 保留，因此不拿它补分类数量。
