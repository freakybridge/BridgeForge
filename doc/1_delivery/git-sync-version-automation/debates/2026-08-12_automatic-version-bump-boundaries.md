---
status: accepted-and-implemented
date: 2026-08-12
requirements: ../requirements_2026-08-12_git-sync-version-automation.md
issue: automatic version bump ownership, discovery, and failure atomicity
---

# `$git-sync` 自动版本升级边界辩论

## 目标

在不改变已确认业务规则的前提下，收敛一套可实施设计，重点回答：

1. 自动 bump 应进入 `$git-sync` 的哪个阶段，才能兼顾 fetch、stash、commit 与失败恢复。
2. 如何区分下游项目改动、纯 `/bridgeforge` 骨架更新和混合改动。
3. 如何以根 `VERSION` 为唯一事实源，安全同步常见原生版本字段和项目扩展配置。
4. 如何将 BridgeForge 三套版本与 CHANGELOG 迁移为一套，同时保持分发和更新契约有效。

## 已确认边界

- 有新提交才 bump；干净 no-op 或仅推送已有提交不 bump。
- BridgeForge 任意新提交 bump 唯一根 `VERSION`，只写根 `CHANGELOG.md`。
- 下游任何项目提交都 bump；纯 `/bridgeforge` 骨架更新不 bump；混合提交 bump。
- 下游根 `VERSION` 是唯一事实源，原生版本字段必须同步。
- 常见文件自动识别，允许项目配置额外位置；歧义、冲突、解析失败必须阻断。
- 已人工 bump 仍再自动 bump 一次。
- 提交类型映射：常规类型 patch，`feat` minor，breaking major。
- 用户确认最终辩论大纲前禁止实施。

## 待核实问题

- 当前 `$git-sync` 在 fetch/pull 前后处理脏工作区的真实时序与安全插入点。
- 当前 BridgeForge 管理路径是否已有可复用的机器清单，能可靠识别纯骨架更新。
- 原生版本字段及锁文件同步可支持到什么确定性边界。
- 删除模板 VERSION/CHANGELOG 会影响哪些 init、update、manifest、测试和版本戳逻辑。

## Agent 登记

- 只读研究：`/root/version_bump_research`（light-explorer）。
- A（implementation-worker）：`/root/version_bump_proposal`。
- B（review-auditor）：`/root/version_bump_audit`。

## 只读研究事实

1. 当前 runner 的真实时序是：读取 dirty → dirty 前置检查/生成 → fetch → 必要时
   stash/pull/pop → `git add .` → commit → push。自动 bump 最安全的写入窗口是远端
   合并完成、stash 已恢复之后，`git add .` 之前；写入后必须重新执行受版本影响的
   生成与验证。
2. 当前没有一个完整、机器可消费的“下游 BridgeForge 受管路径清单”。init/update
   手册提供人工分类，`precommit_merge.py`、`hooks_merge.py` 只覆盖局部所有权，
   `shared-skill-manifest.json` 不是下游受管路径清单。
3. 当前没有业务版本写回器。根 `VERSION` 与简单 `package.json` 可确定性支持；
   Cargo workspace、dynamic Python 版本、多 manifest 和各种锁文件存在歧义，不能以
   无边界文本替换实现。
4. 删除模板 VERSION/CHANGELOG 会影响分发 manifest、下游 fixture、init 复制清单和
   版本域测试；switch 已从 BridgeForge 根 VERSION 生成骨架版本戳，对删除模板
   VERSION 没有直接依赖。
5. 模板 CHANGELOG 历史不能只按版本标题去重；相同标题下内容可能不同。

## 研究证据入口

- runner 时序：`.codex/scripts/codex_git_sync.py:189-284`。
- 下游受管边界：`skills/bridgeforge/references/init.md:92-113`、
  `skills/bridgeforge/references/update.md:18-43`、
  `templates/codex/scripts/precommit_merge.py:26-29`、
  `.codex/scripts/hooks_merge.py:25-36`。
