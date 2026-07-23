# {{PROJECT_NAME}} 项目开发规范

> 项目专属指令，每次新对话自动加载。
> 详细规则按需加载自 `.codex/rules/`。

---

## 0.5 专业表达风格

- 默认先给结论，再给依据；不确定时标明“未验证 / 缺证据 / 只是推断”，并说明下一步怎么验证。
- 禁止空泛安抚句；禁止连续用“可能 / 可以考虑 / 建议”稀释判断。
- 代码审查先列问题；排障先给最可能根因、证据和验证动作；架构判断先给推荐结论。
- 执行类任务默认接管到结果：读上下文 -> 判断风险 -> 修改 / 执行 -> 验证 -> 汇报。
- 交付时报告“已做什么 / 验证了什么 / 还剩什么风险”，不要用“你可以……”当主要收尾。

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
| `rules/workflow.md` | 范式同步文档 + 文档索引同步 + 经验总结 | 编辑 `doc/**`、`.codex/rules/**` |
| `rules/portability.md` | 换机可移植性 + 包安装陷阱 + hooks 路径约束 | 编辑 `.codex/**`、配置文件、依赖清单 |
| `rules/meta_rule_design.md` | 元规则：怎么写 rule（强制力梯度 + 加载策略 + 反模式速查） | 编辑 `.codex/rules/**` 或 `AGENTS.md` |
| `rules/anti_drift_hooks.md` | 反漂移 hook（clarify / focus / ctx-budget）的分工论述 + 路径 / 调参 / 豁免 | 编辑 `.codex/hooks/**`、`.codex/settings.json` |

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

技能目录：`.agents/skills/<name>/SKILL.md`（项目内，仅项目专属）和 `~/.agents/skills/<name>/SKILL.md`（用户级通用；Codex 规范路径）。

常见通用 skill：`$confirm`（统一需求确认）/ `$develop`（大需求交付流水线）/ `$plan` / `$collab` / `$debate` / `$summary` / `$todo` / `$find-doc` / `$archive-scan` / `$escalate` / `$snapshot` / `$resume` / `$git-sync`。

---

## 4.5 Codex 模型 / effort 路由（红线）

配置负责选档，hook 负责防漂：`.codex/config.toml` 是主对话默认档，`.codex/agents/*.toml` 是子 agent 预设档，`model_policy_check.py` 负责检查这些档位是否被改坏。

| 场景 | Agent / 配置 | 模型 | Effort |
|------|--------------|------|--------|
| 高档主对话（marker=`high`） | `.codex/config.toml` | `gpt-5.6-terra` | `high` |
| 保守档主对话（marker=`conservative`） | `.codex/config.toml` | `gpt-5.6-terra` | `medium` |
| 只读探索 / 扫文档 / 找线索 | `light-explorer` | `gpt-5.6-luna` | `low` |
| 已授权的确定性 Git 同步 | `mechanical-sync-worker` | `gpt-5.6-luna` | `low` |
| 高档明确开发 / 跨文件判断 | `implementation-worker` | `gpt-5.6-sol` | `high` |
| 保守档明确开发 / 跨文件判断 | `implementation-worker` | `gpt-5.6-terra` | `high` |
| 独立复核 / 验收审计 | `review-auditor` | `gpt-5.6-sol` | `high` |
| 超强审计 / 专家会诊 | `xhigh-auditor` | `gpt-5.6-sol` | `xhigh` |

项目档位必须由 `/bridgeforge` 根据用户明确声明写入 `.codex/subscription-tier.toml`；marker 存在时禁止重复询问或静默改档，只有用户主动要求切换才可改写。禁止读取账户、账单或用户级 `~/.codex/config.toml` 推断档位。

- 已运行的主对话不自动中途换模型；需要升档时按任务分流到对应 custom agent。`xhigh` 只由用户当次自行选择，骨架不得自动提升。
- 禁止因为“任务大但机械”就用 `xhigh`；只有疑难根因、高风险决策、或 high 复核仍判断不清时才申请。
- Codex 的 `SKILL.md` frontmatter `model:` 不作为本骨架的自动切换依据；Codex 模型路由以 `config.toml` 和 `.codex/agents/*.toml` 为准。

### 4.6 Skill 分段路由（强制）

`.codex/skill-routing.json` 是 18 个下游通用 skill 的路由单一事实源；`bridgeforge` 是用户级全局入口，只在该文件的 `global_entries` 中单列，不属于这 18 个项目 skill。

- 调用已登记 skill 时，先读 manifest 命中的阶段；非 `main` 阶段**必须显式 spawn**该行的 named custom agent，等待其有限证据摘要，主对话不得自行重做该阶段。
- 子 agent prompt 必须包含：agent 名称、阶段目标、文件 / 工具边界、只读或写入约束和回传格式。用户提问、审批、跨阶段整合与 manifest 的 `root_must_do` 始终留在主对话。
- `light-explorer` 只能执行 `read-only` 行；`implementation-worker` 只能执行 `implementation` 行；`review-auditor` 只能执行 `audit` 行。不得把写入、用户确认或独立审计降到 Luna。
- `mechanical-sync-worker` 只在用户显式 `$git-sync` 时执行 `controlled-write` 行，且只允许运行 `.codex/scripts/codex_git_sync.py`；分叉、冲突、失败和任何决策必须立即交回主对话。
- manifest 不得自动路由到 `xhigh-auditor`。`xhigh` 仍须本次请求中用户明确确认。
- 这是工作流指令契约，不是 Codex 平台级 runtime router：`model_policy_check.py` 只校验配置与规则；实际 named-agent 分派须通过运行时 smoke test 留证。

