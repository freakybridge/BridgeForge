# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本按 `templates/<agent>/rules/workflow.md §9` **简版**（小项目退化版）：

- **major (X)** — 破坏性变更 / 范式重写
- **minor (Y)** — 新功能（新 hook / 新 skill / 新 rule / 新模板）
- **patch (Z)** — bug 修复 / 文档调整 / refactor

**层标签**（每条 entry 前缀，让下游一眼看懂该不该 sync，语义见 `CLAUDE.md §3`）：

- `[product]` — 改了 `templates/` / `skills/`，会下沉到下游 → 下游 sync-from-upstream 时**应当**拉取
- `[repo]` — 只改了 setup_agent 自身配置 / 工具，不下沉 → 下游无关
- `[meta]` — 只改了 `docs/` / `README` / `SKILL.md` 等说明 → 一般无关
- 混合改动并列标，如 `[product][meta]`

> **追溯说明**：v0.1.0 - v0.7.0 基于 git log 历史回溯标记，**git tag 仅从 v0.8.0 开始打**。早期未启用版本号管理是 setup_agent 自打脸问题（要求下游用但自己没用），v0.8.0 修补。

---

## [0.45.0] - 2026-07-06

### Added
- `[product][repo]` **Codex 空 `.agents/` 工作区清洁 hook**：新增 `templates/codex/hooks/legacy_agents_cleanup.py` 并同步 dogfood 到 `.codex/hooks/`，SessionStart 时只删除项目根普通空 `.agents/`；非空、symlink、junction 或异常均静默 no-op。`templates/codex/VERSION` 同步升至 `0.16.0`。

## [0.44.0] - 2026-07-06

### Added
- `[repo]` **最小 harness 回归试验田**：新增 `tests/harness/run_downstream_fixture.py`，每次在 `.runtime/harness/downstream-codex/` 生成一次性 Codex fixture，覆盖 D6 规则闸（rule index / rule size exit 2）、D8 dogfood 镜像闸（缺文件 exit 2 + 纯下游 no-op）、关键 PostToolUse matcher 必含 `Edit|Write|MultiEdit`、根 `.githooks/pre-commit` 必须同时覆盖 Claude/Codex 两侧提交闸，并扫描 `skills/**/SKILL.md` 高置信本地引用死链；新增 `tests/harness/README.md` 说明运行方式。
- `[product]` **验证通过三件套**：`templates/claude/CLAUDE.md` / `templates/codex/AGENTS.md` 增加红线，凡交付中写「验证通过 / 测试通过 / 已验证」，必须同时列出实际命令或 test receipt 指纹、具体验证断言、覆盖路径 / 场景；缺任一项只能标「已运行但验证有效性未确认」或「未验证」。BridgeForge 自身根 `AGENTS.md` 同步补同款约束。

### Fixed
- `[repo]` **根 pre-commit Codex 侧裸奔**：`.githooks/pre-commit` 原只调用 `.claude/hooks/*` dogfood / rule 闸和 `.claude/scripts/memory_rebuild_index.py`，现改为 Claude + Codex 双侧执行；缺文件类 exit 2 继续硬拦，memory 索引重建循环覆盖 `.claude` / `.codex`。
- `[repo]` **Claude dogfood scripts 缺口**：补齐 `.claude/scripts/archive_scan.py` 与 `.claude/scripts/bridgeforge_switch.py`，避免本仓 Claude 侧 `/archive-scan` 或状态展示调用到模板承诺但自身未安装的脚本。
- `[product]` **harvest skill 旧模板路径死链**：`skills/harvest/SKILL.md` 仍引用拆分前的 `templates/CLAUDE.md` / `templates/rules/`，现改为 `templates/claude/CLAUDE.md`、`templates/codex/AGENTS.md`、`templates/<agent>/rules/`，避免反哺时把 agent 引到不存在的路径。
- `[product][meta]` **拆目录后的旧路径死链**：修正 `templates/claude/rules/portability.md` 的 dogfood 镜像路径为 `templates/claude/hooks ↔ .claude/hooks`，并把 Claude/Codex settings 注释里的 `templates/rules/meta_rule_design.md` 改为各自 agent 分支路径。
- `[product][repo]` **archive_scan 旧 Python 兼容**：`templates/<agent>/scripts/archive_scan.py` 与自身 `.claude/.codex` 副本补 `from __future__ import annotations`，避免默认 `python` 低于 3.10 时因 `int | None` 类型注解运行时求值直接崩溃。
- `[meta]` **同步 / 反哺 playbook 路径分支化**：`docs/sync-from-upstream-playbook.md` 与 `docs/reverse-sync-playbook.md` 的当前流程改为先选 `agent`，再读写 `templates/<agent>/hooks`、`templates/<agent>/scripts`、`templates/<agent>/settings.json`、`templates/<agent>/rules`，避免按拆分前路径操作失败。

## [0.43.0] - 2026-07-06

### Added
- `[product][repo]` **Codex 专业表达风格**：`templates/codex/AGENTS.md` 新增常驻段，要求 Codex 默认先给结论再给依据，减少空泛安抚和弱判断；新增"默认工作姿态"，明确执行目标时默认读上下文、判断风险、动手、验证并交付；新增"高价值场景输出结构"，要求代码审查先问题、排障先根因、架构判断先推荐结论。BridgeForge 自身根 `AGENTS.md` 同步写入同款规则；`templates/codex/VERSION` 同步升至 `0.14.0`。

## [0.42.0] - 2026-07-06

### Added
- `[product][repo]` **自改审计必须独立**：当审计对象包含本轮 agent 自己刚做的改动，且用户要求"审计 / 复核是否达成需求 / 找遗漏"时，必须启动独立 agent 做二次审计；普通解释、轻量自查、用户未要求审计时不强制。下游常驻规则写入 `templates/claude/CLAUDE.md` / `templates/codex/AGENTS.md`，BridgeForge 自身约束写入根 `CLAUDE.md` / `AGENTS.md`。

### Changed
- `[repo]` **补齐 Codex dogfood 配置层**：新增源头仓库自身 `.codex/`（hooks / scripts / memory / settings），settings hook 命令按 dev 仓库约定使用系统 `python`；根 `AGENTS.md` 中旧大小写写法统一为 `.codex`；移除项目根下无职责的空 `.agents/`。

## [0.41.0] - 2026-07-06

### Added
- `[product]` **引入 agent 分支模板目录**：现有 Claude 骨架整体迁入 `templates/claude/`，并复制出 `templates/codex/` 作为 Codex 骨架起点；Codex 入口文件改名为 `AGENTS.md`，后续按 `/bridgeforge switch <agent>` 方案继续清理 Claude 专属假设。
- `[product]` **新增骨架切换脚本**：`scripts/bridgeforge_switch.py` 随两套模板下发，支持 `claude` / `codex`、`--dry-run`、Git 工作区强保护、切换后验证；脚本只改工作区文件，不自动 stage/commit/push，并拒绝在 BridgeForge 源头仓库自己身上执行。

### Changed
- `[meta]` `SKILL.md` / `README.md` / `INSTALL.md` 的当前模板路径改指向 `templates/claude/`，避免拆目录后现有 Claude 初始化说明引用失效。

## [0.40.1] - 2026-07-06

### Fixed
- `[product]` **`show_state.py` 支持 `VERSION` 兜底版本源**：无 `pyproject.toml` / `setup.py` / `package.json` / `Cargo.toml` 的下游项目，现在会直接读取根目录 `VERSION` 文件显示版本号；已同步 dogfood 镜像 `.claude/hooks/show_state.py`。

## [0.40.0] - 2026-07-02

> **全仓库 harness 体检后的 P0 整批修复 + 2026-07-01 搁置欠账全部收口**。4 维并行审计（hook 可靠性 / token 重量 / agent 行为质量 / v0.39 落地+欠账核查），高影响 finding 逐条人工核验后动手。审计结论：v0.39.0 十二工单交付合格；本批集中修「静默失效」「每轮重复注入」「软闸」三类结构性问题。

### Fixed
- `[product]` **4 个 hook 输入通道静默失效（P0）**：`find_doc_reminder.py`/`memory_lint.py` 只读 legacy 环境变量 `CLAUDE_TOOL_NAME/_INPUT`、`rule_index_check.py`/`rule_size_check.py` 的 PostToolUse 软提醒路径同病——当前 Claude Code 仅走 stdin 时**挂着但永不触发**（此前该根因只修了 `requirements_check.py`，4 个结构同胞漏网；rule 两闸有 pre-commit 兜底、另两个 100% 死）。统一补 stdin-first + env fallback 双通道（与 requirements_check 同范式）。镜像已同步、哈希逐一验证一致。
- `[product]` **templates/settings.json PostToolUse matcher 漏 `MultiEdit`**：`Edit|Write` → `Edit|Write|MultiEdit`，与 `.claude/` 侧对齐——此前下游经 MultiEdit 改代码/memory/rule 时 memory_rebuild/memory_lint/rule 两闸/fallback_smell/requirements_check 全不触发，且 `mirror_drift_check` 只比对 `*.py` 不查 settings.json，无闸可拦此漂移。
- `[product]` **find-memory SKILL 幻影引用（P0 死链+幻觉源）**：引用 v0.36.0 已删除的 `memory_access_tracker.py` 与已废弃的「读取→升回热区」机制（索引实为无热度确定性函数，重建也早从 Stop 移至 PostToolUse+SessionStart）——三重过时一并改写为现行机制描述，防下游 agent 建立错误世界模型。
- `[product]` **collab SKILL 阈值错误引用**：「全局『同一 bug 2 次失败必停』红线」不存在——全局是 CLAUDE §8「前 3 次失败、第 4 次禁动手」（v0.39.0 已统一），改为正确引用，防下游把鬼打墙阈值误记成 2。
- `[product]` **git-sync SKILL 过时 Why（欠账清偿）**：「这俩文件由 Stop hook 每轮重建」双重过时（重建早移 PostToolUse+SessionStart；v0.38.0 起 pre-commit 亦重建并 `git add`）——改写为现行机制，动作本身不变。

### Changed
- `[product]` **6 个 skill 软闸→硬闸（闸硬度红线铺全）**：escalate Step4（等拍板）/ archive-scan Step2（批准归档）/ git-sync（diverged 分支决策）/ plan（确认后实施）/ spinoff Step1（确认派生）/ summary 3b·5（删除候选）全部升级为「⛔ 硬契约：AskUserQuestion 结束当前回合，用户未答前禁动」——此前该范式只落在 debate/collab 两个 skill，其余需拍板处全是描述性软措辞（memory `feedback-skill-gate-hardness` 实证拦不住 agent）。
- `[product]` **3 个信号 hook 输出裸化（每轮重复注入止血）**：clarify_reminder / focus_reminder / find_doc_reminder 此前每轮（find_doc 一轮可 ×N 次）把完整行为指令重发，与常驻层（templates/CLAUDE.md §9.5/§9.6、find-doc skill description）双付甚至三付——改为裸信号 + 动态字段 + 指针，完整契约靠常驻层查。典型 session 省千级 tokens。
- `[product]` **context_warning.py `WINDOW` 注释升级为显式陷阱警告**：默认保持 1_000_000（用户拍板），注明 200k 模型不下调则三级预警**永不触发且无任何报错**——装模板后第一个必核对的旋钮。
- `[product]` **modules.md 占位示例去双语言（解欠账 E-4）**：Step1 的 Python/Rust 并列示例合并为语言无关结构草图、Step2 同步泛化——省常驻行数，不再隐含「只支持两种语言」。
- `[product]` **rule_size_check.py 白名单注释补硬闸警示（解欠账 E-5）**：标注 v0.39.0 起该检查是 pre-commit 硬闸（exit 2），`CROSS_CUTTING_RULES` 白名单按「硬闸白名单」标准维护、增删前掂量误拦/漏拦后果。
- `[repo]` **CLAUDE.md 新增 §5「hook 信号速查」表**：镜像 hook 裸化后，自身仓库的信号响应契约落位（此前 [clarify]/[focus] 等契约只存在于 templates/CLAUDE.md，bridgeforge 自身无常驻契约——dogfood 配套补齐）。
- `[repo]` 7 个改动 hook（4 输入通道 + 2 裸化 + context_warning + rule_size 二改）全部同步镜像 `.claude/hooks/`，`Get-FileHash` 逐一验证两侧一致。

### 欠账收口（2026-07-01 精简会搁置项，全部清账）
- `[meta]` **E-1**（四问豁免机械改动）→ KEEP 收口：不豁免——任务深浅与改动分层正交，且 Q4 已有 mirror_drift 机检，开豁免口子会在漏镜像事故上开洞。**E-2**（workflow §4 收尾自查）→ KEEP 收口，语境无变化。**E-4 / E-5** → 已修（见上）。**行为变更1**（debugging §11 根因预测收紧）→ 判定已被 v0.39.0 debugging §3 verbalized-uncertainty 红线吸收（低置信假说禁包装成结论下手），不再单独改。**B-6**（「适用才镜像」替代提案）→ 不采纳收口：现行「也要挂上 + `[dogfood-exempt]` 豁免语法」已是机检硬机制，07-01 的纯自觉搁置语境不复存在。**git-sync 过时 Why** → 已修（见上）。
- `[meta]` **补记 v0.39.0 漏账**：f6788d3 实际还夹带 8 个 skill（git-sync/collab/summary/sync-docs/archive-scan/debate/escalate/resume）+ 2 个 rule（modules/anti_fabrication）的文本瘦身——均为 `[product]` 层 cosmetic 改动，当时 CHANGELOG 未记，本条补记，下游 sync 时一并覆盖。

## [0.39.1] - 2026-07-02

> 修复下游项目（ClaudeBridgeAssist）实测报告的 P0 假阳性，调查报告见 `docs/调查报告_rule-index-check-HTML注释误判_2026-07-02.md`。

