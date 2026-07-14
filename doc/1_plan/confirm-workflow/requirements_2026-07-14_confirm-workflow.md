# 需求：统一需求确认 skill

> 日期：2026-07-14
> 状态：trial
> 入口：将 `develop` 的单题选择式需求确认抽为可直接调用、可被 `develop` / `debate` / `collab` 强制复用的 `confirm`。

## 背景与目标

三个高级 skill 各自维护需求确认闸，规则重复且粒度不一致。新增 `confirm` 作为唯一确认入口：开发者可单独理清需求，高级 skill 则必须持有匹配的确认卡才能开始专业流程。

## 非目标

- 不把日志、权限、附件等纯材料索取伪装成选择题。
- 不要求高级 skill 重复需求访谈。
- 不自动提交或推送。

## 用户可见行为

- `/confirm` 每轮只问一个选择题，确认后写入完整需求卡。
- 需求卡写在 `doc/1_plan/<topic>/`，直接调用时可自动交接给 `develop`、`debate` 或 `collab`。
- 三个高级 skill 缺少、失配或过时需求卡时，强制进入 `confirm`。

## 约束 / 风险边界

- 确认卡必须匹配目标、范围、约束和验收，不能按同名目录误复用。
- 高级 skill 只保留各自专业流程的最终实施确认。
- 用户显式确认前不得写需求卡、改代码或启动高成本 agent。

## 验收清单

- [x] `confirm` 具备有效 frontmatter，支持直接调用和高级 skill 内部调用。
- [x] `confirm` 生成并落盘完整需求卡，直接调用可选择自动交接目标。
- [x] `develop`、`debate`、`collab` 均有确认卡硬闸，且不再重复需求访谈。
- [x] 入口文档列出 `confirm`。
- [x] 独立 agent 审核真实 diff，并运行元数据 / 文本 / diff 校验。

## 暂缓项

- 不实现跨会话自动判断需求卡“过时”的脚本化机制；本期由 agent 按任务事实核对。

## 实施计划

- 新增 `skills/confirm/SKILL.md`。
- 重写三项高级 skill 的输入闸，保留各自专业阶段的最终确认。
- 更新入口清单、版本、CHANGELOG 和用户级实际 skill 入口。

## 实施记录

- 2026-07-14：已新增 `confirm`，并接入 `develop` / `debate` / `collab`；独立审核发现 BridgeForge 主入口两处技能清单漏列 `confirm`，已补齐。

## 验证记录

- `python .codex/hooks/skill_metadata_check.py`：通过。
- `python .codex/scripts/harness_parity_check.py --check`：通过；共享 skill 计数更新为 18/18。
- `git diff --check`：通过。
- 独立审核：除 BridgeForge 主入口两处清单遗漏外无问题；遗漏已修复。

## 用户试用反馈

待补。
