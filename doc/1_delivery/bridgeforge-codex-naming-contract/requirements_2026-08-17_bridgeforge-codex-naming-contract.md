# 需求：bridgeforge-codex 分层命名统一

> 日期：2026-08-17  
> 状态：implemented-awaiting-user-acceptance  
> 下一步：用户刷新用户级 Skill 后确认菜单显示  
> 调用来源：用户直接调用 `$confirm` 统一产品名、用户命令、UI 显示与内部技术标识边界。

## 原始需求摘要

用户发现当前 `BridgeForge Codex`、`BridgeForgeCodex`、`bridgeforge-codex`、
`bridgeforge_codex`、`$bridgeforge-codex` 与 `/bridgeforge-codex` 混用，希望建立
清晰、长期稳定的唯一命名规则，同时不破坏 GitHub 仓库 identity、已发布持久化协议和
旧用户迁移能力。

## 目标

- 用户命令统一为 `$bridgeforge-codex`。
- 菜单、Skill chip、聊天窗口、活跃提示和产品正文统一显示 `bridgeforge-codex`。
- GitHub 仓库名及远程地址继续使用 `BridgeForgeCodex`。
- 内部技术标识按其语言和载体采用稳定命名，不要求所有位置使用同一字面量。
- 建立机器可验证的命名契约，阻止后续重新引入混用。

## 不做

- 不重命名 GitHub 仓库或 canonical remote。
- 不重命名 `bridgeforge_codex_*` Python / PowerShell 脚本和代码标识。
- 不重命名 `BRIDGEFORGE_CODEX_*` 常量、环境变量、receipt 与 managed marker。
- 不迁移 `.bridgeforge_codex_version` 等已发布持久化协议。
- 不改写旧 `CHANGELOG`、归档文档、历史 hash、fixture 与 migration lineage。
- 不删除旧 `$bridgeforge` 一次性迁移能力。

## 规模与预算

- 规模：M。
- 判定依据：改动跨用户命令、UI 元数据、运行时提示、Template / dogfood、manifest 和
  兼容边界，但不引入新的数据格式或架构。
- 时间预算：45 分钟。
- Token 预算：20k 新增 token 估算；平台无可靠计量器，标记为未实测。
- Agent 预算：0 个子 agent。
- 验证预算：最多两轮。
- 超预算停止点：发现必须新增持久化标识迁移、GitHub 改名或旧用户兼容协议变化时停止，
  重新确认扩大预算或缩小范围。

## 已核实事实

- `skills/bridgeforge-codex/agents/openai.yaml` 已把 `display_name` 设为
  `bridgeforge-codex`。
- 活跃 README、Skill、安装说明与 hook 提示仍混用 `$bridgeforge-codex` 和
  `/bridgeforge-codex`。
- `BridgeForgeCodex` 同时承担 GitHub identity、工厂项目名、稳定技术标识和历史载体；
  不能按纯文本全量替换。
- snake_case、大写 snake_case 与 kebab-case 分别对应代码标识、常量和文件系统载体，
  这种分层差异本身合理。
- 旧 `$bridgeforge` 仍承担一次性迁移，当前不能直接删除。

## 已确认命名规则

| 场景 | 唯一形式 |
|---|---|
| 产品名、菜单、聊天显示 | `bridgeforge-codex` |
| 用户调用 | `$bridgeforge-codex` |
| Skill、目录、manifest、ledger | `bridgeforge-codex` |
| Python / PowerShell 文件与标识 | `bridgeforge_codex_*` |
| 常量、环境变量、receipt、marker | `BRIDGEFORGE_CODEX_*` |
| GitHub 仓库与 canonical remote | `BridgeForgeCodex` |
| 已发布版本戳 | `.bridgeforge_codex_version` |
| 旧入口 | `$bridgeforge`，仅限一次性兼容迁移 |

## 拟修改

- 将活跃文档、Skill、hook 提示和安装输出中的 `/bridgeforge-codex` 改为
  `$bridgeforge-codex`。
- 清理不属于 GitHub identity、兼容协议、历史载体或明确稳定技术 allowlist 的活跃
  `BridgeForgeCodex`。
- 保证 UI metadata 的显示名和默认提示遵守本命名矩阵。
- 增加机器回归检查，分别验证用户面、技术标识 allowlist 和兼容面。
- 同步 Template、dogfood、manifest、版本与 CHANGELOG。

## 验收

