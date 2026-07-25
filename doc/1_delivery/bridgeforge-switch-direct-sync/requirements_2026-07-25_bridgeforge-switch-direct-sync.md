# BridgeForge switch 项目双骨架直接同步需求卡

> 状态：`implemented`
> 确认日期：2026-07-25
> 来源：用户在复核项目级 `.codex` / `.claude` 切换模型后调用 `$confirm` 的逐项确认
> 后续交接目标：以项目双骨架直接同步取代项目根 `.bridgeforge/` 的 archive / receipt / lineage 模型。

## 原始需求摘要

项目同时长期保留 `.codex` 与 `.claude`。用户在当前宿主打开项目后执行 `bridgeforge switch <当前宿主>`，BridgeForge 将另一骨架的项目资产语义同步到当前骨架，随后用户直接在当前宿主继续工作。BridgeForge 是用户级工具，不在项目根目录持有运行状态。

## 已核实事实

- 当前 `scripts/bridgeforge_switch.py` 将 archive 和 migration receipt 写入项目根 `.bridgeforge/archive/` 与 `.bridgeforge/migrations/`。
- 当前实现将两侧 live 骨架视为冲突，并以 archive / receipt / lineage 协调切换；这与“双骨架长期并存、每次从当前完整文件重新同步”的目标不一致。
- Claude 与 Codex 的 hook 生命周期、配置格式、agent 调度、skill 入口等宿主原生能力不完全相同；项目级存放位置不能使宿主专属文件被另一宿主直接执行。
- 现有项目可能遗留旧模型创建的项目根 `.bridgeforge/`。

## 已确认业务规则

1. `.codex` 与 `.claude` 是长期并存的项目资产；切换时源端保持不变，目标端接收同步结果。
2. `bridgeforge switch codex` 只能在 Codex 中执行，`bridgeforge switch claude` 只能在 Claude 中执行；宿主与参数不匹配必须报错。
3. switch 的含义固定为“同步 + 在当前宿主继续工作”：不维护 active marker，不启动另一宿主，不要求额外交接操作。
4. 每次 switch 必须从当前两侧真实文件重新盘点全部源端项目资产；不得依赖项目根持久 lineage 或 receipt 决定同步内容。
5. 宿主专属源文件禁止原样复制到另一骨架。可表达的项目意图必须转译为目标宿主的原生资产。
6. 无法等价转译的资产不阻断 switch：保留源端真实资产，在目标端映射表标记为 `untranslated` 并向用户显示缺口；不得伪装为已同步。
7. 目标端已有专属资产，或已生成的目标资产被用户人工修改时，禁止自动覆盖；保留目标内容并输出冲突 / 待处理项。
8. 映射表确认由 BridgeForge 生成、且目标文件未被人工修改的资产，后续源端修改或删除时允许自动更新或删除对应目标结果。
9. 映射表缺失、损坏或不可解析时，禁止自动覆盖或删除可能属于用户的目标文件；仍可同步无歧义资产，并输出冲突 / 待处理项。
10. 不在项目根创建、读取或写入 `.bridgeforge/`。已有遗留 `.bridgeforge/` 不自动处理，只提示用户可手动删除。

## 映射表契约

1. 映射表固定放在目标骨架内：`.codex/.bridgeforge-map.json` 与 `.claude/.bridgeforge-map.json`。
2. 每次成功切入目标骨架后更新其当前完整映射快照；下一次从该骨架切出时读取该表，以识别此前转译的资产。
3. 映射表纳入 Git，使用格式化 JSON；内容必须确定性，不写绝对机器路径、时间戳或其他机器特定值。
4. 映射表只保存映射关系：相对路径、内容哈希、资产类型、转译规则、目标路径、状态、冲突或未转译说明。
5. 映射表禁止保存任何源端或目标端资产原文；`.codex`、`.claude` 中的真实文件是唯一权威源。
6. 映射按语义资产项记录，必须支持一对多、多对一的源文件 / 目标文件关系。

## 不做

- 不删除或归档任一 live 骨架以完成切换。
- 不在项目中创建新的 `.bridgeforge/` 目录、迁移回执目录或 archive 目录。
- 不直接复制 Claude / Codex 宿主专属格式到另一宿主。
- 不因不可转译项、映射表缺失或人工修改而静默丢弃目标端内容。
- 不复制资产正文到映射表或制造第二权威副本。
- 不自动删除已有旧 `.bridgeforge/`。

## 拟修改范围

- `scripts/bridgeforge_switch.py` 及 Claude / Codex 模板镜像：重构为双骨架直接同步、目标内映射表和无根 `.bridgeforge/` 状态。
- `tests/harness/`：替换 archive / receipt / lineage fixture，覆盖双向同步、映射表、不可转译、人工修改、映射表损坏和旧目录遗留场景。
- `skills/bridgeforge/SKILL.md`、`skills/bridgeforge/references/switch.md`、相关设计 / 需求文档：同步新的 switch 心智模型与行为边界。
- 产品层模板、版本号和 `CHANGELOG.md`：按实际产品改动更新。

## 验收标准