### Fixed
- `[product]` **`rule_index_check.py` HTML 注释误判死链（P0）**：`_detect()` 对 CLAUDE.md 全文正则扫描前未剔除 `<!-- ... -->` 注释块——§2 索引表下方的占位示例注释（如 `<!-- rules/api.md -->`）会被当成真实索引条目，命中不存在的文件后 0.39.0 新增的 pre-commit 硬拦直接 `exit 2`，且不会自愈（触发条件本身不变）。**影响面**：早期 bootstrap、CLAUDE.md 仍带"具体文件名占位示例"写法（当前模板已改用 `<topic>` 占位规避）的存量下游项目，升级到 0.39.0 后每次 commit 都会被卡住。修法：`read_text()` 后先剔除 HTML 注释块再做索引正则匹配。已同步镜像 `.claude/hooks/rule_index_check.py`（逐字一致）。
- `[product]` **修复上条补丁自身的级联误判边界漏洞（对抗测试实测坐实）**：初版补丁用非贪婪 `re.sub(r"<!--.*?-->", ...)`，若 CLAUDE.md 里存在**未闭合**的 `<!--`（人手误漏写 `-->`），非贪婪匹配会跨越到**后面一段不相关注释的收尾 `-->`**，把中间跨越的真实索引行一并当注释删掉，级联触发全新方向的误报（unlisted，漏索引 exit 2），且排查成本高（根因在远处一个漏闭合的注释，不易联想）。改用不跨越注释边界的模式 `re.sub(r"<!--(?:(?!<!--|-->).)*-->", ...)`：若首个 `<!--` 与其后最近的 `-->` 之间又出现了另一个 `<!--`，视为该注释未正确闭合、整体放弃匹配（退化为补丁前的"该注释不生效"，不新增回归），不会级联吞掉中间的真实内容。
- `[product]` **`rule_size_check.py` 同类误判（次级风险由本次对抗测试排查实证）**：`check_rule()` 统计版本号（`v\d+\.\d+\.\d+`）/日期（`20\d{2}-\d{2}-\d{2}`）出现次数时同样未剔除 HTML 注释块，若非白名单 rule 文件在注释里写了教学性质的版本号/日期占位示例（如解释"案例太多要挪 memory"时举例列出多个），会被计入"案例越界"信号误判超阈值——且 `pre_commit()` 同样直接 `exit 2` 硬拦（原调查报告 §3 误判为"不涉及 hard-block"，实测已更正）。修法：统计前先用同一套注释剔除逻辑处理一份副本，仅用于版本号/日期计数，不影响体积/行数/长 code 块等其余检查项。已同步镜像 `.claude/hooks/rule_size_check.py`。
- 三处修复均已用真实脚本执行验证：正常场景（回归修复）、真实死链/未索引护栏（防止补丁削弱检测能力）、真实仓库两侧镜像文件逐字节比对 + `mirror_drift_check.py` 均 exit 0 无 drift。

## [0.39.0] - 2026-07-02

> **Harness 九维方案整批落地**（12 工单 P0-1~P2-11，蓝图 `docs/harness-engineering-design.md`，施工序 `docs/harness-impl-plan.md`）。宪法原则：硬闸只给「机器一眼判死的事实」（近零误伤），软的留给用户判断。
> **dogfood 声明（§1 第 4 问）**：D6 规则闸在 bridgeforge 自身**恒 no-op**（无 `.claude/rules/` 目录）、D8 镜像闸的真实拦截也只发生在下游——两闸仍全量挂上自身 pre-commit，自门控 no-op 正是持续验证产品承诺。

### Added
- `[product]` **新增 pre-commit 镜像闸 `mirror_drift_check.py`（D8，解 E-6）**：dogfood 镜像漂移机检——`templates/hooks/*.py` 有而 `.claude/hooks/` 缺 → **exit 2 硬拦**（二值确定近零误伤）；正文差异（归一化 python 前缀后）→ **仅 stderr 软提示不拦**（合法差异不止前缀，逐字硬闸会误伤）。豁免走 CHANGELOG 顶部 `[dogfood-exempt: <hook> <因>]`（pre-commit 阶段 commit message 尚未生成，只能走 staged CHANGELOG）。下游无 `templates/hooks/` 自门控 no-op。
- `[product]` **新增测试收据 hook `test_receipt.py`（D1-M2，尽量版）**：PostToolUse(Bash) 匹配 pytest/cargo test/npm test/go test/tsc/make 时写一行收据（时间戳+命令指纹+退出状态）落 `.runtime/test_receipts/receipts.jsonl`，声称「测试通过」须指到命令签名匹配+本轮时间窗+exit==0 的收据（CLAUDE §2.5）。**尽量版说明**：实测 Claude Code 成功场景 tool_response 无退出码字段（成功=无声），故分级提取（显式字段→文本 "Exit code N"→无错误标记推断 0→unknown），收据带 `source` 字段自知硬度；同时每次存原始 payload 样本（保 5 份）供后续把提取逻辑改准。**边界诚实**：收据只证「跑过+退出状态」不证断言有效；命令硬卡死则 PostToolUse 不触发无收据（继承 C2 失明，已记账）。
- `[product]` **新增兜底坏味道 hook `fallback_smell_check.py`（D3-M1）**：PostToolUse(Edit|Write) 只抓**裸/宽异常吞掉**一类（裸 `except:`/`except Exception:` 后仅 pass、空 `catch{}`）——近零合法用途的高置信坏味道；合法默认值（`.get(k,d)`/`or []`/`unwrap_or`）、具体异常、诚实 `#兜底` 注释**均不命中**（防误伤/防罚诚实）。`[fallback-smell]` 软提醒 exit 0 非阻塞。
- `[product]` **新增空转弱提醒 hook `stall_warning.py`（D4-M4）**：UserPromptSubmit 多特征**合取**（≥2 轮高 output 零 tool_use + 续接式 nudge 驱动 + thinking 占比代理）才注入 `[stall]`，宁漏不烦。配 CLAUDE.md **§10.5 新节**写明定位：**弱事后代理提醒非实时刹车**（空转发生在上一 assistant 轮内，hook 只能下一轮触发）、对合法长思考轮无区分力、Opus 4.8 无硬开关不保证根治。兑现 antifabrication-framework §7 残余风险 2 的节流信号预留。

### Changed
- `[product]` **D6 规则闸升 pre-commit 硬拦（rule_size / rule_index，读法分治）**：`rule_size_check.py` 加 `--pre-commit` 分支**读 staged blob**（`git show :path`，单文件自洽、把"工作树脏改没 stage"误伤降到零）；`rule_index_check.py` 加 `--pre-commit` 分支**读工作树**（跨文件集合比对，纯 staged 反漏部分暂存死链，注释声明局限）。确定违规 → stderr 可执行修复信息 + exit 2；脚本自身异常一律 exit 0 放行（宁漏不误伤）；豁免走 CHANGELOG 顶部 `[skip-rule-size]`。F4：索引正则 `[a-z_]`→`[\w-]`（`gateway-v2.md` 不再恒判 unlisted）；F2：无 `.claude/rules/` 自门控干净 no-op。PostToolUse 软提醒版保留（同一检测函数双层复用）。
- `[product]` **`.githooks/pre-commit` 升三段闸**（两处逐字镜像）：① mirror 段**置最前**（缺文件 exit 2 先于任何 exit 0，防被末行吞）→ ② rule 闸段（size+index，exit 2 / try 兜底）→ ③ 既有 memory 索引段（永 exit 0 卫生闸）。
- `[product]` **templates/CLAUDE.md 文本红线批**：§9.5 加保守权重（真·新的/大而模糊 → 默认先问，与评估类收口分行不冲淡）；§9.6 增第五类「**方案替换**」+ **N7 大偏离必先说**红线（换方案/扩缩范围先一句话告知）+ **顺手改必告知**红线（非点名改动必主动声明，绝不静默夹带）；§10 软化（CRITICAL「立即拒绝」→「强烈建议 /snapshot、决定权交用户」，HIGH 同口径；软化的是拒不拒活，不是报不报用量）；§2.5 收据口诀升**明文红线**（交付/危险处结论必贴工具返回原文；**假验证澄清**：exit 0 ≠ 验证有效，须说清断言与路径）+ test_receipt 对账指针；§8 lvl1 加「rules-based 验证 > LLM-judge（只补充不裁决）」。
- `[product]` **`context_warning.py` instruction 软化（P0-3b）**：注入文案与 §10 同口径（CRITICAL/HIGH 改"建议+交用户"），判定逻辑与阈值一字未动——消除"文档说建议、hook 喊拒绝"的自相矛盾。
- `[product]` **`debugging.md`**：§6 T1 鬼打墙阈值 ≥2→**≥3**（**解 E-3**，计数唯一权威=CLAUDE §8；**T2 用户回报轴是独立信号，刻意不抬**）、T6 同步指回 §8；§3 补 verbalized-uncertainty（根因未确认须标假说置信度%，<50% 直说不确定）；§5 加量化自证闸（>N 文件/>M 行贴 `git diff --stat` 逐文件说明）+ 顺手改告知红线。
- `[product]` **`memory_rebuild_index.py --from-hook` 追加 `[memory-write]` 纯 ASCII 行（D5-M3）**：memory 写入当轮即可见（PostToolUse 注回 context），兑现「主动写+当场报」透明承诺。刻意不接 `allow_memory_write.py`（PreToolUse 只吐 permissionDecision 注不回）也不接 pre-commit 版（当轮已结束看不到）。
- `[product]` **`meta_rule_design.md` §5/§6.4/§8**：硬度描述同步（「只提醒不阻塞」→「PostToolUse 软提醒 + pre-commit 硬拦，`[skip-rule-size]` 可豁免」）。
- `[product]` **`portability.md` §5** 加镜像红线：templates/hooks ↔ .claude/hooks 必须**文件齐全**（正文差异仅软提示），缺失由 mirror_drift_check 硬拦，豁免须 `[dogfood-exempt]` + Why 指针。
- `[product]` **`config_health_check.py`** DELEGATED 表登记 `hooks-mirror-intact → mirror_drift_check.py (pre-commit)`（开机知晓不亲测，防双重刷屏）；**`githooks_path_check.py`** 提示文案泛化为「提交前闸（含 memory 索引 + dogfood 镜像）」。
- `[product]` **settings.json**（两侧）：注册 `fallback_smell_check`/`test_receipt`（PostToolUse）+ `stall_warning`（UserPromptSubmit）。**deny/ask 危险动作清单经 P0-5 查漏确认无缺项、零新增**——在此明示：该清单（`rm -rf`、`git reset --hard/clean`、`push --force/--delete`、`npm/cargo publish`、`twine upload`、`gh release create`、`docker push`、`Remove-Item` 等 deny + push/rebase/reset/checkout/merge 等 ask）是**产品层承诺**，下游继承的危险动作 PreToolUse 硬闸。
- `[repo]` **P0-1 dogfood 欠账清偿**：`.claude/hooks/` 补齐 4 个缺失镜像（`show_state.py`/`rule_index_check.py`/`memory_lint.py`/`find_doc_reminder.py`）+ 对齐 `clarify_reminder`/`context_warning`/`requirements_check` 正文漂移 + `.claude/settings.json` 补注册（系统 python 前缀）。自此 snapshot 开场提示（`[snapshot]`）在自身也生效。
- `[repo]` memory `ghost-wall-threshold-conflict` 标已收口（P0-4 解 E-3）。
- `[meta]` 新增 `docs/harness-engineering-design.md`（九维设计 v1，含对抗批评 11 项+verify 修正融入）+ `docs/harness-impl-plan.md`（12 工单施工序）+ `docs/调查报告_AB对话_空转与幻觉_2026-07-01.md`（外援调查核实与纠偏记录）。
- `[meta]` D9（人机沟通）确认零产品改动：三条沟通偏好归用户级全局 CLAUDE.md（skill/advisory + user-global），不进 templates。

### 验证
- `[repo]` P1-6 下游模拟 dry-run：临时造 `.claude/rules/` + 超标 rule + 索引，实测 exit 2 真拦、`[skip-rule-size]` 真放行、脚本异常 exit 0（验后清理）。P1-7 启闸前现场重验零缺文件漂移（批评⑪紧前置守卫）。
- `[repo]` P2-11 自验：模拟成功 payload → `exit=0 source=inferred`；失败文本 → `exit=101 source=text`；非测试命令/词边界 near-miss → 静默 no-op；本会话热加载后真实 Bash 调用已落收据，真实 payload 样本确认 `tool_response={stdout,stderr,interrupted,isImage,noOutputExpected}` **无退出码字段**（尽量版分级提取的前提被实测坐实）。

`templates/VERSION` 0.9.0→0.10.0。

## [0.38.0] - 2026-06-30

### Added
- `[product]` **新增 git 原生提交闸 `.githooks/pre-commit`（根治"sync 完 `_stats.json` 又脏"）**：提交前确定性重建 memory 衍生索引（`_stats.json` / `MEMORY.md` / `MEMORY_COLD.md`）并 `git add` 纳入本次提交，**杜绝"花名册欠账"溜过任意提交路径**（git-sync / 手动 `git commit` / IDE 提交全拦得住）。脚本 `#!/bin/sh` + python 自动探测（下游优先 `.venv`、自身回退系统 python）→ **两层逐字一致**，比 `.venv`-vs-系统硬编码更干净地满足 dogfood。卫生闸非质量闸：任何异常 `exit 0` 不阻断提交。
  - `[product]` **新增 SessionStart 自愈 hook `templates/hooks/githooks_path_check.py`**：`core.hooksPath` 是 local config、clone 不带、每机要单独设，散文 README 拦不住"忘了设"。本 hook 每次开机检查——有 `.githooks/pre-commit` 而 `core.hooksPath` 未指向它就自动 `git config --local core.hooksPath .githooks`，让"clone 即生效"。仿 `memory_junction_check` / `enforce_no_effortlevel` 自愈模式；自门控：无闸文件 / 已设好 → 静默 no-op。已注册进 `templates/settings.json` SessionStart。
  - `[product]` **新增 `.gitattributes`**：强制 `.githooks/**` 以 LF 存储+checkout。**Why**：git 原生 hook 由 sh 执行，CRLF 会让 shebang 变 `/bin/sh\r` 直接报错失效（Windows autocrlf 高发坑）。

### 根因 / 决策
- **病灶**：v0.37.0 那次提交漏带 `_stats.json` 的两条 `created_at` 登记（花名册欠账）→ 该次 commit 一切看似干净，但下次开机 `memory_rebuild_index.py`（SessionStart 兜底）点名时补登欠账 → 工作区凭空变脏。**根因不是 git-sync，是"提交前重建"只挂在 git-sync skill 第3步这道软步骤上，手动/IDE 提交能绕过。**
- **力度选硬闸门**（用户拍板）：把"提交前重建"从 skill 软步骤升级为 git 原生 pre-commit，对**所有**提交路径生效，不依赖记得用 /git-sync。git-sync skill 第3步**保留**（事实上的双管齐下、过渡期兜底，无害）。
- `[repo]` 已即时对本 dev 仓库执行 `git config --local core.hooksPath .githooks`，闸已生效；端到端 dogfood 验证：`sh .githooks/pre-commit` 自动重建并 stage 了 v0.37 遗留的 `_stats.json` 欠账。
- **dogfood 镜像（CLAUDE.md §1 第4问）已吃**：`.githooks/pre-commit` 与 `.claude/hooks/githooks_path_check.py` 同步装进自身 `.claude/`，自身 SessionStart 已注册（用系统 python）。

