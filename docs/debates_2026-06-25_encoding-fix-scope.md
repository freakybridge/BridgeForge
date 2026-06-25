# 讨论：乱码修复「组合方案」是否 right-sized（还是过度加固）
> 日期：2026-06-25
> 相关文件：.claude/settings.json(env)、.claude/hooks/*、templates/rules/portability.md、CHANGELOG
> 问题描述：把本轮调查得出的所有改进合成一套，复评是否右尺寸；警惕"幸存者偏差陷阱"（为已解决问题过度加固，并把坏惯例下沉所有下游）。

## 已钉死的事实（辩论地基）
1. 根因：中文 + Windows GBK 默认 + Python 非 UTF-8 → 乱码注入 context，修复前高频（8.5万字符 / 横跨所有下游），曾致漂。
2. 已修复（6-24, v0.28.1）：① 全局 `env.PYTHONUTF8=1`+`PYTHONIOENCODING`（用户级 settings）；② 16/16 hook 各带 `reconfigure`。修复后真实会话乱码 ≈ 0。
3. PYTHONUTF8（UTF-8 Mode）强制所有 Python stdio + open() + subprocess text 走 UTF-8，**与逐文件 reconfigure 功能重叠**（若 env 可靠生效，reconfigure 冗余）。
4. junction 那次跑偏 = 模型自身流式解码故障（� 在 assistant 输出、客户端层），harness 修不了，与本编码问题不同源。
5. git 编码三件套（quotepath/logOutputEncoding/commitEncoding）当前全未设；无编码审计脚本；门是开的但残留休眠。

## 待评估的组合方案
- T1：新增 `encoding_guard.py`（SessionStart 守卫）——查 ① settings 有 PYTHONUTF8 ② 所有 hook 有 reconfigure，缺则报警。[product+dogfood]
- T2a：git UTF-8 三件套配置。[repo + 写进 /bridgeforge 安装步骤]
- T2b：写 memory（完整地图）。
- Rule：portability.md §4.7 红线（写时提醒，点名指向 T1 守卫）。[product]
- T3：控制台代码页 UTF-8 —— 默认不做，记残留。
- T4：模型流式抽风 —— 修不了，memory 诚实声明。
