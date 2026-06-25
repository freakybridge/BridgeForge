---
name: project-rename-bridgeforge
description: v0.29.0 起项目/skill 由 setup_agent 更名为 bridgeforge；历史流水账故意保留旧名
metadata: 
  node_type: memory
  type: project
  originSessionId: f1298de8-a5d2-4c9c-a503-c9d847237305
---

2026-06-25（v0.29.0）：本骨架库 / skill 由 `setup_agent` **更名为 `bridgeforge`**（`bridge`=作者署名+“跨接”，`forge`=锻造工厂，对应“协作骨架工厂”自定位）。

**注意双名共存——不是 bug，是刻意决策**：
- **活文档 / 活代码** = `bridgeforge`（README/INSTALL/SKILL.md/CLAUDE.md/docs 活 playbook/skills/templates/自身 .claude hooks，共 252 处已替换）。
- **历史流水账故意保留旧名 `setup_agent`**：本仓库 `CHANGELOG.md` 旧条目、`.claude/memory/*` 旧文件、dated docs（`repositioning-from-StratusAgent-2026-06-24.md` / `public-release-readiness-2026-06-25.md`）。更名锚点是 CHANGELOG v0.29.0 条目。
- **`memory_junction_check.py` 两处 `setup_agent` 也故意保留**：那是讲解“路径含下划线/点会算错哈希”的教学例子，bridgeforge 同样无特殊字符，改了注释会自相矛盾。

**大小写约定（刻意，别当 bug 改）**：人面向 PascalCase（GitHub repo `BridgeForge` + 本机目录 `D:\Quant\BridgeForge`）；机器面向小写（命令 `/bridgeforge`、junction `~/.claude/skills/bridgeforge`、戳 `.bridgeforge_version`、hook 硬编码）。同"仓库 VSCode→命令 code"惯例。文档里 clone URL / dev-dir 路径用 PascalCase，其余小写。

**接口契约变更（下游必读）**：skill `/setup_agent`→`/bridgeforge`、junction `~/.claude/skills/setup_agent`→`bridgeforge`、版本戳 `.claude/.setup_agent_version`→`.bridgeforge_version`。

**仓库内未完成、需手动收尾**（agent 改不了：工作目录外 / 会抽掉自身 cwd）：GitHub repo 改名为 `BridgeForge` + `git remote set-url`、本机目录 `D:\Quant\setup_agent`→`D:\Quant\BridgeForge`、memory 系统路径哈希 `d--Quant-setup-agent`→新哈希（memory 数据 junction 在 repo 内，随目录走，hook 下次 session 自愈建新链）、skill junction 重建、下游各项目 junction + 版本戳重建（属正向同步 [product] 红线）。

相关：[[project-v026-state]]