`templates/VERSION` 0.8.0→0.9.0。

## [0.37.0] - 2026-06-30

### Added
- `[product]` **新增常驻红线 `templates/rules/anti_fabrication.md`（防 AI 幻觉资源 R1–R5）**：源自 CausisRiskSuite 一次「幻觉文件名 → 工具空转 → 纯文字嫁祸」真实事故，经两轮跨项目对抗式 debate 反哺。R1 用前必验存在 / R2 验不到如实说缺啥并停下 / R3 禁编造资源来源 / R4 禁把失败甩锅给用户·工具·编辑器没做过的事 / R5 先认再改。**始终加载**（幻觉不挑 path → 无 frontmatter 触发器、常驻；口诀写在 rule 开头每轮在场）。新增「始终加载」rule 已对齐 meta_rule §4.1。
  - `[product]` CLAUDE.md §2 规则索引登记一行（`rule_index_check` 要求）。**未在 CLAUDE.md 正文新增小节**——该文件已 274 行、超 meta_rule ≤200 红线，改由「始终加载 rule」承载常驻，不加剧超标（CLAUDE.md 瘦身是既有债，另案处理）。
- `[meta]` **新增 `docs/antifabrication-framework.md`**：四层纵深框架（L1 诱因 / L2 认知 / L3 行为 / L4 IO）+ 通用壳 vs 项目填充切分判据 + C1 deny / C2 超时哨兵 / Stop 甩锅自检三个 hook 的完整设计与「为什么都不进产品层」决策留痕。
- `[meta]` 新增 `docs/examples/antifab-deny-hook.py`：C1 四-gate deny 参考脚本（宿主无关纯函数 + 3 个项目配置占位 + 空配置降级），**非出厂 hook、不注册、不自动运行**，下游撞痛点自取。

### 决策（两轮 debate 定案，详见 `docs/handoff_2026-06-30_antifabrication-playbook*.md`）
- **三个 hook（C1/C2/Stop）一律不进 `templates/hooks/`**：C1 误伤是硬停 + 价值零件 `REAL_SOURCE_HINT` 在 templates 恒空 + dogfood 先伤自己；C2 对真·硬卡死失明（PostToolUse 不触发）+ 软超时与 C3 重叠 + 阈值误刷噪声；Stop 需每回合 LLM judge 太贵。→ 产品强制层只进零误伤的 C3 红线，hook 设计降级 docs。
- **据此本次不新增任何 hook、不动 `settings.json`、不触发 dogfood 镜像**（CLAUDE.md §1 第 4 问不触发）。
- 残余风险诚实标注：纯文字嫁祸（L3）是 0 工具调用，任何 hook 都看不见，全靠 C3 常驻 + R5 反激励压低概率，无事后补救。

### Changed
- `[product]` **templates/CLAUDE.md 瘦身 275 → 193 行**，回到 meta_rule §5 的 ≤200 行红线内。**坚守 redline-placement**：所有 always-on 行为红线（§2.5 工具选择 / §8 鬼打墙 / §9 主观体验问 / §9.5 clarify / §9.6 focus / §10 ctx-budget / §11 文档管理）的「禁止 / 必须」条款逐条保留、语义不动（含 §8 鬼打墙阈值不碰），只压缩解释性长句；砍的是占位注释、§6 与 `portability.md` 重复的可移植性陷阱详情、§5 派生索引实现细节（均非红线）。顺带修掉 §2 注释里 `rules/api.md` 示例触发 `rule_index_check` 假死链接的老毛病（改 `rules/<topic>.md`）。

`templates/VERSION` 0.7.0→0.8.0（本次瘦身并入同版，未再 bump）。

## [0.36.0] - 2026-06-28

### Added
- `[product]` **新增 SessionStart 开机配置体检 hook `config_health_check.py`**（只读、纯 ASCII、全绿静默）。背景：harness「两大 bug 复发」调查（中文乱码 / 工具回传抽风致跑偏）发现 v0.28.1 的 PYTHONUTF8 env 修复从用户 `~/.claude/settings.json` 悄悄丢失，而 warn-only 的 utf8-guard 喊了却没人接 → 需要一个把骨架必要配置「每次开机照单体检」的统一入口。
  - `[product]` **定位「体检仪」：只报告、不自动修**——照清单核对，不达标只打一行纯 ASCII 报告 + 修复提示，修不修由用户决定。理由：本 hook 复印进所有下游、每机每次开机跑，一个会自动改配置的 hook = 在别人机器上自作主张埋雷（沿用 2026-06-25 encoding-fix-scope debate 决策）。输出纯 ASCII 是硬约束：万一缺的恰是 PYTHONUTF8，用中文报警自己会糊成乱码（正是它要查的病）。
  - `[product]` **utf8 承重柱检查归位**：原 `_utf8_mode_guard()`（查 `sys.flags.utf8_mode` 事实值）从 `memory_junction_check.py` 的「顺带搭车」中抽出、移入本 hook，消除职责混挂；告警前缀 `[utf8-guard]` → `[health-check]`。
  - `[product]` 初版 ACTIVE_CHECKS 两项：① **PYTHONUTF8**（UTF-8 Mode 真生效没，GBK Windows 乱码承重柱）；② **user/project settings.json 是否合法 JSON**（坏掉会静默架空 hooks/permissions）。其余必要配置（memory junction 自愈 / 项目级 effortLevel 剔除 / 用户级 skill 同步）已有专职 hook 兜，登记进文件内 `DELEGATED` 备查、**不重复测**（避免双重刷屏 / 时序竞争）。`ACTIVE_CHECKS + DELEGATED` 即「骨架要求哪些配置 + 谁来保证」的**单一事实源**，新增必要配置只改这一处。
  - `[repo]` dogfood 镜像同步进自身 `.claude/`（脚本逐字一致，hook 命令用系统 `python`）；自身 `memory_junction_check.py` 同步移除 utf8 guard。注册为两边 settings.json 的 SessionStart **首个** hook。`templates/VERSION` 0.6.0→0.7.0。

## [0.35.0] - 2026-06-27

### Changed
- `[product]` **debate / collab 重构为渐进对齐六步流程 + 四项护栏（A/E/G/D）**，并经 L1 静态审计 + 独立 agent 复审后修补闸硬度。
  - **六步流程**（两者统一）：`闸① 引导发问 → 闸② 复述确认 → 研读(可追问) → [辩论/拆分大纲(闸③)] → 执行 → 收尾`；每道闸改为「⛔ 硬契约」格式，明确必须以 **AskUserQuestion 调用结束回合**、用户未回复禁止任何后续动作，防止三道闸被一口气连跑。
  - **A**（debate）：轮次上下文机制改为 SendMessage 续接同一 A/B agent（而非每轮新起），补了 id 取法（spawn 返回值）→ 存 MD 头部 → 续接失败降级路径。
  - **E**（collab）：子任务失败重试上限共 2 次即停（比全局「2 次失败必停」红线更严）。
  - **G**（两者）：轻量出口给粗判据（≤2 文件），collab 在 Step3 研读后补出口检查点。
  - **D**（collab）：整合后独立 review agent 的三项输入（目标/接口约定/文件清单）明文定义，硬性要求独立 Read 实际代码/跑 diff，不得只复核主 agent 文字结论。
  - debate 另修：collab 建议转向、agentId 字段硬编码改为描述性措辞（harness 演化安全）。

## [0.34.0] - 2026-06-27

### Changed
- `[product]` **Memory 索引系统：废弃艾宾浩斯热度评分，改为确定性事件驱动**（templates/VERSION 0.5.0→0.6.0）。根因：热度分 `exp(-days/S)` 含 `today` 变量 → MEMORY.md 是时间的函数 → 没人改 memory 也每天自发变脏，与用户硬需求「git-sync 后工作区干净、多机不莫名冲突」**数学上不兼容**；辅以实测 `_stats.json` 长期仅 1 条记录、17 条全进 Top-40 = 伪热度、属过早优化。双 agent 两轮辩论定案，见 [docs/debates_2026-06-27_memory-untrack.md](docs/debates_2026-06-27_memory-untrack.md)。决定性技术事实：git 只比对内容、不看 mtime，故脏的唯一来源是「内容自发变化」。
  - `[product]` MEMORY.md / MEMORY_COLD.md 改由 `memory_rebuild_index.py` 按「memory 文件集 + created_at + pinned」**确定性生成**（无访问热度、无日期戳）→ 不碰 memory 时逐字不变、工作区不自发变脏；多机同规则同输入算出一致结果、不冲突。
  - `[product]` 排序：pinned 置顶 + created_at 倒序（新增在前），主索引满 `ACTIVE_N=40` **自动滚入冷区** —— 冷热维护全自动、不需人工决定，只在真增删 memory 时变（本就该提交）。
  - `[product]` 触发时机从 Stop 链路移到 **PostToolUse(Write/Edit memory，`--from-hook` 过滤防自触发) + SessionStart 兜底**；memory 写入当下即同步索引 → sync 后对话结束不再弄脏。
  - `[product]` **删除**：`memory_access_tracker.py`（访问追踪 hook）、`memory_bootstrap_cold.py`（衰减冷启动工具）、`_stats.json` 的 `session_dates`、MEMORY_COLD.md 日期戳。
  - `[repo]` dogfood 镜像同步进自身 `.claude/`（脚本逐字一致，hook 命令用系统 `python`）；删自身 `memory_access_tracker.py` + 简化 `_stats.json`；junction 那条 memory 的 description 去 YAML 引号转义（修提取半截）。
  - `[meta]` 重写 [docs/memory-scoring-design.md](docs/memory-scoring-design.md) 为新确定性设计；`templates/CLAUDE.md` §5「热区」措辞改「主索引」+ 补确定性说明。

## [0.33.0] - 2026-06-26

### Changed
- `[product]` **`templates/CLAUDE.md` 三处手填占位（§1 架构红线 / §3 快速命令 / §7 项目结构）从"一句话提示"升级为"带分类骨架 + 多语言示例的填写引导"**。原占位只有一句"填好后删此注释"，新建项目时下游(尤其架构红线)常对着空白发懵、被晾着不填。现在：① §1 给"数据流方向 / 容量上限 / 时序约束"三类各一行填空 + 例句，并提示"不确定就先写你最怕 Claude 踩的那条"；② §3 给"构建/运行/测试/检查"四行命令表 + 跨语言示例(cargo｜npm｜python)；③ §7 给"`ls` 看顶层 → 逐目录补一句职责"的格式 + 多目录示例。引导仍包在 HTML 注释里，填完即删，不污染长期 context。
  - 不动 SKILL.md 逻辑 / 不加 hook：纯模板文本增强，下游 sync 后下次 init 即生效。背景见本轮对话（用户实跑 `/bridgeforge` 时反馈"这三处对新手不明朗"）。

## [0.32.1] - 2026-06-26

### Fixed
- `[product]` **git-sync 根治"sync 完 memory 又被改脏、被迫再 sync 一次"**。根因：`MEMORY.md` 热区 / `MEMORY_COLD.md` 是由 Stop hook 在**每轮回答结束后**自动重建的衍生产物（数据源 `_stats.json` 在会话中持续累积访问日期，但重建有 5min 节流）；git-sync 提交的往往是"上一次重建的旧产物"，提交**之后** Stop hook 再重建一次 → 工作区被新产物顶脏 → 用户只能再 sync 一次（机器人永远等你转身走才动手，成果永远赶不上那张照片）。
  - 修法（"先重抄、再拍照"）：`skills/git-sync/SKILL.md` 在 `git add` **之前**新增一步——若存在 `.claude/scripts/memory_rebuild_index.py` 则先跑它重建索引，使提交进去的就是最新态；提交后 Stop hook 同日、同 `_stats.json` 再重建产出字节一致 → 工作区干净。脚本不存在则静默跳过（非 bridgeforge 系下游无此机制，不报错）。
  - 已镜像进用户级副本 `~/.claude/skills/git-sync/SKILL.md`（实体副本非 junction，`/git-sync` 实际跑它，故当场同步使修复立即生效）。

## [0.32.0] - 2026-06-26

### Added
- `[product][meta]` **反漂移 / 反工具污染红线补强（"评估仓库能否公开"会话跑偏调查的落地）**——一次评估问被做成全量脱敏执行（实则全程 dry-run、一字未落盘）+ 工具"传结果线"概率性抽风（重影 / 命中 0 假空 / 幻影文件名 `clouddev` / 含大段中文的 `AskUserQuestion` 入参转义炸成 `__unparsedToolInput`）的复盘后，往 `templates/CLAUDE.md` 补 4 条软约束红线。**经多 agent 结构化辩论裁定：产品层 hook 加固性价比为负**（招牌污染标记一个对 `AskUserQuestion` call 隐形、一个在本 repo 高误报、一个时序慢一拍，正中 v0.28.2 focus 重武装"噪声诱导跑偏"覆辙），故**零新 hook、零 settings 改动**，只补软约束文本。
  - `[product]` **`templates/CLAUDE.md §2.5`**：① 禁止自拼 `for`+管道 / 多命令 `;` 串做大检索 / 大输出（一律受控 `Grep`/`Glob` 单命令）——这是传话线抽风的首要触发器；② **红线·脏数据上不拍板**——返回现重影 / 命中 0 与预期矛盾 / 不认识文件名 / `__unparsedToolInput` 时禁止直接下结论或改盘，先 `wc -c`/`git status`/受控 `Grep` 二次验真（口诀"dry-run 报的 N 处 ≠ 已改 N 处"——调查中母对话正因误信 dry-run 数字而把"已改 81 处"传错）。
  - `[product]` **`templates/CLAUDE.md §9.5`**：① 新增第三条红线——评估 / 咨询 / 可行性类问（"能不能 / 有没有 / 该不该"只要结论的诊断问）答完即收口，**禁止**主动把建议包装成 `AskUserQuestion` 执行菜单（要不要执行由用户下一条 prompt 决定）；同时收窄原第一分支为"已表达执行意图、但范围模糊"的需求——堵住本次跑偏的真门（评估被悄悄递成执行菜单、用户顺手点选）；② `AskUserQuestion` 选项 / 入参必须短、纯文本、避免大段中文（长中文→`\u` 长串是 `__unparsedToolInput` 转义炸的直接诱因）。
  - `[meta]` **`docs/design-rationale.md §7`**：记一条 focus 对"点击背书的 scope 升级"结构性盲区的"按设计不修"指针（focus 是 `UserPromptSubmit` hook 抓不到"点击选项"那一跳、且重武装重蹈 v0.28.2 覆辙），改由 medium baseline + §9.5 红线 + `/focus` 被动入口三层兜底——作为后人不再重提此议的指针。
  - 背景：病根（Opus 4.8 答完不收口 / 思考空转）不在本轮范围，已由 `[0.31.0]` effort 治理（`medium` baseline）接管；本轮只补 medium 够不着的"工具传话抽风"与"clarify 把评估推成执行"两条具体路径。调查 + 辩论存档见 `.runtime/spinoff/live-offtrack-FINDINGS.md`。

