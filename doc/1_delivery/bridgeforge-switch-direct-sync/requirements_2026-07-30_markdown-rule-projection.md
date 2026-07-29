# BridgeForge Switch 的 Markdown Rule 投影增强建议

> 状态：部分采纳：仅实现 portable Rule 迁移候选发现 / 报告；自动投影、v2–v4 与 root map 已拒绝  
> 候选目标：`templates/codex/scripts/bridgeforge_switch.py` 及对应宿主模板  
> 来源：下游双宿主 Rule 无损切换实践，已脱敏

## 1. 结论

建议 BridgeForge 将 Markdown Rule 纳入 switch 的内置、受限 adapter，并吸收
frontmatter `paths` 转译、生成物 hash、人工修改保护和 roundtrip 抑制能力。

禁止整文件覆盖 canonical `bridgeforge_switch.py`。下游增强版增加了约五百行投影、
map 和迁移逻辑，其中 v2-v4 属于有损或结构迁移能力，必须先固化协议、权威关系和
fixture，再进入产品实现。

本提案不改变 switch 的核心边界：

- source 始终保持不变；
- target 只接收当前宿主可安全表达的原生 projection；
- target 被人工修改时保留并报告冲突；
- adapter 必须内置 allowlist，禁止执行 map 中的命令或动态 patch；
- gaps 可以降级 readiness，但不能伪称语义等价。

## 2. 传播四问

1. **属于哪一层**：本文件是元文档需求；采纳后的实现属于
   `templates/*/scripts/bridgeforge_switch.py` 产品层。
2. **是否应进入模板**：Markdown Rule 与双宿主 `paths` 语义属于跨项目通用能力，
   应进入模板；任何下游 rule 名称和业务约束不得进入。
3. **是否需要版本与 CHANGELOG**：本报告不 bump；产品实现落地时必须 bump，
   并记录 `[product]` CHANGELOG。
4. **是否需要 dogfood**：本报告不改脚本；实现落地时必须同步 BridgeForge 自身
   `.codex` / `.claude` dogfood 副本，并运行双向 fixture。

## 3. Canonical 能力与当前缺口

canonical direct-sync 已具备：

- 双宿主 map；
- 稳定 `asset_id`；
- source / target members；
- generated hash 与人工修改检测；
- `forked_projection`、`conflict`、`untranslated`；
- allowlist adapter；
- TOCTOU 重检；
- 可捕获异常回滚。

当前缺口是：Markdown Rule 仍缺少正式 adapter 和跨宿主投影契约。普通
whole-file 复制不能安全处理：

- Claude / Codex 不同的 rule 路径；
- frontmatter `paths:` 语义；
- shared 与 host-specific 段落；
- target 端已有人工补充；
- 有损 projection 的回环与 provenance。

## 4. 下游增强能力概况

下游实践新增：

- `markdown-rule` adapter；
- UTF-8 / BOM 与受限 Markdown 校验；
- Claude / Codex 宿主标记转译；
- v1 同名 Rule 投影；
- v2 分段投影；
- frontmatter `paths:` 重写；
- v3 显式正文 replacement；
- v4 memory 分类路径映射；
- project-root map 与宿主 map 的联合读取；
- projection hash、takeover hash、forked 状态和 map 漂移检查。

这些能力证明了产品需求，但不代表其全部实现都应原样进入上游。

## 5. 建议直接吸收

### 5.1 Markdown Rule 内置 Adapter

把 `markdown-rule` 注册为 switch 内置 allowlist adapter。Map 只能引用已注册版本，
禁止携带任意命令、Python 表达式、patch 或脚本路径。

最低支持：

- UTF-8 Markdown 文件；
- 受限 YAML frontmatter；
- 同名 Rule 的宿主路径映射；
- 确定性生成 bytes；
- source / target hash；
- target 人工修改保护；
- gaps / conflict 收据。

### 5.2 v1 同名 Rule 投影

v1 只处理能够确定一一对应的 Rule：

```text
source rule -> target host 原生 rule 路径
```

要求：

- source 不变；
- target 不存在时可生成；
- target 与既有 generated hash 一致时可更新；
- target 人工修改时标记 `forked_projection` 或 `conflict`；
- target 无可靠 ownership 时禁止覆盖或删除。

### 5.3 Frontmatter `paths` 转译框架

