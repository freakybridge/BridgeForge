# 用户级 skill 与重复副本维护

根入口完成刷新和模式判定后，所有 init / update / adopt 模式都必须读取并执行本文件。若用户明确说“不安装这些通用 skill”，可跳过用户级安装，但不得把项目专属 skill 当作通用 skill 清理。

## 目录

- 1-3：单一源、用户级同步、退役清理
- 4-5：项目重复副本与扁平 shadow
- 6-8：allow、Claude 全局规则与 UTF-8
- 9：收据和停止条件

## 1. 单一源与入口布局

- 通用协作 skill 的产品源是 `$BRIDGEFORGE_HOME/skills/<name>/`，实际清单以目录为准，禁止硬编码个数。
- Claude Code 用户级目录是 `~/.claude/skills/`；Codex 是 `~/.agents/skills/`。两者都只扫描 `<name>/SKILL.md` 顶层，不递归扫描 `$BRIDGEFORGE_HOME/skills/`。
- `$USER_SKILLS_DIR/bridgeforge/` 必须是只含 `SKILL.md` 的叶子入口。完整工厂只放 `~/.bridgeforge`，禁止 clone/junction/symlink 到入口货架。
- 入口源：Claude 用 `scripts/claude_bridgeforge_entry.SKILL.md`；Codex 用 `scripts/codex_bridgeforge_entry.SKILL.md`。
- `~/.codex/skills/bridgeforge` 是历史错误位置；发现后只报告并建议移到 `~/.codex/backups/`，禁止静默删除真实仓库。
- 发现 `~/.agents/bridgeforge-home` 或 `~/.claude/skills/bridgeforge/templates` 旧完整仓库时，提示按 `INSTALL.md` 迁移，禁止静默删除。

## 2. 幂等同步用户级 skills

```bash
SKILLS_SRC="$BRIDGEFORGE_HOME/skills"
SKILLS_DST="$USER_SKILLS_DIR"

mkdir -p "$BRIDGEFORGE_COMMAND_DIR"
if [ "$TEMPLATE_AGENT" = "codex" ]; then
  cp "$BRIDGEFORGE_HOME/scripts/codex_bridgeforge_entry.SKILL.md" "$BRIDGEFORGE_COMMAND_DIR/SKILL.md"
else
  cp "$BRIDGEFORGE_HOME/scripts/claude_bridgeforge_entry.SKILL.md" "$BRIDGEFORGE_COMMAND_DIR/SKILL.md"
fi

for s in $(ls "$SKILLS_SRC"); do
  [ -d "$SKILLS_SRC/$s" ] || continue
  if [ ! -d "$SKILLS_DST/$s" ]; then
    cp -r "$SKILLS_SRC/$s" "$SKILLS_DST/$s"
    echo "✓ 安装缺失 skill: $s"
  elif diff -rq "$SKILLS_SRC/$s" "$SKILLS_DST/$s" >/dev/null 2>&1; then
    echo "- 已是最新，跳过: $s"
  else
    echo "⚠ 已存在但与上游不一致: $s"
  fi
done
```

不一致时逐个显示 diff，并询问“覆盖成上游版 / 保留定制”。禁止静默覆盖。若确认只是未定制的旧版镜像，可逐个覆盖；若含定制，默认保留。

## 3. 清理已退役用户级 skill

读取根 `RETIRED.md` 的 `- <name> | ...` 条目。若 `$SKILLS_DST/<name>/` 仍存在，向用户展示退役原因，逐个询问“删除 / 保留”；绝不静默或批量删除。用户改过的定制版按用户选择保留。

本步只处理用户级 skill。退役 hook 不在本步范围，仍按 CHANGELOG 处理。

## 4. 清理项目级重复副本

所有模式都执行。只检查 `$PROJECT_SKILLS_DIR/` 中与 `$BRIDGEFORGE_HOME/skills/` 同名的目录；不在上游清单里的项目专属 skill 绝不碰。

