# bridgeforge — 项目级 CLAUDE.md

> ⚠️ **这不是普通项目**。bridgeforge 是个**"协作骨架工厂"**：它的产出（`templates/` + `skills/`）会被复印进每一个未来项目。
> 所以在这个 repo 里干活，第一红线不是"把功能做对"，而是**"把改动放对层、该传播的传播出去"**。

---

## §1 工厂红线：每个改动落地前，过一遍「传播四问」（always-on）

任何修改 / 新功能落地**之前**，必须显式回答这四问（写不出答案就别动手）：

1. **这属于哪一层？**
   - **产品层** `templates/` `skills/` → 会被复印给所有下游项目
   - **自身配置层** `.claude/` `CLAUDE.md`（本文件）→ 只影响 bridgeforge 这个 repo 自己
   - **元文档** `docs/` `README.md` `SKILL.md` `CHANGELOG.md` → 描述产品，但不随产品下沉
2. **如果是通用改进，我写进 `templates/` / `skills/` 了吗？**
   - 最常见的事故：把一条通用规矩只写进了自身配置层或元文档，**忘了镜像进产品层** → 下游永远拿不到。
   - 反向也算事故：把项目特定的东西误塞进 `templates/` → 污染所有下游。判据见 [docs/design-rationale.md](docs/design-rationale.md) §6「模板 vs 占位」。
3. **传播出去要不要 bump 版本 + 记 CHANGELOG？**
   - 改动产品层 → 几乎一定要 bump（下游靠版本号判断该不该 sync）。
   - 记 CHANGELOG 时**按 §3 打层标签**。
4. **改的是 `templates/hooks/` 或 `templates/settings.json` 吗？那我吃狗粮了吗？（dogfood 镜像，红线）**
   - **凡确认要进产品层的 hook / settings 改动，必须当场镜像进自身 `.claude/`** —— 不能只发给下游、自己不装（§2 dogfood 约定的强制版）。
   - **现已机检硬拦**：`mirror_drift_check.py` 在 `.githooks/pre-commit` 对「缺文件」exit 2、正文差异（归一化 python 前缀后）软提示；漏镜像的 hook 提交时会被拦（细则 → `templates/rules/portability.md §5.1`）。
   - 镜像时按 dev 仓库约定改 hook 命令：`templates/` 用 `.venv/Scripts/python.exe`，自身 `.claude/settings.json` 用系统 `python`（dev 仓库无 `.venv`）。注意 hook `.py` 正文两侧应逐字一致——前缀差异只在 `settings.json` / `pre-commit` 的命令行，不在 `.py` 里。
   - 对 bridgeforge 不适用的 hook（如 Rust-only 的 `target_cleanup`）**也要挂上**——它的自门控 no-op 正好用来验证产品承诺，挂着 = 持续 dogfood 测试。
   - 例外：纯下游业务场景的 hook（本 repo 永远跑不到）可豁免，但要在 CHANGELOG 顶部当条加 `[dogfood-exempt: <hook> <因>]` 注明「不 dogfood + 原因」（这也是 `mirror_drift_check.py` 硬拦的豁免开关）。

> 写在 CLAUDE.md 而非 rules/：任何任务常驻、不按 path 触发（理由 → design-rationale §5）。

---

## §2 分层地图（哪个目录 = 哪一层）

| 目录 / 文件 | 层 | 改动会不会传到下游 |
|------------|----|------------------|
| `templates/**` | 产品层 | ✅ 下游复印时全量继承 |
| `skills/**` | 产品层 | ✅ 下游 `/bridgeforge` Step 0 自检补齐到 `~/.claude/skills/` |
| `.claude/**` `CLAUDE.md` | 自身配置层 | ❌ 只管 bridgeforge 自己（自产自用：理论上应与 `templates/` 同款，见下） |
| `docs/**` `README.md` `SKILL.md` | 元文档 | ❌ 描述产品 |
| `CHANGELOG.md` `VERSION` | 元文档（流水账 / SoT） | ❌ 自己的版本号；模板版本号是 `templates/VERSION` |

**自产自用（dogfood）约定**：bridgeforge 自己也按自己的手册活——`.claude/hooks/*.py` 理论上应与 `templates/hooks/*.py` **逐字一致**（仅 hook 命令前缀按 dev 仓库无 `.venv` 改用系统 `python`）。改了一边就该同步另一边（已提升为 §1 第 4 问红线）。

---

## §3 CHANGELOG 层标签约定

每条 CHANGELOG entry 前缀打一个标签，让下游一眼看懂"这次该不该拉"：

| 标签 | 含义 | 下游动作 |
|------|------|---------|
| `[product]` | 改了 `templates/` / `skills/`，会下沉 | sync-from-upstream 时**应当**拉取 |
| `[repo]` | 只改了 bridgeforge 自身配置 / 工具，不下沉 | 无关，跳过 |
| `[meta]` | 只改了 `docs/` / `README` / `SKILL.md` 等说明 | 一般无关（除非想了解设计） |

混合改动就并列标，如 `[product][meta]`。这是让"下游同步收益"最直接的抓手——下游 `grep "\[product\]" CHANGELOG.md` 即知增量。

---

## §4 跨项目传播机制（详见 docs/）

- **上游 → 下游**（拉新手册回老房子）：[docs/sync-from-upstream-playbook.md](docs/sync-from-upstream-playbook.md)
- **下游 → 上游**（把老房子攒的通用经验脱敏反哺回手册）：[docs/reverse-sync-playbook.md](docs/reverse-sync-playbook.md)
- **整体设计 / 双重身份论述**：[docs/design-rationale.md](docs/design-rationale.md) §9

两条 playbook 都**靠人脑判断、手动触发**——§1 四问是它们的"前门闸"（改动进门即分层 + 产品层 hook 当场 dogfood）。
