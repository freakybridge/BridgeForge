# 统一需求确认工作流

## 2026-07-14 决策

- 新增通用且可直接调用的 `confirm` skill：先核验既有载体事实，再以“每轮一个选择题”确认开发要点；最终完整确认卡写入 `doc/1_plan/<topic>/requirements_YYYY-MM-DD_<slug>.md`。
- `develop`、`debate`、`collab` 必须先持有目标、范围、约束和验收均匹配的确认卡；缺少、失配或过时即强制转入 `confirm`，不得自行补问后继续。
- 直接调用 `confirm` 后，由用户以选择题交接到 `develop`、`debate` 或 `collab`；三个高级 skill 不重复需求访谈，只保留各自专业流程的最终实施确认。
- 不把纯材料索取（日志、权限、附件）伪装为选择题；若事实缺口暴露需求卡失配，回到 `confirm`。
