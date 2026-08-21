# 设计原则

> 本文只描述 bridgeforge-codex 1.4.31+ 的现行设计。历史迁移、Claude 双骨架、
> switch、junction 与版本谱系不属于当前运行时契约。

## 1. 产品边界

bridgeforge-codex 只维护 Codex 协作骨架：

- `templates/` 是下游公共骨架的唯一来源；
- `skills/` 是用户级通用 Skill 的唯一来源；
- `scripts/` 只放工厂发布、同步和校验工具；
- `.codex/` 是工厂自身的 dogfood 投影，不是第二份产品源。

工厂专属检查不得下沉到普通项目。下游也不得反向把业务约束吸收到 Template。

## 2. 指令分层

- 根 `AGENTS.md` 承载全项目常驻红线；
- 嵌套 `AGENTS.md` 承载目录专属红线；
- hook 与 pre-commit 承载可机器判断的约束；
- Skill 承载用户主动调用的流程；
- `doc/` 承载原理、方案、案例和长 SOP。

Markdown `paths:` 不是 Codex 的自动指令路由机制。项目不得建立第二套隐式规则索引。

## 3. 公共资产与项目资产

同一个文件可以同时包含公共区和项目区，但 ownership 必须可解析：

- `AGENTS.md`：公共区由 Template 管理，项目专区逐字保留；
- `.githooks/pre-commit`：受管区由 Template 管理，项目扩展区逐字保留；
- `.codex/hooks.json`：BridgeForge handler 与项目 handler 分开校验；
- 项目 Rule：`.codex/rules/**` 中不属于公共合同的文件逐项进入 `PreservationManifest`；
  新增项目 Rule 推荐集中放在 `.codex/rules/project/**`，但同步器不靠目录名猜 ownership；
- 项目 Hook：每个 Hook 独占 `.codex/hooks/project_XXXX/`，入口为 `entrypoint.py`，
  私有代码、配置和数据都放在同一目录内；
- 项目 Memory 与 Skill：整棵项目资产保留，但必须通过当前版本兼容性检查。

版本分类比较 ownership projection，而不是只看文件路径。项目区发生变化就属于业务变化；
公共区发生变化才属于骨架变化。

## 4. 两条更新路径

### 4.1 旧项目重装

恰好一个合法版本戳且版本 `<1.4.31` 时进入破坏性重装，戳文件名不参与路由。Planner 先只读盘点项目资产，生成临时
`PreservationManifest`；所有需要用户决策的项目必须明确选择 preserve 或 delete，未选择
不得默认为删除。

重装不解析旧 `.codex/managed-skeleton.json` 恢复 ownership。未知 `.codex/**` 结构、散落 Hook
或非 canonical 注册必须阻断；独立 Agent 只能先在临时副本或受控前置步骤中把 Hook 整理为
`.codex/hooks/project_XXXX/entrypoint.py` 自包含目录，再重新规划并逐项确认。

清单只服务本次升级：Apply 重新核对指纹、安装当前骨架、回灌确认资产、完成全部校验并
写入最终版本戳后，清单即失效，不作为长期迁移状态保存。

### 4.2 当前版本更新

`1.4.31+` 项目只接受 current-only 合同。公共资产漂移、合同损坏或身份不一致
必须在写盘前阻断。

合法旧文件名与当前文件名使用同一版本规则；`1.4.31+` 的旧文件名通过 prospective version
校验后，在同一事务内删除并最终只写当前戳。双戳、非法戳和高于当前产品的版本仍然阻断。

若新合同移除了资产，同步器只允许删除满足以下全部条件的旧资产：旧合同确实拥有、策略为
`whole`、路径安全、目标内容仍精确匹配旧合同。部分 ownership、项目改动或无法证明的目标
一律阻断，不靠历史 retirement 表猜测。

## 5. 事务与失败边界

- Planner、`--check` 与 pre-commit 必须零写；
- Apply 在任何写入前重算输入指纹；
- 自动写入、删除、派生索引和 Git index 都纳入同一事务；
- 可捕获失败恢复本轮写入，并保留用户原有 staged/unstaged 边界；
- 版本戳最后写；失败不得留下“已升级”假象；
- hook、JSON、路径和合同解析均 fail-closed，禁止用宽松 fallback 吸收损坏状态。

pre-commit 只验证当前工作树和 index。需要重建 Memory 索引、manifest 或版本文件时，用户
先运行 repo-local `$git-sync`，由单一写事务生成并暂存，pre-commit 不在 `git commit` 内暗写。

## 6. 工厂与 dogfood

工厂身份由严格校验的根 `bridgeforge-codex-manifest.json` 主张，并要求 Template 合同、
入口 Skill 与项目同步器三项 factory witness 同时存在。单独复制任一 witness 或提供畸形
manifest 都只能得到身份不一致，不能绕过普通下游必须具备的当前版本戳。

Template 与 `.codex/` 的公共运行时必须保持当前投影一致。校验通过合同和当前文件直接比较，
不保留逐版本 hash 谱系，也不向下游复制工厂专属检查器。

## 7. 文档与项目知识

项目文档固定使用 `0_architecture / 1_delivery / 2_bugs / 3_reference / 4_archive` 五层结构，
`doc/README.md` 是唯一索引。活跃架构文档只描述当前行为；历史决策留在交付记录、Bug、
archive 与 Git 历史中。

项目 Memory 保存在 `.codex/memory/` 并纳入 Git，与 Codex 原生用户级 memories 分离；禁止
junction。项目 Skill 保存在 `.codex/skills/<name>/SKILL.md`，必须满足当前 metadata、结构、
引用和体积规则。

## 8. 有意不做

- 不自动迁移 Claude、旧 ledger、旧用户目录或任意未知项目结构；
- 不维护每个历史版本的 adapter、hash 表或 retirement 表；
- 不执行目标项目自带的旧校验脚本来证明兼容性；
- 不解析任意 shell 命令猜测项目 Hook 的动态依赖；
- 不自动 Git commit 或 push；
- 不用工厂扫描器监管全部下游项目。

这些边界减少活动部件和派生状态：无法由当前合同与明确 ownership 证明的情况，停下来让用户
处理，比继续堆兼容分支更安全、更容易删除。
