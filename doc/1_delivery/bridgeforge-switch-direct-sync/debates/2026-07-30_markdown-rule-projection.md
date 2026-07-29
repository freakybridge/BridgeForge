# Markdown Rule 投影 Debate

> 确认卡：`requirements_2026-07-30_markdown-rule-projection-debate.md`
> 状态：研究中

## 目标与边界

评审 v1–v4 Markdown Rule 投影与 project-root map 是否应进入 BridgeForge 产品层；本轮不编码。
source 保持不变，目标人工修改必须保留，任何解析歧义不得伪称语义等价。

## 参与者

- 研究：`/root/markdown_projection_research`（`light-explorer`）
- 方案方：`/root/markdown_projection_design`（`implementation-worker`）
- 审查方：`/root/markdown_projection_audit`（`review-auditor`）

## 证据

- 现有 adapter allowlist 仅 `whole-file`、`json-pointer`、`none`；其中 whole-file
  仅限 portable memory Markdown，不能承载 Rule。
- source / target 各自的宿主 map 是现有权威；legacy root `.bridgeforge/` 只提示，
  不读取、不写入、不删除。
- 现有 map hash、fork/conflict、预状态重检、写后验证与精确回滚可被 v1 复用。

## 轮次记录

### 第 1 轮

- 方案方：主张以新的 `markdown-rule` adapter 分阶段实现 v1–v4，拒绝 root map；v1
  以受限 frontmatter、同名 Rule、现有 map/hash/回滚为边界。
- 审查方：指出 target Rule 新建后会触发 Rule 索引硬闸；switch 当前不拥有入口索引。
  同名 Rule 亦不证明正文宿主等价。root map 是第三份事实源；v2 是 partial ownership，
  v3 会把 map 变成 patch DSL，v4 是不应混入 switch 的 memory migration。

### 第 2 轮

- 方案方接受索引闸问题：若自动 v1，Rule 文件与入口表行必须成为原子 asset，并仅允许
  显式 portable 的非模板 Rule；v2/v3/v4/root map 均建议拒绝。
- 审查方复核后否决该修正：当前 selector 仅支持 JSON Pointer；入口 Markdown 行的局部
  ownership 需要新的 selector、局部 hash、插入/删除/转义与回滚协议，实质上已是 v2。
  整个入口文件 ownership 同样不可接受。

## 收敛结论

- **采纳**：Rule 迁移候选的只读发现 / 报告能力；不得写 target Rule 或入口。
- **拒绝**：当前自动 v1 投影、v2 分段、v3 replacement、v4 memory 路由、project-root map。
- **前置条件**：若未来重开自动投影，必须先独立证明一个由机器完整拥有、且两宿主真实加载的
  Rule 索引面；禁止在人工维护的 `AGENTS.md` / `CLAUDE.md` 表格中做行级 patch。
- **最低验收**：候选、collision、fork、map 缺失/损坏/漂移与 echo 仅报告；两侧入口和
  Rule 文件在运行前后字节完全不变。