## [0.31.0] - 2026-06-26

### Changed
- `[product][repo]` **effort 治理反转：项目层不再钉 `effortLevel`，改由用户级全局统一管 + 会话级临时提升 + SessionEnd 自动还原**。跨下游 transcript 法医调研确认"token 空转无回复"主因 = Opus 4.8 高 effort 下"拿到信息不收口"（每拿到一点工具结果 / 一句琐碎 prompt 就思考到 64k 输出上限被 `max_tokens` 截断、全程无字；触发分布：普通工具结果 61% / 琐碎 prompt 10% / 报错仅 ~6%）；而项目级 `effortLevel`（合并优先级 Project > User）会把"顺手的 `/config` slider / `/effort`"顶掉 → 用户"调了不生效、被锁在 high 难降"。
  - `[product]` **`templates/settings.json`**：删除 `effortLevel: high`（不再随骨架下沉）。
  - `[product]` **新 hook `enforce_no_effortlevel.py`（SessionStart）**：自愈式强制从项目 `.claude/settings.json` 剔除 effortLevel（原子删 + `.bak`，无则静默 no-op）——拦下游 sync/clone/手加"流入"，否则整套全局机制被架空。**机检 hook 替代散文 rule（本骨架特征）**；已 dogfood 镜像进 `.claude/hooks/` + 注册。
  - `[product]` **`templates/rules/portability.md §1`**：删除旧"项目级**应当**写 effortLevel"红线，改为一行反向例外 + 指向 enforce hook（不再用散文约束）；§3 表述同步更新。
  - `[repo]` **dogfood**：本仓库 `.claude/settings.json` 同步删除 effortLevel（与瘦后模板一致）。
  - **用户级（不下沉，仅本机）**：`~/.claude/settings.json` baseline 设 `medium` + 新增 `SessionEnd` hook `reset_effort.py`——关对话把 effortLevel 原子还原回 medium（json 读改写 + temp+os.replace + `.bak`），使"临时 `/effort high` 顶一格、用完自动还原"成立。背景：平台无内建 effort 自动还原，且普通 `/effort` 落盘是已知 bug #53331（唯一会话级是 `ultracode`=xhigh+workflows）。**此 hook 为个人全局，刻意不进 `templates/`**（否则 N 个下游抢改同一全局文件）。
  - **下游迁移**：sync 后各自删除项目级 `.claude/settings.json` 的 effortLevel，回落用户级全局（用户逐一在下游侧确认）。
  - memory：新增 `effort-config-layering`（配置覆盖关系 + 反转决策全图）。

## [0.30.0] - 2026-06-25

### Changed
- `[product]` **产品层第一类瘦身（无争议纯外置/压缩，护栏零丢失）**——目标：让下游每轮常驻 context 的文件变瘦。手法限定外置/去重/压缩三种，不动任何"必须/禁止"红线效力（已逐条 grep 当前内容验证保留）。
  - **`templates/CLAUDE.md` 325 → 259**：§9.5/§9.6/§10 三个反漂移 hook 信号的「机制分工表/配置/调参/豁免论述」等低频细节外置到新 rule；§2.5 工具、§5 junction、§9 场景示例就地压缩。**可执行红线全部留在正文**（漂移分类表【前置/附加/无关/正当深入】、四级信号行为表 + CRITICAL 红线、"绝不硬删可能含数据的目录"等）。§8 鬼打墙、§11 文档分层**刻意未动**（留给第二类 debate：跨文件红线该收敛到常驻层还是触发层）。
  - **新增 `templates/rules/anti_drift_hooks.md`（64 行）**：承接上述外置的 hook 机制/配置细节，`paths:` 触发 `.claude/hooks/**` + `.claude/settings.json`（编辑 hook/settings 时才加载）；CLAUDE.md §2 规则索引表已登记。
  - **`skills/find-doc/SKILL.md` 170 → 97**（高频自动调用 skill，注入成本最高）：Step 3 输出模板 + Step 4 映射 SOP 外置到 `references/{output-format,map-reminder-sop}.md`（仿 summary/deep-steps 范本，命中时才 Read）；Step 4 三条禁止护栏随外置文件原样搬运并标注"不可丢"。repo 源与 `~/.claude/skills/find-doc/` 部署副本逐字一致（dogfood）。
  - **`templates/rules/` 三件就地压缩**：`workflow.md` 243→213（§9 版本号 SemVer 通识教程 + commit 举例压缩，保留 bump 红线 + §9.7 禁止 + §9.8 hook 兜底）；`portability.md` 244→192（§4 三语言包安装"正确❌错误✅"对照大块压成各一行最小命令，红线全留）；`meta_rule_design.md` 227→206（§3 的 >20 行教学示例压成 ≤10 行骨架——消除"自打脸"：正撞它自己 §7「>20 行示例搬 doc」红线；§5 量化阈值等地基判据一字未动）。
  - **背景**：本轮溯源发现"每次敲长 skill/常驻长文档把 context 顶过 auto-compact 阈值"是高频痛点的帮凶（见 `[0.29.2]` summary 瘦身）。第二类「跨文件红线去重」因涉及"红线放常驻层还是触发层"的护栏覆盖权衡，单独走 debate（见下条）。
- `[product]` **第二类跨文件红线去重——doc 分层组落地（debate 驱动，鬼打墙组暂缓）**。两轮 debate（`docs/debates_2026-06-25_redline-placement.md`）的核心结论：三个诊断 agent 报的"红线重复"实为**骨架（粗粒度红线）+ 细节（场景操作）的分工**，meta_rule §4.3 禁的是「逐字复制正文→漂移」而非分工式共存。切分判据：**「这条约束在不触发该 rule 的轮次也可能被违反吗？是→红线骨架常驻 CLAUDE.md / 否→场景细节沉触发层」**，红线断言一律不降为纯 pointer。
  - **doc 分层组**：`CLAUDE.md §11` 259→251——保留红线骨架（六层目录树 + 5 条禁止/强制 + 立场句），删「为什么是红线」3 段论述（Why 正文改向触发层）。`workflow.md §5.5` 213→210——删与 §11 逐字重叠的「强制项表」正文（消除双份漂移），改承接 Why 正文 + 操作细节，顶部加"红线条文见 §11"指针。常驻层留断言、触发层留 Why+操作，无逐字重叠。
  - **鬼打墙组暂缓**：debate 暴露 `CLAUDE.md §8`(连续 3 次/第 4 次硬停) 与 `debugging.md §6 T1`(≥2 次升级) **阈值冲突**。统一阈值=改变 agent 行为，属行为变更，**不混进"只省体积不改效力"的瘦身**；用户选"不修改"。该组整组去重（删近义句+加 pointer）与阈值统一打包待单独决策，记入 memory `ghost-wall-threshold-conflict`。
  - 注：CLAUDE.md 当前 251 行仍超 `meta_rule §5` 的 ≤200 软红线，但剩余超额主要在 §8 鬼打墙（暂缓组），且 debate 判定"宁可超 200 也不误伤红线骨架"——降回 200 待鬼打墙组决策时一并完成。

## [0.29.2] - 2026-06-25

### Changed
- `[product]` **`/summary` skill 瘦身：主模板 135 → 55 行（注入 context 省 59%）**。把两块**低频条件触发**且最长的步骤——步骤 3b（rule 写入后 memory 对账）+ 步骤 5（TODO 清理完整流程）——外置到新文件 `skills/summary/references/deep-steps.md`，主模板各步只留**触发条件 + 一句话要点 + "命中时先 Read 附属节"**。高频步骤（2/6/7）完整保留主模板。背景：每次敲 `/summary` 都把整套七步长文本注入 context，是把占用顶过 auto-compact 阈值、导致"summary 真正执行前就被压缩、丢原始细节"的帮凶之一（溯源见本轮对话：最大膨胀 +31 行来自 v0.24.0 加的"防 memory 膨胀"对账流程——反膨胀规则自己成了膨胀源）。
  - **安全 SOP 不丢**：主模板明确指示触发该步前先 Read 附属节，详细约束（"删 memory = 4 处同步"误删安全网等）原样保留在 `references/deep-steps.md`。
  - **外置安全性已验证**：`skill_sync_check.py` 用 `os.walk` 递归整个 skill 目录做内容哈希（非只看 `SKILL.md`），故附属文件会被同步机制一并搬运/比对到下游与 `~/.claude/`。
  - **dogfood**：repo 源 `skills/summary/` 与部署副本 `~/.claude/skills/summary/` 两份（SKILL.md + references/deep-steps.md）逐字一致，`diff` 已验证。

## [0.29.1] - 2026-06-25

### Added
- `[product]` **`memory_junction_check.py` 加 UTF-8 Mode 承重柱自检 `_utf8_mode_guard()`**（`templates/hooks/` + 自身 `.claude/hooks/` 双份 dogfood）— SessionStart 时查 `sys.flags.utf8_mode`（**事实**，不被文件顶部 `stdout.reconfigure` 掩盖），仅 OFF 时打**一行纯 ASCII** 告警提示补 `env.PYTHONUTF8=1`，稳态静默。守的是唯一承重柱（PYTHONUTF8 是否生效），**不**巡逻与之功能重叠的 per-hook `reconfigure`。背景：中文 hook 输出在 GBK Windows 上糊成 U+FFFD 注入 context、曾高频致 agent 跑偏（8.5 万字符 / 横跨所有下游；根因 + 调查 + 反过度加固决策见 memory `utf8-garble-rootcause` + `docs/debates_2026-06-25_encoding-fix-scope.md`）。

### Changed
- `[product]` **`templates/CLAUDE.md` §6 换机 checklist 加一行可选 git UTF-8 配置**（`core.quotepath=false` + `i18n.logOutputEncoding/commitEncoding=utf-8`）— 中文 Windows 下避免 git 中文文件名 / log 显示乱码；`.git/config` 不随 clone 走，换机需重跑。本仓库已 `--local` 应用。

> **刻意未做（经两轮 debate 砍掉镀金项）**：未新增独立守卫 hook、未加 portability rule 红线。因 PYTHONUTF8（v0.28.1 已落）是 env 层**透明**兜底，新 hook 作者无需记忆任何编码约束 → rule 红线无可执行内容；为 0 复发问题动产品层会把安慰剂式加固复印进所有下游（幸存者偏差陷阱）。真病已治本，本版只补"承重柱自检 + 记账"。

## [0.29.0] - 2026-06-25

### Changed
- `[product][repo][meta]` **项目 / skill 更名：`setup_agent` → `bridgeforge`**：
  - **更名说明**：自本版（v0.29.0）起，本骨架库 / skill 由 `setup_agent` 更名为 `bridgeforge`（`bridge` = 作者署名，亦取"跨接"之意——把一套上游骨架跨接到每个下游项目；`forge` = 锻造工厂，对应本仓库"协作骨架工厂"的自定位）。**历史 CHANGELOG / `.claude/memory/` 等流水账保留旧名 `setup_agent` 不改写**——本注脚是唯一的更名锚点。
  - **改了什么**：活文档 + 活代码共 252 处 `setup_agent` 字样替换为 `bridgeforge`，覆盖 README / INSTALL / SKILL.md / CLAUDE.md / docs/ 活 playbook / `skills/*/SKILL.md` / `templates/`（含 `templates/hooks/skill_sync_check.py` 的 junction 名硬编码 `~/.claude/skills/bridgeforge/` + SKILL.md 里版本戳文件名 `.bridgeforge_version`）/ 自身 `.claude/hooks/`。
  - **接口契约变更（下游必读）**：skill 名 `/setup_agent` → `/bridgeforge`，junction 名 `~/.claude/skills/setup_agent` → `~/.claude/skills/bridgeforge`，版本戳 `.claude/.setup_agent_version` → `.claude/.bridgeforge_version`。**下游每个项目需重建 junction + 改调用习惯 + 改版本戳文件名**（正向同步红线，属 `[product]`）。
  - **故意未改**：① `memory_junction_check.py` 的两处 `setup_agent` 是讲解哈希下划线 bug 的教学例子（`bridgeforge` 同样无下划线，改了会让"本仓库正中此坑"的注释自相矛盾）→ 保留；② 历史流水账（本文件旧条目 / `.claude/memory/*` / dated docs）按"保留旧名 + 本注脚"决策不改写。
  - **大小写约定（刻意，非不一致）**：人面向用 PascalCase（GitHub repo `BridgeForge` + 本机目录 `D:\Quant\BridgeForge`），机器面向用小写（skill 命令 `/bridgeforge`、junction `~/.claude/skills/bridgeforge`、版本戳 `.bridgeforge_version`、hook 硬编码）。同"仓库 VSCode → 命令 code"惯例。文档里 clone URL / dev-dir 路径示例用 PascalCase，其余小写。
  - **未在本仓库内完成、需手动收尾**：GitHub repo 改名为 `BridgeForge` + `git remote set-url`、本机目录 `D:\Quant\setup_agent` → `D:\Quant\BridgeForge`、memory 系统路径哈希迁移（`d--Quant-setup-agent` → 新哈希，memory 数据 junction 在 repo 内随目录走、hook 下次 session 自愈）、本机 + 下游 junction 重建。

---

## [0.28.2] - 2026-06-25

