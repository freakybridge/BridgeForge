---
title: ClaudeBridgeAssist BridgeForge 1.4.26 白名单式干净安装需求
status: confirmed
date: 2026-08-20
product_version: 1.4.26
source: $confirm
---

# ClaudeBridgeAssist BridgeForge 1.4.26 白名单式干净安装需求

## 原始需求摘要

用户决定先只处理 `D:\Quant\ClaudeBridgeAssist`：不再为本次安装追溯旧骨架谱系，回退未完成的
1.4.27 release-artifact 方案，以已审计的 1.4.26 为一次性干净基线。安装前逐项确认项目内容
白名单，保留项目 rule 语义、项目 hooks、根 `AGENTS.md` 项目区及其他 CBA 资产；安装完成后再按
正常更新检查流程维护。

## 目标

- 保存 CBA 完整 before 状态与可复验摘要。
- 按已确认白名单保留项目资产，清理其余旧 BridgeForge 骨架并安装 1.4.26。
- 完成 `plan -> apply -> validators -> stamp-last -> no-op replan`。
- 形成逐项保留、替换、删除和未触碰内容的最终报告。

## 不做

- 不删除 Git 历史、项目 memory 正文或业务资料。
- 不修改 Causis、Stratus 主项目或 M2 worktree。
- 不对 CBA 执行 reset、restore、stash、clean、commit 或 push。
- 不遍历、复制、删除或重建 `vault/`，不重建 `vault-mirror/`。
- 不并发执行 Native Memory 用户级 hooks status/repair。
- 不把无法证明所有权的内容归入公共骨架或自动删除。

## 任务规模与预算

- 规模：L。
- 依据：包含产品 1.4.27 定向回退、白名单式重装、真实 dirty 项目保护和独立审计。
- 时间预算：90 分钟。
- token：未实测，以范围增长、agent 数和验证轮次作为代理闸。
- agent：最多复用 1 个独立审计 agent。
- 验证：最多 2 轮完整验证。
- 停止点：出现新的项目所有权类别、无法分类资产或预计超出任一预算时，停止并只向用户确认一个问题。

## 已核实事实

- CBA 当前骨架戳为 1.4.25，Git 工作树在确认阶段为 clean。
- CBA 没有 `.claude/` 遗留目录。
- 根 `AGENTS.md` 已有完整公共区与项目区标记；项目区声明 CBA vault 数据流和安全红线。
- `.githooks/pre-commit` 项目扩展区为空。
- `.codex/config.toml` 与五个 `.codex/agents/*.toml` 均为公共骨架配置。
- `.codex/scripts/` 未识别出 CBA 项目专用脚本。
- CBA 项目 hook 为 `vault_junction_check.py` 与 `vault_snapshot.py`，当前注册使用裸 `python`。
- CBA 项目 rule 仅有 `.codex/rules/obsidian_vault.md`，其有效红线已存在于根 `AGENTS.md`
  项目区；该文件被项目区定义为历史参考，不是运行时指令源。
- CBA 项目 Skill 为 `vault`、`vault-chat`、`linkify`；`vault` 与 `linkify` 缺当前标准
  frontmatter。
- `.codex/memory/` 保存 CBA 项目事实；`MEMORY.md`、`MEMORY_COLD.md` 是派生索引，
  `_stats.json` 保存索引配置与 `created_at` 元数据。
- `vault_node_map` 是 Git 跟踪的多机器 vault 地址表；`vault_path.local` 是 Git 忽略的本机备用路径。
- `vault/` 是指向 `F:\BridgeCloudDrive\Obsidian\Main` 的 junction；`vault-mirror/` 是 Git 管理的普通目录。
- BridgeForge 1.4.26 是上一轮已完成测试与独立审计的版本；1.4.27 是未完成的连续未提交发布
  artifact 草稿，尚未安装到真实项目。

## 已确认保留白名单

### 根指令与 rule

- 根 `AGENTS.md` 项目区逐字保留。
- 将 `obsidian_vault.md` 的全部有效红线并入并复核根 `AGENTS.md` 项目区，随后删除该旧 rule。
- 公共区安装 1.4.26 canonical 内容。

### 项目 hooks

- 保留 `.codex/hooks/vault_junction_check.py`。
- 保留 `.codex/hooks/vault_snapshot.py`。
- 两个 hook 的业务脚本内容不改；注册命令改用当前项目 `.venv\Scripts\python.exe`。
- 其余 hooks 与带 `bridgeforgeCodexId` 的 dispatcher 安装 1.4.26 公共版本。

### 项目 Skills

- 保留 `vault`、`vault-chat`、`linkify`。
- 只补齐当前 Skill frontmatter，不改变业务流程、参数或外部副作用。

### 项目 memory

- 保留全部正文和 `_stats.json` 有效配置、时间元数据。
- 使用 1.4.26 脚本重新生成 `MEMORY.md`、`MEMORY_COLD.md`。

### vault 与机器映射

- 逐字保留 `vault_node_map` 和 `vault_path.local`。
- 安装器不得触碰 `vault/` junction 或 `vault-mirror/` 内容。

### 其他项目边界

- `.githooks/pre-commit` 空项目扩展边界保留。
- 业务代码、文档、根业务 `VERSION`、Git 状态和所有非骨架内容不在写入范围。

## 公共骨架替换范围

