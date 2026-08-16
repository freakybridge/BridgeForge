---
status: implementing
size: L
---

# BridgeForgeCodex 1.0.0：Claude 退役与 Codex-only 全量改名需求卡

## 原始需求摘要

用户要求退役 Claude 骨架，使产品只专注 Codex；随后将整体项目改名为 `BridgeForgeCodex`，并采用破坏性的全技术标识迁移，不保留长期兼容入口。

## 调用来源与后续交接

- 调用来源：用户直接调用 `$confirm`。
- 当前阶段：实现与主代理验证已完成；首次独立审计发现的迁移阻断已修复，等待复审。
- 后续交接目标：`$develop`；实施完成并通过真实样本与独立审计后，必须等待用户明确“同意验收”，才可提交、推送及执行 GitHub/本地仓库改名。

## 目标

1. 完整退役 Claude 产品骨架、用户分发与 dogfood。
2. 删除双骨架 switch、map 和 parity 体系，使 BridgeForgeCodex 只维护 Codex。
3. 产品、仓库及全部活跃技术标识改名为 `BridgeForgeCodex 1.0.0`。
4. 保证所有 `0.86.0+` 已发布 Codex 骨架可直接升级至 `1.0.0`。
5. 保留现有下游 Codex 的 AGENTS、rules、hooks、memory 与项目定制。
6. 最终验收后完成 GitHub 仓库、本地目录和 `origin` 的实际改名。

## 不做

- 不迁移、清理或维护项目内 Claude 骨架。
- 不读取或修改下游项目的 `.claude/`、`CLAUDE.md`。
- 不测试 Claude 下游。
- 不重写历史需求卡、Bug 报告、归档文档或旧 CHANGELOG。
- 不在本轮处理“删除自定义 agents、改用 Codex 原生调度”的独立问题。
- 未经最终验收，不 commit、push 或修改 GitHub 仓库与本地仓库目录。

## 规模与预算

- 规模：L。
- 判定依据：破坏性产品退役、全局技术标识迁移、用户级资产重装、`0.86.0+` 升级兼容、GitHub 与本地仓库改名。
- 时间预算：180 分钟。
- Token 预算：约 90k 新增 token；平台无可靠计量器，未实测。
- Agent 预算：最多 3 个子 agent。
- 验证预算：最多 5 轮完整验证。
- 超预算停止点：无法保持 `0.86.0+` 兼容、真实样本出现未知破坏、需要读取/修改项目内 Claude 资产、GitHub 改名权限不足，或预计超过任一预算时停止，由用户选择扩大预算或缩小范围。

## 已核实事实

1. `templates/claude/**` 当前约有 50 个活跃产品文件。
2. BridgeForge 自身 `.claude/**` 当前约有 68 个 dogfood 文件。
3. `shared-skill-manifest.json` 仍向 `~/.claude/skills` 分发产品。
4. `$bridgeforge` 和 `scripts/bridgeforge_switch.py` 仍以 Claude/Codex 长期共存为基础。
5. `scripts/bridgeforge_project_sync.py` 已经是 Codex 专用同步器。
6. 当前 `main` 存在多轮已验收但未提交的 `0.95.0` 改动。
7. 两个高定制验收 worktree 均存在，但当前沙箱读取 Git 状态需要窄范围授权。
8. 当前远程地址为 `https://github.com/freakybridge/BridgeForge`，当前本地目录为 `D:\Quant\BridgeForge`。

## 已确认产品规则

1. Claude 采用彻底退役，不冻结兼容。
2. 删除活跃 Claude 模板、dogfood、分发、入口和测试；Git 历史自然保留，不复制一套 Claude 源码归档。
3. 项目中意外发现 Claude 资产时仅提示，不读取、不修改，也不阻止 Codex 更新。
4. `$bridgeforge switch claude|codex` 整体删除。
5. parity checker、比较测试和发布硬闸删除；相关设计与报告通过 `git mv` 进入 `doc/4_archive/`。
6. 历史需求卡、Bug、归档和旧 CHANGELOG 保持原文；只修改活跃入口、架构说明与运行手册，并新增 `1.0.0` 退役记录。
7. 所有风险动作合并为一张精确清单，整轮最多确认一次，并使用统一 fingerprint 防止确认后漂移。
8. 当前全部已验收改动合并进入 `1.0.0`，不再单独发布 `0.95.0`。
9. 旧技术标识不保留长期兼容别名；旧 `$bridgeforge` 仅允许承担一次过渡启动。
10. 已发布旧 updater 硬编码要求双 platform、旧 bundle 名和旧 canonical remote，无法在同一调用中直接消费 Codex-only 新 manifest；迁移必须分两步完成。

## 标识映射