- 活跃用户面不再出现 `/bridgeforge-codex`。
- 菜单元数据精确为 `bridgeforge-codex`，默认提示使用 `$bridgeforge-codex`。
- 所有活跃用户提示统一要求运行 `$bridgeforge-codex`。
- `BridgeForgeCodex` 只存在于 GitHub identity、必要稳定技术 allowlist 和历史 / 兼容载体。
- `bridgeforge_codex_*`、`BRIDGEFORGE_CODEX_*` 与 `.bridgeforge_codex_version`
  保持兼容，不被误改。
- Template 与 dogfood 镜像一致。
- 命名硬闸、manifest `--check`、完整自动测试和完整 fixture 通过。
- 发布并刷新用户级 Skill 后，实际菜单由用户确认显示为 `bridgeforge-codex`。

## 合理假设与风险

- `$bridgeforge-codex` 是 Codex 当前标准 Skill 显式调用写法；`bridgeforge-codex` 是其
  不含调用前缀的 slug 与显示名。
- GitHub 仓库 `BridgeForgeCodex` 是外部 identity；显示该 URL 或仓库名不构成产品名漂移。
- 兼容 manifest、冻结 fixture、旧版本文档和历史 hash 允许保留旧名称，但不得被正常用户
  路径加载为当前推荐命令。
- 纯文本全局替换会破坏 compatibility 与 ownership lineage，实施必须采用语义 allowlist。

## 自动化边界

- 命名检查只扫描活跃产品面；历史、归档、兼容 payload 必须使用精确路径 allowlist。
- 自动化不得重命名持久化标识、删除旧入口或改写历史 hash。
- manifest 与派生 contract 只通过仓库重建器更新；`--check` 必须保持只读。
- Git commit / push 仅在用户显式调用 `$git-sync` 后执行。

## 实施记录

- 2026-08-17：用户确认按 M 级预算进入 `$develop`；开始统一活跃命令面并建立命名硬闸。
- 2026-08-17：活跃 README、安装说明、根 Skill、迁移 Skill、summary Skill、安装输出和
  Template / dogfood hook 提示已统一为 `bridgeforge-codex` / `$bridgeforge-codex`。
- 2026-08-17：Python / PowerShell 标识、`BRIDGEFORGE_CODEX_*`、版本戳、GitHub identity
  与历史 / 兼容载体保持原协议；未进行危险的全局文本替换。
- 2026-08-17：新增用户命令与 PascalCase 技术 allowlist 回归；版本更新为 `1.4.2`，
  CHANGELOG 和两份 manifest / managed contract 已同步。

## 实施计划

1. 将活跃用户命令从 `/bridgeforge-codex` 统一为 `$bridgeforge-codex`，旧入口统一写作 `$bridgeforge`。
2. 同步 Template、dogfood、Skill、安装输出、版本与 manifest，并保留技术标识与历史 allowlist。
3. 增加命名契约回归，完成定向测试、完整 fixture 与发布门禁验证。

## 验证记录

- 定向命名契约：`python -m unittest scripts.tests.test_bridgeforge_codex_root_skill`，
  10/10 通过。
- 完整 discovery：231 项中 224 项直接通过，7 项失败均为本轮改名后的旧测试期望；修正
  这些期望后，受影响的 project-sync、version-release、summary 三个模块 61/61 通过。
  两轮组合收据覆盖全部 231 项；遵守“最多两轮”约束，未机械重复完整 discovery。
- 完整 downstream fixture：状态 `passed`；21/21 个可执行发布谱系迁移成功，包含
  `0.86.0` 至 `1.4.1`，init stamp-last 与 legacy marker migration 均通过。
- `rebuild_shared_skill_manifest.py --check`：exit 0，`already current`。
- `instruction_source_check.py --post-edit`、`mirror_drift_check.py --pre-commit`、
  `skill_metadata_check.py`、`project_structure_check.py`、`git diff --check`：均 exit 0。
  project structure 仅输出既有归档 advisory，不构成阻断。
- Template 与 dogfood 的本轮 hook 修改已同步，并由 mirror gate 验证。
- 尚未验证：刷新用户级 Skill 后 Codex 菜单 / 聊天窗口的实际显示；该项需要发布后由用户
  进行 UI 验收。

## 后续交接

- 实现与仓库验证已完成；等待用户通过发布流程刷新用户级 Skill，并确认菜单、聊天窗口和
  命令入口均显示 `bridgeforge-codex`。
