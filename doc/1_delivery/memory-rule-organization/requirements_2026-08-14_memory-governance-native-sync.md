---
name: BridgeForge 项目 memory 可发现性与 Codex 原生 memories 云同步
description: 修复项目 memory 的确定性加载、自动召回和可审计回执，并通过用户级 Codex hooks 与 GitHub 私有仓库同步原生 memories。
type: requirements
category: architecture
status: completed
date: 2026-08-14
scale: L
source: confirm -> develop
---

# 项目 memory 可发现性与原生 memories 云同步确认卡

## 原始需求摘要

用户要求 BridgeForge 同时维护两套相互独立的 memory：

1. Codex 原生 `~/.codex/memories/`，内容由 Codex 自动生成，通过用户级 hook 与 GitHub 私有仓库持续同步，允许一定时效偏差。
2. 项目 `.codex/memory/`，继续由 `memory_context.py`、summary、项目 Git 和确定性检索机制维护。

本卡承接 `.runtime/handoff/feedback_memory_governance_discoverability_not_count.md` 的审计结论，并替换其中已经过时的本机原生 memories 开关状态。

## 目标

- 退役 Codex 项目 memory 对 `~/.codex/projects/<hash>/memory/` 的错误依赖，保持项目知识库与原生 memories 分离。
- 让项目 `MEMORY.md` 在 SessionStart 后确定性进入任务上下文。
- 让 UserPromptSubmit 自动召回 3-5 个候选，并让 agent 读取最相关的 1-2 个正文。
- 改进项目 memory 的字段加权排序和运行时可审计回执。
- 在用户同意开启原生 memories 后，通过用户级 hooks 和 `$bridgeforge` 将整个 `~/.codex/memories/` 最终一致地同步到 GitHub 私有仓库。
- 支持单写入设备下的换机恢复，以整套最新快照覆盖旧快照。

## 不做

- 不把 `.codex/memory/` 与 `~/.codex/memories/` 合并或 junction 到同一目录。
- 不修改 Claude Code 的项目 memory junction。
- 不引入 vector DB 或语义向量服务。
- 不支持两台电脑同时写入原生 memories。
- 不加密 GitHub 中的 memories。
- 不保证会话退出前 GitHub 已确认上传成功。
- 不由 BridgeForge 创建、编辑或整理原生 memory 正文。
- 不自动 commit 或 push BridgeForge 源码。

## 任务规模与预算

- 规模：L。
- 依据：跨越项目 memory 架构、用户级 Codex 配置与 hooks、GitHub 外部状态、换机恢复、模板传播、dogfood 和发布元数据。
- 时间预算：2-3 小时。
- token 预算：最多 60k 新增 token（估算，平台无可靠计量器，未实测）。
- agent 预算：最多 3 个阶段性子 agent，分别用于只读 discovery、实现和独立审计。
- 验证预算：3 轮。
- 超预算停止点：扩大功能范围、增加 agent、进入第 4 轮验证、或需要支持多设备并发写入前必须停止确认。

## 已核实事实

- 审计报告确认项目热索引只重建磁盘文件，当前没有确定性证据证明其内容进入当轮上下文。
- 当前 `memory_search.py` 只按正文词频排序并截取前 10 个结果。
- 当前项目 `_stats.json` 不保存历史访问次数，不能补算真实加载次数。
- Codex 模板、hook 和 `$bridgeforge` init/update 手册仍把 `~/.codex/projects/<hash>/memory/` 当成项目 memory 系统路径。
- 当前官方 Codex memories 位于 `~/.codex/memories/`，属于本地生成状态；生成可能在后台延迟发生。
- Codex 支持用户级 `~/.codex/hooks.json`，并支持 `SessionStart`、`Stop`、`SessionEnd` 等事件；普通用户级 hook 需要 review/trust，且用户可禁用。
- 当前本机 `config.toml` 已设置 `features.memories=true`、`memories.generate_memories=true`、`memories.use_memories=true`；原报告中“未开启”的事实已经过时。
- 当前本机用户级 `hooks.json` 已包含 SmallDesktopDisplay 的多类 hook，新增同步 hook 必须 merge 并逐字保留既有配置。
- 当前 BridgeForge 工作区在确认阶段未显示已跟踪或未跟踪改动，仅出现用户级 Git ignore 权限警告。

## 未核实事实

- 真实 Codex Desktop 中新增用户级 hook 的 trust 与事件时序尚未 smoke。
- 真实 GitHub 仓库创建、公开转私有、单提交 force-with-lease 和换机恢复尚未联调。
- GitHub 对不可达旧对象的后端保留周期不受 BridgeForge 控制；“只保留最新”不等于安全擦除。
- Codex 原生 memories 的内部文件组织属于生成状态，BridgeForge 只能按不透明整树快照处理。

