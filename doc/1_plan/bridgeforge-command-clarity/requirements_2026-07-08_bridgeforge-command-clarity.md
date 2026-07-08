# 需求：BridgeForge 命令心智收敛
> 日期：2026-07-08
> 状态：trial
> 入口：用户希望把 BridgeForge 命令讨论得更清晰：空项目如何初始化，已有项目如何更新；随后明确用户只应记住 `bridgeforge` 和 `bridgeforge switch <agent>` 两个命令。

## 背景与目标

BridgeForge 当前已经具备多种内部模式：全新初始化、已有版本戳项目更新、无版本戳旧骨架收编、非 BridgeForge 既有项目安全接入，以及 Claude/Codex 切换。

本轮目标不是新增一堆用户命令，而是把对外心智收敛为两个入口：

1. `bridgeforge`
   - 用于普通项目骨架维护。
   - 叶子入口先刷新用户级骨架库 `~/.bridgeforge`，再读取完整 `SKILL.md`。
   - 默认维护当前正在运行的 agent 骨架：Codex 里维护 Codex 骨架，Claude Code 里维护 Claude 骨架。
   - skill 自行判断当前目录属于空项目、已托管项目、旧骨架项目，还是有业务内容但未接入 BridgeForge 的项目。
   - 若发现当前 agent 骨架不存在、但项目已有另一套 agent 骨架，先提示继续会执行 `bridgeforge switch <当前agent>`，用户确认后才启动 switch。
   - `init` / `update` / `adopt` 只作为内部模式名和日志说明，不作为用户必须记忆的命令。
2. `bridgeforge switch <agent>`
   - 用于显式切换当前项目使用的 agent 骨架。
   - `<agent>` 只支持 `claude` / `codex`。
   - 切换语义继续保持归档旧 agent、优先从当前项目归档恢复目标 agent、必要时从上游模板安装。

## 非目标

- 不把 `init` / `update` / `adopt` 暴露成用户主命令。
- 不改变 `switch` 的归档与恢复核心语义。
- 不做跨项目批量同步。
- 不自动 commit / push。
- 不在本轮替用户编填项目架构红线、快速命令或项目结构。

## 用户可见行为

用户在项目根目录运行 `bridgeforge`：

- 入口先对用户级骨架库 `~/.bridgeforge` 执行 `git pull --ff-only`；成功后读取最新 `SKILL.md`，失败则停止并要求用户处理，不继续用旧模板执行。
- 空项目：自动进入初始化路径，铺设当前 agent 的协作骨架，写入 `.bridgeforge_version`，最后提示用户手填占位。
- 已接入 BridgeForge 的项目：自动进入更新路径，比较本项目版本戳与上游版本，只处理下游相关的 `[product]` 增量。
- 旧版 BridgeForge 骨架但缺版本戳：自动识别为收编候选，只登记纳管，不覆盖已有内容；需要写戳前向用户确认。
- 有业务内容但不像 BridgeForge 衍生：识别为“既有项目首次接入”候选，先说明会保留已有内容，再让用户确认是否接入；禁止静默覆盖入口文件、rules、settings、memory 或 doc。
- 项目已有另一套 agent 骨架但没有当前 agent 骨架：识别为隐式 switch 候选，先提示继续会归档旧 agent 并切到当前 agent；用户确认后才启动 switch，用户不确认则不改文件。
- 当前 agent 入口文件或 rules 已存在但不像 BridgeForge：识别为“既有项目首次接入 + 当前 agent 文件冲突”，让用户选择保留补缺、备份覆盖或退出。
- Claude / Codex 两套 live 骨架同时存在：识别为双骨架冲突，停止并让用户明确选择维护哪套或先退出清理。

用户运行 `bridgeforge switch codex` 或 `bridgeforge switch claude`：

- 只做 agent 骨架切换，不混入普通初始化/更新流程。
- 若当前项目已经是目标 agent，则回落到普通 `bridgeforge` 的自动判场路径。

## 约束 / 风险边界

- 对外文档和入口提示必须强调“用户只需记两个命令”：`bridgeforge`、`bridgeforge switch <agent>`。
- `init` / `update` / `adopt` 可以出现在内部日志、设计文档、代码函数名中，但不得作为 README / SKILL 主路径要求用户记忆。
- 普通 `bridgeforge` 必须先做工厂自检，命中 BridgeForge 源头仓库时硬拒，避免在模板工厂自己身上 bootstrap。
- 普通 `bridgeforge` 和 `bridgeforge switch <agent>` 都必须在读取/执行完整 skill 前刷新用户级骨架库；`switch` 不得绕过刷新。
- 已有项目首次接入必须默认保守：先识别冲突和已有配置，再问用户；不能把“空项目初始化”逻辑直接套到已有业务项目。
- 更新模式不得自动覆盖 rules / 入口文件，不得动 memory / doc。
- `switch` 仍是显式切换流程，因为它可能删除 live agent 目录并归档；普通 `bridgeforge` 只能在发现另一套骨架时先提示并经用户确认后转入 switch，不能静默触发。
- 双 live 骨架场景不得自动猜测用户想保留哪套；必须停止让用户选择。

## 验收清单

