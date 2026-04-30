# 设计原则

> 解释为什么 setup_agent 这样分层。读这个能让你判断"什么该写进哪里"。

---

## 1. 双层 CLAUDE.md：全局 vs 项目

| 层 | 路径 | 内容 |
|----|------|------|
| 全局 | `~/.claude/CLAUDE.md` | **跨项目稳定的我**：沟通语言、安全确认协议、环境隔离习惯、执行节奏（"先列计划再动手" 等） |
| 项目 | `<repo>/CLAUDE.md` | **项目特定的事**：架构红线、rules 索引、快速命令、项目结构、跨机 checklist |

**判断标准**：换一个项目还成立的内容 → 全局；只对这个项目成立 → 项目。

setup_agent **不动全局**——全局是个人偏好，应一次性配好；setup_agent 只铺项目这一层。

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

## 4. doc/ 三层归档

```
doc/
├── 0_architecture/  ← 架构红线（PRD / 约束 / Roadmap）
├── 1_plan/          ← 活跃推进（按 topic 子目录）
├── 2_pending/       ← 未决问题 / 辩论
├── 3_design/        ← 模块实现设计
├── 4_archive/       ← 已完成归档
└── 9_reference/     ← 外部参考资料
```

**为什么是三层（plan / pending / archive）而不是单一 todo**：

- `1_plan/`：知道要做、正在做或下个 sprint 做的事
- `2_pending/`：知道要做但暂时不做（缺时间 / 缺信息 / 等其他事先发生）
- `4_archive/`：已经做完的，留作历史参考

差别在于"行动状态"——pending 是**冷冻待解冻**，plan 是**进行中**，archive 是**已落幕**。

文档随时间在三个目录间流动：`pending → plan → archive`。`/archive-scan` skill 周期性扫 plan / pending 看哪些可以归档。

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

setup_agent 的模板分两类：

**深模板（直接搬全文）**：
- 鬼打墙红线 / UI 主动问范式 / 修 bug 前确认根因 / 性能先量化 / 经验总结流程
- 这些是"任何项目都该有"的通用工作流，搬就完了

**骨架（占位让用户填）**：
- 架构红线 / 数据流方向 / 项目结构 / 快速命令
- 这些是项目特定的，AI 不该替用户瞎编

**判断标准**：内容是否依赖具体业务领域？依赖 → 骨架；不依赖 → 深模板。

---

## 7. 不做什么

setup_agent 故意**不做**这些事，留给项目自己决定：

| 不做 | 原因 |
|------|------|
| 不动 `~/.claude/CLAUDE.md` | 全局规范是个人偏好，不该被 skill 覆盖 |
| 不预装具体 skill（plan / debate / escalate 等） | 那些 skill 应该独立维护，setup_agent 只在 CLAUDE.md §4 给个 TODO 让用户自己决定要装哪些 |
| 不自动 git commit | 让用户先填占位再 commit，避免污染历史 |
| 不替用户编架构红线 | 架构是用户自己想清楚的，AI 编的内容反而误导 |
| 不强制目录结构 | 只给"推荐范式"，用户可以删掉用不上的目录 |

---

## 8. 模板素材的来源

模板出自 [StratusAgent](https://github.com/freakybridge/StratusAgent) 项目长期沉淀。这个项目是一个量化交易终端，多 Gateway / 双语言（Rust + Python）/ UI 强交互，在以下方面踩了足够多的坑形成稳定经验：

- 鬼打墙红线（来自 2026-04-14 CTP vtable mismatch / 2026-04-27 BTC-PERP pnl 4 连撞墙事故）
- UI 主动问范式（来自反复出现的"用户截图 + 描述前 N 步" 信息缺口）
- 可移植性约束（来自换机时反复踩的 pip 绝对路径 / vnpy_ctp 包内 DLL 版本不一致）
- 文档分层（来自从单一 TODO 文件混乱演进到三层归档）

剥离项目特定内容后留下的就是这套模板。
