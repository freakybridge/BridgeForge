# 上游同步 Playbook（sync-from-upstream）

> **定位**：setup_agent 上游（`D:/Quant/setup_agent`）更新后，把改动派发到下游消费者（用户级 `~/.claude/skills/`、下游项目 `<project>/.claude/`）。与 [reverse-sync-playbook](reverse-sync-playbook.md)（下游 → 上游）方向相反，互为镜像。
>
> **为什么不做成 skill / 自动化**：同步核心是"上游通用增量 vs 下游业务专属"边界判断，需要人脑。setup_agent 更新频率低（季度级），手动可控。详见 §6 工具化判断。

---

## 1. 触发时机

满足任一即可触发一次上游同步：

- **setup_agent push 了新内容**（README 改 / 模板加 / hook 加 / skill 改）— 主要触发器
- **下游项目跑某 skill 报错** — 往往是上游更新了脚本但下游没 sync（如本会话 ClaudeBridgeAssist 缺 5 个 hook 导致 settings.json 注册的 hook 无文件可跑）
- **新机 clone 下游项目** — 装 setup_agent 后发现某些 skill 行为跟预期不一致，因为下游 `.claude/` 是历史版本
- **月度 / 季度盘点同步**

---

## 2. 同步目标分类（关键 — 决定覆盖策略）

下游"消费者"按业务专属程度分三层，各自的同步策略不同：

| 消费者 | 业务专属程度 | 同步策略 | Why |
|--------|-------------|---------|-----|
| 用户级 `~/.claude/skills/<name>/` | 零 | **直接 cp 覆盖** | 这是 setup_agent skill 的 install 镜像，没业务专属内容；下游绝不该改这里 |
| 下游项目 `<project>/.claude/hooks/*.py` | 零 | **直接 cp 覆盖** | hook 是模板派发产物，下游不会自改这些 .py 内部逻辑 |
| 下游项目 `<project>/.claude/scripts/*.py` | 零 | **直接 cp 覆盖** | 同上 |
| 下游项目 `<project>/.claude/settings.json` | 低 | **merge，不覆盖** | 下游可能加了项目特定 permissions / additionalDirectories；通用 hook 段更新 |
| 下游项目 `<project>/.claude/rules/*.md` | **中-高** | **手动 diff 选择性吸收** | 下游可能已演进自己的业务版本（比上游脱敏版更全） |
| 下游项目 `<project>/CLAUDE.md` | **中-高** | **手动 diff 选择性吸收** | 同上 |
| 下游项目 `<project>/.claude/memory/` | **极高** | **绝对不动** | memory 全是业务踩坑经验，覆盖会丢用户多年积累 |
| 下游项目 `<project>/doc/` | **极高** | **绝对不动** | doc 是业务设计文档 |

**核心边界判断**：
- 文件路径在 setup_agent `templates/` 里 + 内容跟 install 时一致 → 可覆盖
- 文件被下游开发过程修改过 → 不要无脑覆盖

---

## 3. 五步操作流程

### Step 1：列改动 + 探查下游现状

```powershell
# 看 setup_agent 自上次同步以来改了什么
cd D:/Quant/setup_agent
git log <last-sync-commit>..HEAD --stat

# 列所有候选下游
ls D:/Quant/StratusAgent/.claude/
ls D:/Quant/causis_risk_suite/.claude/
ls D:/Quant/<其他>/.claude/
ls C:/Users/<user>/.claude/skills/
```

明确**这次同步的范围**（哪些上游文件 → 哪些下游目标）。范围不要贪大，一次 1-2 类同步为宜。

### Step 2：按 §2 表格分类执行

**类 A 简单覆盖**（hooks / scripts / 用户级 skill）：

```powershell
# 下游 hooks/
cp -r D:/Quant/setup_agent/templates/hooks/. D:/Quant/<下游>/.claude/hooks/

# 下游 scripts/
cp -r D:/Quant/setup_agent/templates/scripts/. D:/Quant/<下游>/.claude/scripts/

# 用户级 skill
cp -r D:/Quant/setup_agent/skills/<name>/. C:/Users/<user>/.claude/skills/<name>/
```

**类 B settings.json merge**（**不要直接覆盖**）：

读下游 `.claude/settings.json` + 上游 `templates/settings.json` → 手动 merge：
- **保留下游**：`permissions.allow`、`permissions.additionalDirectories`、`permissions.defaultMode`、下游自定义的 hook 注册段
- **更新 / 加入上游通用**：`hooks.PostCompact`、`hooks.Stop`、`hooks.PreToolUse`、`hooks.PostToolUse`、`hooks.UserPromptSubmit`、`hooks.SessionStart` 等
- **路径适配**：下游若无 `.venv` → 把命令里的 `.venv/Scripts/python.exe` 改成裸 `python`，每条 hook 的 `comment` 字段尾加"建好 .venv 后改回 .venv/Scripts/python.exe"

**类 C rules / CLAUDE.md 选择性吸收**：

对每对文件做 diff（`diff <下游>/CLAUDE.md <上游 templates>/CLAUDE.md` 或对应 rule 文件）。看每个差异段：

- 🟢 **上游新增的通用增量** → 吸收到下游（如本会话反哺的 `modules.md §3.1 §3.2` 就是这种）
- 🟡 **下游业务专属补充** → 保留不动（上游脱敏版没业务细节是设计意图，不要被覆盖）
- 🔴 **上游脱敏后比下游原版"减弱"** → 保留下游原版（如 StratusAgent `architecture.md` 含具体 gateway 红线，上游模板是通用版，绝不能覆盖丢业务）

**类 D 绝对不动**：
- `<project>/.claude/memory/`
- `<project>/doc/`