- [x] `SKILL.md` 的用户入口说明只要求记住 `bridgeforge` 与 `bridgeforge switch <agent>`。
- [x] `SKILL.md` 的判场流程把 `init` / `update` / `adopt` 表述为内部模式，而非用户子命令。
- [x] README / INSTALL / 相关 playbook 中面向用户的命令说明与上述两命令模型一致。
- [x] 空项目、已托管项目、旧骨架缺戳项目、非 BridgeForge 既有项目这四类场景在文档中都有清晰判定和结果。
- [x] 当前 agent 不存在但另一套 agent 存在时，普通 `bridgeforge` 先提示并经确认后转入 switch。
- [x] 当前 agent 入口/rules 已存在但不像 BridgeForge 时，有“保留补缺 / 备份覆盖 / 退出”的兜底。
- [x] 双 live 骨架场景不会静默更新或切换，必须让用户选方向。
- [x] `switch` 文档仍明确归档/恢复语义，并保持与普通 `bridgeforge` 分流。
- [x] 薄入口 wrapper 在读取完整 `SKILL.md` 前先刷新 `~/.bridgeforge`；根 `SKILL.md` 有同等兜底，且 `switch` 分流不能绕过刷新。
- [x] 有对应验证记录，至少覆盖文档 grep 检查和现有 switch/update fixture 或等价脚本。
- [x] 完成交付前有独立验证记录；若平台不可用，交付时明确写未完成独立 agent 验证。

## 暂缓项

- 不在本轮设计新的交互 UI。
- 不把 `bridgeforge` 做成真实 shell 可执行安装器；本轮先统一 skill / 文档语义。
- 不处理跨机器安装布局迁移，除非现有文档引用命令心智时需要顺手统一措辞。

## 实施计划

1. 对齐文档口径：更新根 `SKILL.md`、Codex/Claude wrapper 或相关 README 中的入口说明。
2. 保留内部状态机：只改对外表达，不把已有 `init/update/adopt/switch` 判场逻辑打散。
3. 检查模板内下游说明：确保 `templates/claude` 与 `templates/codex` 面向用户的描述也只要求记两个命令。
4. 跑文档和脚本验证：检查旧命令心智残留、现有 switch/update fixture 是否仍通过。
5. 更新本需求包的实施记录和验证记录。

## 实施记录

- 2026-07-08：需求澄清中。用户已确认命令心智应收敛为 `bridgeforge` 与 `bridgeforge switch <agent>` 两个入口。
- 2026-07-08：用户确认兜底分支：普通 `bridgeforge` 发现另一套 agent 骨架时，先提示即将 switch，确认后启动 switch 程序；当前 agent 文件存在但不像 BridgeForge 时，按既有项目首次接入的冲突兜底处理。
- 2026-07-08：开始实现，更新根 `SKILL.md`、README、INSTALL、版本与 CHANGELOG。
- 2026-07-08：实现完成后进入验证。注意：工作区里 `skills/feature-dev/SKILL.md` 的 0.52.1 授权闸改动在本轮开始前已经存在，本需求未继续修改该文件；交付时需把它作为并存未提交改动说明。
- 2026-07-08：trial 反馈修正：用户指出下游调用 `/bridgeforge` 前应先把用户级骨架库拉到最新。已把 `git pull --ff-only` 前移到 Codex/Claude 薄入口读取完整 skill 之前，并在根 `SKILL.md` 加 Step -2 兜底，确保 `switch` 分流也不会绕过刷新。

## 验证记录

- `python tests/harness/run_downstream_fixture.py --case skill-metadata --case skill-refs --case switch-dry-run --case switch-same --case switch-conflict`：通过。覆盖 skill 元数据、skill 本地引用、switch dry-run 完整计划、同 agent no-op、目标 live path 冲突停止。
- `python .codex/hooks/skill_metadata_check.py --pre-commit`：通过，无 stdout，exit 0。
- `git -c safe.directory=D:/Quant/BridgeForge diff --check`：通过；仅有 Git for Windows 的 LF/CRLF 提示，无 whitespace error。
- `python tests/harness/run_downstream_fixture.py --case root-precommit --case switch-conflict`：通过。覆盖根 pre-commit 双 agent gates 与 switch 目标冲突停止。
- `rg -n "初始化或更新当前项目骨架|用户只需记两个入口|维护当前 agent|隐式 switch|当前 agent 文件冲突|双 live 骨架|继续将执行.*switch|0\\.52\\.2" ...`：确认新入口语义和版本号落在 `SKILL.md`、README、INSTALL、CHANGELOG、VERSION、两个 wrapper 与本需求包；旧 wrapper 参数文案“初始化或更新当前项目骨架”未命中。
- 独立 verification agent 第一轮结论：核心命令心智改动通过核对，但需求包验证记录过期、且工作区存在本轮预期外的 `skills/feature-dev/SKILL.md` 既有未提交改动。已补充本验证记录，并在实施记录中标明该文件是并存改动、非本需求继续修改项。
- 2026-07-08 trial 反馈修正验证：
  - `python tests/harness/run_downstream_fixture.py --case skill-metadata --case skill-refs --case switch-dry-run --case switch-same --case switch-conflict`：通过。确认 wrapper / skill metadata 仍健康，switch 相关回归不受 Step -2 说明调整影响。
  - `python .codex/hooks/skill_metadata_check.py --pre-commit`：通过，无 stdout，exit 0。
  - `git -c safe.directory=D:/Quant/BridgeForge diff --check`：通过；仅有 Git for Windows 的 LF/CRLF 提示，无 whitespace error。
  - `rg -n "初始化或更新当前项目骨架|可选.*GitHub 新鲜度|0\\.52\\.3|读取完整 BridgeForge skill 前|Step -2|switch 子命令优先分流（刷新后）|pull --ff-only" ...`：确认 0.52.3 版本、wrapper 预刷新、根 Step -2、switch 刷新后分流均已落地；旧 wrapper 参数文案和旧“可选 GitHub 新鲜度”未命中。

## 用户试用反馈

- 待用户确认需求包是否写对。
