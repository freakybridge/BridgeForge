# 需求：BridgeForge 用户级工厂目录改为 `.bridgeforge`
> 日期：2026-07-08
> 状态：trial
> 入口：用户认可将完整 BridgeForge 工厂从 Codex 专属 `.agents` 下移出，并明确不要额外 `repo` 包装层。

## 背景与目标

当前 Codex 安装形态把完整 BridgeForge 仓库放在 `~/.agents/bridgeforge-home`，再用 `~/.agents/skills/bridgeforge/SKILL.md` 作为薄入口。这个形态能解决 Codex slash 菜单只扫描叶子 skill 的问题，但用户看到 `.agents/bridgeforge-home` 时会误以为 BridgeForge 工厂隶属于 Codex 骨架，尤其是它同时包含 Claude 和 Codex 两套模板。

目标是把完整 BridgeForge 工厂源头移动到中立路径 `~/.bridgeforge`，让 `.agents` 和 `.claude` 只保留各自 agent 可扫描的 skill 货架。

## 非目标

- 不取消 Codex 的薄入口 wrapper；`~/.agents/skills/bridgeforge/SKILL.md` 仍必须是叶子 skill。
- 不把完整 BridgeForge 仓库放进 `~/.agents/skills/bridgeforge` 或 `~/.claude/skills/bridgeforge`。
- 不在产品层改造提交里自动迁移用户机器上的目录；真实迁移需由用户单独确认后执行。
- 不改变项目级骨架目录：Codex 项目仍是 `.codex/ + AGENTS.md`，Claude 项目仍是 `.claude/ + CLAUDE.md`。

## 用户可见行为

- 新安装时，完整 BridgeForge 仓库放在 `~/.bridgeforge`。
- Codex 用户级入口仍在 `~/.agents/skills/bridgeforge/SKILL.md`，但它读取 `~/.bridgeforge/SKILL.md`。
- Claude Code 用户级入口也采用薄入口，位于 `~/.claude/skills/bridgeforge/SKILL.md`，同样读取 `~/.bridgeforge/SKILL.md`。
- 通用 skill 继续复制到各自 agent 的用户级 skill 货架：Codex 为 `~/.agents/skills/<name>/SKILL.md`，Claude 为 `~/.claude/skills/<name>/SKILL.md`。

## 约束 / 风险边界

- 必须保留历史兼容：旧的 `~/.agents/bridgeforge-home` 和 `~/.claude/skills/bridgeforge` 安装不能被静默删除。
- 入口 wrapper 必须保持 UTF-8 无 BOM，避免 frontmatter loader 跳过。
- `skill_sync_check.py` 必须从中立 `~/.bridgeforge/skills` 找上游通用 skill 源。
- `bridgeforge_switch.py` 的 fallback template root 必须优先查 `~/.bridgeforge`，并保留旧路径兜底。
- 产品层改动必须同步 Claude / Codex 模板、根文档、版本和 CHANGELOG。

## 验收清单

- [x] 根 `SKILL.md` 将 `BRIDGEFORGE_HOME` 统一为 `~/.bridgeforge`，并说明 `.agents` / `.claude` 只放扫描入口。
- [x] Codex wrapper 从 `~/.bridgeforge/SKILL.md` 读取完整流程，并只把旧 `~/.agents/bridgeforge-home` 当兼容提示。
- [x] Claude 也有薄入口 wrapper，不再要求完整仓库 clone 到 `~/.claude/skills/bridgeforge`。
- [x] `skill_sync_check.py` 在 Claude / Codex 模板中都从 `~/.bridgeforge/skills` 读取上游，并保留旧路径 fallback。
- [x] `bridgeforge_switch.py` 三份镜像都优先识别 `~/.bridgeforge`，再兜底旧路径。
- [x] README / INSTALL / SKILL.md / templates changelog / root changelog / VERSION 均同步。
- [x] 全仓搜索主路径不再把 `~/.agents/bridgeforge-home` 当推荐安装路径；剩余命中仅为迁移 recipe、兼容 fallback、历史记录或需求背景。