### Fixed
- `[product]` **`templates/hooks/focus_reminder.py`(+ setup_agent 自用副本)防漂移 `[focus]` 措辞中性化 —— 治"反漂移机制自己变漂移源"**：
  - 原措辞「本会话原始任务:「X」。这轮是否仍在推进它? … 别闷头做 … 前置阻塞→/spinoff …」是**审问 + 催办**语气,默认假设"用户漂了",诱导模型把当前正当的新任务误判为漂移 → 跑去谈旧任务 / 大谈该不该 `/spinoff` 交接 → **答非所问**
  - 根因:hook 把"会话第一条实质 prompt"死锁为唯一 anchor,但真实会话里做完一件事后自然转入新任务是常态;陈旧 anchor + 催办措辞凑一起,在 `FOCUS_MIN_TURN` 后周期性把模型带跑
  - 改为**中性措辞**:显式声明"用户转入新任务是【正常的】,默认忽略本提示",仅当模型察觉自己确实在【不知不觉】偏离一个用户没喊停的未完成任务时才按 §9.6 分类响应。把默认姿态从"纠偏"翻成"忽略"
  - 单文件 `print` 块改动,零连锁(不碰 `/focus`、`/spinoff` skill、不改触发逻辑 / 存储)。下游 StratusAgent 已实测复现 + 修复后 5 项验证通过
- `[product][meta]` **全局统一 hook/script 的 UTF-8 兜底 `except` 写法 —— 消除冗余 + 修正 v0.27.0 回归**：
  - 27 个 `.py`(templates 16 + 自用 `.claude` 11) 顶部 UTF-8 兜底块里的 `except (AttributeError, Exception):` 统一改为 `except Exception:` —— `Exception` 本就是 `AttributeError` 父类，并列纯冗余，**行为完全等价**
  - 同步修正 `docs/repositioning-from-StratusAgent-2026-06-24.md` 里把冗余写法定为 normative 规范的表述：v0.27.0 (见下方条目) 曾把两个 hook 改成 `except Exception`，但被后续 UTF-8 批量补丁按旧规范覆盖回去 → **悄悄回归**，本次连同规范源头一并纠正
  - 纯 refactor，零行为变更；27 文件 `py_compile` 全过 + dogfood 双份逐字一致复验

---

## [0.28.1] - 2026-06-24

### Fixed
- `[product]` **`templates/scripts/audit_user_allow.py` 5 处 bug 修正（F3/F4/F7/F8/F9/F10/F12）**：
  - F3: 删除 `--fix` 功能（交互式删条目）——违反 C3 spec"只报不删"红线；同步修 `SKILL.md` 去掉 `--fix` 用法说明
  - F4: Windows 路径正则改为只认反斜杠 `[A-Za-z]:\\`，跳过含 `://` 的 URL（原 `[A-Za-z]:[/\\]` 误报 `https://`）
  - F7: IPv4 正则加 0-255 octet 约束 + 要求网络上下文（原正则误报 `pip install foo==1.2.3.4` 版本号）
  - F8: 循环内加 `isinstance(entry, str)` 守卫（原代码遇 null/数字/对象 allow 条目直接 TypeError 崩）
  - F9: `allow_list` 取出后加 `isinstance(allow_list, list)` 检查（原代码遇 dict 类型静默遍历 key 出乱报告）
  - F10: Unix 路径正则改为白名单制（原 `/[a-z]+/[A-Za-z]` 误报 `/usr/bin/env`、漏报 `/Users/**`）
  - F12: 删除死代码 `or data.get('allow', [])` 分支
- `[repo]` **`.claude/hooks/` 4 文件补 dogfood 镜像（F1+F2，C7 红线收尾）** — `context_warning.py` / `allow_memory_write.py` / `memory_access_tracker.py` / `target_cleanup.py` 整体覆盖至 templates 版本：补 UTF-8 reconfigure（C7 之前只改了 templates/，.claude/ 镜像 0 处改动）；同步 `target_cleanup.py` 从旧 L1-only (174行) 升级至 L1+L2 deps 裁剪 (296行)。
- `[repo]` **`.claude/scripts/audit_user_allow.py` 补 dogfood 镜像（F11）** — 与 templates/scripts/ 版本保持同步（已修正版）。

### Notes
- C9（用户级 env encoding 自动 merge）：SKILL.md 采方案①——安装期自动 merge `PYTHONUTF8/PYTHONIOENCODING` 进 `~/.claude/settings.json`；无实际生效物（安装期 hook 调用时才写入）。此方案未经用户明确追认，待下次 `/setup_agent` 实跑后确认或调整。

## [0.28.0] - 2026-06-24

### Added
- `[product]` **`templates/scripts/audit_user_allow.py`（C3）** — 扫 `~/.claude/settings.json` `permissions.allow` 揪出疑似项目专属/一次性条目（绝对路径/PID/IP/一次性命令），只报不删，列给用户拍板后下沉到项目 `settings.local.json`。
- `[product]` **`templates/rules/portability.md` §3.1（C4+C5）** — 新增"项目专属授权禁放用户级"范式文档：allow 下沉红线 + 合法/污染分类表 + 豁免边界（通用 skill 本体 = 合法 DRY；项目专属授权 = 污染）。

### Changed
- `[product]` **`templates/CLAUDE.md`（C1）** — §1/§3/§7 三处冗长 TODO 占位改成一行明确留白（"项目专属红线，随开发增量补充"），符合"init 时内容还不存在，不应预设填空"原则。
- `[product]` **`templates/hooks/` 4 个 hook 补 UTF-8 兜底（C7）** — `context_warning.py` / `allow_memory_write.py` / `memory_access_tracker.py` / `target_cleanup.py` 补 `sys.stdout/stderr.reconfigure(encoding="utf-8")`，与已有的 12 个 hook 对齐（全 16 个覆盖）。防止 Windows GBK 控制台 mojibake 注入 context。
- `[product]` **`SKILL.md` v0.19.0（C2+C3+C6+C8+C9+C10）** — Step 0 新增用户级 allow 审计步骤 + 全局 settings.json env 编码检查 + 写 rule 红线自检；Step 0.5 新增用户级扁平残留清理 + frontmatter key 标准化；Step 3 新增"这批各干嘛"速查表 + hook 成本最佳实践注释。

## [0.27.0] - 2026-06-24

### Added
- `[product]` **`skills/focus/` + `skills/spinoff/`（2 新 skill）** — 任务防漂移双剑：`/focus` 手动查看/重置任务锚 + 当场自检跑没跑偏；`/spinoff` 把"推进 A 必须先解 B"的 B 干净甩到新对话交接，避免就地展开引起漂移。
- `[product]` **`templates/hooks/clarify_reminder.py` + `templates/hooks/focus_reminder.py`（2 新 hook）** — 自动版防漂移：clarify 便宜负向 gate 后注入澄清提醒；focus 维护任务锚、攒够轮数后周期贴 `[focus]` 拉回主线。两者均已在 `templates/settings.json` 注册 + 自身 `.claude/` dogfood 镜像。
- `[product]` **`templates/settings.json` 加 `effortLevel: high`** — 产品层默认推理深度，可在项目级 settings.json 按需覆盖（portability.md §1 唯一例外条款）。

### Changed
- `[product]` **`templates/CLAUDE.md`** — 新增 §9.5 较大需求澄清（`[clarify]` 信号）+ §9.6 任务防漂移（`[focus]` 信号 + 漂移分类响应）两节，与 §10 ctx-budget 同范式。
- `[product]` **`templates/rules/portability.md`** — §1 补 `effortLevel` 唯一例外红线 + Why；§3 表注更新 effortLevel 分层语义。
- `[meta]` **`SKILL.md` 表更新**、**`docs/repositioning-from-StratusAgent-2026-06-24.md`**（C1–C10 反哺总 spec）、**`.claude/harvest-inbox.md`** 指针。

## [0.26.4] - 2026-06-10

### Changed
- `[product]` **`find-memory` / `resume` / `snapshot` / `find-doc` 加 `model: sonnet`** — 四个 skill 均属纯读/搜/写操作，步骤固定，无主观判断，不需要主模型推理强度。至此高频低难度 skill 全部走轻模型（完整清单：git-sync / summary / sync-docs / find-memory / resume / snapshot / find-doc + setup_agent 入口）。

### Fixed
- `[meta]` **根目录 `SKILL.md` 全局 CLAUDE.md 自检描述修正** — 中文规则 fallback 从歧义的"在文件头部新建"改为"在文件顶部新建 `## 沟通风格` 段落再插入"，消除执行歧义。

## [0.26.3] - 2026-06-10

### Changed
- `[repo]` **根目录 `SKILL.md` 加 `model: sonnet`** — `/setup_agent` 是一次性安装脚本，步骤固定，不需要主模型推理强度。与 git-sync / summary 模式对齐。

## [0.26.2] - 2026-06-10

### Changed
- `[product]` **`skills/git-sync/SKILL.md` frontmatter 加 `model: sonnet`** — git-sync 是纯机械活（fetch / 分析 diff / 生成提交消息 / push），不需要会话主模型（Opus/Fable）的推理强度。加 `model: sonnet` 后该 skill 当轮临时切 Sonnet 执行，**轮结束自动回到会话原模型**（model 字段只管当轮，官方语义）。与 `summary` 已有的 `model: sonnet` 做法对齐——至此两个高频低难度 skill 都走轻模型省 token。

## [0.26.1] - 2026-06-10

### Changed
- `[product]` **`templates/hooks/rule_size_check.py` 新增横切规则白名单（`CROSS_CUTTING_RULES`）** — 骨架自带的 architecture / modules / debugging / workflow / portability 这几条规则，其宽触发器是**有意且合理**的（调试横切所有源码、工作流横切 doc、架构/模块常驻、可移植性横切 `.claude`/config/libs）。v0.26.0 新增的触发器宽度检查会对它们**永久误报** → 训练人忽略 `[rule-size]` 信号（狼来了）。改为：显式列名豁免触发器宽度检查（**禁用通配**，否则退化成"关掉这条 lint"；下游可按需增删）；**仅豁免触发器宽度，不豁免体积/行数/戳数**（宽 ≠ 可以无限胖）。
- `[product]` **`templates/rules/meta_rule_design.md` §8 校准** — 触发器宽度 self-check 项注明"横切框架规则在 `rule_size_check.py` 白名单豁免"，与 hook 实际行为对齐。
- `[repo]` **`.claude/hooks/rule_size_check.py` 同步上述白名单改动** — §1 第4问 dogfood 镜像红线，与产品层逐字一致。

## [0.26.0] - 2026-06-09

### Added
- `[product]` **`templates/hooks/memory_junction_check.py`（新 hook，SessionStart）+ settings 注册** — memory junction 自愈。把 memory 纳入项目 git（`.claude/memory/`），系统路径 `~/.claude/projects/<hash>/memory/` 透明转发；每次 session 开始静默检查，不是 junction 则恢复，让"clone 即恢复"无需人工。三情形：已链接 → noop（稳态）/ 系统缺失 + 项目内有 → 建 junction（新机 clone）/ 系统是实目录 → 首迁复制后 **rename-to-.bak（绝不硬删数据）**。project-hash 从 repo root 通用推导（**每个非字母数字字符 → `-`，大小写原样保留**，如 `d:\Quant\setup_agent` → `d--Quant-setup-agent`），项目无关。补 `portability.md §2.1` 自认欠账的"待迁 SessionStart hook"。
- `[product]` **`templates/hooks/requirements_check.py`（新 hook，PostToolUse Edit|Write）+ settings 注册** — `requirements*.txt` 可移植性红线机械化：① 绝对路径 URL（`@ file://`，换机/换盘符即 fail）② 非 ASCII 字符（Windows pip 默认 GBK 解码会 UnicodeDecodeError）。非阻塞提醒。自门控：非 `requirements*.txt` 静默 no-op。对应 `portability.md §4.1/§4.2`。
- `[product]` **下游 `.gitignore` 机制块（`SKILL.md` Step 3 + 更新模式 U2 类 E）** — setup_agent 的 hook 会自动生成临时产物（Python 字节码 `__pycache__`/`*.pyc`、session 快照 `.runtime/session_state/`、hook 日志 `.runtime/*.log`），下游若无 `.gitignore` 兜底会被 `git add .` 误提交。新增：init / 更新时**幂等 append** 一段"setup_agent 机制块"到下游 `.gitignore`（缺行才补，不删项目自有项，无则新建）。**不整份 ship `.gitignore`**（避免与项目主语言耦合），只挡 setup_agent 自身机制产生的物（Python hook 是所有项目硬依赖，故这几行语言无关）。

### Changed
- `[product]` **`templates/hooks/rule_size_check.py` 增强 — 新增触发器宽度检查** — 通用启发式：frontmatter `paths` 里单段目录通配（`a/**`）或裸 `**`/`*` 等同始终加载（伪常驻），flag 之；≥2 段前缀（`a/b/**`）才算够窄。不写死任何项目名。补 `meta_rule_design.md §4.2/§8` 此前只能靠人工 self-check 的盲点。
- `[product]` **`templates/rules/meta_rule_design.md` §6.4 + §8 校准** — §6.4 TODO 占位补实：登记 rule_index_check / rule_size_check 两道护栏实际查什么 + 点明 normative 比例需人工判断。§8 self-check 阈值与 hook 对齐（版本 > 5 / 日期 > 8 / 触发器单段通配），消除"文档说 >3、hook 实际 >8"的漂移；已被 hook 覆盖的项标注【hook 已自动查】。

### Fixed
- `[product]` **`memory_junction_check.py` project-hash 编码修正（关键，dogfood 挖出）** — 旧实现只替换 `: \ /` 且强制盘符小写，**漏了 `_`/`.`** → 在路径含下划线/点的项目（`setup_agent` 自己正中此坑）算出错误 hash，找不到系统 memory 目录 → hook **静默失效（永不自愈）**。改为 `re.sub(r"[^A-Za-z0-9]", "-", path)`（非字母数字 → `-`，大小写保留），与 Claude Code 实测目录编码一致。本仓库 junction 现能正确识别。
- `[product]` **`requirements_check.py` 输入读取改双兜底** — 原只读 legacy env-var `CLAUDE_TOOL_INPUT`，CC 仅走 stdin 时永不触发。改为 stdin JSON（`tool_input.file_path`）优先 + env-var fallback，与 `allow_memory_write.py` 一致。
- `[product]` **两个新 hook 小瑕疵** — 冗余 `except (AttributeError, Exception)` → `except Exception`；`memory_junction_check._is_link` 改用 `normcase(abspath)` 规范化比较，避免实目录被误判为链接。
- `[product]` **`templates/CLAUDE.md §5` 文档对齐** — 场景 A 由"删系统目录"改述为 hook 实际的 **rename-to-.bak（绝不硬删）**，并标明由 SessionStart hook 自动执行。
- `[product]` **`templates/rules/portability.md` 补 §2.1（实体化死引用）** — 原 hook docstring / settings 注释 / 本 entry 均引用 `portability.md §2.1`，但该小节**实际从未创建**（声称补了实际没补）。本次补上，记述 memory junction 自愈机制 + project-hash 编码规则。