Rule 的正文约束与加载范围必须分开处理。Adapter 应把 source `paths` 解析成受限结构，
再由目标宿主 renderer 生成原生 frontmatter。

禁止只做全局字符串替换。

最低协议：

- 缺少 `paths` 时如何处理；
- 单路径与多路径；
- 空列表；
- 重复路径；
- 不支持的 YAML 结构；
- 注释、BOM、CRLF/LF；
- 路径逃逸、绝对路径和宿主外目录；
- renderer 输出排序和换行必须确定。

### 5.4 Provenance 与人工修改保护

Markdown projection 必须复用 canonical 已有状态：

- `generated`
- `takeover`
- `created_unowned`
- `untranslated`
- `stale`
- `forked_projection`
- `conflict`
- `echo_suppressed`

状态名称和 hash 语义应由 direct-sync 协议统一维护，禁止 Markdown adapter 创建第二套
相似但不等价的 ownership 状态机。

## 6. 需设计后吸收

### 6.1 v2 分段投影

分段投影允许只同步 shared 段、保留 host-specific 段，但它是有损转换。

必须先定义：

- segment 标记语法；
- segment ID 稳定性；
- 嵌套、重复、未闭合和未知 segment 的处理；
- segment 外正文归属；
- 哪一侧是 source of truth；
- target 人工修改如何识别；
- source 删除 segment 时是否允许删除 target；
- roundtrip 是否只抑制回声，还是允许反向编辑。

任何解析歧义必须 fail-closed 为 gap，禁止猜测段落边界。

### 6.2 v3 显式 Replacement

Replacement 只能是 map schema 中的确定性数据，不能演变成动态 patch。

必须定义：

- source 与 target 字符串；
- replacement 顺序；
- 重叠规则；
- 重复 source；
- source 未命中；
- target 中再次包含 source；
- replacement 版本升级；
- roundtrip 的可逆性或明确不可逆标记。

建议默认禁止重叠 replacement，并对未命中输出 `stale`，不要静默成功。

### 6.3 v4 Memory 分类路径映射

把扁平 memory 映射到 `architecture`、`engineering`、`domain`、`operations` 或
`topics/<topic>`，会接触 memory category 契约。

Switch 只能生成 target projection，禁止借此移动、删除或重分类 source。涉及已有
target memory 的路径迁移时，必须与 BridgeForge memory update 的明确确认边界分开：

- category / topic metadata 必须合法；
- target 目录按实际写入创建，禁止预建空目录；
- 同路径异内容必须冲突；
- completed topic 保留原 topic 路径；
- 禁止创建 `memory/_archive/`；
- 禁止把 switch 变成隐式 memory migration。

### 6.4 Project-Root Map

下游实现增加了 project-root map，用于宿主 map 缺失时保留语义 ledger。该能力不能
直接吸收，因为 canonical 当前以目标骨架内 map 为权威。

上游必须先裁定：

- project map 与 `.codex/.bridgeforge-map.json`、`.claude/.bridgeforge-map.json`
  的权威关系；
- 哪个 map 可创建、更新和删除；
- 三者 schema 与生命周期；
- Git 是否跟踪 project map；
- map 不一致时的 fail-closed 条件；
- 一侧宿主缺失时是否仍允许读取 project map；
- root map 是否违反“目标 map 位于目标骨架内”的现有公开契约。

在协议明确前，建议不吸收 root project map，只复用现有双宿主 map。

## 7. 明确禁止吸收

- Map 中的动态命令、可执行脚本、任意 patch 或表达式。
- 把 topic rule 作为默认产品能力；当前没有正式 `rules/topics/` 契约。
- 任何下游业务 Rule 名称、路径、正文和专属 replacement。
- 未验证的复杂 YAML 全量解析承诺。
- source 侧移动、删除、重分类或改写。
- target 被人工修改后强制覆盖。
- 把 degraded readiness 写成 fully equivalent。
- 用 switch 代替 BridgeForge update 的 memory 迁移确认流程。

## 8. 权威与 Roundtrip 契约

### 8.1 单向生成

每次 switch 的 source 是另一宿主当前 live 资产，target 是当前宿主。一次运行只允许
单向生成，不建立实时双向同步。

### 8.2 回声抑制

当 source 内容能够证明是上一跳 target 的 clean generated projection 时，可以标记
`echo_suppressed`，禁止把有损结果反向灌回 canonical source。

证据至少包括：

