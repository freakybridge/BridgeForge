# {{PROJECT_NAME}} 文档索引

> 唯一索引 — 任何 `doc/*.md` 文件的新增 / 删除 / 重命名都要同步本文件。

---

## 目录职责

| 目录 | 放什么 | 状态 |
|------|--------|------|
| [`0_architecture/`](0_architecture/) | 架构红线（PRD、需求、约束、roadmap） | 长期，慎改 |
| [`1_plan/`](1_plan/) | 按主题归集的活跃推进 + 协作记录 | 活跃 |
| [`2_pending/`](2_pending/) | 未决问题备忘 + 未决讨论 | 短期 |
| [`3_design/`](3_design/) | 模块实现的最终形态（项目自产） | 较稳定 |
| [`4_archive/`](4_archive/) | 已完成归档 | 只读 |
| [`9_reference/`](9_reference/) | 外部 / 第三方参考资料 | 只读 |

完整边界规则见 `.codex/rules/workflow.md` §6。

---

## 0_architecture/

<!-- TODO: 列入 PRD / Roadmap / 核心需求文档
| 文件 | 说明 |
|------|------|
| `1_PRD.md` | 产品需求 |
| `2_约束与红线.md` | 不可变约束 |
| `3_数据结构与常量.md` | 核心数据对象 |
| `acceptance.md` | **正在做的验收清单**（全项目 Milestone 验收单一勾选位置）|
| `TODO-INDEX.md` | **暂时没空做的短期 TODO + 远期 backlog 索引**（与 acceptance 形成"做 vs 暂缓"二分）|
-->

## 1_plan/

<!-- TODO: 按 topic 子目录归集，例：
| 文件 / 子目录 | 说明 |
|------|------|
| [`feature_x/`](1_plan/feature_x/) | 特性 X 的设计 + 验收 + collab 记录 |
| [`sprints/`](1_plan/sprints/) | **正在做的 Sprint / Task 级日程**（per Milestone 一份）|
-->

## 2_pending/

<!-- TODO: 未决问题备忘（已识别但有上下文要展开的），例：
| 文件 | 说明 |
|------|------|
| `YYYY-MM-DD_<topic>.md` | 单个未决问题的展开备忘 |
| `debates_YYYY-MM-DD_<topic>.md` | 多 agent 辩论记录 |

注：TODO-INDEX.md 不放此处，已迁至 0_architecture/。
-->

## 3_design/

<!-- TODO: 模块设计，例：
| 文件 / 子目录 | 说明 |
|------|------|
| [`module_a/`](3_design/module_a/) | 模块 A 的实现设计 |
-->

## 4_archive/

<!-- TODO: 已归档文档，按时间倒序 -->

## 9_reference/

<!-- TODO: 外部参考资料，例：
| 文件 / 子目录 | 说明 |
|------|------|
| `external_api/` | 外部 API 协议文档 |
| `competitor_screenshots/` | 竞品截图 |
-->
