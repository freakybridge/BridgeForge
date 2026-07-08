---
paths:
  - "doc/**"
  - ".codex/rules/**"
---

# 开发工作流规则

> 适用场景：涉及架构范式、接口约定、数据流方向、较大改动时

---

## 1. 范式改动必须同步文档

当改动涉及以下任一类别时，**代码提交前**必须同步更新对应文档：

| 改动类别 | 需更新的文档 |
|---------|------------|
| 核心职责边界、数据流方向 | `.codex/rules/architecture.md` |
| 模块组织 / 新增模块流程 | `.codex/rules/modules.md` |
| 调试规范变更 | `.codex/rules/debugging.md` |
| 可移植性 / 依赖管理 | `.codex/rules/portability.md` |
| 新增数据对象或核心枚举 | `doc/0_architecture/` 下对应文件 |
| 接口契约变更 | `doc/3_design/` 下对应文件 |

<!-- TODO: 按本项目实际有的 rule / 设计文档补充 -->

**判断标准**：如果改动会影响其他模块的开发者（含未来的 AI Agent）做决策，就必须同步文档。

---

## 2. 主动发现范式并写入 Rule

在开发过程中，如果发现代码中存在**反复出现的模式或约定**（无论是好的范式还是需要禁止的反模式），且当前 rules 中尚未覆盖，应**主动**将其提炼为规则写入对应的 `rules/*.md` 文件。

**触发条件**（满足任一即可）：
- 同一种写法在 2 个以上模块/文件中重复出现
- 修 bug 时发现根因是某种编码习惯，但 rules 中没有禁止
- 做 code review 时发现"这里应该这样写"但没有明文规定
- 引入新的外部依赖/API，其使用方式有特定约束

**写入位置**：根据范式所属领域，写入对应的 path-specific rule 文件（参见 AGENTS.md §2 规则索引）。

---

## 3. 经验总结

每次遇到以下情况，必须将经验写入 memory（`.codex/memory/` 下的 memory 文件，详见 AGENTS.md §5）：

- **踩坑修复**：一个 bug 花了超过 2 轮才定位到根因
- **范式决策**：在多个方案中做了选择，且选择理由不显而易见
- **外部 API 行为差异**：发现某外部 API 的非文档行为或隐性约束
- **工作流 / 工具选择决策**：经过 debate / 性能实测 / 多次踩坑后形成的稳定原则。**严格触发**：必须有数据支撑或多次会话验证；**不触发**：单次任务里临时选了某工具

---

## 4. 任务收尾自查

当一轮**较大的开发或调试任务完成后**，主动回顾本次对话，逐项检查：

- [ ] 是否有尚未写入 rules 的新范式？（→ 执行 §2）
- [ ] 是否有尚未写入 memory 的踩坑经验？（→ 执行 §3）
- [ ] 是否有需要同步的文档？（→ 执行 §1）

**触发时机**：用户说"提交"、"收工"、"结束"，或一个功能模块开发完毕准备 commit 时。如有遗漏，先补齐再提交。

---

## 5. 文档索引同步

`doc/README.md` 是文档目录的唯一索引。以下操作**必须同步更新索引**：

- 新增文档：在对应分类表格中添加条目
- 删除文档：从索引中移除对应条目
- 移动文档：更新路径
- 重命名文档：更新文件名和链接
- 新增目录：在索引中添加对应分类章节

**判断标准**：任何导致 `doc/` 下 `.md` 文件变化的操作都需要同步索引。

---

## 5.5 doc/ 是项目级强制（红线）

> **红线条文**（必须分层 / 禁止散落根目录 / 禁止跳层 / 禁止改名合并 / 禁止新增同级 / `doc/README.md` 唯一索引）见 `AGENTS.md §11`（常驻，每轮在场）。本节是触发层增量：只给 **Why 正文 + 操作细节**，不重复条文（避免双份正文漂移，见 `meta_rule_design.md §4.3`）。

