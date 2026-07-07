# {{PROJECT_NAME}} 项目开发规范

> 项目专属指令，每次新对话自动加载。
> 详细规则按需加载自 `.claude/rules/`。

---

## 1. 架构红线

<!-- 填 3-5 条“必须 X / 禁止 Y”硬约束（数据流方向 / 资源上限 / 时序约束），填好删注释。 -->

---

## 2. 规则文件索引

| 规则文件 | 内容 | 加载条件 |
|---------|------|---------|
| `rules/architecture.md` | 职责边界 + 数据流方向（核心红线） | 始终加载 |
| `rules/modules.md` | 模块组织范式 + 目录职责 + 新模块接入流程 | 始终加载 |
| `rules/anti_fabrication.md` | 防 AI 幻觉资源四层红线 R1-R5（用前必验 / 缺了直说 / 禁编造 / 禁甩锅 / 先认再改） | 始终加载 |
| `rules/debugging.md` | 调试检查项 + 鬼打墙红线 + 修 bug 前确认根因 | 编辑 `tests/**` 或核心代码目录 |
| `rules/workflow.md` | 范式同步文档 + 文档索引同步 + 经验总结 | 编辑 `doc/**`、`.claude/rules/**` |
| `rules/portability.md` | 换机可移植性 + 包安装陷阱 + hooks 路径约束 | 编辑 `.claude/**`、配置文件、依赖清单 |
| `rules/meta_rule_design.md` | 元规则：怎么写 rule（强制力梯度 + 加载策略 + 反模式速查） | 编辑 `.claude/rules/**` 或 `CLAUDE.md` |
| `rules/anti_drift_hooks.md` | 反漂移 hook（clarify / focus / ctx-budget）的分工论述 + 路径 / 调参 / 豁免 | 编辑 `.claude/hooks/**`、`.claude/settings.json` |

<!-- 按需追加项目特定 path-rule，如 `rules/<topic>.md`（按 `src/<topic>/**` 触发）。 -->

---

## 2.5 工具与证据红线

- 找文件 / 查内容用 `Glob` / `Grep` / `Read`；shell 只用于构建、测试、git、进程等执行动作。禁止反射性用 `find` / `Get-ChildItem` / `Select-String` 做大检索。
- 工具返回出现同段重影、命中 0 与预期矛盾、不认识的文件名、`__unparsedToolInput` 时，禁止直接下结论或改盘，先用单命令二次验真。
- 交付处或危险处的结论（改了什么 / 验证通过 / 某资源存在）必须有真实工具返回作证；拿不到就写“未验证”或“不知道”。
- 写“验证通过 / 测试通过 / 已验证”必须同时列出：实际命令或 test receipt 指纹、具体验证断言、覆盖路径 / 场景。缺任一项只能写“已运行，验证有效性未确认”。

---

## 3. 快速命令

<!-- 填项目构建 / 运行 / 测试 / 检查命令（每天敲得最多的几行），填好删注释。 -->

---

## 4. Skills（可调用技能）

技能目录：`.claude/skills/<name>/SKILL.md`（项目内）和 `~/.claude/skills/<name>/SKILL.md`（用户级）。

常见通用 skill：`/feature-dev`（大需求交付流水线）/ `/plan` / `/collab` / `/debate` / `/summary` / `/todo` / `/find-doc` / `/archive-scan` / `/escalate` / `/snapshot` / `/resume` / `/git-sync`。

---

## 5. Memory 项目内托管（自动）

memory 纳入项目 git（`.claude/memory/`），系统路径 `~/.claude/projects/<hash>/memory/` 用 junction 透明转发；`memory_junction_check.py` 每次 SessionStart 自动维护。禁止硬删可能含数据的目录，迁移失败用 `.bak`。

检索顺序：先查 MEMORY.md 主索引；无匹配再用 `/find-memory <关键词>` 搜冷区；禁止跳过主索引直接 grep 全量 memory。MEMORY.md 是派生索引，勿手改。

---

## 6. 换机首次启动 Checklist

用户提到“换电脑 / 新机 clone / 重装”时，先 clone 并按主语言初始化依赖，再按 `rules/portability.md` §2 / §4 处理 Python hook、git UTF-8、junction 和依赖清单陷阱。

```bash
git clone <repo_url> {{PROJECT_NAME}} && cd {{PROJECT_NAME}}
```

---

## 7. 项目结构速查

<!-- 列顶层目录及职责（一行一个），帮 Claude 快速定位代码。跑 `ls` 看顶层照填。 -->

---

## 8. 鬼打墙觉察 + 渐进升级（红线）

默认单 agent。以下情况必须主动升级，不等用户提醒：