## 已确认业务规则

### 原生 memories 启用

1. BridgeForge 默认不擅自开启原生 memories。
2. `$bridgeforge` 每次发现原生 memories 未开启时都提示用户。
3. 用户拒绝时继续其他 BridgeForge 工作，不创建仓库、不安装同步 hook。
4. 用户同意时，才 merge 用户 `config.toml` 并确保 `features.memories`、`memories.generate_memories`、`memories.use_memories` 为 true。
5. 用户以后关闭原生 memories 时，已有仓库和 hook 保留，hook 稳态 no-op；重新开启后恢复同步。

### GitHub 仓库

1. 使用当前 `gh` 登录账户下固定名称 `bridgeforge-codex-memories`。
2. 仓库必须是私有仓库，内容明文保存。
3. `gh` 未安装或未登录时，停止本次 memories 配置，提示用户处理后重新运行；禁止自动启动登录流程。
4. 仓库不存在时由 `$bridgeforge` 自动创建私有仓库。
5. 同名仓库已经存在且为私有时复用。
6. 同名仓库为公开时，必须先取得用户明确确认；确认后才允许转为私有，未确认前禁止上传。

### 快照与同步

1. 同步整个 `~/.codex/memories/`，仅排除临时文件、锁文件和同步工具自己的元数据。
2. 采用单写入设备模型，同一时间只有一台电脑使用 Codex。
3. 比较整套 memories 快照，最新快照整体覆盖旧快照；禁止逐文件拼接成混合状态。
4. 快照清单至少包含 UTC 捕获时间、递增版本、文件相对路径和 SHA-256；实现须保留足够状态来判断本地、远端或未同步变化。
5. 不保留本地覆盖备份。
6. GitHub 分支始终只保留一个快照提交；每次同步以 `--force-with-lease` 替换该提交。
7. `SessionStart` 执行完整 reconciliation；`Stop`、`SessionEnd` 触发非阻塞上传；无参数 `$bridgeforge` 执行完整补同步。
8. 只有内容变化才产生快照，不产生空提交；短时间重复触发须去重。
9. 同步失败只输出警告并保留待补同步状态，不阻止 Codex 对话；允许本地与 GitHub 存在时效偏差。

### 用户级 hook

1. 同步 hook 安装到 `~/.codex/hooks.json`，对所有项目生效。
2. 必须按稳定 command 身份 merge，保留用户全部既有 hook、事件、matcher 和字段。
3. `$bridgeforge` 必须安装、检查并修复缺失或漂移的同步 hook。
4. 尊重 Codex `/hooks` review/trust；BridgeForge 不伪装为企业 managed hook，也不剥夺用户的最终禁用权。

### 项目 memory

1. `.codex/memory/` 继续作为项目 Git 跟踪的知识库，不写入原生 memories 仓库。
2. 退役 Codex 的 `~/.codex/projects/<hash>/memory/` junction 和相关 init/update/runtime 契约；Claude Code junction 保持原状。
3. SessionStart 必须在索引重建后注入压缩的 `MEMORY.md` additional context。
4. UserPromptSubmit 使用轻量 router 自动返回 3-5 个候选路径、摘要和命中理由；agent 再读取最相关的 1-2 个正文。
5. 排序优先级：exact topic / related_paths > tags > name / description > 正文词频 > created_at。
6. `$find-memory` 保留为深度检索和人工兜底，不再是唯一入口。
7. 每轮显示类似 `Memory: auto searched X; candidates N; used M` 的可见回执，并将检索、候选和正文读取事件写入 `.runtime/memory_usage.jsonl`。
8. 运行事件禁止写回 `_stats.json`，避免污染项目知识库和 Git。
9. `$summary` 继续通过项目 `project_memory_writer.py` 写入 `.codex/memory/` 并重建索引。

## 数据映射

| 数据 | 唯一事实源 | 云端/版本载体 | 加载方式 |
|---|---|---|---|
| Codex 原生 memories | `~/.codex/memories/` | 私有仓库 `bridgeforge-codex-memories` 的单一最新快照 | Codex 原生机制 |
| 项目 memory | `<repo>/.codex/memory/` | 当前项目 Git | SessionStart context + UserPromptSubmit router + `$find-memory` |
| 同步运行状态 | 用户级同步工作目录 | 不进入 memories 快照 | `$bridgeforge` 与用户级 hooks |
| 项目召回运行事件 | `<repo>/.runtime/memory_usage.jsonl` | 不提交 Git | 诊断与验收 |

## 拟修改范围

### 产品层

