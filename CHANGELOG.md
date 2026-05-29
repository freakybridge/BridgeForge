# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/) — 语义化版本按 `templates/rules/workflow.md §9` **简版**（小项目退化版）：

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

## [Unreleased]

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