- 工厂版本检查：`.codex/scripts/factory_version_check.py:15-66`。
- 模板版本测试：`tests/harness/test_downstream_version_sot.py:62-209`。
- git-sync fixture：`tests/harness/run_downstream_fixture.py:2704-2895`。
- 分发完整性：`tests/harness/test_shared_skill_distribution.py:189-194`。

## 轮次记录

### 第一轮：方案与挑战

#### A：实现方案

- 将版本逻辑拆入独立纯逻辑模块，runner 只保留 Git 时序。
- 固定时序为：只读预检 → fetch/pull/stash-pop → 重新分类最终 diff → 构建零写入
  release plan → 写恢复日志 → 原子写版本与 CHANGELOG → 重建派生资产并验证 →
  add/commit/push。
- 用显式仓库配置区分 BridgeForge 工厂与下游；用 `/bridgeforge` 生成的逐文件
  hash 收据证明纯骨架更新，禁止只按路径前缀判断。
- 首版只支持稳定版三段 SemVer 和白名单 manifest schema；未知锁文件、dynamic
  version、多包歧义必须阻断。
- 删除模板 VERSION/CHANGELOG 前，将旧模板历史放入根 CHANGELOG 的宿主命名空间，
  再更新 init、manifest、fixture 与测试。

#### B：对抗审计

- 指出 commit/pre-commit 失败后重跑会再次 bump；必须有与 HEAD、消息和 diff 指纹
  绑定的恢复日志，同一现场重跑只能复用已准备版本。
- 指出“路径属于骨架”不等于“变化来自 `/bridgeforge`”；同一受管文件内可能保留
  项目扩展，必须以 `/bridgeforge` 的逐字更新收据证明来源。
- 指出根 VERSION 已存在时，它必须压过原生字段漂移；只有首次缺根 VERSION 时才
  把原生字段当候选，否则“人工 bump 后再 bump”与“不一致阻断”互相冲突。
- 指出 `perf` 在现有 git-sync skill 中合法，但确认卡没有 bump 映射；breaking
  正文还需要 message-file 流程。
- 指出 push 失败时变更已经位于本地提交，不一定留在工作区；失败验收必须按
  fetch、写入、commit、push 阶段分别表述。
- 指出 BridgeForge 根 CHANGELOG 的自动条目仍须保留 `[product]`、`[repo]`、
  `[meta]` 分类，否则下游更新收益筛选会失真。

### 第一轮共识

1. bump 必须在 fetch/必要 pull 和 stash-pop 成功后、`git add .` 前执行。
2. 必须采用先全量规划、再原子写入，并有可续跑恢复日志；否则失败重跑会连续跳号。
3. 纯骨架更新必须由 `/bridgeforge` 成功事务生成的逐文件收据证明，不能靠目录猜。
4. 原生 manifest 与锁文件只能采用明确适配矩阵；未知生态 fail closed。
5. 模板版本历史需命名空间迁移；新下游不应继承 BridgeForge 工厂 CHANGELOG。

### 升档与预算停止点

第一轮发现确认卡未包含两项新的跨流程数据契约：

- `/bridgeforge` 更新收据，用于可靠区分纯骨架与混合改动。
- git-sync release 恢复日志，用于防止 commit 失败重跑重复 bump。

两项都涉及新持久化 schema、跨流程生产/消费、迁移和安全测试，任务从 M 升为 L，
预计超过原 `45 分钟 / 20k token（未实测）/ 0 子 agent / 两轮验证`。按确认流程，
第二轮辩论和任何实施在用户选择扩大预算或缩小范围前暂停。

### 用户纠偏

用户明确指出：下游项目不允许修改 BridgeForge 受管骨架文件，因此为证明每个骨架
字节来源而设计 `/bridgeforge` 逐文件收据属于过度设计。

第二轮改用以下可信边界：

- 受管骨架路径由 BridgeForge 机器清单定义；普通项目流程触碰受管路径直接阻断。
- `/bridgeforge` 是唯一骨架更新入口；骨架版本戳变化作为该流程完成后的简单标志。
- 不额外防御用户伪造版本戳或主动绕过禁止规则。
- commit 失败优先回滚本次自动生成的 VERSION/manifest/CHANGELOG 改动，保留原项目
  修改；先评估是否可避免持久化恢复日志。

