# Codex 既有项目接入

仅在根 skill 判定为 `adopt` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode adopt` 生成计划。
2. 既有项目缺少 current 版本戳时必须零写阻断；禁止猜测其来源或自动补戳。
3. 用户需要先安装当前骨架，或提供任一文件名下可识别的 `<1.4.31` 版本戳进入重建流程。
4. 散落 Hook 必须先由独立 Agent 在临时副本或受控前置步骤中整理为
   `.codex/hooks/project_XXXX/entrypoint.py` 自包含目录；同步器不解析历史 Hook 命令。

发现 `.claude/` 或 `CLAUDE.md` 时仅提示“Claude 骨架已停止支持”，不得读取、迁移、
删除。