### Dogfood
- `[repo]` **v0.26.0 全部 hook + settings 改动镜像进自身 `.claude/`（§1 Q4 红线）** — `memory_junction_check` / `requirements_check`（新）+ `rule_size_check`（改）复制进 `.claude/hooks/` 并补 `.claude/settings.json` 注册（命令用系统 `python`）。
- `[repo]` **顺带修复 `session_snapshot.py` 历史断链** — settings 早注册了它（PostCompact + Stop）但 `.claude/hooks/` 一直缺该文件 → 每轮 Stop/PostCompact `exit 2` 报错、**memory 自动重建（艾宾浩斯评分）从未运行**。本次镜像补齐。dev `.gitignore` 同步补 `.runtime/session_state/` + `.runtime/*.log`，防 hook 产物误提交。

## [0.25.1] - 2026-06-09

### Changed
- `[product]` **`SKILL.md` Step 0.5 — 项目级重名 skill 副本改为逐个确认删除** — 此前 DUP-IDENTICAL（与上游字节一致的纯重复）是"直接删"不问，只有含项目专属数据才问用户。现统一为**每个重名副本删除前都单独问一次"删/留"**（含字节一致的纯重复），分类结果降级为给用户的"推荐动作"。理由：单一源去重是低频一次性动作，删的是项目 git 里的文件，让用户对每个重名 skill 有知情权 + 否决权，胜过省那几次确认；用户不答即保留。配套在「禁止」段补一条"❌ 批量/静默删项目级重名 skill 副本"。

## [0.25.0] - 2026-06-09

### Added
- `[product]` **用户级 skill 漂移自检 + 退役检测（支柱 B / 开机自检，设计见 [docs/skill-distribution-gaps.md](docs/skill-distribution-gaps.md)）**：
  - **`templates/hooks/skill_sync_check.py`（新 hook）+ dogfood `.claude/hooks/` + 两处 settings `SessionStart` 注册**：每次 session 开始比对 `~/.claude/skills/<skill>` 副本与上游源 `~/.claude/skills/setup_agent/skills/` 的内容哈希，**缺失/不一致/已退役**则打印一行 `[skill-sync]` 提示跑 `/setup_agent`。**只读不改**（补/更/删仍由 Step 0 在用户确认下做，绝不静默覆盖或删除）。自门控：本机没装 setup_agent → 静默 no-op（范式同 `target_cleanup.py`）。
  - **`RETIRED.md`（新增 repo 根墓碑名单）**：机器可读的"已退役 skill"清单（首条 `prune-memory` v0.24.0），让自检 + Step 0 认出"下架的 skill 还赖在架子上"——补「删除不传播」洞（正向同步只增不减）。
  - **`SKILL.md` Step 0 退役清理**：读 `RETIRED.md`，把仍在用户级架子上的退役 skill 列出来**问用户删**（Step 0.5 清"重复"副本的亲兄弟，本步清"退役"副本；绝不静默删）。
  - **范围 v1**：离线比对本机上游 clone（不 git fetch，SessionStart 必须快）；退役 **hook**（项目级，如 `memory_guard`）不在自动清理内，仍手动删。**有意未做**：带版本号的 manifest —— 内容哈希自检已覆盖"漂移/落后"，再叠 manifest 属冗余机械（反膨胀取舍）。

## [0.24.0] - 2026-06-09

### Added
- `[product]` **`SKILL.md` Step 0.5（新增）— 清理项目级通用 skill 重复副本（单一源红线）** — 通用 skill 单一源在 setup_agent（装用户级 `~/.claude/skills/`）；项目 `.claude/skills/` 里的同名副本会 shadow 单一源、各项目各自漂移。Step 0.5 对 `skills/` 清单逐个比对：DUP-IDENTICAL / 纯旧版镜像 → 删；含项目专属数据（find-doc/sync-docs 旧内联字典 → 先迁 `.map.md` 再删；其他用户定制 → 给 diff 问用户）→ **绝不静默删**。init / 更新 / 收编三模式都跑（幂等，fresh-init 空跑）。项目专属 skill（不在 `skills/` 清单里的）绝不碰。

### Changed
- `[product]` **`skills/find-doc/SKILL.md` + `skills/sync-docs/SKILL.md` — 项目专属字典/映射表外置** — find-doc 的 `topic→rule` 字典、sync-docs 的源码→文档映射，从 skill 本体内联 placeholder 改为**读项目本地** `.claude/find-doc.map.md` / `.claude/sync-docs.map.md`。skill 本体回归纯通用单一源（怎么查），项目只维护数据文件（查什么）；这是让 find-doc/sync-docs 也能安全去重（Step 0.5）的前提。Step 4/7 收尾提醒同步改为"建/补 `.map.md`"。
- `[product]` **`SKILL.md` Step 0 install loop — 改 `ls` 派生（修 find-memory 漏装）** — 安装清单从硬编码 13 名改为 `ls "$SKILLS_SRC"` 派生；历史硬编码漏了 `find-memory`（仓库 ship 但从不装用户级），`ls` 派生杜绝此类漂移，且日后增删 skill 只动目录、不改这段。
- `[product]` **`templates/rules/portability.md §2` — 记录 skills 单一源拆分** — 明确"项目专属 skill + 通用 skill 的项目数据（`.map.md`）进项目 git；通用 skill 本体**不进**项目 git，靠 `/setup_agent` 装用户级恢复"。DRY 对 clone-完整性的有意取舍。
- `[product]` **`templates/hooks/context_warning.py` + dogfood `.claude/hooks/`** — 移植下游 (StratusAgent) 已验证的「读真实 usage」机制回灌上游：弃用 char/4 文件大小估算（受 JSONL 结构开销 UUID/时间戳/JSON 信封污染、越聊越虚高），改为从 transcript 末尾倒查最近一条 assistant 消息的 `usage`（input + cache_creation + cache_read + output），与 Claude Code `/context` 一致、精确到个位 token；缺 usage 字段（旧 session/损坏）时 fallback char/4。模板侧此前一直是老的 char/4 版，本次补齐。
- `[product]` **`context_warning.py`** — `WINDOW` 默认值 200k → `1_000_000`（**反转 v0.23.2**）。动因：Claude Code 不向任何 hook 暴露 model-id 的 `[1m]` 窗口标记（transcript 剥后缀、project/user settings 无 model 字段、`~/.claude.json` 无激活 model、env 无 model 变量、切 model 不触发 hook、仅 SessionStart 带 model 但同样剥 `[1m]`），hook 无法自动判窗口；默认 1M 让 1M Opus 主力用户开局即准。**权衡（已知并接受）**：标准 200k 模型项目若忘记手动下调 WINDOW，会因分母过大永不预警（静默 compact 风险），实例化后须手动改回 `200_000`。

### Removed
- `[product]` **废弃手动 MEMORY.md 治理整代：`memory_guard.py` hook + `prune-memory` skill 退役** — 删 `templates/hooks/memory_guard.py`（185 行硬阻断）+ dogfood `.claude/hooks/` + 两处 settings 注册；`prune-memory` skill 正式废弃（手动引导式裁剪）。动因：`memory_rebuild`（Stop hook 自动评分，封顶活跃 40 条 + >45 天冷区化）已把 MEMORY.md 自动控制在 ~45 条、且改由机器每轮重排 —— 185 cap 从不触发，手动 prune 成冗余。`summary` skill / `docs/memory-scoring-design.md` 内 `/prune-memory` 引用一并清理。**下游**：已装项目若有 `memory_guard.py` / `prune-memory/`，需手动删（update 模式暂不自动删"上游已移除"的文件）。

## [0.25.0] - 2026-06-05

### Added
- `[product]` **`templates/hooks/target_cleanup.py` 加 L2 deps 变体裁剪** — 在原 L1（incremental/ 体积触发清）之上新增第二遍 pass：扫 `target/**/deps`，按 crate 分组、每组按 hash 的 max mtime 只留最新 `DEPS_KEEP_VARIANTS=2` 个变体、删更旧的。治本 deps/ 里同一 crate 旧 hash 变体无限堆积（本地 workspace crate 因频繁重编尤甚，长期占 target 绝大头）的问题。安全设计：留 2 给足余量（当前变体即便第二新也存活）、只动 ≥3 变体的 crate（稳定 deps 不碰）、无 hash 当前产物正则不匹配永不删、可回收 < `DEPS_MIN_FREE_GB=5` 跳过避免扰动；run_worker 重构成 L1+L2 两遍 pass 共用节流。下游实测删旧变体后 `cargo build` 仍为增量（仅本地 crate 因 incremental 缓存被清重编一次，deps 全复用）。来源 StratusAgent harvest

## [0.24.0] - 2026-06-05

### Added
- `[product]` **`templates/scripts/memory_bootstrap_cold.py`（新脚本）** — 冷启动一次性引导：把从未被 recall（`session_dates` 为空）的 memory 的 `created_at` 拨到数周前，使其立即沉入 Cold 区，让 Hot 区在首次铺设/重置后立刻收敛成"近期 recall 过的"，跳过约 1-2 周自愈期；只动空 `session_dates` 文件（`created_at` 对已 recall 文件是死字段，绝对安全）。来源 StratusAgent harvest
- `[meta]` **`docs/memory-scoring-design.md`** — 加「冷启动 / 首次激活」节：首次重建覆盖手工 MEMORY.md 的备份提醒 + Hot 区头 1-2 周随机的成因 + bootstrap 引导 + 安全不变量

## [0.23.2] - 2026-06-03

### Fixed
- `[product][repo]` **`context_warning.py`** — `WINDOW` 默认值从 1M 改为 200k（标准版 Opus 4.8 / Sonnet 4.6 / Haiku 4.5 默认 200k context，1M 专用版才需改为 1_000_000）；同步更新注释中的模型版本说明；dogfood 同步 `.claude/hooks/` 与 `templates/hooks/`

## [0.23.1] - 2026-06-03

### Fixed
- `[product]` **`templates/scripts/memory_search.py`** — `main()` 顶部加 stdout UTF-8 reconfigure（`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`），防止 Windows 中文环境下 memory 文件名/内容输出乱码或报 UnicodeEncodeError；来源 CausisRiskSuite harvest

## [0.23.0] - 2026-06-03

### Added
- `[meta]` **`docs/memory-scoring-design.md`（新文档）** — Memory 热度评分系统完整设计规范（艾宾浩斯衰减公式 + 五组件架构 + 决策记录），来源 2026-06-03 双轮 debate
- `[product]` **`templates/hooks/memory_access_tracker.py`（新 hook）** — PostToolUse/Read：检测 memory 文件访问，快速预过滤后写入 `_stats.json` 唯一日期，防突发读取污染
- `[product]` **`templates/hooks/session_snapshot.py`** — Stop 末尾追加调用 `memory_rebuild_index.py`（`_rebuild_memory_index()`），闭合触发链路
- `[product]` **`templates/scripts/memory_rebuild_index.py`（新脚本）** — 按艾宾浩斯衰减分重建 MEMORY.md 热区 + MEMORY_COLD.md 冷区；Stop hook 末尾调用
- `[product]` **`templates/scripts/memory_search.py`（新脚本）** — 关键词 grep 搜索 memory/ 所有文件，由 /find-memory skill 调用
- `[product]` **`templates/memory/_stats.json`（新模板）** — 访问记录初始模板，含 config（hot_n/pinned）+ files{}
- `[product]` **`skills/find-memory/SKILL.md`（新 skill）** — 按需 memory 搜索，Claude 找不到热区记录时调用
- `[product]` **`templates/settings.json`** — PostToolUse/Read 追加 `memory_access_tracker.py` 注册

### Known TODO
- 端到端测试：新项目 setup → 写 memory → Stop → 验证 MEMORY.md 重建正确

## [0.22.0] - 2026-06-03

### Added
- `[product]` **`templates/hooks/memory_guard.py`（新 hook）** — PreToolUse 硬阻断：Write/Edit 到 MEMORY.md 超 185 行时 exit 2，提示 `/prune-memory`。补全 `memory_lint.py`（PostToolUse 非阻塞警告）缺失的"阻止写入"环节
- `[product]` **`skills/prune-memory/`（新 skill）** — 引导 Claude 按删留标准逐章节分析 MEMORY.md 条目，展示 🔴/🟡/🟢 候选清单，用户确认后执行删除并移档至 `memory/archive/`
- `[product]` **`templates/settings.json`** — 在 PreToolUse `Write|Edit` hook 数组追加 `memory_guard.py` 注册

## [0.21.1] - 2026-05-31

### Added
- `[meta]` **`INSTALL.md` 新增「开发者模式：junction 指向开发仓库（单一真相源）」小节**，并给「升级」节补注记。澄清一个长期文档缺口：INSTALL 主安装流程教的是直接 `git clone` 到 `~/.claude/skills/setup_agent`（在 C 盘留**真实副本**），但维护者本人（既用又改 setup_agent、做下游 harvest）实际跑的是 **junction 模式**——开发仓库放工作区（如 `D:\Quant\setup_agent`），`~/.claude/skills/setup_agent` 只是 junction 透明入口，物理一份、改即生效
  - 此前该模式只在 `README.md` 自举提示里顺带提过一句，没有正式集中说明；文档系统大量讲的 junction 其实是 **memory junction**（另一回事）
  - 附「验真 & 防骗」：`Get-Item ... -Force` 看 `LinkType: Junction` / `Target`；**Glob 会穿透 junction** 把同一份列成两份一模一样的内容（连 `.git/objects` 哈希都对应），别误判成两个独立副本。经验已存本仓 memory `project_skill_junction_single_source`
  - **不触发 dogfood 镜像红线**（§1 第4问只管 hook / settings，这是元文档）；不下沉、下游无关

### Added
- `[product]` **`SKILL.md` Step 0 新增"全局 CLAUDE.md 自检"**：`/setup_agent` 执行时自动检查并补全用户 `~/.claude/CLAUDE.md` 里的"Glob 查文件"规则（幂等，已有则跳过）。补完后，该用户所有项目、所有新对话都不会因为 agent 反射性用 shell 搜文件而触发权限弹窗。`~/.claude/CLAUDE.md` 不存在的新用户跳过此项（只靠项目级 `CLAUDE.md §2.5` 兜底）

## [0.20.0] - 2026-05-31

