# Skill 分发机制：漏洞盘点与修复设计

> 状态：设计/未实施。2026-06-09 一次架构 review 的产物。
> 性质：元文档（描述产品机制，**不**随产品下沉）。

## 背景：当前分发机制（事实）

- **单一源**：`D:\Quant\BridgeForge`（GitHub: freakybridge/BridgeForge）。
- **用户级架子** `~/.claude/skills/`：Claude 真正加载 skill 的地方（全机共享，所有项目共用）。
  - `bridgeforge` 这一项 = **junction**（开发机）/ **git clone**（真下游），指向上游仓库。
  - 各通用 skill（find-doc/summary/…）= 从 `bridgeforge/skills/` 复印来的**实体副本**（非软链——`portability.md §2` 有意取舍：换可移植性）。
- **正向同步**（`/bridgeforge` Step 0）：缺→补、旧→更（给 diff 问用户）、**无删除语义**。
- **反向同步**（`/harvest`）：下游收件箱→脱敏→写上游 `templates/`/`skills/`→**人工 review + push**（不自动 push）。

## 五个漏洞

| # | 洞 | 一句话 | 严重度 |
|---|---|---|---|
| 1 | **脱敏泄露** | harvest 写的是**公开**仓库，唯一防线是**人工** checklist + 人工敏感词扫描；下游是量化项目（`CAUSIS_*` 凭证、策略名、`D:\Quant` 路径）。漏一项 = 永久公开。 | **高** |
| 2 | **复印件漂移** | 更新通道通（Step 0 会 diff+问），但**只在手动重跑时触发**，无过期信号、无版本钉子 → 各机静默跑旧版。 | 中 |
| 3 | **删除不传播** | 正向同步只增不减。v0.24.0 删了 prune-memory/memory_guard，下游**僵尸**赖着（hook 僵尸还**继续作恶**）。CHANGELOG 自承"需手动删"。 | 中 |
| 4 | **开发机特例** | junction 让本机复印**活工作区**（含未提交/未跟踪垃圾，如曾经的 `__pycache__`）；真下游 clone 的是**已 push 快照**。"本机 dogfood 通过"是**虚假安心**。 | 中低 |
| 5 | **版本信号靠手打** | 同步决策靠 `grep [product]` + VERSION，但 bump/打标全手动 → 忘了/标错就**假报平安**，下游静默漏更。本会话 `[skip-version]` 已是发飘苗头。 | 中 |

> **2–5 是同一根的四张脸**：整套靠"复印件 + grep 信号 + 人手 bump"，**没有机器强制"信号==现实"**。

## 修复：两根支柱

### 支柱 A — 脱敏安检闸（`secret-scan`）｜决定：**暂不做**（用户判断单人够用）
- 机制：在 **push 前**（git pre-push，工具无关的最后卡点）扫**本次 diff**，对照可维护的危险词单（凭证/项目名/绝对路径/内网 URL/疑似密钥 hash/个人邮箱）；命中 `exit 2` 阻断，逃生口需留痕。
- 局限：启发式，只逮已知模式；**逮不住语义机密**（白话描述的策略逻辑）。是 defense-in-depth，不替代人判断。
- 可吃狗粮 + 反哺下游（"push 前敏感词扫描"通用）。

### 支柱 B — 配货清单 + 开机自检｜决定：**可以有**（用户 2026-06-09 认可）
**端掉洞 2–5 的同一招。** 分两块实施：

#### 第一块 — 开机自检（检测 + 通知）｜**已实现 v0.25.0（待发版）**
- 落点：`templates/hooks/skill_sync_check.py` + dogfood `.claude/hooks/` + 两处 settings `SessionStart` 注册。
- 做什么：每次 session 开始，**离线**比对用户级 `<skill>` 副本与上游源 `~/.bridgeforge/skills/` 的**内容哈希**，缺失/不一致打印一行 `[skill-sync]` 提示跑 `/bridgeforge`。
- **只读不改**：hook 绝不动文件；真正的补/更/删仍由 `/bridgeforge` Step 0 在用户确认下做（**绝不静默覆盖定制** —— 与既有原则一致，故 hook 只通知不自动盖）。
- 自门控：没装 bridgeforge → 静默 no-op（范式同 `target_cleanup.py`）。
- **v1 有意收窄**：离线比对本机上游 clone 工作区（不 git fetch —— SessionStart 必须快且不能联网失败）；只报缺失/漂移，**不报"已退役"**（需下方第二块的 provenance 标记/退役清单）。
- 关键取舍（已定）：**不做"全自动悄悄盖"**（会毁定制 + 半路换砖）；自检只到"通知"，应用动作交 Step 0 分级处理（没动过的可自动更、改过的/退役的停下问）。

#### 第二块 — 退役检测｜**已实现 v0.25.0（待发版）**（精益版，非重型 manifest）

实施时的工程判断：原设想"version-stamped manifest + 每 skill 版本标签"被**有意砍掉**——
第一块的**内容哈希自检已覆盖"漂移/落后"**（哈希比对压根不需要版本号），再叠 manifest 是
冗余机械。真正还缺的只有**退役检测**，用一张轻量墓碑清单即可，无需 manifest、无需 backfill。

- **`RETIRED.md`（新增 repo 根墓碑名单）**：机器可读，每行 `- <name> | <版本> | <日期> | <原因>`，机器只取第一列。首条 `prune-memory`。退役一个 skill = 删目录 + 追加一行 + CHANGELOG Removed。
- **`skill_sync_check.py` 退役检测**：读 `RETIRED.md`，墓碑名单里仍在 `~/.claude/skills/` 的 → 报 "N 个已退役待删"。
- **`SKILL.md` Step 0 退役清理**：同上，列出来**问用户删**（Step 0.5 清"重复"副本的亲兄弟，本步清"退役"副本；绝不静默删）。→ **关掉洞 3**。

#### 仍未做（诚实边界）
- **退役 hook（项目级）**：`memory_guard` 这类退役 hook 活在下游项目 `.claude/hooks/` + 项目 settings 注册里，是项目级、改下游 settings 的更重操作，**仍靠手动删**（CHANGELOG v0.24.0 已提示）。
- **GitHub 新鲜度**：自检只比**本机上游 clone**。要比 GitHub 最新，`SKILL.md` Step 0 给了**手动 `git pull` 上游 clone**的指引（开发机 junction 则跳过，避免 pull 动未提交工作区）；没做自动 fetch（SessionStart 不宜联网）。
- **洞 4（开发机特例）未真正关闭**：之前设想"manifest 只认声明的正品、junction 脏东西进不来"——但既然没做 manifest，离线哈希比对**仍会把工作区未提交脏东西算作"不一致"**。洞 4 的真正解法是**用干净 clone / CI 验安装流**（进程/CI 事，非 manifest），归future work。

## 后续
- 实施 B 时，版本钉子/manifest 与 [memory-scoring-design](memory-scoring-design.md) 的 `_stats.json` 思路可参考（都是"机器维护的状态文件"）。
- Step 0.5（清项目级**重复**副本）已落地；"清用户级**退役**副本"是它没补的亲兄弟，归入 B 的"已下架→撤"。