- `.codex/hooks/` 中除两个 vault hook 外的公共 hooks。
- `.codex/scripts/`、`.codex/agents/`、`.codex/config.toml`、`.codex/skill-routing.json`。
- 1.4.26 managed contract、骨架版本戳及合同明确列出的公共资产。
- `.githooks/pre-commit` 公共区和根 `AGENTS.md` 公共区。

## 自动化与安全边界

- before 清单完成后，安装器必须先验证白名单冻结值，再执行任何删除或覆盖。
- 发现清单外且无法证明为公共骨架的文件时，必须整轮零删除并停止。
- 事务失败必须恢复本轮写入；禁止用手工改戳、删冲突文件或提交混杂工作区绕过。
- Native Memory 只允许串行状态核验；repair 必须由独立证据触发且不得与其他项目并行。
- 用户级或外部 vault 资源不属于本事务。

## 验收标准

1. before 文件清单、Git 状态、骨架戳和关键摘要已保存。
2. 白名单内容逐项相等，或只发生本卡明确批准的 runtime/frontmatter 适配。
3. `obsidian_vault.md` 红线在根 `AGENTS.md` 项目区语义齐全且旧文件删除。
4. 1.4.26 公共骨架资产与 canonical 源一致。
5. 当前项目 `.venv` 通过 CPython 3.11+ runtime identity 验证。
6. CBA 项目 validators 全部通过。
7. 统一 release evaluator 通过后最后写入 1.4.26 骨架戳。
8. no-op replan 的 safe/risk/gap/blocker/action-required 均为零。
9. `vault/`、`vault-mirror/`、业务代码和 memory 正文没有未批准变化。
10. 独立审计 Blocker/High/Medium 为零。
11. 最终报告记录保留、适配、替换、删除、验证和未验证边界。

## 合理假设与风险

- “摒弃历史”仅适用于本次 CBA 旧骨架识别，不删除 Git 历史、项目 memory 或业务资料。
- 1.4.27 回退只撤销本轮 release-artifact 草稿，不撤销已验收的 #1～#9 和 1.4.26 修复。
- `vault/` 当前 junction 目标在安装期间保持不变；本任务不验证或写入外部活库正文。
- 三个项目 Skill 的 frontmatter 适配可能触发 metadata gate，必须以定向测试验证而非修改其业务正文。

## 后续交接目标

- 用户直接调用 `$confirm`；确认完成后进入实施交付流程。
- 首阶段只交付 CBA，完成报告和用户验收后再决定 Causis 与两个 Stratus checkout 的顺序。

## 实施记录占位

- 实施计划：
  1. 仅撤销 1.4.27 release-artifact 草稿，恢复 1.4.26 VERSION、产品代码、测试、合同和文档口径。
  2. 运行 1.4.26 定向与完整产品闸；失败时只允许一次实质修复重测。
  3. 冻结 CBA before 与白名单摘要，执行白名单式安装并完成 validators、stamp-last、no-op。
  4. 独立审计产品回退和 CBA after，更新本卡及最终报告。
- Discovery：两次只读 light-explorer 调用均未在限定时间内返回，已按防循环规则中止；主对话继续以
  当前真实 diff、1.4.26 封存快照和既有独立审计证据确定精确回退块，最终 review 不因此豁免。
- 1.4.27 定向回退：产品源码、测试、合同、manifest 与文档口径已恢复到 1.4.26；两份临时 runtime artifact 已删除。
- 1.4.26 产品闸复核：完整 `unittest` 311/311 通过；downstream fixture `status=passed`，覆盖
  29 个发布版本、9 个自动迁移与 19 个显式适配场景；manifest、Template/dogfood 镜像与
  `git diff --check` 均 exit 0。
- CBA before：Git `master@55919c202acca6228e6bbf8bb58ca31c67d26244`，工作树 clean，骨架戳
  `1.4.25`，CPython 3.11.9 项目 `.venv` identity 通过。白名单摘要：AGENTS 项目区
  `sha256:4e226f44...ddd51`；两个 vault hook 脚本分别 `sha256:f1396bac...8b02`、
  `sha256:99dbedb7...89e6`；三个 Skill 正文分别 `sha256:79562d7b...b295`、
  `sha256:6a13ebae...b183`、`sha256:7b671331...7622`；29 个 memory 正文聚合
  `sha256:5d63bc01...a3bb`；`_stats.json` 为 `sha256:50a50039...d4e`；
  `vault_node_map` / `vault_path.local` 分别 `sha256:f558d275...ff63`、
  `sha256:d1c1c71f...8a76`；`vault/` 仍为指向 `F:\BridgeCloudDrive\Obsidian\Main` 的 junction。
  只读 Planner 为 `safe=0 / risk=0 / gaps=2 / blockers=0`，两个 gap 仅是已确认放弃旧谱系的
  managed contract 与 version-release whole-file 凭证；fingerprint
  `sha256:724766f8bfa257e862fbd0eb5a6235694988ab5caaecfe1ec0a994fbee441e12`。
- CBA 白名单安装：已完成。普通 transition 的 G1 明确不可执行；按用户批准的“摒弃历史”决定，
  在白名单、canonical after 和 validators 独立证明后封存一次性 1.4.26 新基线，未伪造历史或补 hash。
- validators/no-op：runtime、memory、config、instruction、structure、encoding、rule、mirror、Skill metadata
  与 diff 硬闸均通过；终态 no-op 的 safe/risk/gap/blocker/G 全零。
- 独立审计：待执行。
- 最终报告：已创建 `report_2026-08-20_cba-bridgeforge-1-4-26-clean-reinstall.md`，待审计后补最终结论。
