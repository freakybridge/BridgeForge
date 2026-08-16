# 嵌套 Workspace 版本 SoT 发现增强建议

> 状态：原方案不采纳；由 `requirements_2026-07-30_downstream-version-sot.md` 取代，骨架版本固定为 BridgeForge 根 `VERSION`。  
> 候选目标：`templates/codex/hooks/version_check.py`  
> 来源：下游多 crate workspace 的版本检查实践，已脱敏

## 1. 结论

建议 BridgeForge 吸收“版本 SoT 可能位于嵌套 workspace 根”的通用能力，但禁止
把任何下游目录名写入模板。当前模板只检查仓库根的 `package.json`、
`Cargo.toml`、`pyproject.toml` 和 `VERSION`；当业务 workspace 位于一级子目录时，
hook 可能找不到真实版本源，或者把另一个无关版本文件误当作 SoT。

正式方案必须使用结构性事实发现版本源，并在多个候选同时存在时报告歧义。
“候选列表中第一个存在的文件”不能继续承担多 SoT 裁决。

## 2. 传播四问

1. **属于哪一层**：本文件是元文档需求；采纳后的实现属于
   `templates/codex/hooks/` 产品层。
2. **是否应进入模板**：嵌套 workspace 是跨项目通用布局，应进入模板；具体项目
   子目录名不得进入。
3. **是否需要版本与 CHANGELOG**：本报告不 bump；实现落地时必须 bump，并记录
   `[product]` CHANGELOG。
4. **是否需要 dogfood**：本报告不改 hook；实现落地时必须同步
   `.codex/hooks/version_check.py`，并加入 downstream fixture。

## 3. 当前问题

模板当前使用固定候选：

```python
VERSION_FILES = ["package.json", "Cargo.toml", "pyproject.toml", "VERSION"]
```

下游项目通过把嵌套 `Cargo.toml` 放到列表首位解决实际问题。这个修补证明了需求，
但不能原样反哺：

- 目录名只对一个项目成立。
- 候选顺序被误当成版本语义。
- 多个 package manifest 同时存在时可能选错。
- 找到并 staged 一个无关版本文件，也可能错误放行提交。

需要吸收的是“嵌套 workspace 发现”，不是某个路径字面量。

## 4. 建议的发现契约

### 4.1 第一层：仓库根显式 SoT

继续检查根目录的标准候选，但每个候选必须验证其真实版本声明：

- `package.json`：顶层 `version`
- `Cargo.toml`：`[package].version` 或 `[workspace.package].version`
- `pyproject.toml`：`[project].version` 或上游明确支持的构建后端字段
- `VERSION`：非空单值

仅“文件存在”不足以成为 SoT 证据。

### 4.2 第二层：受控的嵌套 Cargo Workspace

当根目录没有有效版本源时，可以扫描一层 `*/Cargo.toml`，但只接受以下结构性候选：

- manifest 声明 `[workspace]`；
- 同一 manifest 声明 `[workspace.package].version`；或
- workspace 根同时是 package，并声明 `[package].version`。

普通成员 crate 的 `Cargo.toml` 不应自动成为仓库版本 SoT。

默认只扫描一层，禁止无界递归整个仓库。更深布局应通过后续明确配置契约解决，
不能靠猜测。

### 4.3 唯一性

只有恰好一个有效候选时才能自动选择。

| 候选状态 | 行为 |
|---|---|
| 0 个 | 沿用现有无 SoT 安全退化 |
| 1 个 | 选为版本 SoT |
| 多个 | 报告歧义，禁止静默按路径排序选择 |

歧义状态是否 fail-open 或 fail-closed，需要上游单独裁定。最低要求是不得伪称
版本检查已覆盖。

### 4.4 单一发现结果

选出的 SoT 路径必须被后续所有逻辑复用：

- 判断版本文件是否 staged；
- 输出阻断提示；
- 读取当前版本；
- 测试断言和诊断收据。

禁止“显示发现 A，staged 检查却仍匹配固定候选列表 B”。

### 4.5 路径规范化

Git 输出与 Python 路径必须统一为“相对仓库根的 POSIX 路径”：

```text
nested/Cargo.toml
```

