# Harvest 收件箱

> 格式：`- [ ] <学到啥> | 来源 <file:line 或 本轮对话> | 通用性 <为啥跨项目成立> | <日期>`

## 待反哺

- [ ] 轻量墓碑模式：任何"安装+传播+退役"机制，退役检测只需 `- name | ver | date | reason` 平铺文件，内容哈希已覆盖漂移，manifest = 冗余 | 来源 docs/skill-distribution-gaps.md + skill_sync_check.py | 通用性 凡有组件安装同步的框架均可用，与业务无关 | 2026-06-09
- [x] setup_agent 重新定位（v0.28.0 落地，v0.28.1 修正独立审计缺陷 F1-F11）→ **详见 [docs/repositioning-from-StratusAgent-2026-06-24.md](../docs/repositioning-from-StratusAgent-2026-06-24.md)** | 实际完成项：C1/C2/C4/C5/C8/C10 实打实；C3 脚本落地但 v0.28.1 修正 5 处 bug（正则误报/健壮性/--fix 违 spec）；C6 检测到位但自动清做成 report-then-confirm（有据）；C7 模板已改但 dogfood 镜像缺失——v0.28.1 补齐；C9 采方案①（安装期自动 merge env 块）待用户追认 | 来源 StratusAgent 2026-06-24 harness 全面审计 + 辩论 | 2026-06-24
- [ ] 查事实不查声明：hook 自检某 env 是否真生效，读运行时真值（如 `sys.flags.utf8_mode`）而非读 settings/配置文本声明（写了≠生效，可能那台机没读到配置） | 来源 本轮对话 + utf8-garble-rootcause.md | 通用性 任何"配置项是否真生效"的 hook 自检场景都成立，与业务/语言无关 | 2026-06-25
- [ ] 幸存者偏差陷阱：0 复发且已在根层（env/总闸）治本的问题，别再往会复印给所有下游的产品层加守卫——那是安慰剂式加固，下游照抄成包袱 | 来源 本轮对话 + docs/debates_2026-06-25_encoding-fix-scope.md | 通用性 凡有"上游→下游复印"机制的 scaffold 框架均适用，与业务无关 | 2026-06-25
- [ ] redline-placement 原则：跨文件重复的红线不是 bug——按「非触发轮可否违反」分层：是→红线骨架（断言+阈值）钉常驻层（CLAUDE.md），否→场景操作细节沉 path-triggered rule，只删两者间逐字重叠句，不删分工内容 | 来源 docs/debates_2026-06-25_redline-placement.md | 通用性 任何用 CLAUDE.md + 路径触发 rule 双层结构的 Claude 项目都适用 | 2026-06-25
- [ ] external-references 模式：SKILL.md 低频/大段步骤外置到 references/ 子目录，主文件只留「命中时先 Read references/xxx」指针，缩减每次 /skill 注入 context 的字节，降 compact 风险（skill_sync_check 用 os.walk 递归哈希，子目录安全纳入同步） | 来源 skills/summary + skills/find-doc | 通用性 任何有长 skill 且遇 ctx 顶爆的项目都适用 | 2026-06-25
- [ ] effortLevel 多层优先级陷阱 + SessionEnd 自动还原模式：Claude Code 设置优先级 Project > User，项目级 effortLevel 会覆盖全局，导致 slider/`/effort` 调了不生效；治法=项目层不写 effortLevel（由 SessionStart hook 机检剔除）+ SessionEnd hook 还原 medium baseline。SessionEnd hook 写 ~/.claude/settings.json 必须用原子写（temp+os.replace）且 **不进产品层**（多项目抢写同一全局文件会打架）。| 来源 本轮对话 + templates/hooks/enforce_no_effortlevel.py | 通用性 任何用 Claude Code + 关心 effort 控制的项目都有此坑；hook 模式普适 | 2026-06-26
- [ ] "能机检的红线一律 hook 化"原则的实操形态：散文 rule 讲「不得 X」→ 用户/AI 忘了就犯；hook 是机器在每次 SessionStart 自动纠正 X，不依赖记忆。判据：若一个约束可以写 Python 在 0/1 结果上判断，就不该是 rule，该是 hook。rule 只留人脑才能判断的（架构意图/权衡/场景判断），机检的归 hook。| 来源 本轮用户语录 + enforce_no_effortlevel 实现 | 通用性 任何用 Claude Code hooks 机制的框架都成立 | 2026-06-26
- [ ] Bash 工具 cwd 持久化陷阱：cd 进子目录后该 session 内所有后续 Bash 调用都从那里执行，hook 用相对路径 .claude/hooks/xxx.py 全部解析失败；操作子目录一律用绝对路径，必须 cd 时立即 cd 归位；发现 hook 全炸时用 PowerShell Set-Location 归位（Bash/PowerShell 共享 cwd） | 来源 本轮对话 + .claude/memory/feedback-bash-cwd-persistence.md | 通用性 任何用 Claude Code + PreToolUse hook 的项目都会踩，与业务无关 | 2026-06-27
