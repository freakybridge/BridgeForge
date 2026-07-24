# `explain` 通用 Skill 回灌需求卡

**状态：** confirmed  
**确认日期：** 2026-07-24  
**调用来源：** `$confirm`  
**后续交接目标：** 待用户选择 `develop`、`debate` 或 `collab`

## 原始需求摘要

将下游项目中已验证的 `explain` 解释能力回灌到 BridgeForge，使未来的 Claude 与 Codex 下游项目都能使用。

## 目标

新增产品层共享 skill `skills/explain/SKILL.md`。它应在用户显式调用 `$explain`，或明确要求白话解释、举例、表示未理解时触发；输出按“一句话结论 → 白话解释 → 贴近当前话题的例子”组织。

## 不做

- 不将该能力写入 `templates/`。
- 不改下游项目级 `AGENTS.md`、`CLAUDE.md`、hook 或 settings；为使新产品 skill 通过现有 Codex 路由校验，模板路由清单、其镜像检查器及模板计数说明可作最小兼容更新。
- 不自动安装到既有下游项目，不静默覆盖其已有定制。
- 不实施、重设计或扩张被解释的任务。

## 已核实事实

- 实施前 BridgeForge 为 `0.62.1`，`skills/` 中已有 18 个产品 skill，尚无 `explain`。
- Claude 与 Codex 下游共享 `skills/` 产品层；现有模板没有同类常驻解释协议。
- 下游回灌报告指出该能力适合独立 `SKILL.md`，不适合作为项目模板。
- 报告未给出可复核的下游原始 `SKILL.md` 精确路径；不得将报告描述伪称为原文副本。

## 已确认规则

1. 新建下游项目自动获得；既有下游在下次 BridgeForge 更新时，按现有“保留定制、不静默覆盖”规则接收。
2. 输出语言跟随用户当前请求语言；中文请求使用简体中文。
3. 输出必须保留条件、不确定性和限制；无原文或上下文时明确说明，不猜测。
4. 已确认的行为规则是上游规格。若定位到下游原文，仅作为脱敏参考；无法定位时，按本卡新写通用 skill。

## 数据映射

无业务数据、接口、持久化字段或迁移。

## 拟修改范围

- `skills/explain/SKILL.md`
- 根 `VERSION` 与必要的产品版本文件
- `CHANGELOG.md`（新增 `[product]` 条目）
- `doc/3_design/reverse-sync-playbook.md` 的反哺日志
- 与 skill 元数据、Claude/Codex 分发及更新不覆盖定制相关的测试或 fixture

## 传播与发布判断

1. **层级：** 产品层 `skills/`。
2. **通用性：** 已确认，写入共享产品层。
3. **版本与日志：** 新增 skill 属于 minor 版本变更，记录 `[product]` CHANGELOG。
4. **dogfood：** `explain` 本体不需要 hook 或 settings；但本次为维持 19-skill 路由校验而修改 `templates/codex/hooks/model_policy_check.py` 时，必须同步自身 `.codex/hooks/model_policy_check.py`。

## 验收标准

1. `explain` 的 metadata 检查通过。
2. Claude 与 Codex 下游分发 fixture 均能发现该 skill。
3. 模拟新建下游与已有定制的更新路径，证明不会静默覆盖定制。
4. 审阅三类解释请求的预期输出：显式 `$explain`、明确要求白话解释、上下文不足时的保守说明。

## 合理假设与风险

- 假设现有 `skills/` 分发机制继续适用于新增 skill；实施前须以现有分发测试核验。
- 下游原始 skill 的路径与原文目前未核实；不得复制未知内容或带入项目特定信息。
- “自然语言触发”的运行时发现能力取决于 agent skill 发现机制；测试应验证 skill 描述与显式调用入口，不能伪称已验证底层自动路由。

## 自动化边界

- 不对现有下游批量写入或升级。
- 不自动覆盖用户定制。
- 不自动 `git add`、commit 或 push。

## 实施计划