原 L 级升档理由撤销，第二轮要求 A/B 在原 M 级范围内收敛最小方案。

### 第二轮：精简方案再审

#### A：精简实现

- 取消逐文件来源收据；新增机器可读的受管所有权清单，只表达整文件、marker 区域和
  结构化 JSON 受管项三种边界。
- 下游宿主版本戳相对 HEAD 发生变化时，允许清单内的受管骨架变化；没有版本戳变化
  却修改受管部分时直接阻断。项目扩展区仍按项目改动处理。
- 取消持久恢复日志；runner 在内存中保存自动派生目标的工作区字节和 index 状态。
  apply、验证或 commit 失败时只精确恢复这些目标，不碰原项目修改；进程被强杀或
  断电恢复明确不在本期范围。
- 自动写入固定放在 fetch/必要 pull/stash-pop 完成之后、`git add .` 之前。
- 首版只支持白名单版本适配器，未知 workspace、dynamic version 或锁文件阻断。

#### B：最小安全边界

- 所有权清单不能只是路径列表；混合文件必须有 marker 或结构化成员边界。
- 纯骨架判断必须同时满足：版本戳变化、全部 diff 落在受管边界、没有任何项目改动。
- 回滚必须同时恢复工作区字节和原 index 状态；若目标文件出现并发变化，禁止覆盖。
- 根 VERSION 已存在时始终是起算基线；只有首次缺失时才从白名单候选推断。
- `perf` 必须补为 patch；breaking 正文必须实际覆盖 message-file。
- BridgeForge 根 CHANGELOG 必须继续生成 `[product]` / `[repo]` / `[meta]` 标签；
  push 失败应报告改动已在本地提交，而不是要求留在脏工作区。

### 最终推荐大纲

1. **受管骨架边界**：新增一份随模板下沉的机器清单，支持 whole-file、managed-region
   和 managed-json-member；普通下游修改受管部分直接阻断。
2. **纯骨架识别**：首版只接受“宿主骨架版本戳相对 HEAD 变化，且全部 diff 均位于
   受管边界”为纯骨架更新；出现项目改动则为混合提交并 bump 项目版本。
3. **同版本骨架修复**：首版不支持通过 `$git-sync` 豁免；避免新增流程状态文件。
   若将来确有需求，另行确认。
4. **版本时序**：fetch/pull/stash-pop 成功后重新读取最终 diff，构建零写入计划，
   再自动更新版本、白名单原生字段和 CHANGELOG，重建派生资产后 add/commit/push。
5. **失败恢复**：commit 前失败只回滚本次自动派生目标的工作区与 index 状态，保留
   原项目修改；commit 成功而 push 失败时保留本地提交；不承诺断电或强杀恢复。
6. **适配范围**：稳定版 `X.Y.Z`、根 VERSION、经过 fixture 验证的单根静态
   package/Cargo/pyproject 组合；未知 workspace、dynamic version 和未支持锁文件
   fail closed。项目额外位置只允许声明式 selector，禁止任意命令和正则替换。
7. **提交与 CHANGELOG**：补 `perf → patch`；完整消息支持 `!` 与
   `BREAKING CHANGE:`；BridgeForge 保留层标签，下游写最小项目发布记录。
8. **统一骨架版本迁移**：旧模板历史以 Codex/Claude 命名附录去重并入根
   CHANGELOG；init 不再复制工厂历史，首次项目提交创建项目 CHANGELOG；更新 manifest、
   fixture 和引用后删除两份模板 VERSION/CHANGELOG。

### 主要取舍

- 接受正常流程纪律，不防御用户主动伪造版本戳或绕过骨架修改禁令。
- 用 commit 失败时精确回滚换取无持久 journal；不覆盖进程级崩溃恢复。
- 首版宁可阻断复杂生态，也不承诺通用锁文件自动重写。

### 结论

该精简方案可维持 M 级，不需要新增跨流程来源收据或持久事务 schema；用户确认前
禁止实施。

## 收敛结论

> 待辩论完成并由用户裁定。
