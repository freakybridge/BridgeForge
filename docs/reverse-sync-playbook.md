# 反哺工作流 Playbook

> **定位**：把下游项目（StratusAgent / causis_risk_suite / ClaudeBridgeAssist 等）攒到的通用 agent 协作经验，提炼脱敏后写回 setup_agent 这个上游骨架库。
>
> **为什么不做成 skill / 自动化**：反哺的核心是"通用 vs 业务专属"判断，需要人脑逐段把关；setup_agent 又是公开 GitHub 仓库，自动化容易把内部术语/账户号/API endpoint 等敏感物泄露到公网。先把流程跑顺 2-3 次，再判断要不要工具化。

---

## 1. 触发时机

满足任一即可触发一次反哺：

- **下游项目新加了 ≥ 3 条疑似通用范式**（不只本项目能用，换个项目也成立）
- **下游项目又踩了一个通用坑**（如 Windows 行尾 / venv 不可移植 / 编码陷阱这种跨项目都会遇到的）
- **用户主动喊**（"反哺一下 setup_agent"）
- **季度/月度盘点**（建议每季度过一次，避免积压太多差异）

---

## 2. 五步操作流程

### Step 1：列源项目 + 探查现状

```powershell
# 列所有候选源项目的 .claude/rules/
ls D:/Quant/StratusAgent/.claude/rules/
ls D:/Quant/causis_risk_suite/.claude/rules/
ls D:/Quant/<其他>/.claude/rules/

# 对比 setup_agent 现有 templates
ls D:/Quant/setup_agent/templates/rules/
```

明确**这次反哺的范围**（哪几个源 → 哪几个目标文件）。范围不要贪大，一次 5-8 个文件对比为宜，超过就拆成几次。

### Step 2：逐文件 diff，标候选段

每个目标文件（如 `portability.md`），把所有源项目对应文件并排读，标出：

- 🟢 **通用增量**（setup_agent 没有 + 真的跨项目通用）
- 🟡 **可抽象**（偏某语言/某平台特有，但脱敏后仍有参考价值）
- 🔴 **业务专属**（gateway / oms / 内部包名等，绝对不能反哺）

工具技巧：

- 用 `Read` 并行读多个文件
- 用 `Grep` 快速找特定段落是否已存在
- 标 🟢 的段落，逐字记下"来源文件 + 行号"，方便 review 时回查

### Step 3：脱敏（最关键 — 见 §3 checklist）

对每个 🟢 段落，按 **§3 脱敏 checklist** 逐项过。脱敏不彻底就不要进 setup_agent。

### Step 4：写 setup_agent

- 写入路径**只允许**：`templates/rules/`、`templates/CLAUDE.md`、`templates/memory/`、`templates/doc/`、`docs/`
- **禁止**自动写：`skills/`（用户级 skill，独立维护）、`scripts/`、`SKILL.md`、`README.md` 核心段
- 写完用 `git diff --stat` 看改动规模，**逐文件 review**（不批量 confirm）

### Step 5：review + 手动 push

```powershell
cd D:/Quant/setup_agent
git diff                    # 全量看一遍
git diff --check            # 检查空白/编码异常
git status                  # 确认没意外文件
git add <精确路径>          # 不要 git add .
git commit -m "..."
git push                    # 用户手动，不让 AI 自动
```

**push 前最后一道闸**：搜一遍 commit 内容里有没有这些敏感关键词：

```powershell
git diff --cached | Select-String -Pattern "(causis_api|StratusAgent|账户|API.?key|0x[0-9a-f]{8}|D:/|C:/Users)"
```

有命中 → 停下脱敏；全过 → 放行。

---

## 3. 脱敏 checklist（红线）

每个反哺段落必须过这 7 项。**只要漏 1 项，反哺就不安全。**

