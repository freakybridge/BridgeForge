---
status: superseded
topic: codex-harness-parity
source: downstream nested-workspace version SoT proposal, scope revised by user decision
superseded_by: requirements_2026-07-30_version-domain-separation.md
---

# 下游骨架版本单一事实源确认卡

> 已由 `requirements_2026-07-30_version-domain-separation.md` 取代：根 `VERSION` 回归下游业务版本域，骨架版本仅由 `.<host>/.bridgeforge_version` 表示。

## 目标

下游项目根目录的 `VERSION` 是唯一受 BridgeForge 管理的版本源，并在初始化和更新时同步为 BridgeForge 根 `VERSION`。

## 已核实事实

- 当前 init 在检测到 `package.json`、`Cargo.toml` 或 `pyproject.toml` 后会跳过根 `VERSION`。
- 当前 `version_check.py` 在多个 manifest 与 `VERSION` 中按固定顺序寻找版本源。
- 当前 update 的同步基线 `.bridgeforge_version` 已来自 BridgeForge 根 `VERSION`。

## 已确认规则

- 下游根 `VERSION` 始终存在，且跟随 BridgeForge 总版本，不跟随模板版本。
- `version_check.py`、版本展示与提交硬闸只读取/检查根 `VERSION`。
- `package.json`、`pyproject.toml`、`Cargo.toml` 仍是下游业务自己的元数据，但不参与 BridgeForge 骨架版本判断。

## 非目标

- 不扫描嵌套 workspace，不对业务 manifest 做版本发现、排序、歧义裁定或 staged 匹配。
- 不改写下游业务 manifest 的版本号。

## 计划改动

- 调整 Codex / Claude 的 init、update、规则、版本 hook、状态展示和相关文档为根 `VERSION` 唯一 SoT。
- 模板与 BridgeForge dogfood 成对更新；下游 fixture 覆盖有/无 native manifest 的 init 与 update。
- 更新产品版本记录、CHANGELOG 与原下游提议状态。

## 验收

- 有任意 native manifest 的新下游项目仍获得根 `VERSION`，其值等于 BridgeForge 根版本。
- update 会将已有下游根 `VERSION` 同步为上游 BridgeForge 根版本。
- 只 stage 原生 manifest 时版本 hook 阻断；stage 根 `VERSION` 时放行。
- Codex / Claude 模板、dogfood、专项 fixture、全量 downstream harness 和 `git diff --check` 通过。

## 风险

更新会改写已有下游根 `VERSION`；业务 manifest 保持不动。根 `VERSION` 被定义为骨架版本，不得再被下游业务当作独立发布版本。

## 实施与验证记录

- `version_check.py`、`show_state.py` 与 `session_snapshot.py` 的两宿主模板/dogfood 副本均只读根 `VERSION`。
- init / update 手册规定下游根 `VERSION` 与 `.bridgeforge_version` 一并同步为 `$BRIDGEFORGE_HOME/VERSION`；业务 manifest 不再参与骨架版本口径。
- 下游 fixture 根 `VERSION` 已改为复制 BridgeForge 根版本，而非模板版本。
- 已验证：`.venv\Scripts\python.exe -B tests\harness\test_downstream_version_sot.py`，6 项覆盖 manifest 忽略、根 `VERSION` 放行、session snapshot 与 fixture 来源。
- 已验证：两份 `harness_parity_check.py --check`、`git diff --check` 与全量 downstream harness 通过。
