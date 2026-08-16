# {{PROJECT_NAME}} 文档索引

---
delivery_layout: flat # flat | milestone；初始化时确认，已有项目不得静默切换
---

> 唯一索引 — 任何 `doc/*.md` 文件的新增 / 删除 / 重命名都要同步本文件。

---

## 目录职责

| 目录 | 放什么 | 状态 |
|------|--------|------|
| [`0_architecture/`](0_architecture/) | 系统当前架构、关键接口、数据流与 ADR | 长期，慎改 |
| [`1_delivery/`](1_delivery/) | 需求从确认、计划到验收的完整交付包 | 活跃 |
| [`2_bugs/`](2_bugs/) | 尚未归档的 Bug：现象、根因、修复和验证 | 活跃 |
| [`3_reference/`](3_reference/) | 外部 / 第三方资料及可复核摘录 | 只读 |
| [`4_archive/`](4_archive/) | 已完成归档 | 只读 |

完整边界见根 `AGENTS.md` §2.3；长 SOP 由项目自行放入 `doc/3_reference/`。

---

## 0_architecture/

<!-- TODO: 列入 PRD / Roadmap / 核心需求文档
| 文件 | 说明 |
|------|------|
| `system-overview.md` | 系统边界、核心模块与运行方式 |
| `data-flow.md` | 关键数据流 / 控制流 |
| `interfaces.md` | 关键接口与数据契约 |
| `adr/ADR-*.md` | 跨模块、替代成本高的架构决策 |
-->

## 1_delivery/

<!-- TODO: 每个 topic 是完整交付包。布局由本文件 frontmatter 决定：
| 文件 / 子目录 | 说明 |
|------|------|
| [`feature_x/`](1_delivery/feature_x/) | flat：中小项目的需求包 |
| [`M1/feature_x/`](1_delivery/M1/feature_x/) | milestone：按里程碑组织的需求包 |

每个需求包至少包含确认卡 `requirements_*.md`、`plan.md`、`acceptance.md`；正式 debate 放入 `debates/`。`M1/README.md` 只汇总状态和链接，不维护第二套验收勾选。
-->

## 2_bugs/

<!-- TODO: 每个 Bug 记录发现、复现、根因、修复、验证和回归，例：
| 文件 | 说明 |
|------|------|
| `BUG-001_<topic>.md` | 轻量 Bug 记录 |
| `BUG-002_<topic>/` | 需要正式 debate 或附加证据的 Bug 包 |
-->

## 3_reference/

<!-- TODO: 外部资料必须记录来源、获取日期和适用范围，例：
| 文件 / 子目录 | 说明 |
|------|------|
| [`external_api/`](3_reference/external_api/) | 外部 API / 协议资料 |
-->

## 4_archive/

<!-- TODO: 已完成的 delivery 保持原 milestone/topic 层级归档；已解决 Bug 归档至 bugs/。 -->
