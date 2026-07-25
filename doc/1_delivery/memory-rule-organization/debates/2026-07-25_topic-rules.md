---
status: awaiting_decision
topic: memory-rule-organization
created: 2026-07-25
confirmation_card: ../requirements_2026-07-25_memory-rule-organization.md
question: "下游项目是否应支持 rules/topics/<topic>.md？"
pro_agent: /root/topic_rule_pro
con_agent: /root/topic_rule_con
---

# Debate：是否支持 topic rule

## 已确认边界

- memory 允许 `memory/topics/<topic>/` 保存长期 topic 摘要。
- 当前 rule 按触发面与 `paths:` 组织。
- 讨论仅决定是否引入 topic rule；用户确认前不实现任何模板或脚本改动。

## 待比较方案

1. **不支持 topic rule**：topic 专属约束留在 delivery/topic memory，长期跨 topic 红线才升级为 rule。
2. **支持 topic rule**：引入 `rules/topics/<topic>.md`，并由任务锚或确认卡识别后渐进加载。

## 证据与轮次

### 预研

- 当前 hook 与入口只支持扁平 `rules/*.md`：`rule_index_check.py` 使用
  `glob("*.md")`，AGENTS/CLAUDE 的索引也只接受一层路径。
- `rule_size_check.py` 对 staged 文件可覆盖嵌套路径，但 basename 白名单和报告会
  产生同名歧义。
- `focus_reminder.py` 的任务锚来自首条 prompt 的截断文本，session 切换或并发时
  会重置/last-write-wins，不能作为 canonical topic。
- `find-doc.map.md` 已有 `topic_to_rules` 映射入口，但映射缺失时不会全量扫描 rule。
- 确认卡、任务锚和 memory 检索当前互相独立，尚不存在统一 topic resolver。

### 第 1 轮

- 正方（`/root/topic_rule_pro`）：支持，但只允许稀疏、显式、双门控的
  `rules/topics/<topic>.md`。canonical topic 必须由确认卡 slug、目录 slug 与显式
  任务信息唯一收敛；仅当该 topic 唯一且当前目标命中 rule `paths:` 时加载。
  需新增统一 resolver、递归 rule index、exact slug 校验、冲突停止与生命周期审计。
- 反方（`/root/topic_rule_con`）：当前应禁止。嵌套 rule 会逃过索引/初始化/更新
  链路；delivery slug 不是稳定代码边界，无法可靠驱动加载；topic rule 会与 delivery
  和 topic memory 形成重复事实源。若某约束已跨 topic 稳定，应升级为现有扁平 path-rule；
  topic 到 rule 的关联应复用 `find-doc.map.md`，不复制 rule 正文。
- 争点：为支持 topic rule 新建 resolver、递归校验与生命周期治理，是否值得其带来的
  上下文精准性；以及双门控能否避免 topic 生命周期与代码路径之间的错配。

### 第 2 轮

- 正方：承认任务锚不能作为 topic SoT，也禁止从 slug 推导源码路径；将提案收窄为
  可选命名空间。只有既定 topic-memory resolver 已按确认卡/目录 exact+unique 规则
  可靠落地后，才允许探测 `rules/topics/<topic>.md`；必须同时命中该文件显式 `paths:`。
  默认仍是扁平 rule，不预建目录、不迁移既有 rule；无 topic、歧义或 path 未命中时
  fail-closed。前置还包括递归 index、slug/frontmatter 校验、Claude/Codex 对称测试和
  验收时显式生命周期审计。
- 反方：收窄方案技术可行，但仍没有不可替代的第三类内容。长期约束应是普通
  path-rule；topic 临时约束应随确认卡/topic memory 加载。二者交集只增加 active-topic
  状态、解析器、递归 index、冲突和 archive 生命周期成本，并且首次 edit 前无法从工具
  路径可靠获得命中上下文。没有真实用例证明现有两条路径都无法表达前，不应进入默认
  产品；最多保留“下游实验性 opt-in”窗口。

### 收敛

- **根因**：当前 rule 的语义与实现均以稳定代码路径为中心；delivery topic 是文档/
  生命周期维度，现有任务锚、确认卡、memory 与 rule index 没有统一且可在首次修改前生效
  的 resolver。直接添加嵌套目录会绕过 flat index/init/update 契约。
- **推荐**：当前版本不支持 `rules/topics/<topic>.md`。topic 专属约束保留在确认卡和
  `memory/topics/<topic>/`；只有跨 topic 仍稳定、能绑定稳定源码路径的必须/禁止红线，
  才晋升为扁平 `rules/<domain-or-module>.md`。需要按 topic 找到相关普通 rule 时，使用
  `find-doc.map.md` 的 `topic_to_rules` 映射，不复制正文。
- **保留的未来入口**：若先出现真实不可替代用例，可作为下游实验性 opt-in 重新确认；
  必须先证明既不能放确认卡/topic memory、也不能成为普通 path-rule，并一次性补齐
  exact resolver、递归 validator、双端加载时机、archive 行为和 focused harness。
- **等待用户裁决**：接受推荐、采用实验性 opt-in，或要求完整产品支持。
