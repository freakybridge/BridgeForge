---
status: confirmed
date: 2026-07-23
source: $confirm
---

# Codex Subscription Routing

## 原始需求摘要

用户升级至 200 美元套餐后，希望提高模型与思考强度；并要求下游项目运行 `/bridgeforge` 时询问套餐档位，按选择落地高档或原保守配置。

## 目标

为 Codex 下游骨架提供一次性、项目级的套餐档位选择。`/bridgeforge` 首次遇到未选择档位的项目时询问用户，并把选择和对应模型配置持久化到项目 `.codex/`；后续正常运行不重复询问。

## 已核实事实

- Codex 主对话默认由 `.codex/config.toml` 的 `model` 与 `model_reasoning_effort` 控制；明确实现由 `.codex/agents/implementation-worker.toml` 控制。
- 当前高档路由为主对话 `gpt-5.6-terra + high`、实现 `gpt-5.6-sol + high`。
- SessionStart hook 当前是非交互式检查器；`/bridgeforge` 本身承接用户确认与骨架更新。
- 骨架禁止写用户级 `~/.codex/config.toml`。

## 已确认规则

1. 仅 Codex 下游骨架使用套餐分流；Claude 骨架不改。
2. 首次 `/bridgeforge` 询问并持久化项目选择；用户主动切换档位前不重复询问。
3. 高档仅适用于用户明确选择“200 美元及以上”：
   - 主对话：`gpt-5.6-terra + high`。
   - 明确开发 / 跨文件实现：`gpt-5.6-sol + high`。
4. 保守档适用于“100 美元及以下”、100–200 美元之间或无法判定：
   - 主对话：`gpt-5.6-terra + medium`。
   - 明确开发 / 跨文件实现：`gpt-5.6-terra + high`。
5. 两档共同保持：只读探索和受控 Git 同步为 `gpt-5.6-luna + low`；独立审计为 `gpt-5.6-sol + high`；`xhigh` 仍必须取得用户当次明确确认。
6. 不读取或修改用户级 Codex 配置；不由 SessionStart 自动询问或静默改档。

## 数据与落点

- 在下游 `.codex/` 保存可读、可机检的套餐档位标记。
- `/bridgeforge` 根据标记写入项目 `.codex/config.toml` 和 `.codex/agents/implementation-worker.toml`。
- 已托管但没有档位标记的下游项目，在首次升级到该版本时询问一次。

## 拟修改范围

- BridgeForge `/bridgeforge` 的 Codex 更新 / 初始化交互与写入逻辑。
- `templates/codex/` 的路由配置、策略校验与说明；BridgeForge 自身 `.codex/` 按 dogfood 约定同步。
- 对应测试 / fixture、版本和 CHANGELOG、文档索引。

## 验收

1. 新 Codex 下游项目可选择高档或保守档，并写入正确的配置与档位标记。
2. 已托管且无标记的 Codex 下游项目只被询问一次；已有标记时正常运行不重复询问。
3. 100–200 美元或无法判定的输入落到保守档。
4. 两档的模型策略检查均通过；用户级配置写保护继续生效。
5. Claude 下游不出现套餐分流问题或配置改动。

## 风险与自动化边界

- 套餐由用户声明，BridgeForge 不尝试读取账户、账单或平台订阅状态。
- 运行中的会话不会自动切换模型；选择影响后续项目配置生效的会话。
- 需求卡已确认；下一阶段应完成实现、定向测试、模板 / dogfood 一致性检查和用户试用闭环。

## 实施 / 验证记录

- 实施：已新增项目级 `.codex/subscription-tier.toml` 与 `subscription_routing.py`，并接入根 `/bridgeforge` 的 init/update/adopt 流程；高档保留主 Terra+high / implementation Sol+high，保守档使用主 Terra+medium / implementation Terra+high。模板与 BridgeForge dogfood 均保存高档 marker，Claude 未改。
- 安全 / 原子性：路由脚本在任何读写前对 project root、`.codex`、三项目目标和两模板源执行 `resolve(strict=False)`，拒绝真实路径落入用户 `~/.codex` 或逃逸声明根；config、implementation worker、marker 先在各自同目录 staging/backup，再用 replace 提交，任何一步失败都逆序恢复旧文件或删除本轮新文件并清理临时文件。
- 策略：`model_policy_check.py` 现按 marker 选择期望配置；无 marker 时明确要求运行 `/bridgeforge` 选择。根 skill 静态契约明确覆盖首次询问、已有 marker 不再询问、仅用户主动切换、未知套餐落保守档和 Claude 跳过。
- 验证：完整 `python tests/harness/run_downstream_fixture.py` 28 项通过，含两档、无 marker、非法 tier、用户级读写保护；`python tests/harness/test_subscription_routing.py` 3 项通过，覆盖 `.codex` symlink/junction 解析保护、既有三文件第二次 replace 失败全量回滚、新项目 marker replace 失败不留部分文件；`python tests/harness/test_bridgeforge_root_skill.py` 4 项通过；安全修复后 `model_policy_check.py --pre-commit`、`rule_size_check.py --pre-commit` 通过。`encoding_check.py --pre-commit`、settings JSON 解析与 `git diff --check` 在初版实现后通过，P1/P2 安全修复后按主任务收口要求未重复扩大测试。
- 待完成：用户在真实下游项目运行一次 `/bridgeforge` 的交互试用；当前实现阶段不自动 commit / push。