### Added
- `[product]` **`templates/CLAUDE.md` 新增 §2.5「工具选择：检索用 Glob/Grep，执行才用 shell」**。源自本仓实测——Windows 下 agent 反射性用 PowerShell `Get-ChildItem` 查文件，一旦访问工作目录外路径（如 C 盘根）就频繁触发权限弹窗，噪音大且无谓
  - **结论**：找文件 / 查内容优先 `Glob` / `Grep` / `Read`（受控只读、零弹窗、跨平台、不可夹带删改），同时满足用户三诉求"能用 / 清净 / 底线安全"；shell（PowerShell / bash）保留给构建 / git / 进程 / 系统配置等"真要执行"的动作 —— 是各司其职，不是淘汰 shell
  - **为什么进 `CLAUDE.md` 而非 `workflow.md`**：查文件是**每个任务**都会发生的反射，必须 always-on。`workflow.md` 是 `doc/` / `rules/` path-gated，只在改文档时加载，会漏掉最需要它的编码场景（同 §1「跨任务通用规矩进 CLAUDE.md」的逻辑）
  - 附「Glob 三诀」防空手而归：`path` 给具体防超时 / 匹配文件非目录（找文件夹写 `**/foo/**`）/ 默认跳过 `.` 开头隐藏目录（目标在 `.claude` 内时把 path 扎进去）
  - **不触发 dogfood 镜像红线**（§1 第4问只管 hook / settings，这是 rule 内容）；setup_agent 自身经验已存本仓 memory `feedback_glob_search_gotchas`，自产自用已覆盖

## [0.19.0] - 2026-05-30

### Added
- `[product]` **新 hook `templates/hooks/target_cleanup.py`（SessionStart）：Rust 项目 target/incremental 缓存体积触发式清理**。源自下游实测——Rust workspace 的 `incremental/` 缓存会无界膨胀（实测可达数十万小文件 / 200GB+），拖垮磁盘 I/O 致整机发黏（CPU/内存却正常、重启才好）
  - **为什么不用 cargo-sweep**：`cargo sweep --time N` 看文件**访问时间(atime)**，但 Windows 上 Defender 实时扫描 / 每次 build / 目录遍历都刷新 atime，陈年产物长期"看起来热"而清不动（下游实测 `--time 3` 对 200GB+ 缓存只肯清几百 KiB）。atime 在开杀软的 Windows 上不是可靠冷热信号
  - **机制**：改用可信信号 incremental/ **体积**。超 `THRESHOLD_GB`(30) 时先把 `incremental` 瞬间改名为 `.trash`(cargo 立刻能建新的)，再后台慢删；量体积 + 删除全在 detached worker，不阻塞 session 启动。incremental 是纯缓存、100% 可再生，删整个目录绝对安全（cargo 下次 build 自动重建，deps 保留）
  - **自门控 = 条件加载**：`find_workspace()` 无 Cargo.toml 即静默 no-op，故 `templates/settings.json` 无条件挂 SessionStart 对非 Rust 项目零影响，且项目后来新增 Rust crate 会自动激活——比"setup 时按主语言裁剪"更稳，无需改主 SKILL.md
  - `templates/settings.json` SessionStart 注册该 hook（带 `comment` 说明 Rust-only + 自门控）
  - 自测入口 `--dry-run`（前台量体积 + 报告会删什么，不删/不改名/不写时间戳），便于 harvest 后在新项目验证
  - 扫描用 `target.glob("**/incremental")` 递归挖到底：既覆盖普通编译 `target/{debug,release}/incremental`，也覆盖交叉编译 `target/<triple>/debug/incremental`（多埋一层，`*/incremental` 单层 glob 会漏）
- `[product]` **新 hook `templates/hooks/allow_memory_write.py`（PreToolUse Write/Edit）：放行 memory `.md` 写入免弹窗**。根因——`.claude/` 是 Claude Code 受保护目录（连同 `.git`/`.vscode`/`.idea`/`.husky`/`.cargo`），写入无视 `acceptEdits` 和 `permissions.allow` 规则强制弹窗（求值序 deny→ask→allow，受保护优先于 allow）；本范式 memory 在 `.claude/memory/` 下被连带保护，导致每次保存记忆都弹窗
  - **试过的死路（实测全失败）**：① `permissions.allow` 加 `Write(...)`/`Edit(...)` 规则，三种路径格式（`C:\\` 反斜杠 / `//c/` POSIX / 项目相对）全被保护层压过；② `additionalDirectories` 列 memory 目录——只解除"能访问"不免确认；③ 把 memory 搬出 `.claude/`——能修但牺牲"记忆与配置内聚"，被否决
  - **治本**：PreToolUse hook 抢在权限弹窗之前返回 `permissionDecision:allow`（位置比那道问话更靠前，实测能压过受保护目录）。只放行 memory 的 `.md`，settings/hooks 本体不碰，安全边界不破
  - `templates/settings.json` PreToolUse 注册该 hook（matcher `Write|Edit|MultiEdit|NotebookEdit`）
  - **改完须开新会话生效**（hook 不热重载）。详见下游 memory `feedback_claude_dir_protected_memory_write_hook`
- `[repo]` **dogfood：上面两个产品层 hook 当场镜像进自身 `.claude/`**。`allow_memory_write.py` + `target_cleanup.py` 复制进 `.claude/hooks/`，`.claude/settings.json` 注册（命令前缀按 dev 仓库无 `.venv` 改用系统 `python`）。`allow_memory_write` 对 setup_agent 自己的 `.claude/memory/` 实有收益；`target_cleanup` 非 Rust 永远自门控 no-op，挂着 = 持续验证「无 Cargo.toml 静默跳过」这条产品承诺。已实测：JSON 合法、target dry-run 正确跳过、memory `.md` 放行 / 非 memory 不干预
- `[repo][meta]` **「传播三问」升级为「传播四问」**：新增第 4 问——产品层 hook/settings 改动必须当场镜像进自身 `.claude/` 吃狗粮（红线）。本次正是漏了这一环才补立。同步更新 `CLAUDE.md §1`/§2/§4、`docs/design-rationale.md §9.1`/§9.3 的措辞

## [0.18.1] - 2026-05-29

### Added
- `[repo]` **dogfood：setup_agent 自己也装上 ctx 预警 hook**。此前自身 `.claude/hooks/` 只有 `version_check`，缺它发给下游的 `context_warning`（"工厂不吃自己的狗粮"）
  - 复制 `templates/hooks/context_warning.py` → `.claude/hooks/`，并在 `.claude/settings.json` 注册 `UserPromptSubmit`（系统 `python`，dev 仓库无 .venv）。WINDOW=1_000_000 适配 Opus 1M
- 注：仍缺 session_snapshot / show_state 等其余 hook 的 dogfood（memory_lint / rule_index/size_check 因 setup_agent 自身无 .claude/rules、memory 结构，不适用）

## [0.18.0] - 2026-05-29

### Changed
- `[product]` **`templates/settings.json` 权限机制重做为三档：放宽 allow（压噪音）+ 新增 ask（要紧项必弹）+ 加厚跨平台 deny（拦灾难）**。设计目标：**弹窗的每一个都尽量是"需慎重的决策"，而非被训练成无脑确认**
  - **allow 放宽**（3 → 67 条）：日常安全命令静默放行——git 读/常规写（status/diff/log/add/commit/fetch/pull/stash…）+ shell 读（ls/cat/head/grep/find…）+ 构建测试（npm/cargo/pytest/python/node/go/make/maturin…）+ PowerShell 读 cmdlet。**allow 越全，弹窗噪音越少**（与"弹窗即信号"目标一致；deny 优先级更高，publish/branch -D 等危险子命令仍被 deny 碾过）
  - **ask 新增**（7 条）：**强制弹窗**的"慎重决策"类——`git push / rebase / reset / checkout / restore / merge / cherry-pick`（远程/历史/可丢改动）。ask 优先级高于 allow，即使将来被"别再问"误加进 allow 也照样弹
  - **deny 加厚**（11 → 60 条）：安全地板（优先级最高、`bypassPermissions` 下仍生效）。凭证读+写 / git 历史销毁 / POSIX 破坏性 / **Windows·PowerShell 破坏性（补上之前 POSIX-only 的洞）** / 对外发布 / 系统级；含 PowerShell 的 `Remove-Item`（别名自动覆盖 `rm`/`del`/`rmdir`）+ force-push/reset --hard/clean 镜像

### Note
- **三档 = 静默 / 弹窗 / 拦死**，对应"日常 / 慎重 / 灾难"。模式仍 `acceptEdits`：未在任何清单的陌生命令默认**弹窗**（安全），靠"别再问" + `/fewer-permission-prompts` 把 allow 养肥、噪音随时间递减。**不追求 dontAsk 的"100% 弹窗皆要紧"**，因其代价是陌生命令静默罢工（决策见本会话讨论）
- **此前 deny 是 POSIX-only（只拦 Bash `rm`），但用户在 Windows** —— `Remove-Item -Recurse -Force` 完全没拦，是真实漏洞，本版用 PowerShell matcher（语法经 claude-code-guide 核实）+ 别名 canonicalization 补齐
- `git push --force:*` 的空格词边界**不会**误伤 `--force-with-lease`（带安全检查的强推照常放行）
- **deny 是减速带不是保险柜**：靠命令字样匹配，子进程（`python -c "open('.env')"`）可绕过。它防 agent **手滑误删/误推**，真正恢复底牌仍是 git 历史 + 备份。故意**未** blanket-deny `python`/`node`（会废掉跑脚本/测试）
- **PowerShell 覆盖侧重**：Claude 主要走 Bash 工具，故 allow/ask 以 Bash 为主；PowerShell 侧覆盖读 cmdlet（allow）+ 破坏性命令（deny）。PS 跑构建若未 allow 会弹窗（B 模式安全默认），点"别再问"自增长
- `[repo]` dogfood：setup_agent 自己的 `.claude/settings.json` permissions 块已镜像本版三档（allow/ask/deny），与 `templates/settings.json` 一致 —— 总部自己也受同款 Windows 删除防护，不再"卖防盗门自家门敞着"。hooks 段保持 repo 特异性（系统 `python` + 最小 hook 集，dev 仓库无 `.venv`），不在镜像范围

## [0.17.0] - 2026-05-29

### Fixed
- `[meta]` **Step 0 自检堵住"改进流不到已装下游"的传播缺口**：原"逢重名 skill 一律跳过"虽保护用户定制，但副作用是**升级已有 skill 永远到不了老项目**（本会话给 `summary` 加捕捉反射就会卡在这）
  - `SKILL.md` Step 0 循环改为三分支：缺失→装 / 与上游**一致**→静默更新（无定制可保护）/ **不一致**→给 diff 问用户（覆盖 or 保留定制），**绝不静默覆盖**
  - 判断逻辑与「更新模式」§U2 类 A 对齐（一个事实源两处复用）；同步修正「禁止」段"已存在 skill 跳过不覆盖"为"先比对，不静默盖定制"

## [0.16.0] - 2026-05-29

### Added
- `[product]` **反哺机制落地为两个命令：`/summary`（捕捉）+ `/harvest`（推送）**，捕捉/推送分离
  - `skills/harvest/SKILL.md` **新建**（第 13 个通用 skill）：推送侧。无参=读下游 `.claude/harvest-inbox.md` 批量清；带描述=立即单条快车道。两入口汇进同一套脱敏 harvest 仪式（判通用性 → §3 七项脱敏 → 写 `templates/` → bump+CHANGELOG → 记日志 → 回收收件箱 → 给 diff 不自动 push）
  - `skills/summary/SKILL.md` 新增**第 6 步「反哺候选捕捉」**：summary 顺手判"本轮经验是否通用"，通用的追加一行进 `.claude/harvest-inbox.md`（收件箱）。捕捉是 summary 副产品，零新纪律
  - `SKILL.md` Step 0 自检循环加入 `harvest`（12→13 个 skill），各处计数 + 速查表 + 模板速查表同步
- `[meta]` `docs/reverse-sync-playbook.md` §1 触发时机重写：标注 v0.16.0 起捕捉/推送分离；触发从"凭感觉≥3条"升级为"收件箱≥3行（可数）"+ `/harvest <描述>` 快车道；强调"两个入口一个仪式"不分叉
- `[meta]` `docs/design-rationale.md` §7「不做什么」新增"**不监督下游合规**（不做 doctor / fleet）"——记录单项目体检 + 多项目合规盘探讨后**否决**的决定与理由（出版方非监管方 / 合理例外噪音 / 要可信须 PULL 而非 PUSH 自报 / junction 隐患已被开机自检覆盖），防止将来重提。与 §9.3"镜像漂移检查 hook"（工厂自查）区分

### Note
- **设计要点**：反哺真正的痛点不是"推送"（推送必须人工脱敏，公开 repo 不能自动化），而是"等盘点时已忘了学过啥"。故拆分——**捕捉做到当场零成本（搭车 `/summary`），推送保持人工批量**。复用 sync-from-upstream 的"机械半场/判断半场"拆分哲学
- **收件箱文件** `.claude/harvest-inbox.md` 用 ASCII 名（可移植）；是 per-下游项目文件，纳入下游 git
- 下游获得本能力需 sync：Step 0 自检会补 `harvest` skill（但**已存在的 skill 不覆盖**——存量下游的 `summary` 升级需手动覆盖或重装该 skill）

## [0.15.0] - 2026-05-29

### Added
- `[meta]` **`/setup_agent` 进门「认场子」四分类 + 工厂自检硬闸**：前置步骤从"有戳=更新 / 无戳=init（含一个 A/B 例外）"重做成判别树
  - `SKILL.md` 前置新增 **Step 前-2 工厂自检**：cwd 同时有 `templates/CLAUDE.md` + 自己的 `SKILL.md` → 硬拒（堵死"在 setup_agent 源头自己身上跑 bootstrap / 更新"的自伤，2026-05-29 实测可复现）
  - `SKILL.md` 前置 **Step 前-3** 改为四分类表 + setup_agent 衍生指纹判据（鬼打墙 / ctx-budget / `OPTIONAL_BEGIN` 残留 / `meta_rule_design.md` 等，命中 ≥2 即判"像铺过的"）
  - `SKILL.md` 新增 **「## 收编模式 (adopt)」** 主段：无戳但像衍生的项目走"登记纳管，绝不覆盖"——写戳=当前 VERSION 作同步基线，可选补差。固化此前靠 agent 临场判断的安全路径
  - `SKILL.md` 更新模式 U1 新增 **`[product]` 短路**：`(上次, 现在]` 区间无 `[product]` 条目 → 不跑全量 diff，直接刷戳退出（CHANGELOG 标签分布实测近半 bump 与下游无关，省空跑）
  - `SKILL.md` 禁止段补"不在源头仓库自己身上跑"