## 后续项

- 已完成当前机器真实迁移：`C:\Users\bridg\.bridgeforge` 是指向 `D:\Quant\BridgeForge` 的 junction；Codex / Claude 两个 `bridgeforge` skill 入口均为普通 wrapper 目录；旧 `C:\Users\bridg\.agents\bridgeforge-home` 已不存在。
- 是否自动生成迁移脚本暂缓，本轮先改机制说明和代码路径。

## 实施计划

1. 更新需求包和 `doc/README.md`。
2. 修改入口 wrapper、根 `SKILL.md`、README / INSTALL。
3. 修改 Claude / Codex 两套模板里的 `skill_sync_check.py` 与 `bridgeforge_switch.py`。
4. 同步版本和 CHANGELOG。
5. 运行路径搜索、脚本语法检查和轻量行为检查。
6. 交付前做独立复核，核对遗漏和文档同步。

## 实施记录

- 2026-07-08：需求确认。推荐采用 `~/.bridgeforge` 作为完整工厂源头，不使用 `.bridgeforge/repo` 包装层。
- 2026-07-08：实现完成。新增 Claude 薄入口，Codex / Claude wrapper 均指向 `~/.bridgeforge/SKILL.md`；`skill_sync_check.py` 和 `bridgeforge_switch.py` 新路径优先并保留旧路径 fallback；README / INSTALL / SKILL / CHANGELOG / VERSION 同步。
- 2026-07-08：独立 review 发现两项迁移期问题：switch 候选顺序未严格优先 `~/.bridgeforge`，INSTALL 缺旧完整仓库迁移 recipe。均已修复。
- 2026-07-08：用户确认后完成本机真实迁移。旧 `C:\Users\bridg\.agents\bridgeforge-home` junction 移到 `C:\Users\bridg\.bridgeforge`；发现并修正旧 Claude 入口仍是完整仓库 junction 的残留，最终 Codex / Claude 入口均为普通 wrapper 目录。

## 验证记录

- `python -m py_compile scripts\bridgeforge_switch.py templates\codex\scripts\bridgeforge_switch.py templates\claude\scripts\bridgeforge_switch.py .codex\scripts\bridgeforge_switch.py .claude\scripts\bridgeforge_switch.py templates\codex\hooks\skill_sync_check.py templates\claude\hooks\skill_sync_check.py .codex\hooks\skill_sync_check.py .claude\hooks\skill_sync_check.py`：exit 0，语法检查通过。
- `python tests\harness\run_downstream_fixture.py`：17 项 harness 全部 `[PASS]`。
- `git diff --check`：exit 0；仅输出 Git 本地 line-ending warning，无 whitespace error。
- wrapper BOM 检查：`scripts/codex_bridgeforge_entry.SKILL.md` 与 `scripts/claude_bridgeforge_entry.SKILL.md` 均 `bom=False`，首字节为 `b'---'`。
- 镜像哈希检查：Codex / Claude 的 template hook/script 与 `.codex` / `.claude` dogfood 副本均一致。
- 独立 verification agent：只读复核完成，初次指出 2 个 P2 问题；修复后本地复验通过。
- 本机用户级布局验真：`C:\Users\bridg\.bridgeforge` 为 junction 且目标是 `D:\Quant\BridgeForge`；`C:\Users\bridg\.agents\skills\bridgeforge` 与 `C:\Users\bridg\.claude\skills\bridgeforge` 为普通目录；两份 wrapper hash 与源文件一致；`C:\Users\bridg\.agents\bridgeforge-home` 不存在；仓库 `git diff --name-only` 为空。

## 用户试用反馈

- 下游 agent 反馈入口文件已按新版逻辑寻找 `C:\Users\bridg\.bridgeforge`，但本机完整工厂仍停在旧 `C:\Users\bridg\.agents\bridgeforge-home`。已据此完成真实迁移；下一步只剩重启/刷新对应 agent 后实际跑 `/bridgeforge` 验 slash 缓存与入口读取。