```bash
SKILLS_SRC="$BRIDGEFORGE_HOME/skills"
PROJ_SKILLS="$PROJECT_SKILLS_DIR"
for s in $(ls "$SKILLS_SRC"); do
  [ -d "$SKILLS_SRC/$s" ] || continue
  [ -d "$PROJ_SKILLS/$s" ] || continue
  if diff -rq "$SKILLS_SRC/$s" "$PROJ_SKILLS/$s" >/dev/null 2>&1; then
    echo "DUP-IDENTICAL : $s"
  else
    echo "DUP-DIVERGENT : $s"
  fi
done
```

先给总览，再逐个确认；确认一个删一个，用户不答或选择保留则不删：

| 分类 | 推荐动作 | 删除前必做 |
|---|---|---|
| `DUP-IDENTICAL` | 建议删，回落用户级单一源 | 仍须单独确认 |
| divergent 但只是旧版镜像 | 建议删 | 仍须单独确认 |
| divergent 且含项目专属数据 | 建议保留，或迁移后删 | 展示 diff；必须单独确认 |

判定“含项目专属数据”：出现项目真实路径、rule 文件名、非 placeholder 的内联字典。拿不准就按定制处理。

旧版 `find-doc` / `sync-docs` 若内联了项目字典，先迁到 `$PROJECT_AGENT_DIR/find-doc.map.md` / `$PROJECT_AGENT_DIR/sync-docs.map.md`，用户确认迁移正确后才能删副本。

## 5. 清理用户级扁平 shadow

只检查 BridgeForge 出品的 skill 名。若 `$USER_SKILLS_DIR/<name>.md` 与正确的 `$USER_SKILLS_DIR/<name>/SKILL.md` 同时存在，逐个询问删除扁平文件；用户不答则保留。非 BridgeForge 的扁平文件不碰。

目录式 skill 的兼容字段使用 `user_invocable`。若发现历史 `user-invocable` 漂移，提醒修正，但本轮不要借清理扩大改动范围。

## 6. 用户级 allow 审计

init / 换机首次 setup 必跑；已知用户级配置干净时可跳过：

```bash
python "$BRIDGEFORGE_HOME/templates/$TEMPLATE_AGENT/scripts/audit_user_allow.py"
```

扫描 Claude 的 `~/.claude/settings.json` 或 Codex 的 `~/.codex/settings.json` 中疑似项目专属/一次性 allow（绝对路径、PID、IP、一次性编译命令）。只报告，不删除；建议经用户确认后下沉到项目 `settings.local.json`。

## 7. Claude Code 全局规则自检

仅 Claude Code 执行；Codex 跳过。若 `~/.claude/CLAUDE.md` 不存在则跳过。幂等检查并补齐：

1. 回复一律简体中文。
2. 查文件/内容用 Glob/Grep/Read，禁止用 shell 查文件。
3. 写 rule 只留“必须/禁止”红线，事故复盘和长示例移至 memory/doc；path 触发 rule 必须有可解析 YAML `paths:`。

只补缺项，不覆盖用户已有段落。完整措辞必须与 BridgeForge 当前用户级规范一致，禁止另造弱化版本。

## 8. Claude Code 全局 Python UTF-8 自检

仅 Claude Code 执行；Codex 跳过。确保 `~/.claude/settings.json` 的 `env` 含：

```json
{"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
```

已有 `env` 时只追加缺失 key，不覆盖其他 key；文件不存在时可新建最小 JSON。作用是避免 Windows Python 子进程中文 stdout 被按错误编码注入上下文。

## 9. 收据与停止条件

结束时报告：

- wrapper 是否已刷新；新装、相同、冲突的用户级 skill 名单。
- 退役 skill、项目重复副本、扁平 shadow 的逐项决定。
- 是否发现待迁移的项目专属字典。
- allow 审计结果，以及 Claude-only 全局规则/UTF-8 自检结果。
- 若复制了任何 skill，提示重启当前 agent 后才会重新扫描。

遇到任何定制差异、删除候选或迁移候选都必须停下来逐项询问；禁止把“单一源”当作静默覆盖/删除授权。