| 旧标识 | 新标识 |
|---|---|
| `BridgeForge` | `BridgeForgeCodex` |
| `$bridgeforge` | `$bridgeforge-codex` |
| `skills/bridgeforge/` | `skills/bridgeforge-codex/` |
| `bridgeforge_*.py` | `bridgeforge_codex_*.py` |
| `BRIDGEFORGE_*` | `BRIDGEFORGE_CODEX_*` |
| `.codex/.bridgeforge_version` | `.codex/.bridgeforge_codex_version` |
| `~/.bridgeforge` | 删除后安装 `~/.bridgeforge-codex` |
| 旧 Codex managed ledger | 删除后生成 BridgeForgeCodex 新 ledger |
| `freakybridge/BridgeForge` | `freakybridge/BridgeForgeCodex` |
| `D:\Quant\BridgeForge` | `D:\Quant\BridgeForgeCodex` |

## 用户级迁移

1. 用户最后运行一次旧 `$bridgeforge`：过渡 manifest/入口只负责安装并验证新 `$bridgeforge-codex`，随后明确停止并提示改用新入口；当前旧进程禁止继续项目写入或清理。
2. 用户首次运行新 `$bridgeforge-codex`：新入口重新规划并汇总唯一风险卡，确认后删除旧 `~/.bridgeforge` command bundle、旧 Codex managed ledger 与受管旧 `$bridgeforge`，再完成新 `~/.bridgeforge-codex` 和新 ledger 的终态验证；不继承旧产品状态。
3. 删除 ledger 能证明由 BridgeForge 安装的全部 `~/.claude/skills/**` 文件；清空后删除 BridgeForge 的 Claude managed ledger。
4. 第三方、人工或 ownership 无法证明的 Claude 文件必须保持不动。
5. 用户级重装不得删除或重建下游项目的 Codex 骨架和项目定制。

## 项目级迁移

1. 有效 `.codex/.bridgeforge_version` 在整轮唯一一次风险确认中事务迁移为 `.codex/.bridgeforge_codex_version`。
2. 两个版本戳同时存在、内容异常、ownership 不明确或确认后发生漂移时必须零覆盖。
3. 迁移失败必须回滚；验证完成前禁止写新版本戳。
4. `AGENTS.md`、`.codex/rules/`、hooks、memory 和项目自定义继续使用受管资产事务升级，禁止整套删除重装。
5. 每个 `0.86.0+` 已发布 Codex lineage 必须能够直接迁移到 `1.0.0`。

## 拟修改范围

- 删除 `templates/claude/**`、`.claude/**`。
- 删除 Claude 用户级分发、入口脚本和 manifest platform。
- 删除 switch 脚本、协议、map、活跃文档与测试。
- 删除活跃 parity 工具与硬闸，归档 parity 设计与报告。
- 重命名 BridgeForge skill、脚本、配置、hook 标记、receipt、schema、manifest 和版本戳。
- 更新 Codex 模板、AGENTS、rules、文档索引、README、VERSION、CHANGELOG。
- 重建 `BridgeForgeCodex 1.0.0` lineage 与全部派生清单。
- 更新所有当前测试和 fixture。
- 最终验收后改 GitHub 仓库、本地目录和 `origin`。

## 自动化与安全边界

- 所有删除目标必须先解析为精确绝对路径；禁止用 glob 或名称猜测 ownership。
- 第三方、人工修改或无法证明来源的用户文件不得删除。
- 用户级重装必须先验证新 bundle，再退休旧 bundle；失败时恢复旧入口与 ledger。
- 项目迁移必须具备 fingerprint、TOCTOU 复核、事务快照和回滚。
- planner、dry-run、`--check` 必须零写入。
- 项目内 Claude 资产只生成不支持提示，禁止扫描其内容或将其纳入删除计划。
- GitHub 与本地目录改名只能在用户最终“同意验收”后执行。

## 验收

1. Codex-only 全量自动测试通过。
2. 完整 downstream fixture 通过。
3. 两个高定制 worktree 全部通过，且项目定制不得丢失：
   - `D:\Quant\CodexWorktree\test_bridgeforge`
   - `D:\Quant\CodexWorktree\test_bridgeforge_crs`
4. 每个 `0.86.0+` 发布 lineage 都能直接迁移到 `1.0.0`。
5. 用户级两步迁移（旧入口只安装/验证并停止，新入口清理）、Claude 托管清理、失败回滚和 fingerprint 漂移均有测试。
6. 活跃产品面不再含 Claude 模板、Claude 分发、switch 或 parity 依赖。
7. 旧技术标识只能出现在迁移识别器或历史文档中。
8. manifest、schema、mirror、metadata、结构检查和 `git diff --check` 全部通过。
9. 独立 agent 完成发布审计。
10. 用户同意验收后，提交推送并完成：
    - GitHub：`https://github.com/freakybridge/BridgeForgeCodex`
    - 本地：`D:\Quant\BridgeForgeCodex`
    - `origin` 指向新地址。

## 合理假设与风险

- 这是破坏性升级，旧命令、旧目录和旧内部标识会消失。
- GitHub 仓库仍由 `freakybridge` 所有，当前凭据具备改名权限；实施前必须实时核验。
- 用户级旧 bundle 可能含未知改动，删除前仍必须展示精确路径和可恢复性，纳入唯一风险确认。
- 当前工作区存在大量已验收未提交改动，重命名时必须全部保留。
- 本地目录改名会使当前 Codex 任务的工作目录失效，因此只能作为最终动作。
- GitHub 改名失败时不得破坏已推送仓库或伪称远端迁移完成。