**Why（为什么是红线）**：文档分层是 bridgeforge 的核心范式之一，与 rules / memory 深度耦合：

- 多个协作 skill（如 `$feature-dev` `$archive-scan` `$todo` `$find-doc` `$sync-docs`）依赖 doc/ 六层结构 — 缺层会让 skill 静默装死
- `workflow.md §6-§7` + `meta_rule_design.md` 的"案例下沉"范式都假设 `doc/3_design/` 和 `doc/2_pending/` 存在
- 长期可维护性：散落各处的文档随项目演进必然失控；强制集中是经验教训

**How to apply**：

- 写新文档前先想"它属于六层中的哪一层"，找不到归属 → 文档定位本身有问题，先想清楚再写
- AI 创建文档时**默认走 doc/**，**禁止**在 `src/<module>/README.md` / 项目根目录 / 临时位置写设计文档
- 项目早期可能六层中多数为空，**这是正常状态**，不要因为"看着空"就删层 / 合层

---

## 6. 文档目录职责边界

| 目录 | 放什么 | **禁止**放什么 |
|------|--------|--------------|
| `doc/0_architecture/` | 架构级红线（PRD、需求、约束、roadmap）+ **acceptance.md（正在做的验收）** + **TODO-INDEX.md（暂时没空做的短期 todo + 远期 backlog 索引）** | 阶段性总结、临时计划 |
| `doc/3_design/` | 模块实现的最终形态（项目自产的模块设计） | 第三方 API 文档、协议参考、外部截图 |
| `doc/1_plan/` | 按主题归集的活跃推进 + 协作记录 + `sprints/` Sprint 级日程 | 已完成归档项 |
| `doc/2_pending/` | 未决问题备忘 + 未决讨论（短期没精力解决，有上下文要展开的）| 已完成 / 已废弃的文档；**TODO-INDEX.md 不放此处**（在 `0_architecture/`）|
| `doc/4_archive/` | 已完成归档 | 仍在推进中的文档 |
| `doc/9_reference/` | 外部/第三方参考资料（协议文档、竞品截图、AI prompt） | 项目自产的设计或规范 |

**判断标准**：如果文档内容不是你（项目团队）写的，而是来自外部库 / 工具 / 协议，就放 `reference/`，不放 `design/`。

---

## 7. 文档权威位置

| 内容类型 | 权威位置 | 说明 |
|---------|---------|------|
| 架构约束（禁止/必须） | `.codex/rules/` | 唯一维护点，改这里 |
| 设计文档（背景、方案、迁移指南） | `doc/3_design/` | 设计说明，较少改动 |
| 产品需求、Roadmap | `doc/0_architecture/` | 阶段性更新 |
| 踩坑经验 | `.codex/memory/` | 按需积累 |

---

## 8. 子目录 README 同步规则

**新增 / 删除 / 重命名 `doc/<topic>/` 子目录下文件时**，必须同步该目录的 `README.md`：

- `README.md` 的"文件清单"段落要保持跟实际文件一致
- 新增子项目（一级或二级子目录）→ 同步上级 README.md 的子目录索引表

**模板**：每个子目录 README 包含 5 段 — 定位 / 文件清单 / 命名约定 / Agent 改动指引 / 关联资源。

### 远期项目 README 退化规则

子目录内"内容文件数 ≤ 1"且无子文件时，**禁止**建独立 5 段模板的 README。改用单段 stub（≤ 5 行：一句话定位 + 文件链接 + 状态 + 父级链接）。

**判定**：如果 README 行数 ≥ 内容文件总行数的 50%，或 README 比内容文件还长 → 是过度建立，应退化为 stub。

---

## 9. 版本号管理（红线）

> 适合**有 Milestone 节奏 + 长期演进**的项目。小项目（< 5 人、无 Milestone）可退化简版（patch=bug / minor=新功能 / major=破坏性），整节用 TODO 注释包住。

**红线：每次 commit 前必须提升一次版本号。**

### 9.1 单一事实源

版本号只写**唯一一处** SoT 文件（`package.json` / `Cargo.toml` / `pyproject.toml` / `VERSION`），子包靠继承机制（如 Cargo `version.workspace = true`）共享；构建期嵌入（`env!("CARGO_PKG_VERSION")` 等），bump 后须重新 build。展示位置按项目填 <!-- TODO: 标题栏 / CLI `--version` / 关于框 -->。

### 9.2 三段语义（SemVer，Milestone 绑定）

| 段 | 触发 |
|---|------|
| **Major** | Milestone 整体验收通过（M1 ship → 1.0.0） |
| **Minor** | 用户多了一件能干的事（新模块 / 面板 / 接入） |
| **Patch** | 日常 commit（bug / 小调整 / 文档 / refactor） |

**核心判据**：commit 后用户能否多干一件之前不能干的事？能 → minor，否则 → patch。**重置**：major+1 → minor/patch 归 0；minor+1 → patch 归 0。

### 9.3 细颗粒度不进版本号

Phase / Sprint / Task 比 Milestone 细，不进版本号：Phase 用 git tag（`m<N>.<phase>-complete`，链接验收报告）、Sprint/Task 用 commit prefix（1 commit 1 task）。Milestone ship 打 `m<N>-shipped` 并 bump major。Phase 完成本身不强制 bump minor，只看是否引入用户可感知新功能。

### 9.4 Commit message 格式

`<类型>(M<N>.<Phase>.S<Sprint>): <描述> (vX.Y.Z)` — 类型取 `feat`/`fix`/`refactor`/`perf`/`docs`/`chore`，无 phase 概念则省略括号前缀。**末尾必带 `(vX.Y.Z)`** 便于 `git log --oneline` 识别。

> 范例：`feat(M1.D.S1): 接入新数据源 (v0.10.5)`

### 9.5 触发时机

`git commit` 前先编辑 SoT 文件提版本号，一并 `git add` 进本次 commit。

### 9.7 禁止（红线）

- ❌ 跳过 patch 直接跳 minor
- ❌ 一次 commit 跳多级（如 0.9.102 → 1.1.0）
- ❌ 忘编辑版本号就 commit（忘了则后续 commit 补一次并注明"版本补齐"）
- ❌ Milestone 验收通过前自行 bump major（v1.0.0 必须等 M1 ship）
- ❌ 用 4 段版本号（不兼容 SemVer / Cargo / npm）

### 9.8 自动强制（hook 兜底，非自觉）

Python 项目装有 `.codex/hooks/version_check.py`（PreToolUse / Bash）：`git commit` 前查 staged 是否含版本号 SoT 文件（`VERSION` / `package.json` / `Cargo.toml` / `pyproject.toml`），没 bump 直接 `exit 2` 阻断。豁免：message 加 `[skip-version]` / `--amend` / 正在 merge。非 Python 项目无此 hook，退化为仅靠 §9 软规则（自觉 + 收尾自查 §4）。

> **Why**：hook 存在前 §9 作软规则被反复忘记（多次忘 bump / 漏 tag），故把红线从「自觉」升级为「机制强制」。

---

## 10. 大版本依赖升级必做 spike 验证

**任何"为某个可感知体验诉求"（性能 / UI 行为 / 字体 / etc）而跨大版本升依赖，必须先 2-4h spike 验证核心诉求。**

### 流程

1. 在主项目**外**建 minimal 复现项目
2. 新版依赖 + 最小复现代码（几十行够用）
3. 跑起来和现状对比（截图 / benchmark / 主观判断）
4. **用户签字"确实改善"** → 启动全项目升级
5. **"没改善"** → 2-4h 沉没成本止损，放弃升级

### 禁止

- **直接动主项目**（lockfile drift + 回滚困难 + 用户等结果焦虑）
- **"看 CHANGELOG 写着改善就行"**（主观判定 vs 纸面结论往往不一致）
- **"先升级，后来再验证"**（沉没成本心理偏差会让人凑合接受）