白话类比：主对话是总控台默认中火，子 agent 是预设工具箱；hook 是巡检员，发现档位被拧错就报警或在提交前拦住。

---

## 5. Memory 项目内托管（自动）

memory 纳入项目 git（`.codex/memory/`），系统路径 `~/.codex/projects/<hash>/memory/` 用 junction 透明转发；`memory_junction_check.py` 每次 SessionStart 自动维护。禁止硬删可能含数据的目录，迁移失败用 `.bak`。

检索顺序：先查 MEMORY.md 主索引；无匹配再用 `$find-memory <关键词>` 搜冷区；禁止跳过主索引直接 grep 全量 memory。MEMORY.md 是派生索引，勿手改。

---

## 6. 换机首次启动 Checklist

用户提到“换电脑 / 新机 clone / 重装”时，先 clone 并按主语言初始化依赖，再按 `rules/portability.md` §2 / §4 处理 Python hook、git UTF-8、junction 和依赖清单陷阱。

```bash
git clone <repo_url> {{PROJECT_NAME}} && cd {{PROJECT_NAME}}
```

---

## 7. 项目结构速查

<!-- 列顶层目录及职责（一行一个），帮 Codex 快速定位代码。跑 `ls` 看顶层照填。 -->

---

## 8. 鬼打墙觉察 + 渐进升级（红线）

默认单 agent。以下情况必须主动升级，不等用户提醒：

- 等价性验收 / 重写 / 移植：完成后派独立 verification agent，禁止只靠自测。
- 任务跨 ≥ 2 模块且不熟：先派 research agent 调研再动手。
- 同一 bug 前 3 次改动失败，第 4 次禁止继续写代码；列已试方案 + 未验证假说，提议 `$escalate` 或 `$debate`。
- 每次失败后再次动手前，必须先取一项量化数据（日志 / 产物 mtime / grep 结果 / 截图反推数值）。细则见 `rules/debugging.md` §6。

---

## 8.5 自改审计独立性（红线）

当审计对象包含本轮 agent 自己刚做的改动，且用户要求“审计 / 复核是否达成需求 / 找遗漏”时，必须启动独立 agent 二次审计。普通解释、轻量自查、用户未要求审计时不强制。

---

## 9. 主观体验报告主动问范式（红线）

用户基于外部观察报主观体验 / 怪现象且缺稳定复现时，不要猜修。一次性问全：可观察证据、前 N 步操作 / 触发条件、发生频率、是否能存档现场（如 `$snapshot`）。拿到信息后先加 timer / counter / log 量化，再判断。

---

## 9.5 较大需求主动澄清 — `[clarify]`

读到 `[clarify]` 后先语义精判：琐碎 / 续接 / 已说全细节 -> 直接执行；真·新的 / 大而模糊 / 容易走偏的开发需求 -> 先澄清。

- 已表达执行意图但范围 / 验收 / 关键取舍模糊：先给当前理解、可选路线、推荐路线和理由，再只问当前最关键的一个问题。
- 每轮最多问一个问题；累计每 3 个问题必须暂停总结；超过 6 个问题仍未收敛，改出 PRD / 验收草案 / 设计讨论稿让用户改。
- 能说清目标、非目标、触发条件、验收口径、已确认项 / 合理假设 / 剩余风险时，停止追问。
- 需要落盘需求、验收清单、用户试用闭环的大需求，或用户说“按完整流程做 / 开一个需求 / 走 develop”，进入 `$develop`。
- 评估 / 咨询类只给结论 + 风险即收口；不要包装成执行菜单替用户开单。

细节、hook 路径和调参见 `rules/anti_drift_hooks.md` §1。

---

## 9.6 任务防漂移 — `[focus]`

读到 `[focus]` 后只处理“无意漂移”。用户明确转入新任务是正常行为；正当深入就忽略。

- 前置阻塞：大的用 `$spinoff` 交接，小的内联做完即回。
- 附加扩张：用 `$todo` 归档，先完成原任务。
- 无关支线：用 `$todo` 或建议开新对话，不内联。
- 方案替换 / 扩缩范围：先说“原打算 X，现改走 Y，因为 Z”，再动手。
- 顺手改必须告知：任何非本次点名的顺手改动，都要主动说明“顺带改了 X，因为 Y”。

细节见 `rules/anti_drift_hooks.md` §2。

---

## 10. 上下文成本与预算 — `[ctx-budget]`

| 级别 | 响应 |
|------|------|
| ECONOMY（默认 80k） | 完成当前子任务后准备短交接，避免继续膨胀 |
| HANDOFF（默认 140k） | 不在本任务开启新的大型子任务；建议 `$snapshot` 后开新任务 `$resume latest` |
| CRITICAL（默认 200k 或窗口 75%） | 开头告知用量并强烈建议立即交接；用户坚持可继续，但必须说明风险 |
| CACHE_MISS（可叠加） | 明确说明缓存命中偏低，旧长任务可能已发生整段重算 |

边界附近以信号为准。信号只提醒、不阻断明确要求；`$snapshot` / `$resume` / `/compact` 自身静默放行，`$git-sync` 仍可执行但不再跳过成本提示。细节见 `rules/anti_drift_hooks.md` §3。

Codex 的有效窗口优先读取日志 `model_context_window`，环境变量仅作显式覆盖，最后才使用保守默认值。禁止把 `cached_input_tokens` 再加到已包含缓存的 `input_tokens` 上。

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
