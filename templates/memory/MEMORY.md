# {{PROJECT_NAME}} 开发备忘

<!-- 本文件是 memory 索引，每条 memory 一行，控制在 200 行以内（超出会被 Claude Code 截断）。
     具体内容写在同目录下的 .md 文件里，索引指向它。

     4 类 memory 命名约定：
     - user_*.md       — 用户角色、偏好、知识背景
     - feedback_*.md   — 用户给的"如何做事"反馈（必须做 / 禁止做 + Why + How to apply）
     - project_*.md    — 项目正在发生的事（不能从代码 / git history 推出）
     - reference_*.md  — 外部系统资源指针

     什么 NOT 写：代码模式 / 架构（看代码即可）、debug 解法（提交信息有）、CLAUDE.md 已写的内容、临时状态。

     升级路径：feedback memory 沉淀够多 → 升级为 .claude/rules/<topic>.md 的 path-rule。

     完整说明见 ~/.claude/CLAUDE.md 的 "auto memory" 段，或本项目 docs/。
-->

## 用户与项目

<!-- 示例：
- [user_overview.md](user_overview.md) — 角色 / 偏好 / 协作风格
- [project_overview.md](project_overview.md) — 当前阶段 / 主要矛盾 / 决策背景
-->

## 调研方法

<!-- 关于"如何调研 / 验证"的反馈沉淀，例：
- [feedback_must_quantify_first.md](...) — 性能问题先量化再动手
- [feedback_api_behavior_must_test.md](...) — API 行为必须实测，不信代码假设
-->

## 模块 / 功能

<!-- 按本项目实际模块组织，例：
- [project_module_x_decision.md](...) — 模块 X 的关键设计决策
- [feedback_module_y_constraint.md](...) — 模块 Y 的非显式约束
-->
