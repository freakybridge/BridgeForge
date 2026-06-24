# Harvest 收件箱

> 格式：`- [ ] <学到啥> | 来源 <file:line 或 本轮对话> | 通用性 <为啥跨项目成立> | <日期>`

## 待反哺

- [ ] 轻量墓碑模式：任何"安装+传播+退役"机制，退役检测只需 `- name | ver | date | reason` 平铺文件，内容哈希已覆盖漂移，manifest = 冗余 | 来源 docs/skill-distribution-gaps.md + skill_sync_check.py | 通用性 凡有组件安装同步的框架均可用，与业务无关 | 2026-06-09
- [x] setup_agent 重新定位（v0.28.0 落地，v0.28.1 修正独立审计缺陷 F1-F11）→ **详见 [docs/repositioning-from-StratusAgent-2026-06-24.md](../docs/repositioning-from-StratusAgent-2026-06-24.md)** | 实际完成项：C1/C2/C4/C5/C8/C10 实打实；C3 脚本落地但 v0.28.1 修正 5 处 bug（正则误报/健壮性/--fix 违 spec）；C6 检测到位但自动清做成 report-then-confirm（有据）；C7 模板已改但 dogfood 镜像缺失——v0.28.1 补齐；C9 采方案①（安装期自动 merge env 块）待用户追认 | 来源 StratusAgent 2026-06-24 harness 全面审计 + 辩论 | 2026-06-24
