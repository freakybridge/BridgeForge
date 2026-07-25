---
status: confirmed
topic: memory-rule-organization
created: 2026-07-25
source: "$confirm：下游项目 memory / rule 组织与渐进加载"
---

# 下游 memory / rule 组织与渐进加载

## 目标

为所有 BridgeForge 下游项目建立可泛化、可按需扩展的 memory 组织与渐进加载机制：长期知识可按主题检索，当前 delivery topic 可跨会话恢复，而不把全部历史内容带入每次会话。

## 不做

- 不将 rule 常规地按 delivery topic 分目录。
- 不在新项目初始化时预建一批空的 memory 主题目录或 `.gitkeep`。
- 不在既有下游项目更新时静默移动或重分类 memory。
- 不因 topic memory 存在而删除 delivery 文档中的原始需求、讨论、计划或验收记录。

## 已核实事实

- 当前 Claude/Codex 模板只有自动生成的 `memory/MEMORY.md` 索引，尚无主题目录或 frontmatter 分类契约。
- 当前 rule 已按 `architecture`、`workflow`、`debugging`、`portability` 等触发面并通过 `paths:` 分层。
- 当前元规则已要求：事故细节进入 memory，方案过程进入 delivery/doc，长期红线才进入 rule。

## 已确认规则

### Memory 目录与生命周期

1. 新项目初始仅创建 `memory/MEMORY.md`；主题目录在首次实际写入时创建。
2. 可创建的稳定主题目录为：`architecture/`、`engineering/`、`domain/`、`operations/`、`_inbox/`。
3. 每个 delivery topic 可创建长期保留的 `memory/topics/<topic>/`，用于跨会话恢复该 topic 的完整摘要；验收后仍可检索。
4. `MEMORY.md` 是热区与自动索引，不复制所有 memory 正文。

### 分类与整理

1. `summary` 与 `harvest` 负责首次沉淀和归类。
2. 离开 `_inbox/` 的 memory 必须有 frontmatter `category`；`kind`、`tags`、`related_paths` 按需填写。
3. 重建/整理脚本对明确 `category` 的记录直接归位。
4. 缺少或非法 `category` 时，脚本可分析正文和 tags，补写分类并整理。
5. 脚本无法高置信判断时，必须展示候选目录；仅在用户选择后才写入 `category` 并移动文件。

### 渐进加载

1. 会话启动默认仅加载 `MEMORY.md`。
2. 当前任务锚或确认卡能唯一定位 delivery topic 时，额外加载对应 topic memory。
3. 其他 memory 只能通过 `find-memory` 的关键词/语义检索按需读取。

### Rule 边界

1. rule 保持按触发面和 `paths:` 组织。
2. topic 专属约束默认留在 delivery/topic memory；跨 topic 的长期红线才提炼为 rule。
3. 是否支持 `rules/topics/<topic>.md` 为待决 debate 议题，当前不得实现。

### 下游迁移

1. 新项目直接采用新结构与机制。
2. 既有项目在 `/bridgeforge` 更新时仅展示迁移计划；用户确认后才补建目录、补分类或移动文件。

## 数据映射

| 内容 | 权威位置 | 载入方式 |
|---|---|---|
| 当前长期热区与索引 | `memory/MEMORY.md` | 每次会话启动 |
| 通用长期知识 | `memory/<category>/` | `find-memory` 按需检索 |
| 无法分类的候选 | `memory/_inbox/` | 整理时处理 |
| topic 跨会话摘要 | `memory/topics/<topic>/` | 当前 topic 唯一识别时 |
| 原始需求、讨论、计划、验收 | `doc/1_delivery/<topic>/` | `find-doc` / 显式读取 |
| 可执行长期红线 | `rules/*.md` | 路径/事件触发 |

## 拟修改范围

- Claude/Codex 模板：memory 初始结构、索引/整理脚本、入口与相关规则。
- 共享 skills：`summary`、`find-memory`、`harvest`。
- `$bridgeforge`：新项目初始化与既有项目更新迁移说明/逻辑。
- 设计文档、测试与下游迁移收据。

## 验收

1. 新下游项目只含 `MEMORY.md`，没有预建空主题目录。
2. 首次写入主题 memory 时才创建对应目录；`category` 缺失或非法时行为符合分类规则。
3. 低置信分类不会静默写入或移动，必须要求用户选择。
4. 会话启动不全量加载 memory；当前 topic 唯一识别时才加载其 topic memory。
5. `find-memory` 能按关键词/metadata 找到主题 memory 与 topic memory。
6. 既有项目更新仅展示迁移计划，未确认前不改动其 memory。
7. rule 仍按 `paths:` 触发；不存在 `rules/topics/` 实现。

## 风险与待决项

- 正文分类可能误判：低置信场景由用户选择，且保留整理收据。
- topic memory 可能与 delivery 文档重复：delivery 保留原始证据，topic memory 提供可独立阅读的恢复摘要。
- **待 debate**：是否允许 `rules/topics/<topic>.md`；需在实现前完成正式 debate。

## 实施与验证记录

- 实施：2026-07-25 已完成。Claude/Codex 模板、递归索引/检索/整理脚本、`summary`/`find-memory`/`harvest`/`bridgeforge` 契约及下游迁移计划已同步；未实现 topic rule。
- 验证：`python tests/harness/test_memory_rebuild_index.py`（4 tests）、`python tests/harness/test_shared_skill_distribution.py`（13 tests）、`python tests/harness/run_downstream_fixture.py`（34 checks）通过；20 个 memory 脚本 AST 解析通过，memory hook dogfood 镜像字节一致，`git diff --check` 通过。
