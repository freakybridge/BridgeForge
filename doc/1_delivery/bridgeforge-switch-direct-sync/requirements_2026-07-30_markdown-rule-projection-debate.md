# Markdown Rule 投影 Debate 确认卡

> 状态：已确认，待 debate
> 原始需求：下游提出 Markdown Rule 投影增强，用户要求评审其上游采纳边界。
> 调用来源：`$debate`

## 目标

评审 Markdown Rule 投影候选，裁定 BridgeForge 应采纳、暂缓或拒绝的能力与阶段边界。

## 范围

- v1 同名 Rule 投影与 `paths` 转译。
- v2 分段投影、v3 replacement、v4 memory 路径映射。
- project-root map 的权威关系。

## 不做

- 本轮不实现、不修改模板、不创建 root map。
- 不把下游业务 Rule、路径或正文带入产品层。

## 已核实事实

- canonical switch 仅 allowlist `whole-file`、`json-pointer` 与 `none` adapter。
- `whole-file` 仅允许 portable memory Markdown，不能承载 Rule 投影。
- 双宿主目标 map、生成 hash、人工修改保护、事务回滚已经存在。

## 辩论验收

- 给出 v1–v4 与 root map 的采纳 / 暂缓 / 拒绝裁定。
- 说明 map 权威关系、source 不变与人工修改保护的安全边界。
- 每个建议采纳阶段给出最小 fixture 验收。
- 输出推荐实施顺序与主要风险；不输出代码实现。

## 风险与自动化边界

- 有损投影、map 漂移和人工修改必须保守处理，不得伪称等价。
- debate 仅输出设计裁定；任何实现需用户在辩论结论后另行确认。

