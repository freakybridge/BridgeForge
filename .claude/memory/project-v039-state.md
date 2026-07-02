---
name: project-v039-state
description: v0.39.0（templates v0.10.0）harness 九维方案 12 工单全部落地——蓝图/施工序/收尾记账/终验四件套
metadata: 
  node_type: memory
  type: project
  originSessionId: 916e4c2c-bb29-40d5-8ee0-b649d9d5c115
---

2026-07-02，[[harness-preferences]] 19 问访谈 → 九维设计 → 施工序三步走的终点：`docs/harness-engineering-design.md`（蓝图 v1）+ `docs/harness-impl-plan.md`（12 工单）全部照做完毕，`templates/VERSION` 0.9.0→0.10.0、根 `VERSION` 0.38.0→0.39.0，CHANGELOG 已记大 entry。

## 落地了什么（12 工单 P0-1~P2-11）
- **新建 4 个 hook**：`mirror_drift_check.py`（D8 镜像闸，缺文件 exit2/正文差异仅 stderr）、`test_receipt.py`（D1-M2 测试收据，**甲方案尽量版**见下）、`fallback_smell_check.py`（D3 仅裸吞异常）、`stall_warning.py`（D4 空转多特征合取弱提醒）。
- **pre-commit 升三段闸**（两处逐字镜像）：mirror 段（缺文件 exit2，置最前防被末行 exit0 吞）→ rule 闸段（`rule_size_check`读 staged blob / `rule_index_check`读工作树，读法分治见设计 F3）→ 既有 memory 索引段。
- **P0-1 清偿 dogfood 欠账**：`.claude/hooks/` 补齐 4 个早年缺失镜像（show_state/rule_index_check/memory_lint/find_doc_reminder）。
- **文本红线批**：`templates/CLAUDE.md` §9.5 保守权重、§9.6 方案替换类+N7红线+顺手改告知、§10 软化（拒不拒活软化，报不报用量不软化）、§2.5 收据红线明文化、§8 rules-based>LLM-judge；`debugging.md` T1 阈值 ≥2→≥3（**解 E-3**，见 [[ghost-wall-threshold-conflict]]，T2 独立轴不动）。
- **settings.json 两侧**新增 3 个 hook 注册；P0-5 查漏 deny/ask 清单**零缺项**（已有覆盖齐全，CHANGELOG 已明示为产品层承诺）。

## test_receipt.py 甲方案（尽量版）—— 一个真实验证坐实的技术事实
用户拍板"甲：先落尽量版 + 每次存原始 payload，下个会话见真数据再校准"。**实测坐实**：Claude Code 的 PostToolUse `tool_response` 在**成功场景**只有 `{stdout, stderr, interrupted, isImage, noOutputExpected}`，**没有显式退出码字段**——退出码只在**失败场景**的文本开头以 `"Exit code N"` 出现。这不是猜测，是本会话真实 Bash 调用触发 hook 后落盘的样本（`.runtime/test_receipts/payload_samples/`）实测所见。hook 因此做四级提取（显式字段→文本正则→无错误标记推断 0→unknown），收据带 `source` 字段自报硬度。**详情已写进 `templates/hooks/test_receipt.py` docstring，不重复展开**。

## 验收方式（不是自吹，是真跑了）
- P1-6/P1-7 下游模拟 dry-run：临时造 `.claude/rules/`+超标 rule+索引，实测 exit2 真拦、`[skip-rule-size]` 真放行、脚本异常 exit0。
- 收尾终验：三道 pre-commit 闸本机 dry-run 全 exit0；`templates/hooks/*.py` 与 `.claude/hooks/*.py` 逐字节比对**零缺失零差异**；两侧 settings.json JSON 合法性通过；全部 hook `py_compile` 通过。

## 仍未闭环的（不是漏项，是性质不同的后续）
- **D6/D8 硬闸真实下游实测**：本机模拟 dry-run 过了，但没在真实下游 clone 项目里跑一遍——bridgeforge 自身无 `.claude/rules/`、恒 no-op，真实拦截逻辑的最终验证只能靠下游。
- **test_receipt 失败场景 payload 样本**：目前只坐实了成功场景形状，失败场景（真实 pytest/cargo 跑挂）的样本还没攒到，攒够后可把"尽量版"精修为"精确版"。
- **[[harness-trim-2026-07-01-deferred]] 里 E-1/E-4(部分)/E-5 + 2 条搁置行为变更**（debugging §11 根因预测收紧 / B-6 dogfood 政策 `也要挂上→适用才镜像`）：本轮九维实施**未触碰**，仍原样搁置待用户表态。**E-3/E-6 已在本轮解决**（E-3=[[ghost-wall-threshold-conflict]] 收口；E-6=P0-1 补镜像+P1-7 mirror_drift_check 硬闸）。
- `skills/git-sync/SKILL.md` L20 过时 Why（"Stop hook 每轮重建"实际早移到 PostToolUse）——早前发现、本轮未顺手修，仍开着。

## 残余风险（设计上承认防不住，非本轮漏做）
详见 `docs/harness-engineering-design.md` §5：纯文字 A 类幻觉防不住（无工具边界）、假验证 exit0 盖章防不住内容错、谎称已改文件在不 commit 会话里无铁证、stall 对合法长思考轮无区分力、D6/D8 硬闸自身 no-op 真实性只能人眼+下游验、D8 正文差异降软后的漏防。
