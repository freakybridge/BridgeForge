# 协作：token 与 skill 上下文优化实施
> 日期：2026-07-15
> 目标：并行整理 19 个产品 skill，并在主线修复 token、memory 与验证基础设施。
> 确认卡：`requirements_2026-07-15_token-context-optimization.md`

## 协作计划

| # | 子任务 | 文件边界 | 依赖 | 并行组 |
|---|--------|----------|------|--------|
| 1 | 基础 / 检索 / 状态类 skill 标准化 | `skills/{plan,find-memory,focus,snapshot,resume,find-doc,archive-scan}/**` | 无 | A |
| 2 | 文档写入 / 编排 / git skill 标准化 | `skills/{todo,summary,sync-docs,harvest,confirm,develop,collab,debate,escalate,spinoff,git-sync}/**` | 无 | A |
| 3 | 根 bridgeforge skill 渐进拆分 | 根 `SKILL.md`、新建根 `references/**` | 无 | A |
| 4 | token / memory / metadata / 测试 / 文档整合 | `.codex/**`、`templates/codex/**`、`tests/**`、`doc/**`、版本与 CHANGELOG | 1-3 结果 | B |

## 接口约定

- frontmatter 保留 BridgeForge 字段：`name`、`description`、`user_invocable`、`argument`，仅在既有路由需要时保留 `model`。
- description 同时表达“做什么 + 何时用”，不在正文重复触发条件。
- `SKILL.md` 保留核心流程、红线、输出和停止条件；低频细节只放一层 `references/`。
- 禁止新增 `agents/openai.yaml`；禁止修改分配边界外文件。
- 子任务不改版本、CHANGELOG、共享 hook 或测试；统一由主线整合。

## 执行记录

### 并行组 A

- **子任务 1**：完成；7 个基础 / 检索 / 状态 skill 总字符减少 31.3%，metadata、reference、diff 检查通过。
- **子任务 2**：完成；11 个工作流 skill 统一结构并保留全部高风险硬闸，metadata、reference、diff 检查通过。
- **子任务 3**：完成；根 skill 从 784 行降至 205 行，拆出 5 个一层 reference，静态行为对照通过。

### 并行组 B

- **子任务 4**：完成主线整合与独立 review 修复，进入用户试用。

## 整合 + 独立验证

- [x] 接口衔接检查
- [x] metadata / reference / 触发测试
- [x] 模板与 dogfood 镜像
- [x] 独立 review agent 复查真实 diff
- [x] 完整测试通过

## 完成总结

- 三个并行子任务均遵守文件边界，未新增 `agents/openai.yaml`，未执行 commit / push。
- 主线新增真实 token 解析、启动成本规模报告、memory 热区预算和对应回归测试；完整 downstream fixture 通过。
- 独立审计发现并推动修复根 skill 变量顺序、Codex init/update 产品清单和 pinned 预算；新增根契约与 hook 端到端测试。
