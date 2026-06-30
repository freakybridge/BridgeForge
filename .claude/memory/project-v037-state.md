---
name: project-v037-state
description: v0.37.0（templates v0.8.0）防 AI 幻觉资源四层框架落地 + CLAUDE.md 瘦身 275→193 行（2026-06-30）
metadata: 
  node_type: memory
  type: project
  originSessionId: 5b768036-43aa-43eb-97a9-ca6f8fa62a01
---

## 核心改动（2026-06-30）

**起因**：外援 agent（CausisRiskSuite 项目）贡献防 AI 幻觉资源四层纵深打法，经两轮 cross-agent debate 裁决落点。

---

### 出厂即用（进 templates）

**`templates/rules/anti_fabrication.md`**（42 行）：R1–R5 五条行为红线，always-on（无 frontmatter paths），附一句话口诀。  
零代码、零误伤风险——唯一进产品层的组件。

| 条款 | 摘要 |
|-----|------|
| R1 | 用资源前必验证存在（实测 ≠ 推断） |
| R2 | 验不到直说缺什么并停下 |
| R3 | 禁止编造资源标识（名字 / 路径 / 接口） |
| R4 | 禁止把失败甩锅给用户 / 工具 / 编辑器 |
| R5 | 死不认账本身就是违规 |

---

### 仅进 docs（不出厂）

- **`docs/antifabrication-framework.md`**（115 行）：四层框架全文 + C1/C2/Stop hook 设计 + 三者不进 templates 的各自理由
- **`docs/examples/antifab-deny-hook.py`**（138 行）：C1「确证不存在则 deny」参考实现，四 gate 纯函数，smoke tested

#### C1/C2/Stop 不进 templates 的裁决理由
- **C1**：空 `REAL_SOURCE_HINT` 近零价值；误伤是硬停；templates dogfood 先交卷
- **C2**：LLM 工具执行期 SUSPENDED——PostToolUse 对硬超时盲（参见 [[feedback-llm-suspended-during-tool-exec]]）；C3 已覆盖软超时场景；阈值噪声大
- **Stop hook**：每轮 LLM 扫描成本高；per-project 启用比出厂更安全

---

### CLAUDE.md 瘦身

- `templates/CLAUDE.md`：275 → 193 行（-82 行），回到 ≤200 红线
- 7 个红线节（§2.5 / §8 / §9 / §9.5 / §9.6 / §10 / §11）全保留，无条款丢失
- 降幅来源：占位注释精简 + 叙述性长句合并 + 与 portability.md 重复内容删至指针

---

### 顺手修复

- §2 注释里 `rules/api.md` 触发 rule_index_check 假死链接 → 改 `rules/<topic>.md`（角括号绕过 `rules/[a-z_]+\.md` regex）

---

### 版本号

- `templates/VERSION`：0.7.0 → 0.8.0  
- 根 `VERSION`：0.36.0 → 0.37.0

**关联**：[[project-v032-state]]（redline-placement 原则）、[[project-v030-state]]（上一次瘦身）
