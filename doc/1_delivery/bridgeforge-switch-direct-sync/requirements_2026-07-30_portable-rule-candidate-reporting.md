# Portable Rule 候选发现与报告确认卡

> 状态：已实现并验证
> 原始需求：采纳 Markdown Rule 投影 debate 的收敛结论，仅实现安全的迁移候选发现与报告。
> 调用来源：`$debate` → `$collab`

## 目标

direct switch 发现显式 portable 的 Markdown Rule 迁移候选，并持久记录为目标宿主 map 的
`untranslated` 报告。

## 已确认规则

- 仅扫描当前 source 宿主顶层 `rules/*.md`。
- Rule 必须在文件首部 `--- … ---` frontmatter 中唯一声明
  `bridgeforge_portable_rule: true`。
- 字段缺失、重复、非布尔值、frontmatter 损坏或正文伪字段均不报告。
- target map 记录候选的 `untranslated` asset，switch 摘要报告该候选。
- marker 仅表示人工迁移候选，不代表跨宿主语义等价或自动迁移授权。

## 不做

- 不创建、修改或删除 target Rule。
- 不修改 `AGENTS.md`、`CLAUDE.md` 或其规则索引。
- 不新增 Rule adapter、project-root map、segment、replacement 或 memory 路由。

## 已核实事实

- canonical switch 已有 `untranslated` asset 状态与摘要报告，且不会取得 target 文件 ownership。
- 现有规则索引 hook 要求入口索引与顶层 `rules/*.md` 全等；自动写 Rule 会越过该边界。

## 拟修改与验收

- 修改 canonical switch 及所有既有镜像，以识别严格 frontmatter 并生成只读候选资产。
- 新增 downstream fixture：双向字段识别、字段缺失/重复/非法、正文伪字段、同名 target、
  map 缺失/损坏/漂移。
- 断言 source / target Rule、`AGENTS.md`、`CLAUDE.md` 在运行前后字节不变；仅 map / 摘要可变化。
- 运行全部 harness、镜像一致性和相关 switch fixture。

## 风险与自动化边界

- marker 不能成为重建 ownership 或覆盖 target 的依据。
- map 无效、缺失或漂移时继续沿用 canonical fail-closed 行为。
- 实现完成后才按产品层规则同步版本、CHANGELOG 与 dogfood。

## 实施收据

- five-way mirror 的 direct switch 仅识别严格 frontmatter 字段，并生成无 target members 的
  `untranslated` 候选资产。
- 已验证唯一 `true`、缺失、重复、false、非布尔、未闭合、正文伪字段、嵌套 Rule、
  target 存在 / 缺席与 map 异常；Rule 与入口文件保持字节不变。
