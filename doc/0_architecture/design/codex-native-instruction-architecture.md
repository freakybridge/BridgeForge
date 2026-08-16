# Codex 原生指令架构与 Rule 退役映射

## 决策

Codex 指令只经 `AGENTS.md` / 嵌套 `AGENTS.md` 原生加载。`.codex/rules/*.rules` 是命令执行策略，Markdown frontmatter `paths:` 不是指令加载机制。BridgeForgeCodex 不实现自研加载器。

根 `AGENTS.md` 使用两个精确 marker 区域：BridgeForge 公共区由产品维护并按发布 hash 校验，项目级专区由下游完全所有并在更新中逐字保留。下游只能在项目专区、项目自有嵌套 `AGENTS.md` 与项目自有 hook 中增加约束；公共区修改会在编辑后提示、pre-commit 和同步计划中 fail-closed。旧无 marker 项目继续由 `section_layout` 做一次性迁移；无法可靠分类时保留原文件、旧 rule 与旧版本戳。

## 逐节语义映射

| 旧位置 | 新位置 | 处理理由 |
|---|---|---|
| `architecture.md` §1-§3 | `AGENTS.md` 项目专区“项目架构红线 / 项目目录地图” | 职责/依赖/数据流是项目事实；通用模板只要求项目填写，不泛化业务示例 |
| `architecture.md` §4 | `AGENTS.md` 公共区 | 重写等价性是常驻红线 |
| `architecture.md` §5、`modules.md` | `AGENTS.md` 项目专区；本文档 | 保留职责/依赖方向；Python 目录只作参考 |
| `anti_fabrication.md` R1-R5 | `AGENTS.md` §1.3；`antifabrication-framework.md` | 核验/禁编造/立即更正为证据红线；案例留文档 |
| `debugging.md` §1-§5 | `AGENTS.md` §1.3、§5.1-§5.2 | 根因、影响面、外部副作用必须常驻 |
| `debugging.md` §6-§11 | `AGENTS.md` §5.2；`$escalate` / `$debate` | 反循环和量化保留；调试 SOP 由 skill 执行 |
| `workflow.md` §1-§4 | `$develop` / `$summary` / `$sync-docs` / `$archive-scan` | 任务流程不常驻占用上下文 |
| `workflow.md` §5-§8 | `AGENTS.md` §2.3；`codex-project-operating-guide.md` | 文档红线常驻，目录/SOP 按需查阅 |
| `workflow.md` §9 | `AGENTS.md` §2.1；`codex-project-operating-guide.md`「版本域隔离」 | 业务 `VERSION` 与骨架 stamp 是独立生命周期，禁止互相代替 |
| `workflow.md` §10 | `codex-project-operating-guide.md`「大版本依赖升级 Spike」 | 体验驱动的大版本升级先在主项目外验证，用户确认有效后再升级 |
| `portability.md` §1-§4 | `AGENTS.md` §1.3；`codex-project-operating-guide.md` | 环境隔离/禁用户级暗写/可复现依赖常驻，安装细节按需 |
| `portability.md` §5 | hook / pre-commit | 编码、注册、dogfood 是机器可判契约 |
| `anti_drift_hooks.md` | `AGENTS.md` §4.4-§4.5；`codex-hook-signals.md` | 响应红线常驻，机制/调参进参考 |
| `meta_rule_design.md` | `AGENTS.md` §2.1；本文档 | 保留单一事实源/可机判交 hook/说明进 doc；删除伪 path 加载模型 |
| `bridgeforgecodex-product-change.md` | 根 `AGENTS.md` 项目专区“项目架构红线” | 工厂发布红线真正常驻，且不下沉普通项目 |

## 下游退役

历史 hash 精确匹配的官方 Markdown rule 可安全删除。已修改或 ownership 不明的文件必须原样保留为 gap，收据逐文件列出本表的人工迁移目标；有 gap 时禁止写新版本戳。