- `[meta]` `docs/design-rationale.md` §9.4「工厂自身不带版本戳——靠 `templates/` 存在性识别」：把"源头无戳"从 v0.14.0 潜在自伤正式定性为设计意图，附推论"识别项目类型优先用结构性事实而非约定标记"

### Note
- 本批次**全是 setup_agent 自身行为（SKILL.md）+ 元文档（design-rationale）改动**，产品层 `templates/` / `skills/` 未动 → 下游无新增量（无 `[product]` 条目）。下游下次跑 `/setup_agent`（pull 到本版后）自动获得新的认场子行为，无需 per-project sync
- frontmatter `version:` 字段顺手从滞后的 `0.9.1` 对齐到 `0.15.0`（自 v0.9.1 起漏更新的历史遗留）

## [0.14.0] - 2026-05-29

### Added
- `[product]` **`/setup_agent` 更新模式**：不新增 skill，把"拉上游增量到现有项目"并入 `/setup_agent` 自身（一个命令两用：全新项目 init / 已铺过项目更新）。下游在已铺过的项目里重跑 `/setup_agent` 即自动进更新模式
  - `SKILL.md` 新增「前置」步骤：先 `git -C ~/.claude/skills/setup_agent pull --ff-only` 拉上游最新（init/更新都先拿最新，堵住"铺旧版本"坑）+ 按 `.claude/.setup_agent_version` 判定 init/更新模式
  - `SKILL.md` 新增「更新模式」主段（U1 算增量→抓 `[product]` changelog / U2 按 sync-from-upstream §2 表格分类 diff / U3 路径适配 / U4 验证+收尾），机械半场自动、判断半场（类C rules/CLAUDE.md）全程人脑
  - `SKILL.md` Step 7 + 复制清单 + 速查表：init 末尾写 `.claude/.setup_agent_version`（= 安装时版本，既作"上次同步到哪版"记录，又作 init/更新判定信号）
- `[meta]` `README.md` 使用段重构：开头新增「新项目初始化——对 agent 说这一句」自带兜底引导（没装过先 clone+junction 自举、装过直接铺），并保留「更新已有项目（重跑即更新）」说明

### Changed
- `[meta]` `docs/sync-from-upstream-playbook.md` §6：标注机械半场已并入 `/setup_agent` 更新模式（判断半场仍人脑，不违反"别把判断错误自动化"红线）；§5 日志追加 v0.14.0 行

### Note
- **存量项目**（已装过但无版本戳，如早期下游）首次重跑 `/setup_agent` 时落到「前置」例外分支：当作 init 处理已存在文件 + 补写版本戳纳入管理
- 「③ 镜像漂移检查 hook」仍未做（延续 v0.13.0 节奏）

## [0.13.0] - 2026-05-29

### Added
- `[repo]` **工厂自觉前门闸**：新建 setup_agent 自己的 `CLAUDE.md`（之前缺失，自产自用只落实了 version_check 一小块）。核心是 §1「传播三问」always-on 红线——每个改动落地前必须回答 (1) 属于哪一层（产品 `templates`/`skills` vs 自身配置 `.claude` vs 元文档 `docs`/README/SKILL）(2) 通用的话镜像进 `templates/` 了吗 (3) 要不要 bump + 记 CHANGELOG。附 §2 分层地图 + §3 CHANGELOG 层标签约定 + §4 传播机制指引
- `[meta]` `docs/design-rationale.md` §9「setup_agent 的双重身份：工厂 + 自产自用」：固化 framing（工厂 vs 样板间两个身份）+ §9.1 前门闸 + §9.2 CHANGELOG 层标签为何能让下游有抓手 + §9.3 演进节奏（软规则先跑顺再升级为「镜像漂移检查 hook」机制）

### Changed
- `[meta]` `CHANGELOG.md` 顶部图例新增「层标签」说明（`[product]`/`[repo]`/`[meta]`），本版起所有 entry 打标签，下游 `grep "\[product\]"` 即得 sync 增量清单

### Note
- 本批次**全是 setup_agent 自身改动**（前门闸机制 + 元文档），**没有改产品层**——下游无新增量（故无 `[product]` 条目）。属 reverse-sync-playbook §3.1 批次 3 同类「非反哺批次」
- 「③ 镜像漂移检查 hook」本版**未做**——按演进节奏，等三问软规则跑顺 2-3 次、误报场景摸清后再机制化（见 design-rationale §9.3）

## [0.12.0] - 2026-05-29

### Changed
- **策略变更：Python 从「可选」改为「硬依赖」**。所有下游项目（含纯 rust / node / go）安装 setup_agent 时都安装整个 Python hook 体系，不再因主语言非 Python 而跳过 hook。主因：`version_check` 等红线 hook 价值与语言无关，不该因语言失去
  - `SKILL.md` Step 3：「Python hook 体系条件复制」→「所有项目无条件安装」+ 新增「前置硬检查」（无 Python 则停下要求先装）；「Python 解释器路径适配」适用范围改为所有项目；「非 Python 项目跳过说明」→「目标机无 Python 时的处理」（给装 Python 修复路径）
  - `SKILL.md` 复制清单表：hooks/scripts 复制条件 `仅 Python 项目` → `总是`
  - `README.md` 「Python 依赖」段重写：硬依赖声明 + 解释器优先级（.venv → 系统 python → 要求安装）+ 为什么强制 Python

### Added
- **setup_agent 自产自用**：dev 仓库自己装上 `version_check` hook（之前只把它作为模板分发给下游，自己 commit 不受约束 → 历史上自己反复忘 bump）
  - `.claude/hooks/version_check.py`（从 templates 复制）
  - `.claude/settings.json` 注册 PreToolUse(Bash) → version_check，用系统 `python`（dev 仓库无 .venv）

## [0.11.0] - 2026-05-29

### Added
- `templates/hooks/version_check.py` 新 hook：PreToolUse(Bash) 拦截 `git commit`，staged 改动未含版本号 SoT 文件（`VERSION`/`package.json`/`Cargo.toml`/`pyproject.toml`）则 `exit 2` 阻断 → 把 workflow.md §9「每次 commit 必 bump」从软规则升级为**机制硬强制**。`[skip-version]` / `--amend` / 正在 merge / 无版本号文件 可豁免。**未来所有 Python 项目装 setup_agent 时自动注册**（随 templates/hooks + settings.json 下沉）
- `templates/settings.json` PreToolUse 新增 Bash matcher 注册 version_check.py
- `templates/rules/workflow.md` §9.8「自动强制」：说明 hook 兜底机制 + 历史教训（§9 软规则被忘过多次）

### Changed
- `SKILL.md` Step 3 hook 条件复制：修正非 Python 项目应删**整个 hooks 块**（原文漏列 PreToolUse / PostToolUse，会残留死 hook）；明确 `permissions` 块必须保留
- `SKILL.md` 非 Python 跳过说明 + 模板速查表：补 version_check.py / find-doc / permissions 等丢失/保留项

## [0.10.0] - 2026-05-29

### Added
- `templates/settings.json` 新增 `permissions` 块，下沉「少弹框」黄金组合到所有下游项目：
  - `defaultMode: acceptEdits` — 文件编辑（Write/Edit）默认放行，不再逐个弹框
  - `allow` allowlist — 只读工具（Read/Grep/Glob）+ git 看状态类（status/diff/log/show/branch/fetch）+ ls/cat/pwd
  - `deny` 安全闸口 — 挡不可逆操作（`rm -rf` / `git push --force` / `git reset --hard` / `git clean -f`）+ 敏感文件读取（`.env` / `secrets/**` / `*.key` / `*.pem`），deny 优先级最高，bypass 模式下仍生效
- `SKILL.md` Step 1：settings.json merge 逻辑扩展——除 hooks 外，新增 `permissions.allow/deny` 数组追加去重 + `defaultMode` 仅在用户未设时才写（不覆盖用户已有偏好）
- `SKILL.md` 模板速查表：`settings.json` 行补充 permissions 块说明

### Note
- 下游已有项目不自动获得（permissions 只随**新** `/setup_agent` 安装下沉）；存量项目需手动 merge 或重跑 skill 的 settings 合并步骤
- 白名单设计为「精选起步 + 留白」——常用但因人而异的命令交给权限弹框的「别再问」选项自增长，或 `/fewer-permission-prompts` skill 批量补齐

## [0.9.1] - 2026-05-29

### Changed
- 4 个写文档/轻量类 skill 的 `SKILL.md` frontmatter 加 `model:` 字段（利用官方机制 skill 激活期间临时切模型，结束自动恢复）：
  - `sync-docs` / `summary` → `sonnet`（写文档为主，能力够用速度更快）
  - `todo` / `archive-scan` → `haiku`（轻量追加 / 批量 git mv，无需推理）

### Fixed
- 版本号自打脸 v3：v0.9.0 commit (`4aa57c2`) 写了 CHANGELOG 但漏打 git tag → 本次补打 `v0.9.0` tag；`50edbac` 改 skill 配置时也漏走版本号流程 → 本版补齐

## [0.9.0] - 2026-05-24

### Added
- `templates/VERSION`（初始 `0.1.0`，下游项目无原生版本源时用）
- `templates/CHANGELOG.md`（通用骨架，引用 `rules/workflow.md §9` SemVer 语义，所有下游项目无条件复制）
- `SKILL.md` Step 3：新增"版本号 SoT 条件复制"段（检测 `package.json` / `Cargo.toml` / `pyproject.toml` → 跳过 VERSION 避免双 SoT；CHANGELOG.md 仍统一复制）
- `SKILL.md` Step 3 复制清单 + 模板速查表：新增 VERSION / CHANGELOG.md 两行
- `README.md` 新增"未反哺的上游 hook（为什么不在 templates 里）"段，明列 `cargo_check.py` 等语言/业务专属 hook 不反哺的判断标准
- `docs/reverse-sync-playbook.md` 新增 §3.1 实战记录（v0.6.0 / v0.7.0 / v0.8.0 三次反哺的 checklist 实例化）+ §3.2 元规则（含"禁止虚构踩坑故事"红线）

### Fixed
- 自打脸 v2：v0.8.0 给 setup_agent 自己装了版本号但**没下沉到 templates**，下游项目装完 `/setup_agent` 仍然没有版本号机制 → 本版闭环

## [0.8.0] - 2026-05-24

### Added
- `VERSION` 文件（单一事实源，符合 workflow.md §9.1）
- `CHANGELOG.md` 本文件
- `SKILL.md` frontmatter `version: 0.8.0` 字段
- `skills/resume/SKILL.md` **Step 5**：用户确认接续后主动建议对话框重命名（避免 `/resume` 默认 session 名 "resume" 无指导性，多 session 并发时无法区分内容）

### Fixed
- 自打脸：setup_agent 之前要求下游用版本号但自己没用 → 本版补齐版本号机制

## [0.7.0] - 2026-05-24（追溯，commit 4b976da）

### Added
- 反哺 5 个通用 hook：`memory_lint.py` / `rule_index_check.py` / `rule_size_check.py` / `find_doc_reminder.py` / `show_state.py`（脱敏简化版）
- `templates/settings.json` 扩展到 6 类 hook 注册段（PreToolUse / PostToolUse / PostCompact / Stop / UserPromptSubmit / SessionStart）
- `templates/rules/modules.md §3.1 §3.2` 从 causis_risk_suite 反哺（协调中枢三块分层 + 提炼共享常量三件套）
- `docs/sync-from-upstream-playbook.md`（与 reverse-sync-playbook 互为镜像，按业务专属程度分 4 层决定覆盖策略）

### Changed
- `SKILL.md` Step 3 改造：加 Python hook 体系条件复制（基于 Q2 主语言）+ 无 `.venv` fallback + 非 Python 项目跳过说明
- `docs/reverse-sync-playbook.md §7` 改为引用新 sync-from-upstream playbook 的精简版

## [0.6.0] - 2026-05-24（追溯，commit 9cfa7ae）

### Added
- `templates/hooks/session_snapshot.py`（脱敏简化版 ~150 行，去 tag 逻辑 + 通用版本检测）
- `templates/scripts/archive_scan.py`（通用版直接 cp）
- `templates/settings.json` 加 PostCompact + Stop hook 注册
- `README.md` "Python 依赖（agent 安装前必读）"段
- `docs/reverse-sync-playbook.md §4` 白名单扩展（加 `templates/hooks/` + `templates/scripts/`）
- `skills/find-doc` + `skills/sync-docs` SKILL.md 末尾加 placeholder 检测与提醒段

## [0.5.0] - 2026-05-24（追溯，commit d73ea5a）

### Added
- 反哺 StratusAgent + causis_risk_suite 经验：
  - `templates/rules/portability.md §4.3-§4.5` 多项可移植性约束
  - `templates/rules/workflow.md §9` 拆细为 §9.1-§9.7（Milestone-bound SemVer 详细版）
  - `templates/rules/meta_rule_design.md`（新建，元规则）
- `README.md` "适合/不适合"诚实段
- OPTIONAL 段落物理裁剪机制（`<!-- OPTIONAL_BEGIN PLATFORM/LANG/SCENARIO -->`）
- `templates/CLAUDE.md §11` doc/ 红线化

### Removed
- `session-tag` skill（过度设计，整目录删 + snapshot/resume 里的 tag 引用清理）

## [0.4.0] - 2026-05-23（追溯，commit fa8c75f）

### Added
- 13 个通用协作 skill：`archive-scan` / `collab` / `debate` / `escalate` / `find-doc` / `git-sync` / `plan` / `resume` / `session-tag` / `snapshot` / `summary` / `sync-docs` / `todo`（**`session-tag` 后于 v0.5.0 删除**）
- setup_agent SKILL.md 加 skill 自检流程

## [0.3.0] - 2026-05-09（追溯，commit 88db438）

### Added
- `templates/hooks/context_warning.py`（ctx-budget 红线 hook — 跨 75/85/95% 阈值预警）
- `templates/CLAUDE.md §10` ctx-budget 信号响应红线

## [0.2.0] - 2026-05-08（追溯，commit 2ed5df2）

### Added
- doc/ 分层引入 acceptance + TODO-INDEX 二分语义（短期 vs 远期 backlog）

## [0.1.0] - 2026-05-01（追溯，commit 7f30c9a）

### Added
- setup_agent skill 骨架初始化（CLAUDE.md / rules / memory junction / doc 基础模板）
