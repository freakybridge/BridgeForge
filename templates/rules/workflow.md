---
paths:
  - "doc/**"
  - ".claude/rules/**"
---

# 开发工作流规则

> 适用场景：涉及架构范式、接口约定、数据流方向、较大改动时

---

## 1. 范式改动必须同步文档

当改动涉及以下任一类别时，**代码提交前**必须同步更新对应文档：

| 改动类别 | 需更新的文档 |
|---------|------------|
| 核心职责边界、数据流方向 | `.claude/rules/architecture.md` |
| 模块组织 / 新增模块流程 | `.claude/rules/modules.md` |
| 调试规范变更 | `.claude/rules/debugging.md` |
| 可移植性 / 依赖管理 | `.claude/rules/portability.md` |
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

**写入位置**：根据范式所属领域，写入对应的 path-specific rule 文件（参见 CLAUDE.md §2 规则索引）。

---

## 3. 经验总结

每次遇到以下情况，必须将经验写入 memory（`.claude/memory/` 下的 memory 文件，详见 CLAUDE.md §5）：

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

**本项目必须用 `doc/` 分层管理所有文档**，不接受跳过 / 改名 / 合并 / 散落根目录。

| 强制项 | 内容 |
|--------|------|
| **必须存在** | 项目根目录下必须有 `doc/` 目录 + §6 列出的六个子目录（即使为空也要建，用 `.gitkeep` 占位）|
| **必须按六层结构** | `0_architecture / 1_plan / 2_pending / 3_design / 4_archive / 9_reference`，序号 + 名称都不可改 |
| **禁止散落根目录** | `README.md` / `CHANGELOG.md` / `LICENSE` 这种**根级元数据文件**可留根，**其余所有 .md 文档**必须挂 `doc/<层>/` |
| **禁止新增同级目录** | 想加 `doc/notes/` / `doc/wip/` / `doc/legacy/` → 必须归到 §6 现有六层之一（活跃的归 1_plan，未决归 2_pending，归档归 4_archive）|

**Why**：详见 `CLAUDE.md §11`。简短理由 — 文档分层是 setup_agent 与 rules / memory / 4 个 doc-依赖 skill 深度耦合的核心范式；散落即失控。

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
| 架构约束（禁止/必须） | `.claude/rules/` | 唯一维护点，改这里 |
| 设计文档（背景、方案、迁移指南） | `doc/3_design/` | 设计说明，较少改动 |
| 产品需求、Roadmap | `doc/0_architecture/` | 阶段性更新 |
| 踩坑经验 | `.claude/memory/` | 按需积累 |

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

> 本节适合**有 Milestone 节奏 + 长期演进**的项目。小项目（< 5 人、无明确 Milestone）可退化为简版：patch=bug 修复 / minor=新功能 / major=破坏性改动。退化时整节用 TODO 注释包住即可。

**每次 commit 前必须提升一次版本号。**

### 9.1 单一事实源 + 展示位置

- 版本号写在**唯一一处**主版本号文件（如 `package.json` / `Cargo.toml` / `pyproject.toml` / `VERSION`），所有 crate / 子包通过继承机制（如 Cargo workspace 的 `version.workspace = true`）共享
- 编译期由构建工具嵌入（如 Rust 的 `env!("CARGO_PKG_VERSION")` / Node 的 `package.json` 引用），bump 后必须重新 build 才生效
- **展示位置**（按本项目实际填）：
  - <!-- TODO: 主窗口标题栏 / CLI `--version` / 关于对话框 等 -->

### 9.2 三段语义（Milestone 绑定 SemVer）

| 段 | 含义 | 触发条件 |
|---|------|---------|
| **Major (X)** | **Milestone ship** | 当前 Milestone 整体验收通过 — M1 ship → 1.0.0 / M2 ship → 2.0.0 |
| **Minor (Y)** | **用户多了一件能干的事** | 新模块 / 新面板 / 新接入 / 新可感知功能上线 |
| **Patch (Z)** | **日常 commit** | bug 修复 / 小调整 / 文档 / refactor / Sprint 内常规推进 |

**判断 minor vs patch 的核心问题**：这次 commit 后用户能不能多干一件之前不能干的事？能 → minor，否则 → patch。

**重置规则**：major+1 → minor 和 patch 归 0；minor+1 → patch 归 0。

### 9.3 Phase / Sprint / Task 不进版本号

颗粒度细于 Milestone 的层级通过其他机制记录：

| 层 | 记录方式 |
|---|---------|
| **Milestone** | 版本号 Major（ship 时 +1） |
| **Phase** | git tag |
| **Sprint** | commit message prefix |
| **Task** | commit message prefix + 1 commit 1 task |

**Phase 完成本身不强制 bump minor** — 只看该 Phase 是否引入用户可感知的新功能。

### 9.4 Git tag 规范

- **Phase 完成**：`m<N>.<phase>-complete`（如 `m1.a-complete` / `m1.d-complete`），tag message 链接到 Phase 验收报告
- **Milestone ship**：`m<N>-shipped`（如 `m1-shipped`），同时 bump major

### 9.5 Commit message 规范

格式：`<类型>(M<N>.<Phase>.S<Sprint>): <描述> (vX.Y.Z)`

- **类型**：`feat`/`fix`/`refactor`/`perf`/`docs`/`chore`
- **括号内 phase/sprint 标识**：标明本 commit 属于哪个 Phase / Sprint
  - 例：`feat(M1.D.S1): 接入新数据源 (v0.10.5)`
  - 例：`fix(M1.A.S2): 平今 frozen 漏解冻 (v0.10.6)`
  - 跨 Phase 或无 phase 概念的 commit 不带前缀：`<类型>: <描述> (vX.Y.Z)`
- **末尾必带 `(vX.Y.Z)`** 便于 `git log --oneline` 一眼识别版本

### 9.6 触发时机

`git commit` 前先编辑主版本号文件提升版本号，一并 `git add` 进本次 commit。

### 9.7 禁止

- ❌ 跳过 patch 直接跳 minor
- ❌ 一次 commit 跳多级（如 0.9.102 → 1.1.0 一步）
- ❌ 忘记编辑版本号就 commit（如果忘了，后续 commit 补一次并在 message 里注明"版本补齐"）
- ❌ 在 Milestone 整体验收通过前自己 bump major（v1.0.0 必须等 M1 ship）
- ❌ 用 4 段版本号（不兼容 SemVer / Cargo / npm）

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