## 实施记录

- 实施顺序：先落地旧入口到新入口的两步迁移桥，再实现项目双版本戳事务迁移；随后完成 Codex 产品全标识改名、用户级 ownership 清理、Claude/switch/parity 退役和历史 parity 归档；最后重建 schema/manifest 并验证全部 `0.86.0+` 已发布 lineage、完整 fixture 与两个真实样本。
- 用户级终态：完整产品仓库固定在 `~/.bridgeforge-codex`；`~/.codex/skills/bridgeforge-codex` 只保留 `SKILL.md`、references 与 bootstrap updater。旧 updater 安装薄入口后停止；新入口先原子安装 / 验证新 home，再把可信旧 home、旧 Codex bundle / ledger 与 Claude ledger-owned skills 合并进唯一风险卡。
- 旧 `~/.bridgeforge` 是普通 Git home 时，仅在 origin 为旧官方仓库且 fingerprint 未漂移时退休；若是已核验 junction，只删除 junction、保留实体仓库；来源不明或 reparse 目标不可验证则保留为 gap。
- 旧入口兼容仅允许存在于迁移桥；不得恢复 Claude 正常维护能力或长期旧命令别名。
- 分离两份 manifest：`shared-skill-manifest.json` 只服务旧 updater，完整冻结旧 Codex/Claude 受管 skill payload，防止旧进程在统一确认前删除或改写；`bridgeforge-codex-manifest.json` 是 Codex-only 新产品分发 SoT。新 updater 仅在旧 ledger hash 与磁盘实际 hash 一致时接管并事务升级活跃 Codex 资产，人工漂移仍硬阻断。
- 原生 memories 保留为 Codex-only 能力：旧 hook marker 与 `.codex/.bridgeforge/memory-sync` 仅作为迁移输入，维护/首次设置后改写到 BridgeForgeCodex 新标识；普通旧产品 home 只要 Git 工作区非干净就保留为 gap。
- `.agents` 项目旧布局迁移重新接入根 skill，并与用户迁移、原生 memories、项目同步共享同一个 Python 3.11+ 解释器和唯一风险确认。
- 历史 AGENTS 的项目名渲染采用节级显式 normalizer：仅标准 `git clone <repo_url> X && cd X` 且两处 `X` 相同时归一化；迁移后保留原项目名，章节其他改写继续按 gap 零覆盖。
- 实现已完成；GitHub、本地目录、origin、commit 与 push 仍按最终验收闸保持未执行。

## 验证记录

- Codex-only 完整自动测试：`.venv\Scripts\python.exe -B -m unittest discover -s scripts\tests`，最近稳定快照 `208/208` 通过；覆盖项目事务、用户级 ownership/fingerprint、dirty home 保留、原生 memory consent/标识迁移、`.agents` 布局迁移、故障注入回滚、技能与 hook 契约。最终独立复审将在当前落稳快照重跑。
- 真实旧 updater → 新 updater 交接回归直接消费仓库实际两份 manifest 与全部冻结 skill payload：旧阶段除 `$bridgeforge` 过渡 stub 和新 `$bridgeforge-codex` 外，旧 Codex/Claude skill 字节保持不变；新阶段按旧 ledger ownership 升级全部活跃 Codex skill，并保留 `native_memories=declined`。
- 完整 fixture：`.venv\Scripts\python.exe -B scripts\tests\run_downstream_fixture.py` 通过；覆盖 Claude existence-only、Codex init stamp-last、legacy marker migration，并真实构造、应用和二次 no-op 验证 Git 历史中 19 个可达的 `0.86.0+` 发布基线（CHANGELOG 共识别 29 个发布标签）。
- 高定制样本 `test_bridgeforge_crs`：A 方案完成，39 safe、3 risk、2 个同键 U 项被吸收；`gaps=0`，二次计划 0 动作，旧戳删除、新戳为 `1.0.0`，原项目名 `causis_risk_suite` 保留。样本原有 P1-P3 空占位仍作为项目级待办显示，不由产品猜填。
- 高定制样本 `test_bridgeforge`：先把上轮测试残留保存到可恢复 stash，再从干净高定制基线执行 A；29 safe 与 5 risk 完成，16 个 gap 文件前后 SHA-256 全部一致，72 个定制 gap 保留，旧戳仍为 `0.90.0` 且新戳未写，二次计划 safe=0，符合 fail-closed 契约。
- 发布硬闸：manifest `--check`、skill metadata、project structure、mirror drift、`git diff --check` 全部 exit 0；结构检查只有既有归档候选 advisory。
- 最终独立发布审计：通过，无 blocker、high 或 medium 遗留。审计收据为完整单测 `208/208`、19 个 `0.86.0+` fixture 全部 apply + no-op、最终聚焦测试 `22/22`，以及 manifest、metadata、structure、mirror、`git diff --check` 全部 exit 0；唯一旧品牌文案尾项修复后又独立复核通过。