Windows `\`、Git `/` 和大小写语义必须在一个 helper 中处理。不能因分隔符不同漏判
真实 SoT 已 staged。

## 5. 多 SoT 边界

以下文件可能同时存在，但语义不同：

- 仓库发布版本
- 应用产品版本
- Cargo workspace 共享 package 版本
- 单个 crate 版本
- BridgeForge 骨架版本
- 模板版本

Hook 不应仅凭文件存在性断言它们等价。

建议优先遵循：

1. 仓库根唯一、有效的显式版本源。
2. 唯一的嵌套 Cargo workspace 共享版本。
3. 其他情况报告歧义或无 SoT。

如果未来增加显式配置，配置必须是项目级、可审计且由 BridgeForge 管理的稳定契约；
不建议新增隐蔽环境变量或用户级配置作为版本事实源。

## 6. 可直接吸收

- 去除项目目录字面量。
- 把版本发现封装成返回“路径 + 版本值 + 来源类型”的单一函数。
- 对 Git staged 路径做仓库相对 POSIX 规范化。
- 只扫描一层嵌套 `Cargo.toml`。
- 多候选给出明确歧义诊断。
- 下游 fixture 覆盖根与嵌套 workspace。
- 保留现有非 commit、merge、`--amend` 与 `[skip-version]` 放行边界。

## 7. 需设计后吸收

- 多候选时 fail-open 还是 fail-closed。
- virtual workspace 没有共享版本时是否允许选择某个 package。
- 根 `VERSION` 与嵌套 workspace 版本并存时的优先级。
- 是否支持显式项目级 SoT 路径。
- 是否进一步验证版本值确实发生 bump。
- 是否要求 CHANGELOG 与版本文件同时 staged。

这些是不同层级的治理能力，不应在本次嵌套发现修复中顺手混入。

## 8. 禁止直接吸收

- 任意下游项目目录名。
- 依赖某个业务仓库布局的固定路径。
- 把第一个匹配文件静默当作 SoT。
- 把任意成员 crate 版本等同于仓库产品版本。
- 无界递归搜索全部 `Cargo.toml`。
- 为解决歧义读取用户级配置或账户信息。

## 9. Fixture 测试矩阵

| 场景 | 预期 |
|---|---|
| 根 `Cargo.toml` 有 `[package].version` | 选择根 manifest |
| 根 `Cargo.toml` 有 `[workspace.package].version` | 选择根 manifest |
| 根是无共享版本的 virtual workspace | 不静默选择成员 crate |
| 根无 SoT，唯一一级子目录是有共享版本的 workspace | 选择嵌套 manifest |
| 唯一嵌套 workspace 根也是 package | 按契约选择 |
| 多个嵌套 workspace 都有版本 | 报歧义 |
| 多个普通 package manifest | 不猜仓库 SoT |
| 根 `VERSION` 与嵌套 workspace 同时存在 | 按明确优先级处理并留收据 |
| 根 `package.json` 与 `Cargo.toml` 都有版本 | 报歧义或按已裁定契约处理 |
| staged 路径使用 `/` | 正确匹配 |
| staged 路径来自 Windows `\` | 规范化后正确匹配 |
| staged 普通文件但未 staged 真实 SoT | 按现有策略阻断 |
| staged 真实嵌套 SoT | 放行 |
| staged 无关 crate 版本 | 不应冒充真实 SoT |
| 无有效版本文件 | 沿用现有安全退化 |
| manifest 损坏或不可读 | 给诊断并按裁定策略退化 |
| Git 查询失败 | 不抛未处理异常 |
| `--amend`、merge、`[skip-version]` | 保持现有行为 |

Fixture 必须断言最终选择的相对路径，而不只断言 exit code。否则“选错版本文件但仍
放行”的缺陷无法被测试发现。

## 10. 风险

- 根与嵌套 manifest 并存时误判版本语义。
- virtual workspace 没有共享版本却错误选择第一个成员 crate。
- Windows 路径分隔符导致 staged 检查漏判。
- 扫描范围过大拖慢每次提交。
- fail-open 隐藏歧义，fail-closed 又可能阻断原本没有仓库版本概念的项目。
- 产品模板更新后漏同步 BridgeForge 自身 dogfood hook。

## 11. 推荐实施顺序

1. 先提取版本候选解析与路径规范化纯函数。
2. 加入根候选与唯一一级嵌套 Cargo workspace fixture。
3. 对多候选只报告歧义，暂不自动裁决。
4. 用 downstream fixture 验证 staged 的真实 SoT 路径。
5. 同步模板与 BridgeForge `.codex` dogfood 副本。
6. 产品实现完成后 bump 版本并写 `[product]` CHANGELOG。

## 12. 推荐裁定

把该候选判为“可抽象后通用”。

吸收嵌套 workspace 发现和路径规范化，拒绝吸收任何项目路径硬编码。多 SoT 的语义
裁决必须作为显式设计决定，不能继续藏在候选数组顺序里。
