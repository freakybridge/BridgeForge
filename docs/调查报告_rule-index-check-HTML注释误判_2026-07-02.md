# 调查报告：`rule_index_check.py --pre-commit` 硬拦假阳性（HTML 注释未剔除）

> 日期：2026-07-02
> 来源会话：ClaudeBridgeAssist 项目执行 `/bridgeforge` 更新（0.38.0 → 0.39.0）时发现
> 状态：诊断完成，未在下游本地修复（用户要求先写报告到 BridgeForge，暂不本地打补丁）
> 处理建议：这是 P0 级 bug（会硬拦所有命中该模式的下游项目的每一次 commit），建议下一版本优先修

---

## 0. TL;DR

0.39.0 把 `rule_index_check.py` 从"只提醒不阻塞"升级为"PostToolUse 软提醒 + pre-commit 硬拦（exit 2）"。但两层共用的 `_detect()` 函数用正则 `re.findall(r"rules/([\w-]+\.md)", text)` **直接扫描 CLAUDE.md 全文**，没有先剔除 HTML 注释块（`<!-- ... -->`）。

只要下游项目的 CLAUDE.md §2 里有形如下面这种"占位示例"（bridgeforge 早期模板的标准写法，教用户以后怎么加专属 rule）：

```markdown
<!-- TODO: 按需追加项目特定 path-rule，例如：
| `rules/api.md` | API 设计约束 | 编辑 `src/api/**` |
| `rules/db.md` | 数据库 schema / 写入约束 | 编辑 `src/db/**`、迁移文件 |
-->
```

`rules/api.md`、`rules/db.md` 会被正则原样命中当成"真实索引条目"，而这两个文件在 `.claude/rules/` 里并不存在（也不该存在，纯示例），于是判定为"死链接" → **每次 `git commit` 都被硬拦 `exit 2`**，且不会自动恢复（除非改动 CLAUDE.md 或用 `[skip-rule-size]` 逃生舱）。

**核心结论**：这个 bug 在升级前是无害的（PostToolUse 只软提醒，用户可以忽略），升级到 pre-commit 硬拦后变成了**阻断性**的——凡是 CLAUDE.md 里带类似占位示例文本的下游项目，装上 0.39.0 就会立刻卡住提交。

---

## 1. 复现步骤（已在 ClaudeBridgeAssist 项目实测）

1. 项目 `CLAUDE.md` §2（规则文件索引）末尾有如下 HTML 注释块（内容与上文 TL;DR 一致）。
2. 从 bridgeforge 0.38.0 更新到 0.39.0，`/bridgeforge` 更新流程按 changelog 把新版 `rule_index_check.py`（含 `--pre-commit` 分支）、新版 `.githooks/pre-commit`（三段闸，镜像闸 → 规则闸 → memory 索引闸）都装了进去。
3. 手动执行 `.githooks/pre-commit` 验证（未经 `git commit`，直接跑脚本）：

   ```
   $ sh .githooks/pre-commit
   [rule-index] pre-commit 硬拦: CLAUDE.md §2 索引 ↔ .claude/rules/ 不一致, 提交被阻断
   [rule-index]   死链(2): api.md, db.md — 去 CLAUDE.md §2 删掉这些行(或补回文件)
   [rule-index] 修好再提交, 或 CHANGELOG.md 顶部加 [skip-rule-size] 豁免本次
   pre-commit exit=2
   ```

4. 确认 `api.md` / `db.md` 在该项目 `.claude/rules/` 目录下从未存在过——它们只出现在 CLAUDE.md 的 `<!-- TODO: ... -->` 注释块里，是纯示例文字，不是真实索引意图。

---

## 2. 根因（代码位置 + 具体逻辑）

文件：`templates/hooks/rule_index_check.py`（PostToolUse 软提醒与 pre-commit 硬拦共用同一检测函数）

```python
def _detect() -> tuple[list[str], list[str]] | None:
    ...
    text = claude_md.read_text(encoding="utf-8")
    # 捕获 `rules/xxx.md` 形式的路径引用。
    listed = set(re.findall(r"rules/([\w-]+\.md)", text))
    actual = {p.name for p in rules_dir.glob("*.md")}
    missing = sorted(listed - actual)   # CLAUDE.md 列了但文件不存在
    unlisted = sorted(actual - listed)  # 文件存在但 CLAUDE.md 没列
    return missing, unlisted
```

`re.findall` 直接在**整个文件原文**（含 HTML 注释、含 fenced code block 里的示例）上跑，没有任何"先剥离非正文区域"的预处理步骤。只要注释/示例里出现符合 `rules/xxx.md` 形式的字符串，就会被当成真实索引条目对待。

**为什么升级前无害、升级后致命**：
- PostToolUse 分支（`main()` 里非 `--pre-commit` 路径）命中同样的误判，但只是 `print(..., file=sys.stderr)` 后 `return 0`——纯提醒，用户可以选择忽略。
- pre-commit 分支复用同一个 `_detect()`，命中后直接 `return 2` 硬拦，且**每次提交都会重新触发**（因为触发条件本身——那段 HTML 注释——没有变化，不会像别的偶发问题一样自愈）。

**根本原因是同一个**：正则没有区分"HTML 注释里的示例文字"和"正文里真实的索引表格行"。

---

## 3. 影响范围

**谁会中招**：任何下游项目的 CLAUDE.md §2 里，只要含有 bridgeforge 早期模板风格的"具体文件名占位示例"（如本报告 TL;DR 里的 `rules/api.md` / `rules/db.md` 例子），一旦升级到 0.39.0 就会被硬拦。

**注意**：当前（0.39.0）版本的 `templates/CLAUDE.md` 本身 §2 末尾的占位提示已经改成了：

```
<!-- 按需追加项目特定 path-rule，如 `rules/<topic>.md`（按 `src/<topic>/**` 触发）。 -->
```

这种写法里 `<topic>` 含 `<` `>` 字符，不会被 `[\w-]+` 正则捕获，所以**全新用 0.39.0 模板 init 的项目不会中招**。但所有在更早版本（当时 CLAUDE.md 模板还是"具体文件名占位示例"风格）就已经 bootstrap、后续一路 `/bridgeforge` 更新到 0.39.0 的存量项目，会带着这个历史遗留的具体文件名示例一起升级，一装上 pre-commit 硬拦就立刻被卡住。**存量项目数量未知，但只要是早期 bootstrap 的项目大概率都有此风险**。

**次级风险（未实测，仅提示）**：`rule_size_check.py` 里"版本号 > 5 处 / 日期 > 8 处"之类的计数信号，若也是对全文（含注释/code block）做正则计数而未剔除非正文区域，可能有同类误判（程度较轻，因为是软提醒信号而非直接判定死链，且当前不涉及 hard-block），建议一并排查但不属本次报告核心范围。

---

## 4. 修复建议（未落地，仅建议）

在 `_detect()` 里，`read_text()` 之后、`re.findall()` 之前，先剔除 HTML 注释块：

```python
text = claude_md.read_text(encoding="utf-8")
text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)  # 剔除 HTML 注释块，避免占位示例被误判
listed = set(re.findall(r"rules/([\w-]+\.md)", text))
```

**该不该也剔除 fenced code block（```...```）**：本次复现的具体案例只涉及 HTML 注释，暂未发现 code block 内文本触发误判的实例，建议先只修注释这一层，code block 场景留待下次实测命中再补（避免过度设计不存在的问题）。

**是否需要同步排查 `rule_size_check.py` 等其他共享同一 CLAUDE.md 全文扫描逻辑的 hook**：建议一并检查，但因目前只是软提醒非硬拦，优先级低于本报告核心的 `rule_index_check.py --pre-commit`。

修好后建议同步检查所有存量下游项目的 CLAUDE.md，若仍带类似"具体文件名占位示例"风格，考虑批量替换成当前模板的 `<topic>` 写法，从根上消除误判触发面（即便正则修好了，占位示例本身写法也该跟上当前模板标准）。

---

## 5. 本次 ClaudeBridgeAssist 项目现状

用户明确要求**先不在本地修复**，本次调查报告写完后即结束此项工作。ClaudeBridgeAssist 项目目前处于以下状态（如后续需要收尾请知悉）：

- `.claude/settings.json` 中已声明 `.githooks/pre-commit`（`core.hooksPath` 由 `githooks_path_check.py` 自愈设置）
- 手动跑 `sh .githooks/pre-commit` 会 `exit 2`（本报告 §1 复现的假阳性），意味着**该项目当前实际提交也会被卡住**，直到此 bug 修复或采取规避措施
- 用户尚未选择规避方式（未使用 `[skip-rule-size]`，也未改动 CLAUDE.md 示例文字）