| # | 检查项 | 例子（要替换的） | 替换为 |
|---|--------|------------------|--------|
| 1 | **项目名** | `StratusAgent` / `causis_risk_suite` / `causis_api` | 通用占位 `<project>` / `<pkg>` |
| 2 | **内部包/模块名** | `vnpy_ctp` / `causis_api.const.login` / `risk_daily.config` | 通用占位或删掉 |
| 3 | **账户号 / API key / token** | 任何看起来像凭证的字符串 | **整段删，不替换** |
| 4 | **内部 URL / endpoint** | `causis.internal/...` / 内部 IP | 通用占位 `<internal-url>` 或删 |
| 5 | **commit hash / 事故 ID** | `761274f` / `vtable mismatch 78 函数偏移` | 删 |
| 6 | **绝对文件路径** | `D:/Quant/<project>/...` / `C:/Users/<name>/...` | 相对路径或占位 |
| 7 | **业务术语** | 交易所代号 / 期权 greeks / 风控阈值名 / 客户产品名 | 通用化（如"外部 SDK"/"业务字段"）或删 |

**特别注意**：

- 事故案例（"YYYY-MM-DD 那次踩了 X"）原则上**整段删**，rule 文件不留案例，案例归 memory（meta_rule_design.md §2 规定）
- 段落里如果出现版本号/日期超过 3 处 → 信号说明案例越界 → 重写成 normative 表述
- 公开技术名（IB / Schwab / Deribit / CTP / Python / Rust / Node 等开源或公开品牌）**不算敏感**，可保留

---

## 4. 冲突仲裁规则

多个源项目同一段表述不一致时，按以下顺序仲裁：

1. **并集合并 + 用户拍板**（默认）— 列出每个源的版本差异，让用户选
2. **以更新更近的为主**（看 git log mtime）— 用户没空时退而求其次
3. **以源项目实战次数多的为主**（如 StratusAgent 跑了 1 年 vs 新项目跑了 1 周）
4. **不确定就不反哺** — 宁可漏，不可错

---

## 5. 反哺日志

每次反哺在下表追加一行。攒 5+ 行后再回头看是否值得做工具化。

| 日期 | 源项目 | 目标文件 | 反哺内容（一句话） | 操作人 |
|------|--------|----------|--------------------|--------|
| 2026-05-24 | causis_risk_suite | modules.md | +§4 `.runtime/` 运行时数据目录 + §5 根目录极简 | bridgexue |
| 2026-05-24 | causis_risk_suite | portability.md | +§4.3 venv 不可移植 + §4.4 CRLF + §4.4.1 入口脚本 ASCII + §4.5 editable 安装 | bridgexue |
| 2026-05-24 | StratusAgent | workflow.md | §9 版本号简版 → Milestone-bound SemVer 详细版 | bridgexue |
| 2026-05-24 | StratusAgent | meta_rule_design.md（新建） | 整体脱敏搬入元规则（强制力梯度 / 加载策略 / 反模式速查） | bridgexue |

---

## 6. 什么时候考虑工具化

下面 3 个条件**同时满足**再考虑做 `/upstream-sync` skill：

- [ ] Playbook 已用 ≥ 3 次，流程没大改
- [ ] 脱敏 checklist 7 项里没有"凭直觉判断"的项（都能机械化）
- [ ] 有明确的"多源并发反哺"需求，手动协调成本变高

否则**别工具化** — 反哺的判断密集度太高，工具化只会把判断错误自动化。

---

## 7. 反哺的反方向：从 setup_agent 拉新东西回下游

下游项目（StratusAgent 等）**不会自动拿到** setup_agent 的更新。如果想把 setup_agent 的新内容拉回下游：

- **手动 diff**：对比 `D:/Quant/setup_agent/templates/rules/` 和 `D:/Quant/<下游>/.claude/rules/`
- **选择性吸收**：下游可能已经在某段上自行演进，不要无脑覆盖
- **没有 skill 自动做** — 跟反哺一样，靠人脑判断，这是有意为之

---

## 参考

- [docs/design-rationale.md](design-rationale.md) — setup_agent 整体设计思路
- [templates/rules/meta_rule_design.md](../templates/rules/meta_rule_design.md) — 怎么写 rule 才不退化（反哺时判断"通用 vs 业务"的关键依据）