- 等价性验收 / 重写 / 移植：完成后派独立 verification agent，禁止只靠自测。
- 任务跨 ≥ 2 模块且不熟：先派 research agent 调研再动手。
- 同一 bug 前 3 次改动失败，第 4 次禁止继续写代码；列已试方案 + 未验证假说，提议 `/escalate` 或 `/debate`。
- 每次失败后再次动手前，必须先取一项量化数据（日志 / 产物 mtime / grep 结果 / 截图反推数值）。细则见 `rules/debugging.md` §6。

---

## 8.5 自改审计独立性（红线）

当审计对象包含本轮 agent 自己刚做的改动，且用户要求“审计 / 复核是否达成需求 / 找遗漏”时，必须启动独立 agent 二次审计。普通解释、轻量自查、用户未要求审计时不强制。

---

## 9. 主观体验报告主动问范式（红线）

用户基于外部观察报主观体验 / 怪现象且缺稳定复现时，不要猜修。一次性问全：可观察证据、前 N 步操作 / 触发条件、发生频率、是否能存档现场（如 `/snapshot`）。拿到信息后先加 timer / counter / log 量化，再判断。

---

## 9.5 较大需求主动澄清 — `[clarify]`

读到 `[clarify]` 后先语义精判：琐碎 / 续接 / 已说全细节 -> 直接执行；真·新的 / 大而模糊 / 容易走偏的开发需求 -> 先澄清。

- 已表达执行意图但范围 / 验收 / 关键取舍模糊：先给当前理解、可选路线、推荐路线和理由，再用 `AskUserQuestion` 或普通回复只问当前最关键的一个问题。
- 每轮最多问一个问题；累计每 3 个问题必须暂停总结；超过 6 个问题仍未收敛，改出 PRD / 验收草案 / 设计讨论稿让用户改。
- 能说清目标、非目标、触发条件、验收口径、已确认项 / 合理假设 / 剩余风险时，停止追问。
- 需要落盘需求、验收清单、用户试用闭环的大需求，或用户说“按完整流程做 / 开一个需求 / 走 feature-dev”，进入 `/feature-dev`。
- 评估 / 咨询类只给结论 + 风险即收口；不要包装成执行菜单替用户开单。

细节、hook 路径和调参见 `rules/anti_drift_hooks.md` §1。

---

## 9.6 任务防漂移 — `[focus]`

读到 `[focus]` 后只处理“无意漂移”。用户明确转入新任务是正常行为；正当深入就忽略。

- 前置阻塞：大的用 `/spinoff` 交接，小的内联做完即回。
- 附加扩张：用 `/todo` 归档，先完成原任务。
- 无关支线：用 `/todo` 或建议开新对话，不内联。
- 方案替换 / 扩缩范围：先说“原打算 X，现改走 Y，因为 Z”，再动手。
- 顺手改必须告知：任何非本次点名的顺手改动，都要主动说明“顺带改了 X，因为 Y”。

细节见 `rules/anti_drift_hooks.md` §2。

---

## 10. 上下文预算 — `[ctx-budget]`

| 级别 | 响应 |
|------|------|
| MEDIUM | 继续执行，完成后建议 `/snapshot` |
| HIGH | 开头告知用量 + 建议 `/snapshot`；复杂多文件改动建议拆小或换会话，用户坚持则说明风险后继续 |
| CRITICAL | 开头告知用量 + 强烈建议先 `/snapshot` 再新会话 `/resume`；用户坚持可继续，但提示状态可能被 compact 吞 |

边界附近以信号为准；软化的是“拒不拒活”，不是“报不报用量”。`/snapshot` / `/resume` / `/git-sync` 等保命操作放行。细节见 `rules/anti_drift_hooks.md` §3。

---

## 10.5 空转弱提醒 — `[stall]`

读到 `[stall]` 后本轮尽快收口：给结论，或落一个具体动作（工具调用 / 文件改）。它是下一轮弱提醒，不是实时刹车；若确属正当长分析可忽略。判据见 `stall_warning.py`。

---

## 11. 文档管理（红线）

本项目必须用 `doc/` 六层结构：`0_architecture` / `1_plan` / `2_pending` / `3_design` / `4_archive` / `9_reference`。

- 禁止文档散落根目录或源码目录；设计文档放 `doc/3_design/`。
- 禁止删层、跳层、改名、合并、新增同级目录。
- `doc/README.md` 是唯一索引；任何 `doc/**.md` 新增 / 删除 / 移动 / 重命名都要同步。
- 不接受 doc/ 强制，就不应使用 bridgeforge。

每层职责和 README 同步细则见 `rules/workflow.md` §5.5-§8。