### Step 3：跑通验证

每个同步过的下游：

```powershell
cd D:/Quant/<下游>

# 跑新加 / 更新的 hook 看 exit 0
python .claude/hooks/<新加 hook>.py

# 跑 session_snapshot manual 看是否生成新 snapshot
python .claude/hooks/session_snapshot.py manual

# 跑 archive_scan 看是否能执行
python .claude/scripts/archive_scan.py --count
```

任意一个报错 → 检查路径适配 / 文件权限 / .runtime/ 目录是否存在。

### Step 4：reverse-sync 互查（可选）

同步完看下游是否近期演进出新通用增量没回灌上游。跳到 [reverse-sync-playbook](reverse-sync-playbook.md) 走反向流程。

通常**先 sync-from-upstream 拉新 → 再 reverse-sync 推增量**，保证 setup_agent 模板始终向后兼容下游业务。

### Step 5：各下游项目独立 commit

下游各自的 git repo 各自 commit：

```powershell
cd D:/Quant/<下游>
git status                            # 看同步引入的改动
git diff                              # 全量看
git add <精确路径>                    # 不要 git add .
git commit -m "chore: 同步 setup_agent 上游更新（hook + settings.json）"
git push                              # 用户手动
```

**setup_agent 自身不参与下游 commit** — 上游 push 在 reverse-sync-playbook §2 Step 5 完成。

---

## 4. 红线

- **memory 绝对不动**（业务私有，覆盖会丢用户多年踩坑经验）
- **rules / CLAUDE.md 不无脑覆盖**（业务专属版本可能比上游脱敏版本更全）
- **下游 settings.json merge 而非覆盖**（permissions / additionalDirectories 是下游业务专属）
- **doc/ 绝对不动**（业务设计文档）
- **不让 AI 自动跨多下游同步**（用户需要逐个 confirm，对多源同步 AI 容易把业务专属覆盖掉）

---

## 5. 与 reverse-sync 的对照

| | [reverse-sync](reverse-sync-playbook.md)（下游 → 上游）| **sync-from-upstream**（上游 → 下游）|
|---|---|---|
| 方向 | 下游通用增量回灌 setup_agent 模板 | setup_agent 模板派发到下游 |
| 触发器 | 下游攒到 ≥3 条通用范式 / 通用坑 | setup_agent push 新内容 |
| 关键判断 | 通用 vs 业务专属 → 脱敏 | 通用增量 vs 下游业务专属 → 选择性吸收 |
| 主要危险 | 业务专属泄露到公开 repo | 业务专属被覆盖 |
| 工具化 | 暂不工具化（[reverse-sync §6](reverse-sync-playbook.md#6-什么时候考虑工具化) 三条件）| 暂不工具化（同标准）|

---

## 6. 什么时候考虑工具化

> **2026-05-29 更新（v0.14.0）**：机械半场已并入 `/setup_agent` **更新模式**——cwd 有 `.claude/.setup_agent_version` 时，`/setup_agent` 自动 `git pull` 上游 + 按 §2 表格分类 diff + 呈现 `[product]` 增量清单。**判断半场仍全程人脑**：类C（rules / CLAUDE.md）只 diff 不自动改，类D（memory / doc）碰都不碰。
>
> 之所以这次能工具化机械半场而不违反下方红线：把流程切成"机械（拉/diff/分类/呈现）vs 判断（选择性吸收）"两半，只自动化前者。这不是"把判断错误自动化"，是给判断装机械前台。新增 skill 反而是负担，故并入 `/setup_agent` 而非独立 skill。

下方原则仍适用于**判断半场**——参考 [reverse-sync-playbook §6](reverse-sync-playbook.md#6-什么时候考虑工具化) 三条件**同时满足**才考虑把类C 选择性吸收也工具化：

- [ ] 本 playbook 已用 ≥ 3 次，流程没大改
- [ ] 各类同步策略（§2 表格）的边界判断都能机械化（无"凭直觉"项）
- [ ] 多下游并发同步需求出现，手动协调成本变高

否则**别把判断半场工具化** — rules / CLAUDE.md 选择性吸收判断密集度高，自动化只会把判断错误自动化。

---

## 7. 同步日志

每次重大同步可在下表追加一行。攒 5+ 行后回头看是否值得做工具化（参考 §6）。

| 日期 | setup_agent commit | 下游 | 同步内容 | 操作人 |
|------|--------------------|------|----------|--------|
| 2026-05-24 | 9cfa7ae + 后续未 push | ClaudeBridgeAssist | 5 hook（find_doc_reminder / memory_lint / rule_index_check / rule_size_check / show_state）+ settings.json 加 PreToolUse/PostToolUse/SessionStart 注册段 | bridgexue |
| 2026-05-24 | 同上 | `~/.claude/skills/setup_agent/` | SKILL.md Step 3 改造（条件复制 + 无 .venv fallback）同步 | bridgexue |
| 2026-05-24 | 同上 | causis_risk_suite | meta_rule_design.md 补全（之前缺失） | bridgexue |
| 2026-05-29 | v0.14.0 | （机制本身）| 机械半场并入 `/setup_agent` 更新模式（版本戳 `.setup_agent_version` + 拉上游 + §2 分类 diff + `[product]` 增量清单）；判断半场仍人脑 | bridgexue |

---

## 参考

- [reverse-sync-playbook.md](reverse-sync-playbook.md) — 反方向流程（下游通用增量回灌上游）
- [design-rationale.md](design-rationale.md) — setup_agent 整体设计思路
- [templates/rules/meta_rule_design.md](../templates/rules/meta_rule_design.md) — 判断"通用 vs 业务"的关键依据
