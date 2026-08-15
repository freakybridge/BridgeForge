---
status: bridgeforge-resolved-real-copy-verified-runtime-pending
severity: critical
scope: bridgeforge project sync managed Markdown absorption
reported_at: 2026-08-16
downstream: D:\Quant\StratusAgent
---

# BUG：A 激进吸收会覆盖下游 Rule 语义并生成损坏 Markdown

## 结论

BridgeForge `0.94.2` 的 Codex 项目同步器在真实下游执行 A 激进吸收后，确实删除了
项目专属 Rule 红线，并生成重复标题和未闭合代码围栏。canonical memory/config
validator、`rule_index_check.py`、`rule_size_check.py` 与 `git diff --check` 均返回成功，
没有阻止该语义损失或结构损坏。

这是 `managed_blocks.headings` ownership、缺失标题追加策略和 Markdown 标题解析共同造成的
产品级缺陷。不能归因为用户选择 A：A 只授权上游赢得可信受管区块，不应把项目填充区
错误登记为上游正文，也不应生成语法损坏的 Markdown。

## 影响

- 下游核心架构职责边界可被通用模板 `TODO` 覆盖，Agent 随后失去真实项目红线。
- 同义但不同名的项目章节不会被识别为现有内容；同步器会在文件末尾追加第二套通用章节。
- fenced code block 内的示例标题可被误识别为真实 Markdown 标题，截断受管区块并留下
  未闭合代码围栏。
- 反漂移 Rule 可丢失项目增强的响应红线、漂移分类和双宿主说明。
- 模板仍把 Codex hook 注册位置写成 `.codex/settings.json`，与当前
  `.codex/hooks.json` 单一注册源冲突。
- 现有验证全部成功，用户会收到“事务完成”的误导性收据；仅因其他 gap 存在，真实现场
  恰好保留了旧版本戳 `0.90.0`。

## 真实下游复现

### 环境

- BridgeForge source commit：`f16792cb5ab72608daa81f9efeba5c95cf37f209`
- BridgeForge 产品版本：`0.94.2`
- 下游：`D:\Quant\StratusAgent`
- 下游 HEAD：`33d2f1faee465202877e1865206d6ca12ad349cb`
- 下游骨架版本戳：`0.90.0`
- Python：`D:\Quant\StratusAgent\.venv\Scripts\python.exe`，3.12.9
- 模式：`update`
- 用户选择：`A`
- aggregate fingerprint：
  `sha256:87d41fecfdefde879cba4f500ab514f0888571d346a6f557554fbeaff6409be3`

### 命令

```powershell
.venv\Scripts\python.exe -B `
  C:\Users\bridg\.codex\skills\bridgeforge\scripts\bridgeforge_project_sync.py `
  --project-root . `
  --template-root C:\Users\bridg\.codex\skills\bridgeforge `
  --mode update `
  --apply `
  --plan-fingerprint sha256:87d41fecfdefde879cba4f500ab514f0888571d346a6f557554fbeaff6409be3 `
  --confirmed-risk
```

普通权限首次因 Windows 拒绝替换 `.codex/managed-skeleton.json` 失败；使用提升权限原样重试后
exit `0`。两个失败事务临时目录最终均不存在。本报告讨论提升权限后成功落盘的吸收结果，
不是该权限故障。

## 已确认的内容损失

### 1. `architecture.md` 项目职责红线被模板 TODO 覆盖

`.codex/rules/architecture.md` 的 `## 1. 职责边界` 原有 7 组项目规则被删除：

- Gateway 只负责连接、认证、初始同步、协议转换和事件上行；禁止承载 OMS、风控或 UI 策略。
- event_loop / Trader 的协调、投影与原子发布边界。
- MktState 被动仓库与 OMS `OrderStore` 单一订单事实源。
- PlatformSnapshot 单写、原子发布及 UI 禁止长期复制业务 payload。
- egui UI 只经 Trader 请求、只读同帧 Snapshot，禁止持有 Gateway/RiskEngine/Store。
- RiskEngine 的事前拦截和风险状态职责。
- C++ / FFI 只封装 SDK ABI/转换，业务编排留在 Rust。

同步后上述内容被 `templates/codex/rules/architecture.md` 中“TODO：列出本项目各核心模块的
职责边界”的通用占位注释替换。这是项目业务语义丢失，不是等价更新。

