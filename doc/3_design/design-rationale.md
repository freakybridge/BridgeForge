# 设计原则

> 解释为什么 bridgeforge 这样分层。读这个能让你判断"什么该写进哪里"。

---

## 1. 双层 CLAUDE.md：全局 vs 项目

| 层 | 路径 | 内容 |
|----|------|------|
| 全局 | `~/.claude/CLAUDE.md` | **跨项目稳定的我**：沟通语言、安全确认协议、环境隔离习惯、执行节奏（"先列计划再动手" 等） |
| 项目 | `<repo>/CLAUDE.md` | **项目特定的事**：架构红线、rules 索引、快速命令、项目结构、跨机 checklist |

**判断标准**：换一个项目还成立的内容 → 全局；只对这个项目成立 → 项目。

bridgeforge **不动全局**——全局是个人偏好，应一次性配好；bridgeforge 只铺项目这一层。

---

## 2. Rules 分层加载

CLAUDE.md 太长会被 Claude 截断（实测 200 行后部分加载就降级），所以用"按需加载"模式：

- CLAUDE.md 维护一个**索引表**，每行一条 rule + 加载条件
- 具体规则写在 `.claude/rules/<topic>.md`，文件 frontmatter 用 `paths:` 列表声明触发条件
- "始终加载"的 rule 是真正的红线（约 2-3 个，如 architecture / modules）
- "路径触发"的 rule 是局部约束（如 debug 时才加载 debugging.md）

**升级路径**：feedback memory 沉淀够多 → 升级为 path-rule。例如，连续 5 次踩同一个 API 行为坑就升 path-rule，让所有未来编辑同一类文件的对话都自动加载。

---

## 3. Memory junction：让 memory 跟项目走

Claude Code 默认把 memory 存在 `~/.claude/projects/<project-hash>/memory/`——这是**用户级**路径，跨机不同步。

但 memory 的内容（踩坑经验、用户偏好、决策记录）是**项目特有**的，理应跟项目 git 走。

解决方案：**junction**（Windows）/ **symlink**（Unix）把系统路径透明指向 `<project>/.claude/memory/`。

- Claude Code 仍用系统路径读写（不需要改 Claude Code）
- 实际存储在项目内（git 管理）
- 换机 clone 后跑一次 setup-junction 脚本即可恢复

---

## 4. doc/ 分层归档

```
doc/
├── 0_architecture/  ← 架构红线（PRD / 约束 / Roadmap）+ acceptance.md（正在做的验收）+ TODO-INDEX.md（暂时没空 + 远期 backlog 索引）
├── 1_plan/          ← 活跃推进（按 topic 子目录）+ sprints/（Sprint / Task 级日程）
├── 2_pending/       ← 未决问题展开备忘 + 辩论
├── 3_design/        ← 模块实现设计
├── 4_archive/       ← 已完成归档
└── 9_reference/     ← 外部参考资料
```

**核心二分：正在做 vs 暂时没空**：

| 状态 | 落位 | 性质 |
|------|------|------|
| **正在做** | `0_architecture/acceptance.md`（验收勾选）+ `1_plan/sprints/`（Sprint Task 日程）| 当前周期 commit 的工作 |
| **暂时没空（短期）** | `0_architecture/TODO-INDEX.md` §完整清单（短条目）+ `2_pending/<日期>_<topic>.md`（有上下文的展开备忘）| 已识别但排不进当前 Sprint |
| **远期 backlog** | `0_architecture/TODO-INDEX.md` §远期 Backlog 索引 → 跳转 `1_plan/<模块>/<主题>.md`（不带日期前缀）| 功能尚未排到 Milestone |
| **已完成** | `4_archive/` | 留作历史参考 |

差别在于"行动状态"——TODO-INDEX 主表是**冷冻待解冻**，acceptance + sprints 是**进行中**，archive 是**已落幕**。

文档随时间流动：`远期 backlog → TODO-INDEX 主表 → 排进 acceptance + sprints → 完成后 archive`。`/archive-scan` skill 周期性扫 `2_pending/` 看哪些可以归档。

**为什么 TODO-INDEX 在 `0_architecture/` 而不是 `2_pending/`**：因为它是项目级的**单点真相**（汇总短期 + 远期），跟 PRD / Roadmap / 约束属于同一层级 — 不会因为时间推进而过期，只会增量更新。`2_pending/` 是单个具体问题的展开备忘，归档后会消失，TODO-INDEX 不会。

---

## 5. 工作流红线为什么写进 CLAUDE.md（不是 rules）

CLAUDE.md §8 鬼打墙红线、§9 UI 主动问范式 这两条特别重要的元规则**直接写进 CLAUDE.md**，而不是放 rules/。

原因：
- rules/ 是按需加载的，只在编辑特定文件时才出现
- 鬼打墙红线**永远要遵守**，不能等"编辑某个文件时"才加载
- CLAUDE.md 永远在 context 里，写在这里相当于"永远 on"

**判断标准**：什么事 Claude 在**任何任务里**都不应该做？写 CLAUDE.md。什么事只在**编辑某类代码时**要注意？写 rules/。

