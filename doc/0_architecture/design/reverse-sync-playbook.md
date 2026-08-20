# bridgeforge-codex 反向回灌 Playbook

> **定位**：把下游 Codex 项目中已经验证、可跨项目复用的改进，人工提炼回 bridgeforge-codex 产品层。该流程没有自动 harvest/inbox；必须另建并确认一个产品改动任务。

## 1. 适用边界

允许候选来源：下游 `AGENTS.md`、嵌套 `AGENTS.md`、`.codex/hooks/`、`.codex/scripts/`、skills 与参考文档中已实测的通用机制。`.codex/rules/*.rules` 仅作为命令执行策略候选，不得把 Markdown path-rule 当成 Codex 指令来源。

禁止直接回灌：

- `.codex/memory/` 正文、业务文档、凭证和运行时数据；
- 项目名、账户、内部 URL、绝对路径、业务阈值、事故标识；
- 只适用于单一业务或单一仓库布局的规则；
- 旧 `.claude/` 或退役 harvest inbox 的内容。

## 2. 人工流程

1. 明确“来源文件 → 产品目标文件 → 通用收益”，并获得本轮产品改动确认。
2. 逐段比较下游与 `templates/`；只提取规范性约束或通用实现，不复制项目叙事。
3. 完成脱敏：项目名、内部模块、凭证、URL、commit/事故 ID、绝对路径和业务术语必须删除或改为通用占位。
4. 回答传播四问，决定落点：
   - 下游产品资产写入 `templates/`；
   - 用户级命令与通用 skill 写入 `skills/`；
   - bridgeforge-codex 自身说明写入 `doc/`；
   - 通用 hook/settings 同轮镜像到 `.codex/` dogfood。
5. 更新 schema 3 current-only ownership/projection、manifest、VERSION 与 `[product]` CHANGELOG；禁止只改模板正文而遗漏派生哈希。
6. 运行定向测试、完整 fixture、manifest `--check`、mirror drift、结构检查和独立审计。

## 3. 仲裁原则

- 上游模板是通用基线，不以某个下游的“内容更多”作为胜出依据。
- 多个下游表达冲突时，先抽取共同不变量；仍需业务判断则不回灌。
- rule 只保留“必须/禁止”的红线；事故复盘留在下游 memory 或 bridgeforge-codex 元文档。
- 不确定所有权、通用性或脱敏完整性时，默认拒绝写入产品层。

## 4. 验收证据

每次回灌必须记录：

- 源码实现与来源场景；
- `templates/` 产品传播；
- `.codex/` dogfood（适用时）；
- fixture 与自动测试；
- 至少一个授权下游样本；
- runtime/人工项的已验证与未验证边界。

下游消费产品更新的正向流程见 [sync-from-upstream-playbook.md](sync-from-upstream-playbook.md)。