同一文件原有标题为 `## 2. 单向数据流`、`## 3. 发单链路完整性`、
`## 4. 功能完整性`；contract 登记的是 `## 2. 数据流方向`、
`## 3. 关键链路完整性（红线）`、`## 4. 重写 / 移植期间的功能等价性（红线）`。
同步器没有识别语义对应关系，而是在文件末尾追加第二套 `§2/§3/§4/§5`，造成重复结构。

### 2. `anti_drift_hooks.md` 删除 55 行下游增强

被删除内容包括：

- `[clarify]` 的 5 条响应红线。
- `[focus]` 的 5 类漂移分类表和 5 条响应红线。
- Claude/Codex 双宿主适配说明。
- Claude 的上下文预算机制说明。
- shared/codex/claude ownership markers。

此外，两处 Codex 注册位置从 `.codex/hooks.json` 被改为 `.codex/settings.json`。
当前产品架构已声明 `.codex/hooks.json` 是唯一受管 Codex hook 注册源，因此模板正文与产品
实现互相矛盾。

### 3. `meta_rule_design.md` 产生重复标题和未闭合代码围栏

同步后文件同时存在旧、新两套 `§1/§3/§4/§6/§9`，标题顺序回退。文件末尾新增的
`## 3. Rule 的最小骨架` 只包含开头的 `````markdown``，没有对应闭合 fence。

上游模板的该受管章节本来包含完整示例，闭合 fence 位于后续行。当前
`_markdown_heading_sections()` 逐行匹配 `^(#{1,6})`，没有跟踪 fenced code 状态，因而把
代码示例里的 `## <红线标题>` 当成真实章节边界，截断了源区块。

### 4. 其他变化

- `anti_fabrication.md` 仅压缩残余风险说明，核心语义仍在。
- `AGENTS.md` 因 keyed table 表头漂移被保留为 gap，没有发生内容损失。
- 3 个 retirement 文件被删除：`model_policy_check.py` 与 `version_check.py` 已是 no-op；
  项目内 `bridgeforge_switch.py` 被退役，用户级 command bundle 仍有更新实现。该部分符合
  已展示的 R1-R3 授权，不是本报告的核心缺陷。

## 源码根因

### 根因 A：项目填充区被错误登记为 replace-block ownership

`templates/codex/managed-skeleton.json` 把 `architecture.md` 的 5 个标题全部登记在
`managed_blocks.headings`。但模板 `§1-§3` 明确是待下游填写的项目占位内容；下游填充后应
属于项目，而不是继续由上游整段所有。

这也与 `bridgeforge-keyed-index-merge` 确认卡中的已核实事实冲突：架构红线和项目结构速查
属于项目填充区，不应成为上游覆盖区。

### 根因 B：缺失标题在 A 模式下被无条件追加

`scripts/bridgeforge_project_sync.py::_replace_heading_items()` 在目标不存在登记标题时，把上游
区块加入 `appended`，最后由 `_append_managed_blocks()` 追加到文件末尾。该策略适用于明确
可加的独立通用区块，却不适用于已经存在同义项目章节的 Rule，更不应对项目填充区生效。

现有测试 `test_missing_blocks_append_cleanly_and_094_boundary_is_safe_repaired` 明确断言缺失
managed heading 应被追加，因此当前回归测试把本次危险行为当成正确行为。

### 根因 C：Markdown heading parser 不识别代码围栏

`_markdown_heading_sections()` 只按行匹配 ATX heading，没有忽略 ````` / `~~~` fenced code
内部内容。结果是模板示例中的标题参与章节切片，源区块可被截断。

### 根因 D：终态 validator 不检查 Markdown 结构与业务哨兵

真实现场以下检查全部 exit `0`：

- `bridgeforge_project_sync.py` 内 canonical memory validator
- strict config validator
- `.codex/hooks/rule_index_check.py`
- `.codex/hooks/rule_size_check.py`
- `git diff --check`

这些检查都没有验证 Markdown fence 配对、同级标题重复/乱序，也没有验证下游关键业务红线
是否仍存在。事务因此能以 `execution_status=completed` 返回。

## 修复要求

1. `architecture.md` 的项目填充标题必须退出普通 `managed_blocks.headings` 整段覆盖；采用
   project-owned/seed 语义，或新增只管理模板框架而不管理填充正文的显式 strategy。
2. 普通 replace-block 标题在目标缺失时必须 fail-closed 为 gap；只有 contract 明确声明
   additive 的区块才允许追加。不得用 A 授权扩大缺失标题的 ownership。
3. `_markdown_heading_sections()` 必须忽略 ````` 与 `~~~` fenced code 内的 ATX heading，
   并正确处理 fence 长度、缩进和语言标记。
4. apply 后必须检查本轮修改 Markdown 的 fence 配对、受管标题唯一性和结构顺序；失败纳入
   同一事务回滚。
5. `templates/codex/rules/anti_drift_hooks.md` 必须改为 `.codex/hooks.json` 单一注册源，
   并与模板 AGENTS、hook config 和项目事务架构一致。
6. 对下游在受管标题内新增的强化红线，不能仅因选择 A 就静默删除。若无法证明整段仍是
   BridgeForge ownership，应生成逐项冲突、保留为 gap，或使用可合并的稳定身份。
7. 修复不能依赖版本戳相等短路；`0.94.2` 已产生部分落盘、旧戳保留的真实下游状态，下一次
   update 必须能识别并恢复。

## 回归与验收场景

1. 下游把模板 `architecture.md §1` TODO 填成 Gateway/Trader/UI 等项目规则后，A 更新不得
   删除或替换这些规则。
2. 下游存在 `## 2. 单向数据流`，上游存在 `## 2. 数据流方向` 时，更新必须 gap 或按明确
   migration contract 处理；禁止在末尾追加第二套章节。
3. managed block 内含 fenced Markdown 示例及 `##` 示例标题时，提取结果必须包含完整 fence，
   apply 后 fence 数量配对。
4. 下游 `anti_drift_hooks.md` 有额外响应红线时，A 不得静默删除；收据必须准确说明保留、
   冲突或替换结果。
5. Codex anti-drift 文档、AGENTS 索引和实际 hook 注册都必须指向 `.codex/hooks.json`。
6. validator 对重复同级标题、未闭合 fence、项目业务哨兵删除分别失败，并验证事务完整回滚。
7. 使用 `D:\Quant\StratusAgent` 的故障前 HEAD 建立真实下游回归；正式修复后重新运行 A，
   对比四个 Rule 的项目专属字节和语义哨兵均保留。
8. 验证必须同时覆盖 fixture 与真实高定制下游；仅 memory/config/index/size exit `0` 不得标记
   本 Bug 为 Resolved。

## 当前下游恢复边界

StratusAgent 当前工作区尚未 commit/push，全部被删除内容仍可从 HEAD 恢复。BridgeForge
修复应先防止复发；真实下游的 Rule 恢复需在 StratusAgent 内另行执行并验证，禁止由上游
仓库直接跨项目修盘。

## BridgeForge 修复收据（0.94.3）

- 源码：`architecture.md` 使用 `seed`；普通 Rule heading 漂移/缺失保留为 gap；仅显式
  additive 标题可安全追加；fence-aware scanner、结构验证、事务回滚和 stamp-last 已落地。
- 旧伤提示：检测疑似 `0.94.2` 部分升级时，恢复清单必须包含
  `.codex/rules/architecture.md`，要求与可信升级前快照人工比较，禁止自动恢复。
- 产品传播：schema/manifest、模板 AGENTS/config/Rule、BridgeForge skill、四份发布脚本及
  架构文档已同步；hooks 注册源统一为 `.codex/hooks.json`。
- 自动化：相关 unittest `57/57`，完整 downstream fixture `39/39`；全部发布静态硬闸通过。
- 真实副本：`D:\Quant\CodexWorktree\test_bridgeforge` 从 HEAD `33d2f1fa...` / `0.90.0`
  执行 A。四个关键项目文件哈希前后不变，0 个 U 被吸收，旧戳保留，`git diff --check`
  通过；后续增量计划明确把 `architecture.md` 列入恢复清单。
- 独立审计：首轮阻断已修复，最终独立发布审计通过，未发现发布阻断。
- 未验证：真实 `D:\Quant\StratusAgent` 工作区未由 BridgeForge 上游修改；Desktop
  `/hooks` trust、新会话 lifecycle 与旧伤业务语义恢复仍待用户在真实项目验收。
