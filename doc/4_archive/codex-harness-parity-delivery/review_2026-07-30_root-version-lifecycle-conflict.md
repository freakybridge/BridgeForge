---
status: pending
topic: codex-harness-parity
source: downstream integration review, sanitized
---

# 根 VERSION 生命周期契约冲突复核

## 结论

当前根 `VERSION` 同时承担了两种不相容的职责：

1. 记录并跟随 BridgeForge 上游骨架版本；
2. 作为所有下游普通 commit 的强制 bump 文件。

这会迫使纯业务提交修改一个由上游维护的骨架版本，导致版本含义漂移。建议保留根
`VERSION` 作为骨架版本单一事实源，但把提交闸门收窄为：只有 staged 改动触及
BridgeForge 受管骨架表面时，才要求同时 staged 根 `VERSION`。

## 已核实事实

- `requirements_2026-07-30_downstream-version-sot.md` 已确认根 `VERSION` 始终存在，
  并在 init / update 时同步为 BridgeForge 根版本。
- `templates/codex/rules/workflow.md` 同时规定“每次 commit 前必须提升一次版本号”
  和“根 `VERSION` 跟随上游 BridgeForge 总版本”。
- `templates/codex/hooks/version_check.py` 对普通 `git commit` 检查 staged 文件；
  根 `VERSION` 缺失时返回 `exit 2`。
- `package.json`、`pyproject.toml`、`Cargo.toml` 等下游原生 manifest 已明确排除
  在骨架版本判断之外。
- `show_state.py` 与 `session_snapshot.py` 只展示根 `VERSION`，该行为与骨架版本
  单一事实源一致，不是本报告的问题。

## 冲突

| 场景 | 根 VERSION 的定义 | 当前提交闸门结果 | 问题 |
|---|---|---|---|
| BridgeForge init / update | 跟随上游骨架版本 | 写入并 staged | 一致 |
| 只修改受管 hook / rule / settings | 骨架发生变化 | 要求 bump | 合理 |
| 只修改业务源码 | 骨架没有变化 | 仍要求 bump | 骨架版本虚假增长 |
| 只提升业务 manifest 版本 | 业务发布版本变化 | 仍要求 bump 根 VERSION | 两种生命周期被绑定 |

## 风险

- 根 `VERSION` 不再能回答“当前骨架来自哪个 BridgeForge 版本”。
- 下游每次普通提交都会制造与骨架无关的版本噪声。
- 团队可能长期滥用 `[skip-version]`，使硬闸退化为形式上的旁路。
- 下一次 `/bridgeforge` update 将根 `VERSION` 重写为上游版本时，可能出现数值倒退
  或历史含义跳变。
- 下游原生 manifest 仍需独立承担业务发布版本；BridgeForge 不应推断或改写它。

## 建议吸收

### 1. 分离版本域

- 根 `VERSION`：仅表示 BridgeForge 骨架版本。
- `.bridgeforge_version`：继续作为 update 基线；与根 `VERSION` 在 init / update 后一致。
- 下游原生 manifest：由下游自行定义业务发布版本，BridgeForge 不读取、不改写。
- 禁止从任一版本域推导另一版本域。

### 2. 收窄 version_check

`version_check.py` 应先读取 staged 路径：

- staged 改动未触及 BridgeForge 受管骨架表面：静默放行，不要求根 `VERSION`。
- staged 改动触及受管骨架表面但未包含根 `VERSION`：`exit 2`。
- staged 同时包含受管骨架改动和根 `VERSION`：放行。
- `[skip-version]`、`--amend`、merge 等既有显式豁免保持不变。

受管表面应由单一清单定义，至少覆盖入口文件、当前宿主配置目录、项目级 pre-commit
与 BridgeForge 机制块；禁止在 hook、规则和测试中维护多份漂移清单。

### 3. 修正规则措辞

将“每次 commit 前必须提升根版本”改为“每次受管骨架变更 commit 前必须提升根版本”。
业务版本策略明确留给下游项目，不纳入 BridgeForge 通用 rule。

## 验收场景

1. 只 staged 业务源码：不修改根 `VERSION`，commit 闸门放行。
2. 只 staged 业务 manifest：不修改根 `VERSION`，骨架闸门放行。
3. staged 受管 hook / rule，但未 staged 根 `VERSION`：`exit 2`。
4. staged 受管 hook / rule 和根 `VERSION`：退出码 `0`。
5. BridgeForge init / update：根 `VERSION` 与 `.bridgeforge_version` 都等于上游版本，
   业务 manifest 内容逐字不变。
6. `show_state.py` 与 `session_snapshot.py`：继续显示根 `VERSION`。
7. `[skip-version]`、`--amend`、merge：保持现有豁免行为。
8. Codex / Claude 模板、dogfood 副本和 downstream fixture 使用同一受管表面清单。

## 非目标

- 不替下游项目设计业务版本号或发布流程。
- 不恢复扫描嵌套 workspace 或自动选择业务 manifest。
- 不要求根 `VERSION` 与业务版本相等。
- 不在本报告中直接修改模板、hook、版本号或 CHANGELOG。

## 脱敏检查

- 不含下游项目名、内部包名、业务术语。
- 不含绝对路径、内部 URL、凭证或提交哈希。
- 示例只使用公开的通用 manifest 与 BridgeForge 受管资产名称。
