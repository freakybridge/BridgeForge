# Memory Index — bridgeforge

<!-- 自动生成索引，勿手改（改动会被下次重建覆盖）。新增 memory：在 .claude/memory/ 下新建 .md 文件，本索引会自动收录；写法见 ~/.claude/CLAUDE.md「auto memory」段。满 40 条自动滚入冷区，用 /find-memory 搜。 -->

> Active: 10 | Cold: 16

## Active（按新增时间，新在前；主索引上限 6000 字符）
- [engineering/feedback-hook-input-channel-bugclass](engineering/feedback-hook-input-channel-bugclass.md) — 修一个 hook 的 stdin/env-var 输入通道 bug 后要主动排查所有结构同胞，不能只信任单点 CHANGELOG 记录已解决
- [engineering/feedback-llm-suspended-during-tool-exec](engineering/feedback-llm-suspended-during-tool-exec.md) — LLM 在 Claude Code 工具执行期间被 SUSPENDED——PostToolUse 才是最早干预窗口，而非「边等边想」
- [architecture/project-target-cleanup-design](architecture/project-target-cleanup-design.md) — target_cleanup.py 的核心设计决策（体积而非 atime、自门控、全深度扫描）
- [engineering/feedback-bash-cwd-persistence](engineering/feedback-bash-cwd-persistence.md) — Bash 工具的 cwd 在会话内持久——cd 进子目录后所有后续调用都从那里执行，导致相对路径 hook 全部失效
- [engineering/feedback-dogfood-hook-gap](engineering/feedback-dogfood-hook-gap.md) — 改 templates/hooks 时漏了同步 .claude/hooks 的事故模式及已有修复
- [engineering/feedback-glob-search-gotchas](engineering/feedback-glob-search-gotchas.md) — 用户机器上用 Glob/Grep 查文件的首选方式与三个坑（范围、文件非目录、跳过点目录）
- [engineering/feedback-review-technique](engineering/feedback-review-technique.md) — setup_agent review 时的两条操作红线（并行编辑 + hook 删除安全检查）
- [engineering/feedback-skill-gate-hardness](engineering/feedback-skill-gate-hardness.md) — skill 指令里"等用户确认"闸的正确写法——描述性措辞拦不住 agent，必须用 AskUserQuestion 工具级回合终止契约
- [engineering/tool-result-corruption-triggers](engineering/tool-result-corruption-triggers.md) — 工具传结果线腐蚀的两类触发器：shell for+pipe 批处理大输出 + AskUserQuestion 大段中文参数；区别于 hook 编码腐蚀（utf8-garble）
- [engineering/utf8-garble-rootcause](engineering/utf8-garble-rootcause.md) — 中文 hook 输出在 GBK Windows 上糊成 U+FFFD 注入 context、曾高频致 agent 跑偏；根因/已修手段/残留/为何不过度加固的完整地图

## 🔍 Cold（16 条，用 /find-memory 搜索）
详见 MEMORY_COLD.md