1. `codex → claude` 后 `.codex` 保留，`.claude` 得到仅包含 Claude 原生表达的同步结果，并生成 `.claude/.bridgeforge-map.json`；项目根不产生 `.bridgeforge/`。
2. `claude → codex` 读取 `.claude/.bridgeforge-map.json` 和真实 `.claude` 文件，更新 `.codex`，并生成 / 更新 `.codex/.bridgeforge-map.json`。
3. 映射表中的所有路径均为项目相对路径，不包含资产原文、绝对路径或时间戳；同一输入得到稳定 JSON 内容。
4. 一条源资产可映射至多个目标文件，多个源文件也可共同映射至一个目标资产。
5. 无法等价转译的资产不会阻断切换，但会在目标映射表和用户输出中明确标记 `untranslated`，源端文件保持存在。
6. 已映射目标文件未被人工修改时，源端更新 / 删除可同步更新 / 删除；人工修改、映射表缺失或损坏时不得自动覆盖或删除相关目标文件。
7. 发现项目根旧 `.bridgeforge/` 时 switch 不读取、不写入、不删除它，仅给出明确提示。
8. 宿主与 `switch` 参数不匹配时命令失败且不修改项目文件。

## 合理假设与风险

- “等价转译”依据宿主可验证的原生能力判断；无法表达的能力只能以 `untranslated` 缺口交付，不能声称等价。
- 由于映射表不保存正文且双骨架均长期保留，映射表损坏后无法可靠判定旧目标文件所有权；安全策略必须优先保留用户文件。
- 目标映射表纳入 Git 会使同步行为产生可审阅的项目变更；其确定性格式用于避免无意义 diff。
- 本卡替代已实现的 `bridgeforge-switch-semantic-migration` 卡中关于项目根 `.bridgeforge/`、archive、receipt、lineage 与 hard-constraint fail-closed 的项目级行为；不回退该卡之外的已验证安全能力，具体保留范围需在实现前逐项核对。

## 自动化边界

- 仅作用于当前项目内的 `.codex`、`.claude` 及其目标映射表。
- 不读取或修改其他项目、用户级共享 skill、用户级 BridgeForge 安装目录或 Git 历史。
- 不执行 `git add`、`commit`、`push`、`stash`、`merge` 或 `reset`。

## 实施与验证记录

### 实施计划

1. 以双 map、稳定语义组和内置 adapter registry 重写 switch 的 plan / proposal / manifest / apply 状态机；移除项目根 archive、receipt、lineage 和 source skeleton 移动。
2. 保留路径、link、Windows 冲突、hash、stage 与输入漂移校验；实现 source-map 回声抑制、target-map ownership、whole-file / JSON Pointer selector 和 `completed_with_gaps` 输出。
3. 以受控异常精确回滚替代 archive 事务；不引入 transaction journal。强杀、断电或系统崩溃后仅进行 map/live 一致性检查，并对受影响语义组输出 `interrupted-or-modified` 冲突。
4. 同步三份 switch 脚本、入口 / playbook、版本和 CHANGELOG；替换 archive/receipt harness 为 direct-sync 覆盖，并独立审计。

### 已采纳的辩论结论

- 每次同时读取 source 和 target map。source 中未修改的 generated projection 必须抑制回声；被修改的 projection 标为 `forked_projection`，不自动回灌。
- map 是经 schema、路径、host surface、adapter、selector 和 hash 校验的受信项目输入，但不自证 provenance。只有 live target member / selector 的 hash 等于 `last_generated_sha256`，才允许自动更新或删除。
- 语义组必须整体更新或整体进入冲突；共享 JSON 配置仅支持内置 adapter 声明的非重叠 JSON Pointer。TOML 和自由文本共享配置暂标 `untranslated`。
- 仅允许内置 allowlist adapter。map 禁止携带命令、模块路径、资产正文或可执行 patch。
- 不承诺 kill、强制终止、系统崩溃或断电下的跨文件原子性。受影响组下一次只会保留并报告冲突；无歧义的独立资产仍可同步。

### 实施

已完成：以 direct-sync 状态机替换项目根 archive / receipt / lineage；同步根、模板与 dogfood 五份脚本；更新入口、playbook、版本、CHANGELOG、受管分发清单与 downstream harness。

### 验证

已通过：

- `D:\Quant\veighna_studio\python.exe tests\harness\run_downstream_fixture.py`：33/33 PASS，覆盖双向 map、host guard、whole-file / JSON Pointer、map 缺失/损坏、回声/分叉、人工修改、旧根目录、rollback、junction TOCTOU、未转译与五份镜像。
- `D:\Quant\veighna_studio\python.exe tests\harness\test_shared_skill_distribution.py`：13/13 PASS；`shared-skill-manifest.json` 294 个产品源哈希一致。
- 五份 `bridgeforge_switch.py` SHA-256 一致：`f4ac78e9f497047f9b12d631adb56a54d06c48075466618f22eb2144ff7e572f`。
- `git diff --check`：通过（仅有 LF→CRLF 工作树提示）。
- 独立审计：无 P0/P1；已复核 rollback incomplete、target link/junction TOCTOU 与 map 缺失/非法的 `created_unowned` 边界。