---

## 6. 模板 vs 占位

bridgeforge 的模板分两类：

**深模板（直接搬全文）**：
- 鬼打墙红线 / UI 主动问范式 / 修 bug 前确认根因 / 性能先量化 / 经验总结流程
- 这些是"任何项目都该有"的通用工作流，搬就完了

**骨架（占位让用户填）**：
- 架构红线 / 数据流方向 / 项目结构 / 快速命令
- 这些是项目特定的，AI 不该替用户瞎编

**判断标准**：内容是否依赖具体业务领域？依赖 → 骨架；不依赖 → 深模板。

---

## 7. 不做什么

bridgeforge 故意**不做**这些事，留给项目自己决定：

| 不做 | 原因 |
|------|------|
| 不动 `~/.claude/CLAUDE.md` | 全局规范是个人偏好，不该被 skill 覆盖 |
| 不预装具体 skill（plan / debate / escalate 等） | 那些 skill 应该独立维护，bridgeforge 只在 CLAUDE.md §4 给个 TODO 让用户自己决定要装哪些 |
| 不自动 git commit | 让用户先填占位再 commit，避免污染历史 |
| 不替用户编架构红线 | 架构是用户自己想清楚的，AI 编的内容反而误导 |
| 不强制目录结构 | 只给"推荐范式"，用户可以删掉用不上的目录 |
| **不监督下游是否守红线**（不做 doctor / 合规仪表盘）| bridgeforge 是**出版方非监管方**：产出好默认 + 推改进，不盯下游照没照做。下游自治、合理例外正常。详见表后说明 |

> **关于"不监督下游"（2026-05-29 探讨后否决 doctor / fleet 设计）**
>
> 曾设想 `/doctor`（单项目 8 项体检）+ fleet 报表（N 项目合规盘）。**否决理由**：
> 1. **关系模型错**——你管的全是自己的项目，监管者 = 被监管者，给自己建监督自己的仪表盘是空转。
> 2. **远程强制执行必死于"合理例外"噪音**——某些项目因特性无法守某条红线是正常的，仪表盘塞满"预期内的红"后没人看。
> 3. **要可信就得 PULL 现场测**（PUSH 自报会重蹈 CLAUDE.md §8 的"自证陷阱"：项目自己开化验单自己寄）；而你的项目同机，唯一隐形隐患"junction 静默断"已由 CLAUDE.md §5 开机自检覆盖。
>
> **结论**：框架的杠杆在"**发布**好默认 + 把改进**推**出去"，不在"**监管**谁照没照做"。这与本节其余各条（不强制、留给项目自决）一脉相承。
>
> 注：`doc/3_design/design-rationale.md §9.3` 的"镜像漂移检查 hook"是**工厂自查样板间**（bridgeforge 自己的 `.claude/hooks` vs `templates/hooks` 一致性），与"监督下游"是两回事，不受本决定影响。

> **关于 focus 对"点击背书的 scope 升级"结构性盲区（2026-06-26 跑偏调查后否决重武装 focus）**
>
> 一次"评估仓库能否公开 → 被做成全量脱敏执行"的会话跑偏暴露：`focus_reminder.py` 拦不住"agent 把评估包装成 `AskUserQuestion` 执行菜单、用户顺手点选"这类 scope 升级。**按设计不修**，原因：
> 1. **机制接不住**——focus 是 `UserPromptSubmit` hook、只吃 stdin 的 `prompt`；而决定性那一跳是用户**点击选项**而非打字，关键回合 hook 拿不到可判的 prompt。
> 2. **锚判不准**——真实锚"现在仓库可以公开了吗"里"公开"本身是动作动词，纯字符串 `anchor_kind` gate 会误判。
> 3. **重武装重蹈覆辙**——v0.28.2 刚把 focus 文案中性化（旧"审问+催办"语气诱导把正当新任务误判为漂移→答非所问）；再加"评估→执行"检测 = 旧病复发 + 高频误报。
>
> **改由三层兜底**：① 病根（答完不收口 / 思考空转）由用户级 `effort=medium` baseline 压（见 `CHANGELOG [0.31.0]`）；② 真正的门由 `templates/CLAUDE.md §9.5`「评估问答完即停、禁止主动开执行菜单」红线收（v0.32.0 已落）；③ `/focus` 被动入口供用户手动核锚。代价：这层防护靠纪律 / 被动触发而非 hook 自动拦截，是经多 agent 辩论权衡后的取舍（产品层 hook 加固性价比为负）。

---

## 8. 模板素材的来源

