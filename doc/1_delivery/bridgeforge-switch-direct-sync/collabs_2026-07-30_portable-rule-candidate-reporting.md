# Portable Rule 候选发现与报告协作记录

> 确认卡：`requirements_2026-07-30_portable-rule-candidate-reporting.md`
> 状态：已完成

## 目标与边界

只报告在严格 frontmatter 中唯一声明 `bridgeforge_portable_rule: true` 的顶层 source Rule；
不写 target Rule 或入口索引。

## 研究收据

- canonical `build_plan` 已在未投影宿主资产循环中生成 `untranslated` asset；其
  `target_members=[]`，不取得 target ownership。
- switch 脚本有五份字节镜像：根 `scripts/`、两份 `templates/*/scripts/` 与
  `.claude/.codex/scripts/`。
- `tests/harness/run_downstream_fixture.py` 已有双向 switch fixture，可在不修改
  Rule / 入口字节的前提下断言 map 与摘要。

## 拆分

| 并行组 | 负责人 | 文件边界 | 依赖 / 接口 |
|---|---|---|---|
| A | implementation-worker | 五份 `bridgeforge_switch.py` 镜像 | 新候选 asset：`host-specific` + `none` + `untranslated`，无 target members；仅顶层严格 frontmatter Rule。 |
| A | implementation-worker | `tests/harness/run_downstream_fixture.py` | 断言字段有效/缺失/重复/非法/正文伪字段、目标 Rule 与入口快照不变、map 异常不取得 ownership。 |
| B | 主 agent | `VERSION`、CHANGELOG、模板 VERSION/CHANGELOG、需求与协作记录 | 仅在 A 的实现与验证通过后更新产品版本和收据。 |

## 接口约定

- frontmatter：文件首部 `--- … ---` 内唯一 `bridgeforge_portable_rule: true`。
- 候选范围：当前 source 宿主顶层 `rules/*.md`；不得递归或从正文推断候选。
- 候选 asset：`target_members=[]`、`status=untranslated`，只作为迁移提示；不得产生
  target Rule、入口索引写入、删除或 ownership hash。
- map 无效、缺失或漂移时沿用 canonical 保守路径；不得由 marker 重建 ownership。

## 执行状态

- A1 五份 switch 镜像：已按 frontmatter 协议完成。
- A2 downstream fixture：已按 frontmatter 协议完成。

## 验证收据

- `.venv\Scripts\python.exe tests\harness\run_downstream_fixture.py`：全量 PASS，覆盖
  `switch_direct_portable_rule_candidates` 的唯一 true、缺失、重复、false、非布尔、未闭合、
  正文伪字段、嵌套、target 存在 / 缺席与 map 异常。
- 根脚本、Claude / Codex 模板与 `.claude` / `.codex` dogfood 五份镜像逐字一致。
- 独立 `review-auditor` 复核通过：字段边界、零 target ownership、map 异常与 fixture
  均符合确认卡；未发现阻断问题。

## 约束

- canonical switch 与所有产品 / dogfood 镜像必须保持一致。
- map 仅记录报告，不能新增 target ownership。
- 实现 agent 启动前须经用户确认拆分。

## 验证收据

待实施。