- stable asset ID；
- adapter 与 schema version；
- source / target members；
- generated hash；
- 上一跳 provenance；
- 当前 live hash 未漂移。

缺少任一关键证据时不得按内容相似度猜测回声。

### 8.3 Forked Projection

target 与 map 中 generated hash 不一致时：

- 保留 target；
- 不覆盖、不删除；
- 报告 `forked_projection`；
- 其他无歧义资产继续同步；
- readiness 降级。

### 8.4 Map 漂移

Map 缺失、损坏、schema 不兼容、member 越界或 live/hash 不一致时，必须保守冲突。
禁止自动重建 ownership。

## 9. 事务与回滚

Markdown 输出和任何新增 map 必须纳入 canonical 现有事务：

1. 建立完整 plan；
2. 重检 source、target 和 map；
3. 验证全部目标路径；
4. 写入临时文件；
5. 原子替换 target；
6. 最后替换 map；
7. 任一可捕获异常精确回滚本次 owned 改动。

必须覆盖：

- 首次创建失败；
- 覆盖后失败；
- 删除后失败；
- target 写完但 map 未写；
- map 写完后的验证失败；
- rollback incomplete；
- 本事务创建的空父目录清理；
- 既存空目录保持不动。

强制终止、断电和系统崩溃仍按 canonical 契约处理：下次运行将 map/live 不一致报告为
保守冲突，不承诺跨文件原子恢复。

## 10. Fixture 测试矩阵

| 类别 | 必测场景 |
|---|---|
| v1 | 同名 Rule、source 缺失、target 缺失、clean update |
| Frontmatter | 无 `paths`、单路径、多路径、空 paths、重复 paths |
| YAML 边界 | 注释、复杂结构、BOM、CRLF/LF、非法 UTF-8 |
| v2 | shared/host-specific、segment 缺失、嵌套、未闭合、未知 ID |
| v3 | 命中、未命中、重复 source、重叠 replacement、目标含 source |
| v4 | 四类 category、topic、metadata 缺失、目标已存在、内容冲突 |
| Roundtrip | Codex -> Claude -> Codex 三跳无回声 |
| Fork | target 人工修改后保持不变并降级 |
| 双改 | source 与 target 同时修改时冲突 |
| Map | 缺失、损坏、schema 不兼容、member 越界、hash 漂移 |
| 多 map | project map 与宿主 map 一致、不一致、仅一侧存在 |
| Provenance | generated、takeover、created_unowned、untranslated、stale |
| 回滚 | target/map 各 fault point、rollback incomplete |
| Windows | 大小写碰撞、设备名、ADS、junction、symlink、路径逃逸 |
| 跨宿主 | Claude -> Codex、Codex -> Claude |
| Readiness | clean 为 ready；任一 gap 为 degraded |

Fixture 必须断言：

- source hash 前后不变；
- target bytes；
- map 的 canonical JSON；
- status / readiness / gaps / conflicts；
- 未复制宿主专属 hooks、settings、agents 或 skills；
- 旧根 `.bridgeforge/` 未被读取、写入或删除。

## 11. 建议实施阶段

### 阶段 A：协议与 v1

- 固化 `markdown-rule` adapter schema。
- 实现 v1 同名 Rule 投影。
- 实现受限 `paths` parser/renderer。
- 复用现有双宿主 map、hash、冲突和回滚。

### 阶段 B：分段与 Roundtrip

- 固化 v2 segment 协议。
- 实现 echo suppression 与 forked projection fixture。
- 验证三跳无回声。

### 阶段 C：Replacement

- 固化 v3 replacement 顺序和重叠规则。
- 所有不确定情况降级为 gap。

### 阶段 D：Memory 路径

- 与 memory category 契约联合设计 v4。
- 明确 switch projection 与 update migration 的边界。

### 阶段 E：Project Map 决策

- 先 debate 权威关系和公开命令契约。
- 未裁定前不引入 root project map。

## 12. 推荐裁定

将该候选判为“通用增量，分阶段吸收”：

- 立即进入设计：Markdown adapter、v1、`paths` renderer、provenance。
- 完成协议后吸收：v2/v3/v4。
- 暂不吸收：root project map。
- 永不吸收：动态 patch、source 改写、topic rule 默认能力。

这样能把下游双宿主 Rule 实践转化为稳定产品能力，同时保持 canonical direct-sync
已有的安全边界与低活动部件原则。