- `templates/codex/hooks.json`、`templates/codex/hooks/hook_dispatcher.py`。
- 退役 `templates/codex/hooks/memory_junction_check.py` 的 Codex runtime 角色，并清理 Codex 活文档/手册中的假路径契约。
- 新增或调整项目 memory context、router、search 和 usage receipt 脚本。
- `skills/bridgeforge/SKILL.md` 与相关 `references/`，加入原生 memories 询问、用户配置 merge、仓库 onboarding、hook health 和补同步流程。
- `scripts/` 中的用户级原生 memories 同步、配置/hook merge 与 GitHub orchestration 脚本。
- `shared-skill-manifest.json` 及其清单重建逻辑/测试。
- `tests/harness/` 中的项目召回、junction 退役、用户 hook merge、快照选择、单提交同步与分发覆盖测试。

### 自身 dogfood

- `.codex/hooks.json`、`.codex/hooks/hook_dispatcher.py` 和项目 memory 相关脚本与模板保持镜像。
- 用户级真实 hook 与 GitHub 仓库属于外部状态，不在无额外授权时由代码实现阶段直接创建；在用户试运行 `$bridgeforge` 时验收。

### 元文档与发布

- 本需求卡与 `doc/README.md`。
- 必要的 `doc/0_architecture/design/` memory 设计说明。
- `VERSION`、`CHANGELOG.md`，按 `[product]` / `[meta]` 标记。

## 验收标准

1. Codex 模板和 BridgeForge 活手册不再把 `~/.codex/projects/<hash>/memory/` 当成有效项目 memory 路径；Claude junction 测试继续通过。
2. SessionStart 重建项目索引后，hook 输出含受预算限制的项目 memory context。
3. UserPromptSubmit 对验收集返回 3-5 个候选，并达到约定的 top-5 命中；字段权重能够把 exact topic/path 结果排在正文词频噪声之前。
4. runtime receipt 可区分未搜索、零候选、有候选和已读正文，且 `.runtime` 事件不修改 `_stats.json`。
5. 用户级 hook merge 测试证明现有 SmallDesktopDisplay 类第三方 hook逐字保留，BridgeForge handler 幂等增补和修复。
6. memories 未开启时每次询问；拒绝零配置写入并继续；同意后只 merge 三个开关并保留其他用户配置。
7. GitHub 仓库创建命令固定为私有；公开同名仓库未经确认不得转私有或上传。
8. 整树快照排除规则、hash 清单、最新整套覆盖、无本地备份和单提交 force-with-lease 均有隔离测试。
9. SessionStart、Stop、SessionEnd 和 `$bridgeforge` 触发路径均覆盖；失败路径只告警并可在后续触发补同步。
10. 相关 harness、JSON/TOML 解析、manifest check、mirror drift 和 `git diff --check` 通过。
11. 真实 `/hooks` trust、新会话 smoke 和真实 GitHub 建仓/换机恢复若未在当前会话完成，必须明确标为“未验证”，不得用静态测试冒充。

## 合理假设与风险

- 用户接受 GitHub 私有仓库中的明文 memories 可能包含敏感项目上下文。
- 用户接受无本地备份和单一远端快照带来的不可恢复风险。
- 用户接受 GitHub 可能暂时保留 force-push 后的不可达对象，BridgeForge 不提供安全擦除保证。
- 单写入设备约束成立；若未来需要并发多机写入，必须另开需求重新设计冲突模型。
- Codex 原生 memory 文件视为不透明生成状态；BridgeForge 不依赖其内部 schema。
- GitHub、网络或 hook 失败时采用最终一致，不做强制退出阻断。

## 自动化与权限边界

- 需求卡确认只授权写入本仓库文档；产品代码实现需经过 `$develop` 最终开工确认。
- 开发测试优先使用临时 HOME、mock `gh` 或本地 bare repository，不创建真实 GitHub 仓库。
- 真实创建/改可见性/force-push 私有仓库只在用户运行 `$bridgeforge` 并通过对应交互确认时发生。
- 不自动执行 `git add`、commit 或 push BridgeForge 源码。

## 实施计划

- [x] Discovery：核对项目 memory 入口、用户级 command bundle、分发清单、测试夹具和版本边界。
- [x] 实现：项目 memory 确定性加载/召回/回执与 Codex junction 退役。
- [x] 实现：原生 memories 用户配置、hook merge、快照和 GitHub orchestration。
- [x] 传播：模板、dogfood、skill references、manifest、版本与文档。
- [x] 验证：自动测试与独立审计已完成并由用户明确验收；真实用户级同步 hook trust 和 GitHub 换机恢复保留为未验证的上线边界。

## 实施记录