模板出自 [StratusAgent](https://github.com/freakybridge/StratusAgent) 项目长期沉淀。这个项目是一个量化交易终端，多 Gateway / 双语言（Rust + Python）/ UI 强交互，在以下方面踩了足够多的坑形成稳定经验：

- 鬼打墙红线（来自 2026-04-14 CTP vtable mismatch / 2026-04-27 BTC-PERP pnl 4 连撞墙事故）
- UI 主动问范式（来自反复出现的"用户截图 + 描述前 N 步" 信息缺口）
- 可移植性约束（来自换机时反复踩的 pip 绝对路径 / vnpy_ctp 包内 DLL 版本不一致）
- 文档分层（来自从单一 TODO 文件混乱演进到三层归档）

剥离项目特定内容后留下的就是这套模板。

---

## 9. bridgeforge 的双重身份：工厂 + 自产自用

这是理解整个 repo 的总钥匙。bridgeforge **同时是两个东西**：

1. **手册工厂**：`templates/` + `skills/` 是会被复印进每个未来项目的"产品"。改进产品 → 所有下游同步收益（这是它存在的意义）。
2. **自己的样板间**：bridgeforge 这个 repo 自己也按自己的手册活（自产自用，dogfood）——它自己的 `.claude/hooks/version_check.py` 就是从 `templates/` 抄来的、逐字一致的副本。

**为什么两个身份都重要**：

| 身份 | 要保证的 | 失败长什么样 |
|------|---------|------------|
| 工厂 | 通用改进必须落到 `templates/`/`skills/`，下游 sync 时拿得到 | 改动只写进自身配置 / 元文档，下游永远拿不到 |
| 样板间 | 自己必须按宣传的那套活，否则示范是假的 | repo 自己违反自己定的红线，别人来参观不信服 |

### 9.1 前门闸：传播四问

工厂最常见的事故是**"把通用改进只写进了自身配置层或元文档，忘了镜像进产品层"** → 下游永远拿不到。**对称的事故**是 hook 类改进只发给下游（`templates/`），bridgeforge 自己却没装——样板间不住人，示范成假的。

两条 playbook（reverse-sync / sync-from-upstream）能在季度盘点时补救这类漂移，但它们靠人脑判断、手动触发，是**事后**机制。所以在 `CLAUDE.md §1` 立一道**前门闸**——每个改动进门时强制过「传播四问」：(1) 属于哪一层？(2) 通用的话镜像进 `templates/` 了吗？(3) 要不要 bump 版本 + 记 CHANGELOG？(4) 产品层 hook/settings 改动，当场镜像进自身 `.claude/` 吃狗粮了吗？

判断"哪些该进 `templates/`"沿用 §6「模板 vs 占位」：不依赖具体业务领域 → 进产品层；依赖 → 留给项目自己 / 占位。

### 9.2 CHANGELOG 层标签：让下游同步有抓手

光"传播出去"还不够——下游得知道**这次该拉什么**。否则它要么从头 diff 整个 `templates/`，要么干脆不升级。

所以 CHANGELOG 每条 entry 打层标签 `[product]` / `[repo]` / `[meta]`（语义见 `CLAUDE.md §3`）。下游跑 sync-from-upstream 时 `grep "\[product\]"` 即得增量清单。这是"内容传播"成本最低、最可执行的一招。

### 9.3 演进节奏：软规则先跑顺，再升级为机制

本项目的一贯做法（version_check 就是范本：先在 workflow.md §9 写软规则 → 反复被忘 → 升级成 PreToolUse hook 机制强制）：

- **现在（软）**：`CLAUDE.md §1` 四问 + §3 标签约定 + 本节 framing，靠自觉过一遍。
- **跑顺 2-3 次后（硬）**：加「镜像漂移检查 hook」——commit 时自动比对 `.claude/hooks/*.py` 与 `templates/hooks/*.py`，只改一边就告警/阻断。等四问判断稳定、误报场景摸清再上，避免一开始就把判断错误自动化（理由同 reverse-sync-playbook §6「什么时候考虑工具化」）。

### 9.4 工厂自身不带版本戳——靠 `templates/` 存在性识别

bridgeforge 源头仓库**故意不放** `.claude/.bridgeforge_version`。理由：

- 版本戳的语义是"我这个下游上次同步到上游哪一版"——源头仓库**没有上游**，戳对它无意义。
- 若给源头也放个戳，`/bridgeforge` 在它自己身上跑会落进"有戳 → 更新模式"，试图"从上游拉增量到自己"，逻辑自指、实际空转。
- 更糟：早期无戳时，源头会落进"无戳 + 有 CLAUDE.md → 可能 fresh-init"分支，等于**装修队把自己样板间推了重装**（v0.14.0 留下的潜在自伤，2026-05-29 实测在源头自身可复现）。

**正解**（v0.15.0）：`/bridgeforge` 前置第一闸用"`templates/CLAUDE.md` 存在 + 根 `SKILL.md` 是自己"判定"我在源头里"，命中即硬拒。这比"靠戳的有无"更本质——源头的身份由它**含有产品层** `templates/` 决定，不是由一个可丢失的标记文件决定。

> **推论（可复用判别原则）**：识别"是不是某类项目"优先用**结构性事实**（有没有 `templates/`），而非**约定标记**（有没有某个戳文件）。标记会漂移、会忘写、会被 clone 丢掉；结构性事实跟着内容走。同理，v0.15.0 的「收编模式」用"内容指纹"（鬼打墙红线 / OPTIONAL 标记等结构性签名）而非"有没有戳"来判断一个无戳项目是不是 bridgeforge 铺过的。
