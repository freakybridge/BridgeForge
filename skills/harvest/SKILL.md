---
name: harvest
description: 把下游项目攒下的通用经验脱敏后反哺回 bridgeforge 上游骨架库（reverse-sync）。无参=读收件箱批量处理；带一句描述=立即单条快车道。
user-invocable: true
argument: 可选——要立即反哺的一条经验描述。带参走快车道（跳过收件箱）；不带参读收件箱批量处理。
---

# /harvest — 通用经验反哺上游 bridgeforge

把当前下游项目攒下的**通用**经验，脱敏后写回 bridgeforge 骨架库的 `templates/` / `skills/`，让所有项目受益。

> 与 `/summary` 的分工：`/summary` 负责**捕捉**（日常把通用候选记进收件箱），`/harvest` 负责**推送**（脱敏 + 写上游）。两个命令一条流水线，捕捉/推送分离。

## 两个入口，一个仪式

| 调用 | 入口 | 处理 |
|------|------|------|
| `/harvest`（无参）| 慢车道 | 读当前项目 `.claude/harvest-inbox.md`，列全部未处理条目，批量过 |
| `/harvest <一句描述>` | 快车道 | 跳过收件箱，立即处理这一条（一眼就确定要反哺时用）|

两个入口都汇进**同一套脱敏 harvest 仪式**（下方），不分叉。

## 前置：定位上游

bridgeforge 上游仓库通常在 `~/.claude/skills/bridgeforge/`（clone 或 symlink）。harvest 的写入目标是它的 `templates/` / `skills/`。
- 找不到上游 clone → 停下，提示用户先 clone 再跑。
- 上游是 git 仓库 → 后续改动**不自动 commit/push**，留给用户。

## 仪式（严格按 reverse-sync-playbook 执行）

权威流程 + 脱敏 checklist 见 `~/.claude/skills/bridgeforge/docs/reverse-sync-playbook.md`。核心步骤：

1. **取候选**：无参 → 读收件箱全部未处理行；带参 → 就这一条。
2. **逐条判通用性**（playbook §2）：🟢 通用增量(反哺) / 🟡 可抽象(脱敏后反哺) / 🔴 业务专属(**不**反哺)。
3. **脱敏**（playbook §3 七项 checklist，红线）：项目名 / 内部包名 / 凭证 / 内部 URL / commit hash / 绝对路径 / 业务术语，逐项过。**漏一项就不安全。** 拿不准的当场问用户。
4. **写上游**：按 design-rationale §6「模板 vs 占位」决定落点（`templates/<agent>/rules/` / `templates/claude/CLAUDE.md` / `templates/codex/AGENTS.md` / `skills/` 等）；判据 = 不依赖业务领域才进产品层。
5. **bump 版本 + CHANGELOG**：上游 `VERSION` bump，CHANGELOG 打 `[product]` 标签（改了 templates/skills → 下游应当 sync）。
6. **记反哺日志**：在 playbook §5 表追加一行（日期 / 源项目 / 目标文件 / 一句话 / 操作人）。
7. **回收收件箱**：已成功反哺的条目，从下游 `.claude/harvest-inbox.md` 勾掉或删行。
8. **给 diff，不自动 push**：`git -C <上游> diff` 摆给用户，由用户 review + 手动 push（playbook §5 末 + push 前敏感词扫描）。

## 红线
- ❌ 不脱敏直接写公开上游仓库 —— **即使"立即"快车道也必须过 §3 checklist**（高信心恰恰是泄露高发区）
- ❌ 自动 commit / push 上游（留给用户）
- ❌ 把业务专属内容塞进 `templates/`（污染所有下游）
- ❌ 批量跨多个下游同时反哺（一次只处理当前项目；多源仲裁见 playbook §4）

$ARGUMENTS