- 项目 memory：新增 SessionStart 6000 字符确定性上下文、UserPromptSubmit 3-5 项中英文加权召回、PostToolUse 读取回执和按 session/turn 隔离的 `used M` 统计；停止修改 `_stats.json`。
- 路径治理：退役 Codex `~/.codex/projects/<hash>/memory/` junction 运行时角色，保留 Claude junction；模板与 BridgeForge dogfood 镜像同步。
- 原生 memories：新增 `scripts/codex_memory_sync.py`，实现显式启用、用户 hook merge、私有仓库准备、整树快照、最新整快照胜出、parentless force-with-lease、单实例锁、超时、pending 和 SessionStart/Stop/SessionEnd 触发。
- 安全边界：不创建真实 GitHub 仓库；快照拒绝 symlink 和 Windows junction；临时明文工作树每轮删除，删除失败会记录路径并在下一轮优先清理，清理完成前不创建新快照。
- 传播：版本升至 `0.85.0`，更新 CHANGELOG、BridgeForge skill/references、架构说明和共享分发 manifest。
- 独立审计发现的 Hook 字段、中文分词、并发、快照竞态、损坏远端、本地 I/O、临时备份、命令超时、普通仓库初始化和 junction 问题均已修复并补测试。

## 验证记录

- 用户验收：2026-08-14 明确执行 `$summary 同意验收`；Codex Desktop 新任务已实际命中一条原生 memory，并在“引用的记忆”悬浮框显示对应引用。为模拟可见提示而短暂加入的 Hook 文案实验已全部回滚。
- 回滚后复验：memory/Hook/junction 51 项与共享分发 18 项，共 69/69 通过；mirror drift、manifest check 和 `git diff --check` 均通过。
- 相关回归：分别运行 9 个 harness 文件，共 103 项通过、0 失败：`test_memory_native_sync.py` 23、`test_codex_hook_single_source.py` 25、`test_memory_junction_check.py` 3、`test_memory_rebuild_index.py` 4、`test_memory_lifecycle_governance.py` 6、`test_project_memory_recovery.py` 10、`test_summary_skill.py` 9、`test_bridgeforge_root_skill.py` 5、`test_shared_skill_distribution.py` 18。
- 分发硬闸：`.venv\\Scripts\\python.exe scripts\\rebuild_shared_skill_manifest.py --check` 返回 `already current`。
- dogfood 硬闸：`.venv\\Scripts\\python.exe .codex\\hooks\\mirror_drift_check.py` 退出 0，模板与自身镜像无漂移。
- 静态硬闸：变更相关 Python AST、JSON、TOML 解析通过；`git diff --check` 退出 0，仅报告既有行尾转换警告。
- 隔离测试覆盖：GitHub 失败不改配置、hook 幂等 merge、中文召回、真实 Windows junction、快照复制竞态、并发去重、损坏/普通远端修复、本地 I/O 禁止误覆盖、整树恢复、单 parentless commit、临时目录清理和命令超时。
- 未验证：真实 Codex Desktop 的用户 hook trust、新会话实际读文件工具成功/失败载荷与时序；真实 GitHub 建仓、公开转私有、网络 force-with-lease 和换机恢复。开发阶段按权限边界未触碰这些外部状态。

## 验收后缺陷修复：项目 venv 与用户 Hook 运行时

- 现象：下游项目 `.venv` 已是 Python 3.11+，但原生 memories onboarding 仍被跳过；项目骨架更新继续完成，用户未得到 GitHub 仓库和同步 hook 收据。
- 根因：原生 memories 步骤先于项目 Python preflight，且只检查 PATH 的 `python/python3`；同步脚本还把 setup 进程的 `sys.executable` 直接写入用户级 hook，导致简单复用项目 venv 会把项目路径持久化到全局配置。
- 修复：统一 Python preflight 前置，onboarding 复用 `$HOOK_PYTHON`；setup 可由项目 venv 执行，但用户级 hook 固定写入该 venv 的 Python 3.11+ 基础解释器。status/setup 收据新增 setup Python、hook Python、hook 健康和远端配置状态。
- 安全边界：基础解释器不存在时不安装依赖项目目录的用户 hook；隔离测试继续 mock GitHub 和用户目录，不触碰真实 `~/.codex/hooks.json` 或远端仓库。
- 验证：项目 memory / hook / lifecycle / recovery / BridgeForge 入口相关回归 90/90 通过；共享 skill 分发 18/18 通过。真实 GitHub 建仓和 Codex `/hooks` trust 仍留给下游试用，不在隔离测试中改动外部状态。

## 后续交接目标

交给用户试用：更新后的下游项目运行 `$bridgeforge`，确认 `setupPython` 可为项目 `.venv`、`hookPython` 为稳定基础解释器，并完成真实 GitHub onboarding；随后在新会话核对 `/hooks` 载荷、远端最新快照和换机恢复。任何多设备写入或加密范围变化必须重新确认。