1. 新增 `skills/explain/SKILL.md`，沿用现有通用 skill metadata 与停止条件；将本卡确认的触发、三段输出、语言和保守性边界写为可发现的通用描述。
2. 复用现有用户级 skill 分发，不在项目模板中重复安装逻辑；为“新增 skill 与本地下游定制并存”补最小可重复 fixture。
3. 按当前版本事实将根版本从 `0.62.1` 升为 `0.63.0`，Claude 产品版本从 `0.23.0` 升为 `0.24.0`，Codex 产品版本从 `0.33.1` 升为 `0.34.0`；同步现有入口或版本展示的单一事实源。
4. 在 `CHANGELOG.md` 记录 `[product]` 新 skill，并在 reverse-sync playbook 反哺日志追加来源、目标与脱敏判断。
5. 运行 metadata、分发 fixture 与相关单元测试；最后由独立审计核对真实 diff、产品层传播和验收遗漏。

## 实施前发现收据

- `.codex/hooks/skill_sync_check.py` 只报告用户级 skill 货架与上游源的缺失、漂移或退役，不写入文件；下游更新流程负责经用户确认同步，因而可满足“保留定制、不静默覆盖”的边界。
- `.codex/hooks/skill_metadata_check.py` 对 `skills/*/SKILL.md` 强制检查 metadata、BOM、长度及一层 references；其现有 downstream fixture 已覆盖 metadata 缺失，但未覆盖新增 skill 遇到本地定制的分发路径。
- 当前最接近的产品格式为 `skills/find-doc/SKILL.md`；新增 skill 必须保持单层 references、description 预算和 500 行上限。

## 实施与验证记录

### 实施完成

- 新增 `skills/explain/SKILL.md`：覆盖确认的触发条件、三段输出、语言跟随、不确定性边界及“只解释、不实施或重设计”的范围。
- 新增 `tests/harness/test_explain_skill.py`，并扩展 `tests/harness/run_downstream_fixture.py`：Claude/Codex 均覆盖缺失时可发现 `explain`，且本地定制副本会被报告为漂移并保持字节不变。
- 经本次实现中两次用户确认的最小例外，更新两份 Codex 路由清单，将 `explain` 登记为 `main/all`；两份 `model_policy_check.py` 的产品 skill 数由 18 同步为 19；`templates/codex/AGENTS.md` 的相应说明同步为 19。
- 根版本升至 `0.63.0`，Claude 产品版本升至 `0.24.0`，Codex 产品版本升至 `0.34.0`；同步根 skill、两份薄入口、`CHANGELOG.md`、反哺日志及生成的 harness parity 报告。

### 验证通过

| 命令 | 断言与结果 |
|------|------------|
| `python .codex/hooks/skill_metadata_check.py --pre-commit` | 新增 skill 的 metadata、BOM、长度和引用健康检查通过。 |
| `python tests/harness/run_downstream_fixture.py --case skill-metadata --case skill-refs --case user-skill-distribution --case model-policy` | 4 个 fixture 全部 PASS；覆盖 metadata、引用、双端分发维护契约与定制保留、19-skill 路由策略。 |
| `python -m unittest discover -s tests/harness -p 'test_*skill*.py'` | 12 个 skill 相关单元测试通过。 |
| `python .codex/scripts/harness_parity_check.py --check` | 更新生成报告后，Claude/Codex harness parity 检查通过。 |
| `git diff --check` | 通过，无空白错误。 |

### 未完成验证与审计状态

- `skill-creator` 的 `quick_validate.py` 未运行：当前系统缺少 `PyYAML`，且仓库无 `.venv`；已由项目自身 metadata 闸和 fixture 覆盖本需求的可执行边界，但该外部快速校验不应被表述为通过。
- 现有产品没有可调用的安装器或 agent 运行时发现测试接口；fixture 只验证安装说明契约、缺失/漂移检测和本地定制字节不变。真实缺失 skill 的安装执行及 agent 运行时发现**未验证**。
- 独立 `review-auditor` 已复核最终修正：无代码阻塞；已据其结论收紧上述分发验收措辞。
