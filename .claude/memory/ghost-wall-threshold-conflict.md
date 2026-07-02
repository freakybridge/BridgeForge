---
name: ghost-wall-threshold-conflict
description: 鬼打墙计数阈值 CLAUDE §8(3) 与 debugging §6 T1(原2) 冲突——已于 harness 九维方案 P0-4 收口：T1 统一≥3+指回§8，T2 独立轴保持≥2 不动
metadata:
  type: project
---

## 状态：已收口（harness 九维方案 P0-4 / 设计 D4-M1，2026-07-02）

2026-06-25 产品层瘦身第二类 debate 时发现的**既存 bug**（非当时引入），2026-07-02 随 harness 九维工程方案落地统一。

## 原冲突实体
- `templates/CLAUDE.md §8`：同一 bug 前 **3** 次代码改动失败、第 **4** 次禁止动手（硬停）。
- `templates/rules/debugging.md §6` T1：同一 bug 连续改代码 **≥2** 次仍未解决即升级。

两文件给鬼打墙红线写了**不同的数（3 vs 2）**，下游 agent 同时加载会精神分裂。违反 [[meta_rule_design]] §4.3「单值红线不能两处各写一个数」。

## 收口结论（怎么改的）
- **T1 抬齐到 ≥3**（`debugging.md §6 T1`：≥2→≥3，第 4 次禁动手），并加**权威 pointer**「计数唯一权威 = CLAUDE §8」；`§8` 本体**不动**（它一直是 3）。T6 也补同款 pointer「以 CLAUDE §8 为准」。
- **T2（用户回报"还错"的次数，≥2）是独立信号轴，故意不动**——它量的不是「我改了几次」而是「用户已说几次还没好」，是更该敏感的信号；跟着抬到 3 = 放松了本该更敏感的轴（设计对抗批评③明确点破）。
- 为什么最终选 ≥3 而非当年审阅者倾向的更严的 2：统一到 §8 现值（3）改动面最小、单一权威最清晰；「早停更安全」的诉求由**独立的 T2 轴（≥2）**承接，不必靠压 T1。

## 落点
- 判据源：`docs/harness-engineering-design.md` D4-M1 + §6 修订记录③（T1/T2 轴分离）。
- 施工单：`docs/harness-impl-plan.md` P0-4。
- 鬼打墙组结构去重的其余部分（若还需）以此「单一权威 + pointer」范式续做。
